import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


async def with_retry(
    op: Callable[[], Awaitable[T]],
    *,
    retries: int = 3,
    backoff: tuple[float, ...] = (1.0, 2.0, 4.0),
) -> T:
    """Call an async op with N retries and per-attempt backoff delays.

    backoff[i] is the delay BEFORE attempt i+1 (i.e., after the failure of
    attempt i). If backoff has fewer entries than retries, the final entry
    is reused.
    """
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return await op()
        except Exception as exc:
            last_exc = exc
            if attempt == retries - 1:
                break
            delay_idx = min(attempt, len(backoff) - 1)
            await asyncio.sleep(backoff[delay_idx])
    assert last_exc is not None
    raise last_exc
