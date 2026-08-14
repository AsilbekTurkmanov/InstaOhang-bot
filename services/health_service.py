"""
Health check service for @InstaOhang_bot.
Verifies status and latencies for PostgreSQL, Redis, and FFmpeg.
"""

import time
import logging
import asyncio
import shutil
from typing import dict

from database.postgres import get_pool
from services.redis_service import get_redis
from config import FFMPEG_PATH

logger = logging.getLogger(__name__)


async def check_health() -> dict:
    """
    Performs comprehensive system health checks.
    Returns status dict with components health & timing.
    """
    health = {
        "status": "ok",
        "timestamp": time.time(),
        "components": {
            "postgres": {"status": "unknown", "latency_ms": 0},
            "redis": {"status": "unknown", "latency_ms": 0},
            "ffmpeg": {"status": "unknown"},
        }
    }

    # 1. PostgreSQL check
    try:
        t0 = time.time()
        pool = get_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1")
        latency = round((time.time() - t0) * 1000, 2)
        if val == 1:
            health["components"]["postgres"] = {"status": "ok", "latency_ms": latency}
        else:
            health["components"]["postgres"] = {"status": "error", "error": "Invalid query response"}
            health["status"] = "degraded"
    except Exception as e:
        health["components"]["postgres"] = {"status": "error", "error": str(e)}
        health["status"] = "error"

    # 2. Redis check
    try:
        t0 = time.time()
        client = get_redis()
        if client:
            pong = await client.ping()
            latency = round((time.time() - t0) * 1000, 2)
            if pong:
                health["components"]["redis"] = {"status": "ok", "latency_ms": latency}
            else:
                health["components"]["redis"] = {"status": "degraded", "error": "No ping response"}
                if health["status"] == "ok":
                    health["status"] = "degraded"
        else:
            health["components"]["redis"] = {"status": "offline", "note": "Using in-memory fallback"}
    except Exception as e:
        health["components"]["redis"] = {"status": "error", "error": str(e)}
        if health["status"] == "ok":
            health["status"] = "degraded"

    # 3. FFmpeg check
    try:
        ffmpeg_bin = FFMPEG_PATH if (FFMPEG_PATH and shutil.which(FFMPEG_PATH)) else shutil.which("ffmpeg")
        if ffmpeg_bin:
            health["components"]["ffmpeg"] = {"status": "ok", "path": ffmpeg_bin}
        else:
            health["components"]["ffmpeg"] = {"status": "missing", "error": "FFmpeg executable not found"}
            health["status"] = "degraded"
    except Exception as e:
        health["components"]["ffmpeg"] = {"status": "error", "error": str(e)}
        health["status"] = "degraded"

    return health
