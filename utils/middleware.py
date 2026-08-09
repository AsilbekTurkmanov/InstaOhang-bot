"""
ThrottlingMiddleware for @InstaOhang_bot.
- Separate rate limits per operation type (fast callback vs heavy download)
- TTL-based memory-safe cache (no unbounded growth)
- Periodic cleanup every N seconds to prevent RAM leak
"""

import time
import logging
from collections import OrderedDict
from typing import Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Throttle limits by operation type (seconds)
# ─────────────────────────────────────────────────────────────────────────────
# Heavy operations (download, ffmpeg) are handled by semaphores in bot.py,
# NOT the throttling middleware — so only UI interactions are throttled here.
MESSAGE_THROTTLE_SEC = 0.8      # normal text message (< 1 per 0.8s)
CALLBACK_THROTTLE_SEC = 0.5     # button press (< 1 per 0.5s)
COMMAND_THROTTLE_SEC = 1.0      # commands like /start, /music

# Commands that should use the stricter COMMAND throttle
COMMAND_PREFIX_TRIGGERS = {"/start", "/round", "/music", "/fast", "/slow", "/audio", "/agent"}

# ─────────────────────────────────────────────────────────────────────────────
# TTL LRU Cache (memory-safe, bounded)
# ─────────────────────────────────────────────────────────────────────────────
CACHE_MAX_SIZE = 10_000   # max users tracked simultaneously
CACHE_TTL_SEC = 120       # entries expire after 2 min of inactivity
_CLEANUP_INTERVAL = 300   # prune expired entries every 5 min


class TTLThrottleCache:
    """
    Memory-safe TTL cache for per-user throttle timestamps.
    - Max size: CACHE_MAX_SIZE entries (evicts LRU when full)
    - Expired entries are purged every _CLEANUP_INTERVAL seconds
    - O(1) get/set via OrderedDict (LRU ordering)
    """

    def __init__(self, max_size: int = CACHE_MAX_SIZE, ttl: float = CACHE_TTL_SEC):
        self._cache: OrderedDict[int, float] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._last_cleanup = time.monotonic()

    def get(self, user_id: int) -> float:
        """Returns last timestamp for user_id, or 0.0 if not found / expired."""
        now = time.monotonic()
        self._maybe_cleanup(now)
        ts = self._cache.get(user_id, 0.0)
        if ts and now - ts > self._ttl:
            # Expired — remove it
            self._cache.pop(user_id, None)
            return 0.0
        return ts

    def set(self, user_id: int, timestamp: float) -> None:
        """Records timestamp for user_id, evicts LRU entry if cache is full."""
        if user_id in self._cache:
            self._cache.move_to_end(user_id)
        else:
            if len(self._cache) >= self._max_size:
                # Evict the least-recently-used entry
                self._cache.popitem(last=False)
        self._cache[user_id] = timestamp

    def _maybe_cleanup(self, now: float) -> None:
        """Prunes expired entries at most once per _CLEANUP_INTERVAL seconds."""
        if now - self._last_cleanup < _CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        expired = [uid for uid, ts in self._cache.items() if now - ts > self._ttl]
        for uid in expired:
            del self._cache[uid]
        if expired:
            logger.debug(f"[Throttle] Cleaned up {len(expired)} expired entries. Cache size: {len(self._cache)}")

    def __len__(self) -> int:
        return len(self._cache)


# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────

class ThrottlingMiddleware(BaseMiddleware):
    """
    Aiogram 3.x middleware that limits request rate per user.
    - Separate TTL caches for message vs callback events
    - Memory-safe: bounded by CACHE_MAX_SIZE and TTL-based expiration
    - Heavy downloads/FFmpeg are NOT throttled here (handled by semaphores)
    """

    def __init__(self):
        super().__init__()
        self._msg_cache = TTLThrottleCache()
        self._cb_cache = TTLThrottleCache()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        limit_sec: float = MESSAGE_THROTTLE_SEC
        cache = self._msg_cache

        if isinstance(event, Message):
            if event.from_user:
                user_id = event.from_user.id
            # Stricter limit for bot commands
            text = event.text or ""
            for cmd in COMMAND_PREFIX_TRIGGERS:
                if text.startswith(cmd):
                    limit_sec = COMMAND_THROTTLE_SEC
                    break

        elif isinstance(event, CallbackQuery):
            if event.from_user:
                user_id = event.from_user.id
            limit_sec = CALLBACK_THROTTLE_SEC
            cache = self._cb_cache

        if user_id is not None:
            now = time.monotonic()
            last = cache.get(user_id)
            if last and now - last < limit_sec:
                # Rate-limited
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer("⚠️ Iltimos, biroz kuting!", show_alert=False)
                    except Exception:
                        pass
                return  # Drop the update silently for messages
            cache.set(user_id, now)

        return await handler(event, data)
