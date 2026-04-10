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
