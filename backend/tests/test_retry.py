import asyncio
import pytest

from src.memory.retry import with_retry


async def test_succeeds_first_try():
    calls = []
    async def op():
        calls.append(1)
        return "ok"
    result = await with_retry(op, retries=3, backoff=(0, 0, 0))
    assert result == "ok"
    assert len(calls) == 1


async def test_succeeds_on_second_try():
    calls = []
    async def op():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("transient")
        return "ok"
    result = await with_retry(op, retries=3, backoff=(0, 0, 0))
    assert result == "ok"
    assert len(calls) == 2


async def test_exhausts_and_reraises():
    calls = []
    async def op():
        calls.append(1)
        raise RuntimeError("permanent")
    with pytest.raises(RuntimeError, match="permanent"):
        await with_retry(op, retries=3, backoff=(0, 0, 0))
    assert len(calls) == 3


async def test_backoff_delays_applied():
    calls = []
    async def op():
        calls.append(asyncio.get_event_loop().time())
        raise RuntimeError("fail")
    with pytest.raises(RuntimeError):
        await with_retry(op, retries=3, backoff=(0.01, 0.02, 0.04))
    assert calls[1] - calls[0] >= 0.01
    assert calls[2] - calls[1] >= 0.02
