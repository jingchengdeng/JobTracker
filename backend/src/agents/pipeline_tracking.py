"""Pipeline tracking primitives: event bus + decorator + formatter.

Module-level singleton bus is intentional. Single uvicorn worker is assumed;
multi-worker deployments would need a cross-process broker (Redis pub/sub)
which is out of scope for v1.

Thread-safety note: ``PipelineEventBus`` is intentionally lock-free. It relies
on the cooperative single-threaded asyncio event loop — all mutations to
``_subscribers`` happen without any ``await`` in between, so they cannot
interleave. If you ever move to a multi-threaded executor or multiple workers,
replace this bus with an external broker (e.g. Redis pub/sub).
"""
import asyncio
import logging
import weakref
from collections import deque
from dataclasses import dataclass, field
from typing import AsyncIterator

logger = logging.getLogger(__name__)

MAX_QUEUE = 100


@dataclass
class PipelineEvent:
    job_id: int | None
    graph: str
    workflow_run_id: str
    node_name: str
    status: str
    attempt: int = 1
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    traceback: str | None = None
    round_number: int = 0
    version: int = 1


def _format_pipeline_error(exc: Exception) -> str:
    """Shorten provider errors so the UI doesn't render raw HTML bodies.

    Some providers respond with a Cloudflare challenge page when the caller
    isn't authenticated the way they expect. The OpenAI SDK includes the
    response body in the exception string, which then leaks into
    pipeline_events.error and the UI. Detect HTML bodies and replace with
    a short, actionable message.
    """
    msg = str(exc)
    lowered = msg.lower()
    if "<html" in lowered or "cloudflare" in lowered or "cf_chl_opt" in lowered:
        return (
            "Provider returned a challenge page instead of an API response. "
            "The configured provider appears to be unreachable from this app. "
            "Switch the default chat provider in Settings to one with a valid API key."
        )
    if len(msg) > 500:
        return msg[:500] + "..."
    return msg


@dataclass(eq=False)
class _Subscriber:
    queue: deque = field(default_factory=lambda: deque(maxlen=MAX_QUEUE))
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    closed: bool = False


def _detach_subscriber(
    subscribers: dict[int, list[_Subscriber]],
    job_id: int,
    sub: _Subscriber,
) -> None:
    """Remove *sub* from the global registry. Runs synchronously (no await).

    Uses identity comparison (``is``) rather than ``__eq__`` so that the
    correct object is always removed even if equality semantics change.
    """
    lst = subscribers.get(job_id, [])
    subscribers[job_id] = [s for s in lst if s is not sub]
    if not subscribers[job_id]:
        subscribers.pop(job_id, None)


class _SubscriberStream:
    """Class-based async iterator for a single subscriber.

    A weakref finalizer is registered so that when the consumer abandons
    the iterator mid-loop (via ``return`` or ``break`` inside ``async for``),
    CPython's reference-counting GC drops the object immediately and the
    finalizer deregisters the subscriber synchronously — before the consuming
    coroutine frame returns.  This guarantees that
    ``bus._subscribers[job_id]`` is empty by the time the consuming task
    completes, even without an explicit ``aclose()`` call.

    Callers may also invoke ``aclose()`` explicitly for deterministic cleanup
    (e.g. on PyPy or when GC is disabled). The weakref remains as a safety net.
    """

    def __init__(
        self,
        subscribers: dict[int, list[_Subscriber]],
        job_id: int,
        sub: _Subscriber,
    ) -> None:
        self._sub = sub
        self._job_id = job_id
        self._subscribers = subscribers
        # weakref.finalize holds only weak refs so it won't keep self alive
        self._finalizer = weakref.finalize(self, _detach_subscriber, subscribers, job_id, sub)

    def __aiter__(self) -> "AsyncIterator[PipelineEvent]":
        return self  # type: ignore[return-value]

    async def __anext__(self) -> PipelineEvent:
        sub = self._sub
        while True:
            if sub.queue:
                return sub.queue.popleft()
            if sub.closed:
                raise StopAsyncIteration
            sub.wake.clear()
            # Re-check queue after clearing the event to avoid a lost-wakeup.
            if sub.queue:
                return sub.queue.popleft()
            await sub.wake.wait()

    async def aclose(self) -> None:
        """Detach this subscriber immediately, without waiting for GC.

        Safe to call multiple times. After the first call, the weakref
        finalizer is also disarmed to avoid a redundant second detach.
        """
        if self._finalizer.alive:
            self._finalizer.detach()
            _detach_subscriber(self._subscribers, self._job_id, self._sub)


class PipelineEventBus:
    """In-process asyncio pub/sub keyed by job_id.

    Producers are never blocked. On overflow (subscriber fell behind):
      - If the new event has status='failed', evict the OLDEST non-failed
        event to preserve the failure.
      - If every queued event is already a failure, drop the oldest and
        log a warning (this is rare — all failures fanned to one subscriber).
      - Otherwise, the oldest event is evicted as normal (deque maxlen).
    """

    def __init__(self) -> None:
        self._subscribers: dict[int, list[_Subscriber]] = {}

    def subscribe(self, job_id: int) -> _SubscriberStream:
        """Register a new subscriber for *job_id* and return an async iterator.

        The subscriber is deregistered automatically when the returned stream
        object is garbage-collected (e.g. when the ``async for`` loop exits),
        or when ``aclose()`` is called explicitly.
        """
        sub = _Subscriber()
        self._subscribers.setdefault(job_id, []).append(sub)
        return _SubscriberStream(self._subscribers, job_id, sub)

    async def publish(self, event: PipelineEvent) -> None:
        subs = list(self._subscribers.get(event.job_id, []))
        for sub in subs:
            self._enqueue(sub, event)

    def _enqueue(self, sub: _Subscriber, event: PipelineEvent) -> None:
        if len(sub.queue) < MAX_QUEUE:
            sub.queue.append(event)
            sub.wake.set()
            return
        if event.status == "failed":
            for i, queued in enumerate(sub.queue):
                if queued.status != "failed":
                    del sub.queue[i]
                    sub.queue.append(event)
                    sub.wake.set()
                    return
            logger.warning(
                "PipelineEventBus: dropping oldest failure on overflow "
                "(subscriber backlog is all failures)"
            )
            sub.queue.popleft()
            sub.queue.append(event)
            sub.wake.set()
        else:
            sub.queue.popleft()
            sub.queue.append(event)
            sub.wake.set()

    async def close_subscriber(self, job_id: int) -> None:
        for sub in self._subscribers.get(job_id, []):
            sub.closed = True
            sub.wake.set()


# Module-level singleton. Single-worker deployment is assumed.
bus = PipelineEventBus()
