"""Pipeline debug tab API.

- GET /api/pipeline/current?job_id=X  — snapshot of latest rows per graph
- GET /api/pipeline/stream?job_id=X   — SSE stream of events
- GET /api/pipeline/orphans?workflow_run_id=X — NULL job_id rows for debugging
"""
import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from src.agents.pipeline_tracking import bus, PipelineEvent
from src.db import get_connection
from src.agents.master_workflow import _compiled_master_graph
from src.agents.orchestrator import workflow as _resume_compiled_graph
from src.agents.linkedin_graph import linkedin_graph as _linkedin_compiled_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


async def _fetch_snapshot(job_id: int) -> dict:
    """Return {active_runs: {...}, nodes: [...]} for the given job."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            """
            WITH latest_per_graph AS (
                SELECT graph, MAX(started_at) AS latest_ts
                  FROM pipeline_events
                 WHERE job_id = ?
              GROUP BY graph
            ),
            active_ids AS (
                SELECT DISTINCT pe.graph, pe.workflow_run_id
                  FROM pipeline_events pe
                  JOIN latest_per_graph lpg
                    ON pe.graph = lpg.graph AND pe.started_at = lpg.latest_ts
                 WHERE pe.job_id = ?
            )
            SELECT pe.*
              FROM pipeline_events pe
              JOIN active_ids ai
                ON pe.graph = ai.graph AND pe.workflow_run_id = ai.workflow_run_id
             WHERE pe.job_id = ?
          ORDER BY pe.id
            """,
            (job_id, job_id, job_id),
        )
        rows = [dict(r) for r in await cursor.fetchall()]

    active_runs = {"master": None, "resume": None, "linkedin": None}
    for row in rows:
        g = row["graph"]
        if g in active_runs and active_runs[g] is None:
            active_runs[g] = row["workflow_run_id"]

    nodes = [
        {
            "graph": r["graph"],
            "node_name": r["node_name"],
            "status": r["status"],
            "attempt": r["attempt"],
            "workflow_run_id": r["workflow_run_id"],
            "version": r["version"],
            "round_number": r["round_number"],
            "duration_ms": r["duration_ms"],
            "error": r["error"],
            "traceback": r["traceback"],
            "started_at": r["started_at"],
            "completed_at": r["completed_at"],
        }
        for r in rows
    ]

    return {"active_runs": active_runs, "nodes": nodes}


@router.get("/current")
async def get_current(job_id: int):
    return await _fetch_snapshot(job_id)


@router.get("/orphans")
async def get_orphans(workflow_run_id: str):
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM pipeline_events WHERE workflow_run_id = ? AND job_id IS NULL",
            (workflow_run_id,),
        )
        rows = [dict(r) for r in await cursor.fetchall()]
    return {"rows": rows}


@router.get("/stream")
async def stream(job_id: int, request: Request):
    async def event_generator():
        snapshot = await _fetch_snapshot(job_id)
        yield {"event": "message", "data": json.dumps({"type": "snapshot", **snapshot})}

        active_runs = dict(snapshot["active_runs"])

        async for event in bus.subscribe(job_id=job_id):
            if await request.is_disconnected():
                break

            graph = event.graph
            incoming_wf = event.workflow_run_id
            current_wf = active_runs.get(graph)

            if current_wf is None:
                active_runs[graph] = incoming_wf
            elif current_wf != incoming_wf:
                yield {
                    "event": "message",
                    "data": json.dumps({
                        "type": "graph_reset",
                        "graph": graph,
                        "workflow_run_id": incoming_wf,
                    }),
                }
                active_runs[graph] = incoming_wf

            yield {
                "event": "message",
                "data": json.dumps({
                    "type": "event",
                    "graph": event.graph,
                    "workflow_run_id": event.workflow_run_id,
                    "node_name": event.node_name,
                    "status": event.status,
                    "attempt": event.attempt,
                    "version": event.version,
                    "round_number": event.round_number,
                    "duration_ms": event.duration_ms,
                    "error": event.error,
                    "traceback": event.traceback,
                    "job_id": event.job_id,
                }),
            }

    return EventSourceResponse(event_generator())


# --- Topology endpoint -----------------------------------------------------
#
# Extraction runs ONCE at import time. The handler returns a pre-computed
# Python dict by reference — no await, no I/O, no lock. This is the hard
# requirement: the handler must not block the FastAPI event loop.

_INTERNAL_NODES = ("__start__", "__end__")


def _extract(compiled_graph, graph_id: str) -> dict:
    g = compiled_graph.get_graph()
    nodes = [
        {"id": n, "graph": graph_id, "label": n}
        for n in g.nodes
        if n not in _INTERNAL_NODES
    ]
    edges = [
        {
            "source": e.source,
            "target": e.target,
            "conditional": bool(getattr(e, "conditional", False)),
        }
        for e in g.edges
        if e.source not in _INTERNAL_NODES and e.target not in _INTERNAL_NODES
    ]
    return {"id": graph_id, "nodes": nodes, "edges": edges}


def _build_topology() -> dict:
    return {
        "graphs": [
            _extract(_compiled_master_graph, "master"),
            _extract(_resume_compiled_graph, "resume"),
            _extract(_linkedin_compiled_graph, "linkedin"),
        ],
        "connectors": [
            {"from": "master:resume_branch", "to": "resume:jd_analysis"},
            {"from": "master:linkedin_branch", "to": "linkedin:load_job"},
        ],
    }


try:
    _TOPOLOGY: dict = _build_topology()
except Exception as exc:  # pragma: no cover (surfaced via error field)
    logger.exception("pipeline topology build failed at import")
    _TOPOLOGY = {"graphs": [], "connectors": [], "error": str(exc)}


@router.get("/topology")
async def get_topology() -> dict:
    return _TOPOLOGY
