import asyncio
import time

import pytest

from zaizai.asyncutil import Debouncer, SerialQueue, with_retry


async def test_serial_queue_keeps_order_and_spacing():
    q = SerialQueue(interval_ms=50)
    starts: list[tuple[int, float]] = []

    async def job(i: int) -> int:
        starts.append((i, time.monotonic()))
        await asyncio.sleep(0)
        return i

    results = await asyncio.gather(*(q.run(lambda i=i: job(i)) for i in range(4)))
    assert results == [0, 1, 2, 3]
    assert [i for i, _ in starts] == [0, 1, 2, 3]
    for (_, a), (_, b) in zip(starts, starts[1:]):
        assert b - a >= 0.04


async def test_debouncer_coalesces_burst():
    calls: list[str] = []

    async def action(key):
        calls.append(key)

    d = Debouncer(0.05, action)
    for _ in range(10):
        d.trigger("a")
    await asyncio.sleep(0.2)
    assert calls == ["a"]
    await d.aclose()


async def test_debouncer_fires_again_after_window():
    calls: list[str] = []

    async def action(key):
        calls.append(key)

    d = Debouncer(0.05, action)
    d.trigger("a")
    await asyncio.sleep(0.2)
    d.trigger("a")
    await asyncio.sleep(0.2)
    assert calls == ["a", "a"]
    await d.aclose()


async def test_debouncer_keys_independent():
    calls: list[str] = []

    async def action(key):
        calls.append(key)

    d = Debouncer(0.05, action)
    d.trigger("a")
    d.trigger("b")
    d.trigger("a")
    await asyncio.sleep(0.2)
    assert sorted(calls) == ["a", "b"]
    await d.aclose()


async def test_debouncer_survives_action_error():
    calls: list[str] = []

    async def action(key):
        calls.append(key)
        if len(calls) == 1:
            raise RuntimeError("boom")

    d = Debouncer(0.05, action)
    d.trigger("a")
    await asyncio.sleep(0.2)
    d.trigger("a")
    await asyncio.sleep(0.2)
    assert calls == ["a", "a"]
    await d.aclose()


async def test_with_retry_succeeds_after_transient_failures():
    n = 0

    async def flaky():
        nonlocal n
        n += 1
        if n < 3:
            raise ValueError("transient")
        return "ok"

    assert await with_retry(flaky, attempts=3, delay_sec=0.01) == "ok"
    assert n == 3


async def test_with_retry_raises_after_attempts_exhausted():
    n = 0

    async def bad():
        nonlocal n
        n += 1
        raise ValueError(f"fail {n}")

    with pytest.raises(ValueError, match="fail 3"):
        await with_retry(bad, attempts=3, delay_sec=0.01)
    assert n == 3


async def test_aclose_cancels_pending_action():
    calls: list[str] = []

    async def action(key):
        calls.append(key)

    d = Debouncer(0.1, action)
    d.trigger("a")
    await d.aclose()
    await asyncio.sleep(0.2)
    assert calls == []


async def test_aclose_cancels_in_flight_action():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def action(key):
        started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    d = Debouncer(0.01, action)
    d.trigger("a")
    await asyncio.wait_for(started.wait(), 2)
    await d.aclose()
    assert cancelled.is_set()
