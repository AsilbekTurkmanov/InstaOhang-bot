import sqlite3
import os
from datetime import datetime
from config import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA cache_size = -64000;") # 64MB cache
    cursor.execute("PRAGMA temp_store = MEMORY;")
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            downloads_count INTEGER DEFAULT 0
        )
    ''')
    
    # Mandatory channels table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY,
            title TEXT,
            invite_link TEXT
        )
    ''')
    
    # Downloads history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            url TEXT,
            type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Media cache table for instant re-downloads via Telegram file_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_or_id TEXT UNIQUE,
            file_id TEXT,
            media_type TEXT,
            caption TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_cache ON media_cache(url_or_id);')

    # Portfolio contact messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            subject TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_cached_media(url_or_id: str):
    """Retrieves cached Telegram file_id if exists."""
    if not url_or_id:
        return None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT file_id, media_type, caption FROM media_cache WHERE url_or_id = ?', (url_or_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
    except Exception as e:
        pass
    return None

def save_cached_media(url_or_id: str, file_id: str, media_type: str, caption: str = ""):
    """Saves Telegram file_id to media_cache for instant future responses."""
    if not url_or_id or not file_id:
        return
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO media_cache (url_or_id, file_id, media_type, caption)
            VALUES (?, ?, ?, ?)
        ''', (url_or_id, file_id, media_type, caption))
        conn.commit()
        conn.close()
    except Exception as e:
        pass


def add_user(user_id: int, full_name: str, username: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, full_name, username)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            full_name = excluded.full_name,
            username = excluded.username
    ''', (user_id, full_name, username))
    conn.commit()
    conn.close()

def increment_user_downloads(user_id: int, url: str = "", media_type: str = "video"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET downloads_count = downloads_count + 1 WHERE user_id = ?', (user_id,))
    cursor.execute('INSERT INTO downloads (user_id, url, type) VALUES (?, ?, ?)', (user_id, url, media_type))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    rows = cursor.fetchall()
    conn.close()
    return [row['user_id'] for row in rows]

def get_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as total_users FROM users')
    total_users = cursor.fetchone()['total_users']
    
    cursor.execute('SELECT COUNT(*) as total_downloads FROM downloads')
    total_downloads = cursor.fetchone()['total_downloads']
    
    cursor.execute('SELECT COUNT(DISTINCT user_id) as active_today FROM downloads WHERE DATE(created_at) = DATE("now")')
    active_today = cursor.fetchone()['active_today']
    
    cursor.execute('SELECT COUNT(DISTINCT user_id) as active_week FROM downloads WHERE created_at >= DATE("now", "-7 days")')
    active_week = cursor.fetchone()['active_week']
    
    conn.close()
    return {
        'total_users': total_users,
        'total_downloads': total_downloads,
        'active_today': active_today,
        'active_week': active_week
    }


def get_user_rank(user_id: int) -> int:
    """Returns the sequential registration number of a user (1-indexed)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT COUNT(*) as rank FROM users WHERE rowid <= (SELECT rowid FROM users WHERE user_id = ?)',
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row['rank'] if row and row['rank'] > 0 else None

def add_channel(channel_id: int, title: str, invite_link: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO channels (channel_id, title, invite_link) VALUES (?, ?, ?)',
                   (channel_id, title, invite_link))
    conn.commit()
    conn.close()

def remove_channel(channel_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
    conn.commit()
    conn.close()

def get_channels():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM channels')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_portfolio_message(name: str, email: str, subject: str, message: str):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO portfolio_messages (name, email, subject, message)
            VALUES (?, ?, ?, ?)
        ''', (name, email, subject, message))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database error saving portfolio message: {e}")

def get_portfolio_messages(limit: int = 100):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM portfolio_messages ORDER BY id ASC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Database error getting portfolio messages: {e}")
        return []
