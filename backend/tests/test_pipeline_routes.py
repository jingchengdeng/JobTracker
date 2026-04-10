import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(migrated_db):
    """FastAPI test client pointed at the migrated DB."""
    from src.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_current_returns_latest_per_graph_snapshot(client, migrated_db):
    import aiosqlite

    async with aiosqlite.connect(migrated_db) as conn:
        await conn.execute("INSERT INTO jobs (id) VALUES (1)")
        await conn.execute(
            "INSERT INTO pipeline_events ("
            "workflow_run_id, job_id, graph, node_name, status, started_at"
            ") VALUES ('wf-1', 1, 'master', 'extract_fields', 'completed', '2026-04-10T10:00')"
        )
        await conn.execute(
            "INSERT INTO pipeline_events ("
            "workflow_run_id, job_id, graph, node_name, status, started_at"
            ") VALUES ('wf-1', 1, 'resume', 'jd_analysis', 'completed', '2026-04-10T10:05')"
        )
        await conn.execute(
            "INSERT INTO pipeline_events ("
            "workflow_run_id, job_id, graph, node_name, status, started_at"
            ") VALUES ('wf-1', 1, 'linkedin', 'load_job', 'completed', '2026-04-10T10:06')"
        )
        await conn.commit()

    resp = await client.get("/api/pipeline/current", params={"job_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert "active_runs" in data
    assert data["active_runs"]["master"] == "wf-1"
    assert data["active_runs"]["resume"] == "wf-1"
    assert data["active_runs"]["linkedin"] == "wf-1"
    assert len(data["nodes"]) == 3


@pytest.mark.asyncio
async def test_stream_emits_snapshot_as_first_frame(migrated_db):
    """Pull the first frame directly from the EventSourceResponse's body
    iterator. Both httpx.ASGITransport and starlette's TestClient transport
    buffer the entire response until the ASGI app returns, which deadlocks
    against an infinite SSE generator, so we can't drive this through
    either test client.
    """
    import aiosqlite
    from fastapi import Request

    async with aiosqlite.connect(migrated_db) as conn:
        await conn.execute("INSERT INTO jobs (id) VALUES (1)")
        await conn.execute(
            "INSERT INTO pipeline_events ("
            "workflow_run_id, job_id, graph, node_name, status, started_at"
            ") VALUES ('wf-1', 1, 'master', 'extract_fields', 'completed', '2026-04-10T10:00')"
        )
        await conn.commit()

    from src.api.pipeline_routes import stream as stream_endpoint

    # Build a minimal Request stub with is_disconnected() support.
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/pipeline/stream",
        "headers": [],
        "query_string": b"job_id=1",
    }

    async def _receive():
        return {"type": "http.disconnect"}

    request = Request(scope, receive=_receive)

    response = await stream_endpoint(job_id=1, request=request)

    first_line = None
    async for data in response.body_iterator:
        # sse_starlette yields dicts like {"event": "message", "data": "..."}
        if isinstance(data, dict) and "data" in data:
            first_line = "data: " + data["data"]
            break

    assert first_line is not None
    import json as _json
    payload = _json.loads(first_line.removeprefix("data: "))
    assert payload["type"] == "snapshot"
    assert payload["active_runs"]["master"] == "wf-1"


@pytest.mark.asyncio
async def test_orphans_returns_null_job_id_rows(client, migrated_db):
    import aiosqlite

    async with aiosqlite.connect(migrated_db) as conn:
        await conn.execute(
            "INSERT INTO pipeline_events ("
            "workflow_run_id, job_id, graph, node_name, status"
            ") VALUES ('wf-orphan', NULL, 'master', 'extract_fields', 'failed')"
        )
        await conn.commit()

    resp = await client.get("/api/pipeline/orphans", params={"workflow_run_id": "wf-orphan"})
    data = resp.json()
    assert len(data["rows"]) == 1
    assert data["rows"][0]["job_id"] is None
