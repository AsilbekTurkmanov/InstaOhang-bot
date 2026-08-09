"""
PostgreSQL async connection pool manager using asyncpg.
All database operations in the bot should use this pool for maximum performance.
"""

import logging
import asyncpg
from config import DATABASE_URL

logger = logging.getLogger(__name__)

# Global connection pool (initialized once on startup)
_pool: asyncpg.Pool | None = None


async def init_pool(min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    """
    Creates the global asyncpg connection pool.
    Call once at application startup in bot.py.
    """
    global _pool
    if _pool is not None:
        return _pool

    logger.info("Initializing PostgreSQL connection pool...")
    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=min_size,
        max_size=max_size,
        command_timeout=30,
        statement_cache_size=0,  # Required for pgbouncer compatibility
    )
    logger.info(f"PostgreSQL pool initialized (min={min_size}, max={max_size})")
    return _pool


async def close_pool() -> None:
    """
    Gracefully closes the connection pool.
    Call on application shutdown.
    """
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL connection pool closed.")


def get_pool() -> asyncpg.Pool:
    """
    Returns the active connection pool.
    Raises RuntimeError if the pool hasn't been initialized yet.
    """
    if _pool is None:
        raise RuntimeError(
            "Database pool is not initialized. Call init_pool() first in bot startup."
        )
    return _pool


async def init_db_schema() -> None:
    """
    Creates all required tables and indexes if they don't exist.
    Safe to call on every startup (idempotent).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():

            # ─── Users ───────────────────────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id               BIGSERIAL PRIMARY KEY,
                    telegram_id      BIGINT    UNIQUE NOT NULL,
                    username         TEXT,
                    first_name       TEXT,
                    last_name        TEXT,
                    language_code    TEXT,
                    is_bot           BOOLEAN   DEFAULT FALSE,
                    downloads_count  INTEGER   DEFAULT 0,
                    created_at       TIMESTAMPTZ DEFAULT NOW(),
                    updated_at       TIMESTAMPTZ DEFAULT NOW(),
                    last_activity_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # ─── Channels (mandatory subscriptions) ──────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id  BIGINT  PRIMARY KEY,
                    title       TEXT    NOT NULL,
                    invite_link TEXT    NOT NULL
                )
            """)

            # ─── Downloads history ────────────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id         BIGSERIAL PRIMARY KEY,
                    user_id    BIGINT NOT NULL,
                    url        TEXT,
                    type       TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # ─── Media cache (Telegram file_id reuse) ────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS media_cache (
                    id          BIGSERIAL PRIMARY KEY,
                    url_or_id   TEXT    UNIQUE NOT NULL,
                    file_id     TEXT    NOT NULL,
                    media_type  TEXT    NOT NULL,
                    caption     TEXT    DEFAULT '',
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # ─── Music Categories ─────────────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS music_categories (
                    id         SERIAL PRIMARY KEY,
                    name       TEXT   UNIQUE NOT NULL,
                    is_active  BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # ─── Music ───────────────────────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS music (
                    id             SERIAL PRIMARY KEY,
                    title          TEXT   NOT NULL,
                    artist         TEXT   DEFAULT '',
                    file_id        TEXT,
                    file_unique_id TEXT   UNIQUE,
                    category_id    INTEGER REFERENCES music_categories(id) ON DELETE SET NULL,
                    views          INTEGER DEFAULT 0,
                    is_active      BOOLEAN DEFAULT TRUE,
                    created_at     TIMESTAMPTZ DEFAULT NOW(),
                    updated_at     TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # ─── Favorites ───────────────────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id         BIGSERIAL PRIMARY KEY,
                    user_id    BIGINT NOT NULL,
                    music_id   INTEGER NOT NULL REFERENCES music(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE (user_id, music_id)
                )
            """)

            # ─── Portfolio messages ──────────────────────────────────────────
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_messages (
                    id         BIGSERIAL PRIMARY KEY,
                    name       TEXT,
                    email      TEXT,
                    subject    TEXT,
                    message    TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # ─── Indexes ──────────────────────────────────────────────────────
            # Users
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_telegram_id
                ON users (telegram_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users (username) WHERE username IS NOT NULL
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_last_activity
                ON users (last_activity_at DESC)
            """)

            # Downloads
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_downloads_user_id
                ON downloads (user_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_downloads_created_at
                ON downloads (created_at DESC)
            """)

            # Media cache
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_media_cache_url
                ON media_cache (url_or_id)
            """)

            # Music
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_music_title
                ON music (title) WHERE is_active = TRUE
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_music_artist
                ON music (artist) WHERE is_active = TRUE
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_music_category
                ON music (category_id) WHERE is_active = TRUE
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_music_views
                ON music (views DESC) WHERE is_active = TRUE
            """)

            # Favorites
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_favorites_user_id
                ON favorites (user_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_favorites_music_id
                ON favorites (music_id)
            """)

    logger.info("Database schema initialized successfully (all tables and indexes ready).")
