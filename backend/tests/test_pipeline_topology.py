"""Tests for the /api/pipeline/topology endpoint.

Covers:
- Response shape (3 graphs + 2 connectors)
- Fan-out edges are present (regression guard for path_map)
- Drift guard: extracted node ids ⊇ TRACK_NODE_REGISTRY per graph
- Async purity: handler is `async def`, body contains no await, and two
  successive calls return the same object reference.
"""
import ast
import inspect

import pytest

from src.agents.pipeline_tracking import TRACK_NODE_REGISTRY
from src.api.pipeline_routes import _TOPOLOGY, get_topology


def _ids_for(graph_id: str) -> set[str]:
    for g in _TOPOLOGY["graphs"]:
        if g["id"] == graph_id:
            return {n["id"] for n in g["nodes"]}
    raise AssertionError(f"graph {graph_id} missing from topology")


def test_topology_endpoint_shape():
    assert "error" not in _TOPOLOGY, _TOPOLOGY.get("error")
    assert {g["id"] for g in _TOPOLOGY["graphs"]} == {"master", "resume", "linkedin"}

    master = _ids_for("master")
    assert master == {
        "extract_fields",
        "validate_fields",
        "insert_job",
        "fail_node",
        "resolve_default_resume",
        "resume_branch",
        "linkedin_branch",
    }

    assert _ids_for("resume") == {
        "jd_analysis",
        "rag_retrieval",
        "gap_analysis",
        "suggestions",
        "rewrite",
    }

    assert len(_ids_for("linkedin")) == 17

    assert _TOPOLOGY["connectors"] == [
        {"from": "master:resume_branch", "to": "resume:jd_analysis"},
        {"from": "master:linkedin_branch", "to": "linkedin:load_job"},
    ]


def test_master_fan_out_edges_present():
    """Regression guard: without path_map on fan_out, these edges vanish."""
    master_edges = next(g["edges"] for g in _TOPOLOGY["graphs"] if g["id"] == "master")
    pairs = {(e["source"], e["target"]) for e in master_edges}
    assert ("resolve_default_resume", "resume_branch") in pairs
    assert ("resolve_default_resume", "linkedin_branch") in pairs


def test_topology_matches_track_node_decorators():
    """Drift guard: every @track_node(graph, node_name) must appear in the
    extracted topology for that graph. Catches id mismatches (e.g. `fail` vs
    `fail_node`) and missing decorators (e.g. `rag_retrieval`)."""
    # Importing the agent modules above is what populates the registry — make
    # sure we also import the sibling modules whose decorators we rely on.
    import src.agents.extraction_pipeline  # noqa: F401
    import src.agents.linkedin_graph  # noqa: F401
    import src.agents.master_workflow  # noqa: F401
    import src.agents.orchestrator  # noqa: F401
    import src.agents.resume_agent  # noqa: F401

    assert TRACK_NODE_REGISTRY, "TRACK_NODE_REGISTRY is empty — decorator import failed"

    by_graph: dict[str, set[str]] = {}
    for graph_id, node_name in TRACK_NODE_REGISTRY:
        by_graph.setdefault(graph_id, set()).add(node_name)

    for graph_id, decorated in by_graph.items():
        if graph_id not in {"master", "resume", "linkedin"}:
            continue  # sub-graphs (e.g. extraction) not rendered on this tab
        extracted = _ids_for(graph_id)
        missing = decorated - extracted
        assert not missing, (
            f"Nodes decorated with @track_node but missing from extracted "
            f"{graph_id} topology: {sorted(missing)}. Either the node id in "
            f"build_*_graph() does not match the decorator's node_name, or "
            f"the node is missing from the graph."
        )


def test_topology_handler_is_structurally_async_pure():
    """Handler must be `async def` with zero await expressions in its body.
    Replaces a flaky wall-clock assertion — structural checks are immune to
    CI load variance."""
    assert inspect.iscoroutinefunction(get_topology), "get_topology must be async"

    source = inspect.getsource(get_topology)
    tree = ast.parse(source)
    func = tree.body[0]
    assert isinstance(func, ast.AsyncFunctionDef), "get_topology must be `async def`"

    awaits = [node for node in ast.walk(func) if isinstance(node, ast.Await)]
    assert not awaits, (
        f"get_topology body contains {len(awaits)} await expressions; it "
        f"must return a pre-computed constant by reference with no await."
    )


@pytest.mark.asyncio
async def test_topology_handler_returns_same_object_identity():
    """Two successive awaits return the SAME object reference. Proves the
    handler is returning the cached constant by reference — no rebuilding,
    no copying, no per-call work."""
    first = await get_topology()
    second = await get_topology()
    assert first is second, "handler must return the cached _TOPOLOGY by reference"
