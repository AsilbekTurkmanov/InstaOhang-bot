"""
General-purpose helper utilities for @InstaOhang_bot.
"""

import os
import time
import html
import logging
from aiogram import Bot
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from database.db import get_channels
from config import MAX_FILE_SIZE_MB, DOWNLOAD_DIR

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# In-memory subscription cache
# TTL: 60 seconds, max 5000 entries (prevents unbounded growth)
# ─────────────────────────────────────────────────────────────────────────────
SUB_CACHE: dict[int, tuple[float, bool, list]] = {}
CACHE_TTL_SECONDS = 60
SUB_CACHE_MAX_SIZE = 5000


def _evict_sub_cache() -> None:
    """Removes expired entries when cache grows too large."""
    if len(SUB_CACHE) < SUB_CACHE_MAX_SIZE:
        return
    now = time.time()
    expired = [uid for uid, (ts, _, _) in SUB_CACHE.items()
               if now - ts >= CACHE_TTL_SECONDS]
    for uid in expired:
        SUB_CACHE.pop(uid, None)
    # If still too large, remove oldest half
    if len(SUB_CACHE) >= SUB_CACHE_MAX_SIZE:
        oldest = sorted(SUB_CACHE.keys(), key=lambda uid: SUB_CACHE[uid][0])
        for uid in oldest[: len(oldest) // 2]:
            SUB_CACHE.pop(uid, None)


# ─────────────────────────────────────────────────────────────────────────────
# HTML / text utilities
# ─────────────────────────────────────────────────────────────────────────────

def clean_html(text: str) -> str:
    """Escapes HTML entities to prevent Telegram parse errors."""
    if not text:
        return ""
    return html.escape(str(text))


# ─────────────────────────────────────────────────────────────────────────────
# File size check
# ─────────────────────────────────────────────────────────────────────────────

def check_file_size(filepath: str, max_mb: int = MAX_FILE_SIZE_MB) -> tuple[bool, float]:
    """
    Checks if file size is within limits.
    Returns (is_valid, size_in_mb).
    """
    if not filepath or not os.path.exists(filepath):
        return False, 0.0
    size_bytes = os.path.getsize(filepath)
    size_mb = size_bytes / (1024 * 1024)
    return size_mb <= max_mb, round(size_mb, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Keyboards
# ─────────────────────────────────────────────────────────────────────────────

def get_main_reply_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🎵 Musiqa izlash"), KeyboardButton(text="❤️ Sevimlilar")],
        [KeyboardButton(text="ℹ️ Bot haqida"), KeyboardButton(text="⭕ Dumaloq Video haqida")],
        [KeyboardButton(text="🤖 AI Agent"), KeyboardButton(text="⚙️ AI Agent-Info")],
    ]
    if is_admin:
        keyboard.append([
            KeyboardButton(text="📊 Admin Panel"),
            KeyboardButton(text="📩 Portfolio xabarlari"),
        ])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_media_inline_keyboard() -> InlineKeyboardMarkup:
    """Creates interactive inline keyboard attached below downloaded media."""
    buttons = [
        [
            InlineKeyboardButton(text="🎵 MP3 Musiqani yuklab olish", callback_data="extract_mp3"),
            InlineKeyboardButton(text="⭕ Dumaloq Video (/round)", callback_data="make_round_from_msg"),
        ],
        [
            InlineKeyboardButton(text="⏩ 1.5x Tezlashtirish", callback_data="speed_1.5"),
            InlineKeyboardButton(text="🔄 Qayta yuklash", callback_data="reload_media"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_subscription_keyboard(missing_channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch in missing_channels:
        buttons.append([
            InlineKeyboardButton(
                text=f"➕ {clean_html(ch['title'])}",
                url=ch["invite_link"],
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_subscription")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─────────────────────────────────────────────────────────────────────────────
# Subscription check (async, with TTL cache)
# ─────────────────────────────────────────────────────────────────────────────

async def check_user_subscriptions(bot: Bot, user_id: int) -> tuple[bool, list]:
    """
    Checks if user is subscribed to all mandatory channels.
    Uses a 60-second in-memory TTL cache per user.
    Returns (is_subscribed, missing_channels_list).
    """
    now = time.time()

    # Cache hit?
    if user_id in SUB_CACHE:
        cached_time, is_subbed, missing = SUB_CACHE[user_id]
        if now - cached_time < CACHE_TTL_SECONDS:
            return is_subbed, missing

    channels = await get_channels()
    if not channels:
        _evict_sub_cache()
        SUB_CACHE[user_id] = (now, True, [])
        return True, []

    missing_channels = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["channel_id"], user_id=user_id)
            if member.status in ("left", "kicked"):
                missing_channels.append(ch)
        except Exception as e:
            logger.warning(
                f"Could not check channel membership for {ch['channel_id']}: {e}"
            )

    is_subbed = len(missing_channels) == 0
    _evict_sub_cache()
    SUB_CACHE[user_id] = (now, is_subbed, missing_channels)
    return is_subbed, missing_channels


# ─────────────────────────────────────────────────────────────────────────────
# File cleanup utilities
# ─────────────────────────────────────────────────────────────────────────────

def safe_remove_files(*filepaths) -> None:
    for fp in filepaths:
        if fp and os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception as e:
                logger.error(f"Error deleting temporary file {fp}: {e}")


def cleanup_old_temp_files(max_age_seconds: int = 1800) -> None:
    """Purges files in DOWNLOAD_DIR older than max_age_seconds."""
    if not os.path.exists(DOWNLOAD_DIR):
        return
    now = time.time()
    cleaned_count = 0
    for filename in os.listdir(DOWNLOAD_DIR):
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.isfile(filepath):
            try:
                file_age = now - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    os.remove(filepath)
                    cleaned_count += 1
            except Exception as e:
                logger.error(f"Error cleaning old file {filepath}: {e}")
    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} old temp file(s) from downloads/")
