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
                    # Delete only if the stored token still belongs to us.
                    await client.eval(
                        "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                        1,
                        key,
                        token,
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
    """Sliding-window limiter. A rejected request is never added to the window."""
    key = f"rate:{action}:{identifier}"
    now = time.time()
    cutoff = now - window_sec
    client = get_redis()

    if client:
        try:
            async with client.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(key, 0, cutoff)
                pipe.zcard(key)
                result = await pipe.execute()
                count = int(result[1])
                if count >= max_requests:
                    oldest = await client.zrange(key, 0, 0, withscores=True)
                    retry_after = window_sec
                    if oldest:
                        retry_after = max(1, int(window_sec - (now - oldest[0][1])))
                    return False, retry_after

                member = f"{now:.6f}:{uuid.uuid4().hex}"
                await client.zadd(key, {member: now})
                await client.expire(key, window_sec)
                return True, 0
        except Exception as exc:
            logger.warning("Redis rate-limit fallback: %s", exc)

    timestamps = _in_memory_rate_limits.setdefault(key, [])
    timestamps[:] = [t for t in timestamps if now - t < window_sec]
    if len(timestamps) >= max_requests:
        retry_after = max(1, int(window_sec - (now - timestamps[0])))
        return False, retry_after
    timestamps.append(now)
    return True, 0
