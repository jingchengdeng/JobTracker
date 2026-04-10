import asyncio

import pytest

from src.agents.pipeline_tracking import PipelineEventBus, PipelineEvent


@pytest.mark.asyncio
async def test_bus_delivers_event_to_subscriber():
    bus = PipelineEventBus()
    received = []

    async def consume():
        async for event in bus.subscribe(job_id=42):
            received.append(event)
            if len(received) == 1:
                break

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0)

    await bus.publish(PipelineEvent(
        job_id=42, graph="master", workflow_run_id="run-1",
        node_name="extract_fields", status="running",
    ))

    await asyncio.wait_for(consumer, timeout=1.0)
    assert len(received) == 1
    assert received[0].node_name == "extract_fields"


@pytest.mark.asyncio
async def test_bus_drops_oldest_non_failed_on_overflow_preserves_failure():
    from src.agents.pipeline_tracking import MAX_QUEUE, _Subscriber, PipelineEventBus

    bus = PipelineEventBus()
    sub = _Subscriber()
    bus._subscribers[1] = [sub]

    for i in range(MAX_QUEUE):
        bus._enqueue(sub, PipelineEvent(
            job_id=1, graph="master", workflow_run_id="run",
            node_name=f"n{i}", status="running",
        ))
    assert len(sub.queue) == MAX_QUEUE

    failure = PipelineEvent(
        job_id=1, graph="master", workflow_run_id="run",
        node_name="n_fail", status="failed",
    )
    bus._enqueue(sub, failure)

    assert len(sub.queue) == MAX_QUEUE
    statuses = [e.status for e in sub.queue]
    assert "failed" in statuses
    assert sub.queue[-1].status == "failed"
    assert all(e.node_name != "n0" for e in sub.queue)
    assert len([e for e in sub.queue if e.status == "failed"]) == 1


@pytest.mark.asyncio
async def test_bus_drops_oldest_when_every_event_is_failure(caplog):
    import logging
    from src.agents.pipeline_tracking import MAX_QUEUE, _Subscriber, PipelineEventBus

    bus = PipelineEventBus()
    sub = _Subscriber()
    bus._subscribers[1] = [sub]

    for i in range(MAX_QUEUE):
        bus._enqueue(sub, PipelineEvent(
            job_id=1, graph="master", workflow_run_id="run",
            node_name=f"f{i}", status="failed",
        ))

    with caplog.at_level(logging.WARNING, logger="src.agents.pipeline_tracking"):
        bus._enqueue(sub, PipelineEvent(
            job_id=1, graph="master", workflow_run_id="run",
            node_name="f_new", status="failed",
        ))

    assert len(sub.queue) == MAX_QUEUE
    assert any("dropping oldest failure" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_subscriber_detaches_cleanly_on_iterator_close():
    from src.agents.pipeline_tracking import PipelineEventBus, PipelineEvent

    bus = PipelineEventBus()

    async def consume_one():
        async for _ in bus.subscribe(job_id=7):
            return

    consumer = asyncio.create_task(consume_one())
    await asyncio.sleep(0)
    await bus.publish(PipelineEvent(
        job_id=7, graph="master", workflow_run_id="r",
        node_name="n", status="running",
    ))
    await asyncio.wait_for(consumer, timeout=1.0)

    assert 7 not in bus._subscribers or not bus._subscribers[7]


@pytest.mark.asyncio
async def test_subscriber_aclose_detaches_immediately():
    from src.agents.pipeline_tracking import PipelineEventBus

    bus = PipelineEventBus()
    stream = bus.subscribe(job_id=99)
    assert 99 in bus._subscribers
    await stream.aclose()
    assert 99 not in bus._subscribers or not bus._subscribers[99]


def test_format_pipeline_error_shortens_cloudflare_bodies():
    from src.agents.pipeline_tracking import _format_pipeline_error

    exc = RuntimeError("<html><body>cloudflare challenge page</body></html>")
    msg = _format_pipeline_error(exc)
    assert "challenge page" in msg
    assert "<html" not in msg


def test_format_pipeline_error_truncates_long_messages():
    from src.agents.pipeline_tracking import _format_pipeline_error

    exc = RuntimeError("x" * 1000)
    msg = _format_pipeline_error(exc)
    assert len(msg) <= 503  # 500 + "..."
    assert msg.endswith("...")


def test_format_pipeline_error_passes_short_messages_through():
    from src.agents.pipeline_tracking import _format_pipeline_error

    exc = ValueError("bad input")
    msg = _format_pipeline_error(exc)
    assert msg == "bad input"


def test_track_node_rejects_sync_function_at_decoration_time():
    from src.agents.pipeline_tracking import track_node, TrackBehavior

    with pytest.raises(AssertionError):
        @track_node("master", "noop", TrackBehavior.SINGLE_SHOT)
        def noop(state):
            return {}


@pytest.fixture
async def migrated_db(monkeypatch):
    """Fresh SQLite file with pipeline_events table."""
    import os
    import tempfile
    from src.db_migrations import PIPELINE_EVENTS_DDL
    import aiosqlite

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("JOBTRACKER_DB_PATH", path)
    async with aiosqlite.connect(path) as conn:
        # Minimal FK targets
        await conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY)")
        await conn.execute(
            "CREATE TABLE ai_runs (id INTEGER PRIMARY KEY, job_id INTEGER, resume_id INTEGER)"
        )
        await conn.executescript(PIPELINE_EVENTS_DDL)
        await conn.commit()
    yield path
    os.unlink(path)


@pytest.mark.asyncio
async def test_track_node_single_shot_writes_running_then_completed(migrated_db):
    from src.agents.pipeline_tracking import track_node, TrackBehavior
    import aiosqlite

    @track_node("master", "unit_node", TrackBehavior.SINGLE_SHOT)
    async def node(state):
        return {"result": "ok"}

    await node({"workflow_run_id": "run-1", "job_id": None})

    async with aiosqlite.connect(migrated_db) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT status, attempt FROM pipeline_events WHERE workflow_run_id=?",
            ("run-1",),
        )
        row = await cursor.fetchone()
    assert row["status"] == "completed"
    assert row["attempt"] == 1


@pytest.mark.asyncio
async def test_track_node_marks_failed_and_reraises_on_exception(migrated_db):
    from src.agents.pipeline_tracking import track_node, TrackBehavior
    import aiosqlite

    @track_node("master", "raising_node", TrackBehavior.SINGLE_SHOT)
    async def node(state):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await node({"workflow_run_id": "run-2", "job_id": None})

    async with aiosqlite.connect(migrated_db) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT status, error FROM pipeline_events WHERE workflow_run_id=?",
            ("run-2",),
        )
        row = await cursor.fetchone()
    assert row["status"] == "failed"
    assert "boom" in row["error"]


@pytest.mark.asyncio
async def test_track_node_marks_failed_on_error_sentinel_without_reraising(migrated_db):
    from src.agents.pipeline_tracking import track_node, TrackBehavior
    import aiosqlite

    @track_node("master", "sentinel_node", TrackBehavior.SINGLE_SHOT)
    async def node(state):
        return {**state, "error": "db INSERT failed"}

    result = await node({"workflow_run_id": "run-3", "job_id": None})
    assert result["error"] == "db INSERT failed"

    async with aiosqlite.connect(migrated_db) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT status, error FROM pipeline_events WHERE workflow_run_id=?",
            ("run-3",),
        )
        row = await cursor.fetchone()
    assert row["status"] == "failed"
    assert row["error"] == "db INSERT failed"


@pytest.mark.asyncio
async def test_track_node_treats_none_return_as_success(migrated_db):
    from src.agents.pipeline_tracking import track_node, TrackBehavior
    import aiosqlite

    @track_node("master", "none_node", TrackBehavior.SINGLE_SHOT)
    async def node(state):
        return None

    await node({"workflow_run_id": "run-4", "job_id": None})

    async with aiosqlite.connect(migrated_db) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT status FROM pipeline_events WHERE workflow_run_id=?",
            ("run-4",),
        )
        row = await cursor.fetchone()
    assert row["status"] == "completed"
