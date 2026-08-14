"""Async Redis helpers with safe distributed locks and rate limiting."""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from config import REDIS_URL

logger = logging.getLogger(__name__)

_redis_client = None
_in_memory_locks: dict[str, asyncio.Lock] = {}
_in_memory_rate_limits: dict[str, list[float]] = {}


async def init_redis() -> Optional[object]:
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
        logger.info("Redis connection established")
        return client
    except Exception as exc:
        logger.warning("Redis unavailable; using local fallback: %s", exc)
        _redis_client = None
        return None


async def close_redis() -> None:
    global _redis_client
    client = _redis_client
    _redis_client = None
    if client:
        try:
            await client.aclose()
        except Exception as exc:
            logger.warning("Redis close error: %s", exc)


def get_redis() -> Optional[object]:
    return _redis_client


@asynccontextmanager
async def acquire_lock(lock_name: str, ttl_seconds: int = 60) -> AsyncGenerator[bool, None]:
    """Acquire a lock and release only the lock owned by this caller."""
    key = f"lock:{lock_name}"
    client = get_redis()
    token = uuid.uuid4().hex
    acquired = False

    if client:
        try:
            acquired = bool(await client.set(key, token, nx=True, ex=ttl_seconds))
            yield acquired
        finally:
            if acquired:
                try:
                    await client.eval(
                        "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                        1, key, token,
                    )
                except Exception as exc:
                    logger.warning("Redis lock release failed for %s: %s", key, exc)
        return

    lock = _in_memory_locks.setdefault(key, asyncio.Lock())
    try:
        try:
            acquired = await asyncio.wait_for(lock.acquire(), timeout=0.1)
        except asyncio.TimeoutError:
            acquired = False
        yield acquired
    finally:
        if acquired and lock.locked():
            lock.release()


async def check_rate_limit(
    identifier: str,
    action: str = "general",
    max_requests: int = 5,
    window_sec: int = 60,
) -> tuple[bool, int]:
    """Atomic sliding-window limiter; rejected requests are not counted."""
    key = f"rate:{action}:{identifier}"
    now = time.time()
    client = get_redis()

    if client:
        try:
            member = f"{now:.6f}:{uuid.uuid4().hex}"
            script = """
            local key = KEYS[1]
            local now = tonumber(ARGV[1])
            local cutoff = tonumber(ARGV[2])
            local limit = tonumber(ARGV[3])
            local window = tonumber(ARGV[4])
            redis.call('ZREMRANGEBYSCORE', key, 0, cutoff)
            local count = redis.call('ZCARD', key)
            if count >= limit then
                local first = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
                if first[2] then
                    return {0, math.max(1, math.ceil(window - (now - tonumber(first[2]))))}
                end
                return {0, window}
            end
            redis.call('ZADD', key, now, ARGV[5])
            redis.call('EXPIRE', key, window)
            return {1, 0}
            """
            allowed, retry_after = await client.eval(
                script, 1, key, str(now), str(now - window_sec),
                str(max_requests), str(window_sec), member,
            )
            return bool(allowed), int(retry_after)
        except Exception as exc:
            logger.warning("Redis rate-limit fallback: %s", exc)

    timestamps = _in_memory_rate_limits.setdefault(key, [])
    timestamps[:] = [t for t in timestamps if now - t < window_sec]
    if len(timestamps) >= max_requests:
        return False, max(1, int(window_sec - (now - timestamps[0])))
    timestamps.append(now)
    return True, 0
