"""Discord-free async helpers: rate spacing, debouncing and retrying."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Hashable
from typing import TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


class SerialQueue:
    """Runs jobs one at a time in submission order, spaced by `interval_ms`."""

    def __init__(self, interval_ms: int) -> None:
        self._interval = interval_ms / 1000
        self._lock = asyncio.Lock()  # asyncio.Lock wakes waiters FIFO
        self._last_start: float | None = None

    async def run(self, factory: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            if self._last_start is not None:
                wait = self._last_start + self._interval - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
            self._last_start = time.monotonic()
            return await factory()


class Debouncer:
    """Trailing-edge debounce per key: the first trigger starts the window."""

    def __init__(
        self, delay_sec: float, action: Callable[[Hashable], Awaitable[None]]
    ) -> None:
        self._delay = delay_sec
        self._action = action
        self._pending: dict[Hashable, asyncio.Task[None]] = {}

    def trigger(self, key: Hashable) -> None:
        if key in self._pending:
            return
        self._pending[key] = asyncio.get_running_loop().create_task(self._fire(key))

    async def _fire(self, key: Hashable) -> None:
        try:
            await asyncio.sleep(self._delay)
            # Leave the window before running so triggers during the action
            # schedule a fresh run.
            self._pending.pop(key, None)
            await self._action(key)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("debounced action failed for key %r", key)
        finally:
            if self._pending.get(key) is asyncio.current_task():
                del self._pending[key]

    async def aclose(self) -> None:
        tasks = list(self._pending.values())
        self._pending.clear()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def with_retry(
    factory: Callable[[], Awaitable[T]],
    attempts: int = 3,
    delay_sec: float = 1.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Call `factory` up to `attempts` times; re-raise the last error."""
    for attempt in range(1, attempts + 1):
        try:
            return await factory()
        except retry_on:
            if attempt == attempts:
                raise
            await asyncio.sleep(delay_sec)
    raise AssertionError("unreachable")  # attempts < 1
