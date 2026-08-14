"""
Async Redis integration service for @InstaOhang_bot.
Provides distributed rate limiting, distributed locks, task caching, and state storage.
Includes graceful fallback to in-memory primitives if Redis is unavailable.
"""

import time
import logging
import asyncio
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from config import REDIS_URL

logger = logging.getLogger(__name__)

_redis_client = None
_in_memory_locks: dict[str, asyncio.Lock] = {}
_in_memory_rate_limits: dict[str, list[float]] = {}


async def init_redis() -> Optional[object]:
    """Initializes the global Redis connection pool if REDIS_URL is accessible."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
        )
        await client.ping()
        _redis_client = client
        logger.info(f"✅ Redis connection established cleanly ({REDIS_URL})")
        return _redis_client
    except Exception as e:
        logger.warning(f"⚠️ Redis unavailable ({e}). Using in-memory distributed fallback mode.")
        _redis_client = None
        return None


async def close_redis() -> None:
    """Closes global Redis connection pool on bot shutdown."""
    global _redis_client
    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("Redis connection pool closed.")
        except Exception as e:
            logger.warning(f"Error closing Redis: {e}")
        finally:
            _redis_client = None


def get_redis() -> Optional[object]:
    """Returns active Redis client or None if offline."""
    return _redis_client


@asynccontextmanager
async def acquire_lock(lock_name: str, ttl_seconds: int = 60) -> AsyncGenerator[bool, None]:
    """
    Distributed lock context manager based on canonical key.
    Uses Redis `set(name, value, nx=True, ex=ttl)` when available,
    falling back to in-memory `asyncio.Lock` if Redis is offline.
    """
    key = f"lock:{lock_name}"
    client = get_redis()
    acquired = False

    if client:
        try:
            val = str(time.time())
            # Attempt to set lock in Redis
            ok = await client.set(key, val, nx=True, ex=ttl_seconds)
            if ok:
                acquired = True
                yield True
            else:
                yield False
        finally:
            if acquired and client:
                try:
                    await client.delete(key)
                except Exception as e:
                    logger.debug(f"Redis lock release debug ({key}): {e}")
    else:
        # In-memory fallback
        if key not in _in_memory_locks:
            _in_memory_locks[key] = asyncio.Lock()
        lock = _in_memory_locks[key]

        try:
            acquired = await asyncio.wait_for(lock.acquire(), timeout=0.1)
        except asyncio.TimeoutError:
            acquired = False

        try:
            yield acquired
        finally:
            if acquired and lock.locked():
                lock.release()


async def check_rate_limit(
    identifier: str, action: str = "general", max_requests: int = 5, window_sec: int = 60
) -> tuple[bool, int]:
    """
    Distributed sliding window rate limiter.
    Returns: (is_allowed, remaining_seconds)
    """
    key = f"rate:{action}:{identifier}"
    client = get_redis()
    now = time.time()

    if client:
        try:
            async with client.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, now - window_sec)
                pipe.zcard(key)
                pipe.zadd(key, {str(now): now})
                pipe.expire(key, window_sec)
                results = await pipe.execute()
            count = results[1]
            if count >= max_requests:
                return False, window_sec
            return True, 0
        except Exception as e:
            logger.warning(f"Redis rate limit fallback ({key}): {e}")

    # In-memory sliding window fallback
    timestamps = _in_memory_rate_limits.setdefault(key, [])
    # Clean old timestamps
    _in_memory_rate_limits[key] = [t for t in timestamps if now - t < window_sec]
    if len(_in_memory_rate_limits[key]) >= max_requests:
        return False, window_sec
    _in_memory_rate_limits[key].append(now)
    return True, 0
