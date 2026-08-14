"""Initial database schema migration

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Users
    op.execute("""
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

    # Channels
    op.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id  BIGINT  PRIMARY KEY,
            title       TEXT    NOT NULL,
            invite_link TEXT    NOT NULL
        )
    """)

    # Downloads
    op.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id         BIGSERIAL PRIMARY KEY,
            user_id    BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
            url        TEXT,
            type       TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Media Cache
    op.execute("""
        CREATE TABLE IF NOT EXISTS media_cache (
            id           BIGSERIAL PRIMARY KEY,
            url_or_id    TEXT    UNIQUE NOT NULL,
            file_id      TEXT    NOT NULL,
            media_type   TEXT    NOT NULL,
            caption      TEXT    DEFAULT '',
            hit_count    INTEGER DEFAULT 1,
            last_used_at TIMESTAMPTZ DEFAULT NOW(),
            created_at   TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Music Categories
    op.execute("""
        CREATE TABLE IF NOT EXISTS music_categories (
            id         SERIAL PRIMARY KEY,
            name       TEXT   UNIQUE NOT NULL,
            is_active  BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Music
    op.execute("""
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

    # Favorites
    op.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id         BIGSERIAL PRIMARY KEY,
            user_id    BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
            music_id   INTEGER NOT NULL REFERENCES music(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (user_id, music_id)
        )
    """)

    # Portfolio Messages
    op.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_messages (
            id          BIGSERIAL PRIMARY KEY,
            name        TEXT,
            email       TEXT,
            phone       TEXT,
            subject     TEXT,
            message     TEXT,
            ip_address  TEXT,
            status      TEXT    DEFAULT 'new',
            telegram_id BIGINT,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # AI Conversations & Messages
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_conversations (
            id               BIGSERIAL PRIMARY KEY,
            telegram_user_id BIGINT UNIQUE NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            updated_at       TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_messages (
            id              BIGSERIAL PRIMARY KEY,
            conversation_id BIGINT NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Media Processing Cache
    op.execute("""
        CREATE TABLE IF NOT EXISTS media_processing_cache (
            id                    BIGSERIAL PRIMARY KEY,
            source_file_unique_id TEXT NOT NULL,
            operation             TEXT NOT NULL,
            telegram_file_id      TEXT NOT NULL,
            created_at            TIMESTAMPTZ DEFAULT NOW(),
            last_used_at          TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (source_file_unique_id, operation)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS media_processing_cache CASCADE;")
    op.execute("DROP TABLE IF EXISTS ai_messages CASCADE;")
    op.execute("DROP TABLE IF EXISTS ai_conversations CASCADE;")
    op.execute("DROP TABLE IF EXISTS portfolio_messages CASCADE;")
    op.execute("DROP TABLE IF EXISTS favorites CASCADE;")
    op.execute("DROP TABLE IF EXISTS music CASCADE;")
    op.execute("DROP TABLE IF EXISTS music_categories CASCADE;")
    op.execute("DROP TABLE IF EXISTS media_cache CASCADE;")
    op.execute("DROP TABLE IF EXISTS downloads CASCADE;")
    op.execute("DROP TABLE IF EXISTS channels CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
