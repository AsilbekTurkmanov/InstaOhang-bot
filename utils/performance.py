"""
Performance monitoring utilities for @InstaOhang_bot.
Measures execution time for critical operations and logs structured metrics.
"""

import time
import logging
import functools
from typing import Callable, Any

logger = logging.getLogger("performance")


def measure_time(operation_name: str):
    """
    Decorator that measures async function execution time and logs it.

    Usage:
        @measure_time("music_search")
        async def search_music(...):
            ...

    Log output:
        [PERFORMANCE] Operation: music_search | Time: 342ms
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                if elapsed_ms > 1000:
                    logger.warning(
                        f"[PERFORMANCE] ⚠️  Operation: {operation_name} | "
                        f"Time: {elapsed_ms}ms  ← exceeded 1s target"
                    )
                else:
                    logger.info(
                        f"[PERFORMANCE] ✅ Operation: {operation_name} | Time: {elapsed_ms}ms"
                    )
                return result
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                logger.error(
                    f"[PERFORMANCE] ❌ Operation: {operation_name} | "
                    f"Time: {elapsed_ms}ms | Error: {exc}"
                )
                raise
        return wrapper
    return decorator


class Timer:
    """
    Context manager for measuring multiple sub-operations within one handler.

    Usage:
        async with Timer("handle_instagram") as t:
            t.checkpoint("db_lookup")
            ...db query...
            t.checkpoint("download")
            ...download...
            t.checkpoint("telegram_send")
            ...send...
        # logs full breakdown at the end
    """

    def __init__(self, operation: str):
        self.operation = operation
        self._start = 0.0
        self._last = 0.0
        self._checkpoints: list[tuple[str, int]] = []

    async def __aenter__(self):
        self._start = time.perf_counter()
        self._last = self._start
        return self

    def checkpoint(self, label: str) -> int:
        """Records elapsed ms since last checkpoint and returns it."""
        now = time.perf_counter()
        elapsed = int((now - self._last) * 1000)
        self._checkpoints.append((label, elapsed))
        self._last = now
        return elapsed

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        total_ms = int((time.perf_counter() - self._start) * 1000)
        parts = " | ".join(f"{label}: {ms}ms" for label, ms in self._checkpoints)
        status = "✅" if total_ms <= 1000 else "⚠️ "
        logger.info(
            f"[PERFORMANCE] {status} {self.operation} → {parts} | Total: {total_ms}ms"
        )
