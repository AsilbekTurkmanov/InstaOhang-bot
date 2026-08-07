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
    
    conn.commit()
    conn.close()

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
