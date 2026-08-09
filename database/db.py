"""
Async database access layer for @InstaOhang_bot.
All functions are async and use the global asyncpg connection pool.
"""

import logging
import asyncpg
from datetime import datetime, timezone
from typing import Optional
from database.postgres import get_pool

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────────────

async def upsert_user(
    telegram_id: int,
    first_name: str,
    last_name: Optional[str] = None,
    username: Optional[str] = None,
    language_code: Optional[str] = None,
    is_bot: bool = False,
) -> None:
    """
    Inserts a new user or updates existing one (upsert).
    Race-condition safe — uses PostgreSQL ON CONFLICT DO UPDATE.
    Always updates last_activity_at on every call.
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users
                (telegram_id, first_name, last_name, username, language_code, is_bot,
                 created_at, updated_at, last_activity_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $7, $7)
            ON CONFLICT (telegram_id) DO UPDATE SET
                first_name       = EXCLUDED.first_name,
                last_name        = EXCLUDED.last_name,
                username         = EXCLUDED.username,
                language_code    = EXCLUDED.language_code,
                updated_at       = EXCLUDED.updated_at,
                last_activity_at = EXCLUDED.last_activity_at
            """,
            telegram_id, first_name, last_name, username, language_code, is_bot, now,
        )


async def update_user_activity(telegram_id: int) -> None:
    """Updates only last_activity_at for an existing user."""
    pool = get_pool()
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET last_activity_at = $1 WHERE telegram_id = $2",
            now, telegram_id,
        )


async def increment_user_downloads(
    telegram_id: int,
    url: str = "",
    media_type: str = "video",
) -> None:
    """Increments downloads_count and appends a downloads history row atomically."""
    pool = get_pool()
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE users SET downloads_count = downloads_count + 1 WHERE telegram_id = $1",
                telegram_id,
            )
            await conn.execute(
                "INSERT INTO downloads (user_id, url, type, created_at) VALUES ($1, $2, $3, $4)",
                telegram_id, url, media_type, now,
            )


async def get_all_user_ids() -> list[int]:
    """Returns all telegram_ids for broadcast."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT telegram_id FROM users")
    return [row["telegram_id"] for row in rows]


async def get_stats() -> dict:
    """Returns aggregated statistics: users, downloads, active today/week."""
    pool = get_pool()
    async with pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        total_downloads = await conn.fetchval("SELECT COUNT(*) FROM downloads")
        active_today = await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM downloads "
            "WHERE created_at >= CURRENT_DATE"
        )
        active_week = await conn.fetchval(
            "SELECT COUNT(DISTINCT user_id) FROM downloads "
            "WHERE created_at >= NOW() - INTERVAL '7 days'"
        )
    return {
        "total_users": total_users or 0,
        "total_downloads": total_downloads or 0,
        "active_today": active_today or 0,
        "active_week": active_week or 0,
    }


async def get_user_rank(telegram_id: int) -> Optional[int]:
    """Returns the registration rank (1-based) of a user by created_at order."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rank = await conn.fetchval(
            """
            SELECT rank FROM (
                SELECT telegram_id,
                       RANK() OVER (ORDER BY created_at ASC) AS rank
                FROM users
            ) sub
            WHERE telegram_id = $1
            """,
            telegram_id,
        )
    return rank


# ─────────────────────────────────────────────────────────────────────────────
# Channels (mandatory subscriptions)
# ─────────────────────────────────────────────────────────────────────────────

async def add_channel(channel_id: int, title: str, invite_link: str) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO channels (channel_id, title, invite_link)
            VALUES ($1, $2, $3)
            ON CONFLICT (channel_id) DO UPDATE SET
                title = EXCLUDED.title,
                invite_link = EXCLUDED.invite_link
            """,
            channel_id, title, invite_link,
        )


async def remove_channel(channel_id: int) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM channels WHERE channel_id = $1", channel_id
        )


async def get_channels() -> list[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT channel_id, title, invite_link FROM channels")
    return [dict(row) for row in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Media Cache (Telegram file_id reuse — instant re-sends)
# ─────────────────────────────────────────────────────────────────────────────

async def get_cached_media(url_or_id: str) -> Optional[dict]:
    """Returns cached Telegram file_id metadata if exists. Updates last_used_at and hit_count."""
    if not url_or_id:
        return None
    pool = get_pool()
    try:
        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE media_cache
                SET last_used_at = $2,
                    hit_count    = hit_count + 1
                WHERE url_or_id = $1
                RETURNING file_id, media_type, caption
                """,
                url_or_id, now,
            )
        return dict(row) if row else None
    except asyncpg.PostgresError as e:
        logger.warning(f"get_cached_media DB error: {e}")
        return None
    except Exception as e:
        logger.warning(f"get_cached_media unexpected error: {e}")
        return None


async def save_cached_media(
    url_or_id: str, file_id: str, media_type: str, caption: str = ""
) -> None:
    """Saves or updates Telegram file_id in media_cache for instant future responses."""
    if not url_or_id or not file_id:
        return
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO media_cache (url_or_id, file_id, media_type, caption)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (url_or_id) DO UPDATE SET
                    file_id    = EXCLUDED.file_id,
                    media_type = EXCLUDED.media_type,
                    caption    = EXCLUDED.caption
                """,
                url_or_id, file_id, media_type, caption,
            )
    except Exception as e:
        logger.warning(f"save_cached_media error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio messages
# ─────────────────────────────────────────────────────────────────────────────

async def save_portfolio_message(
    name: str, email: str, subject: str, message: str
) -> None:
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO portfolio_messages (name, email, subject, message) "
                "VALUES ($1, $2, $3, $4)",
                name, email, subject, message,
            )
    except Exception as e:
        logger.error(f"save_portfolio_message error: {e}")


async def get_portfolio_messages(limit: int = 100) -> list[dict]:
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, email, subject, message, created_at "
                "FROM portfolio_messages ORDER BY id ASC LIMIT $1",
                limit,
            )
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"get_portfolio_messages error: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Music
# ─────────────────────────────────────────────────────────────────────────────

async def get_or_create_music(
    title: str,
    artist: str,
    file_id: str,
    file_unique_id: str,
    category_id: Optional[int] = None,
) -> int:
    """
    Upserts a music record. Returns the music id.
    Uses file_unique_id as the unique key to prevent duplicates.
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        music_id = await conn.fetchval(
            """
            INSERT INTO music (title, artist, file_id, file_unique_id, category_id, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $6)
            ON CONFLICT (file_unique_id) DO UPDATE SET
                file_id    = EXCLUDED.file_id,
                title      = EXCLUDED.title,
                artist     = EXCLUDED.artist,
                updated_at = EXCLUDED.updated_at
            RETURNING id
            """,
            title, artist, file_id, file_unique_id, category_id, now,
        )
    return music_id


async def increment_music_views(music_id: int) -> None:
    """
    Atomically increments the views counter for a music track.
    Race-condition safe — uses PostgreSQL atomic UPDATE.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE music SET views = views + 1 WHERE id = $1",
            music_id,
        )


async def get_music_by_file_unique_id(file_unique_id: str) -> Optional[dict]:
    """Returns a music record by Telegram file_unique_id."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, title, artist, file_id, views FROM music "
            "WHERE file_unique_id = $1 AND is_active = TRUE",
            file_unique_id,
        )
    return dict(row) if row else None


# ─────────────────────────────────────────────────────────────────────────────
# Favorites
# ─────────────────────────────────────────────────────────────────────────────

async def add_favorite(user_id: int, music_id: int) -> bool:
    """
    Adds a music track to user's favorites.
    Returns True if added, False if already favorited (duplicate).
    Only catches asyncpg.UniqueViolationError — other errors propagate.
    """
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO favorites (user_id, music_id) VALUES ($1, $2)",
                user_id, music_id,
            )
        return True
    except asyncpg.UniqueViolationError:
        # Expected: user already added this track to favorites
        return False
    except asyncpg.PostgresError as e:
        logger.error(f"add_favorite DB error (user={user_id}, music={music_id}): {e}")
        raise


async def remove_favorite(user_id: int, music_id: int) -> bool:
    """Removes a music track from user's favorites. Returns True if removed."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM favorites WHERE user_id = $1 AND music_id = $2",
            user_id, music_id,
        )
    return result == "DELETE 1"


async def is_favorite(user_id: int, music_id: int) -> bool:
    """Checks if a music track is in user's favorites."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM favorites WHERE user_id = $1 AND music_id = $2",
            user_id, music_id,
        )
    return row is not None


async def get_user_favorites(
    user_id: int, page: int = 0, page_size: int = 10
) -> tuple[list[dict], int]:
    """
    Returns paginated favorites list for a user with total count.
    Returns: (list of music records, total_count)
    """
    pool = get_pool()
    offset = page * page_size
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM favorites WHERE user_id = $1", user_id
        )
        rows = await conn.fetch(
            """
            SELECT m.id, m.title, m.artist, m.file_id, m.views,
                   f.created_at AS favorited_at
            FROM favorites f
            JOIN music m ON m.id = f.music_id
            WHERE f.user_id = $1 AND m.is_active = TRUE
            ORDER BY f.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            user_id, page_size, offset,
        )
    return [dict(row) for row in rows], total or 0


# ─────────────────────────────────────────────────────────────────────────────
# Backward compat aliases used by existing handlers (sync-style wrappers removed)
# ─────────────────────────────────────────────────────────────────────────────

# Kept for smooth migration — old callers can be updated gradually
async def add_user(telegram_id: int, full_name: str, username: str = None) -> None:
    """Backward compatible alias for upsert_user."""
    first_name = full_name or ""
    await upsert_user(
        telegram_id=telegram_id,
        first_name=first_name,
        username=username,
    )
