"""
YouTube video downloader handler for @InstaOhang_bot.
Downloads YouTube video / shorts and attaches action buttons:
- MP3 audio extraction
- Round video note (/round)
- 1.5x Speed up
- 0.75x Slow down
"""

import os
import logging
from aiogram import Router, F
from aiogram.types import Message, FSInputFile

from services.youtube_parser import parse_youtube_url, YOUTUBE_REGEX
from services.downloader import download_youtube_video, set_media_origin
from database.db import get_cached_media, save_cached_media, increment_user_downloads
from utils.helpers import (
    get_media_inline_keyboard, safe_remove_files, check_user_subscriptions,
    get_subscription_keyboard, clean_html, check_file_size,
)
from utils.performance import Timer

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text.regexp(YOUTUBE_REGEX))
async def handle_youtube_link(message: Message):
    user_id = message.from_user.id
    parsed = parse_youtube_url(message.text)
    if not parsed:
        return

    url = parsed.canonical_url
    video_id = parsed.video_id

    async with Timer("youtube_download") as t:
        # 1. Subscription check
        is_subbed, missing = await check_user_subscriptions(message.bot, user_id)
        t.checkpoint("sub_check")

        if not is_subbed:
            await message.answer(
                "🔒 <b>Botdan foydalanish uchun kanallarga obuna bo'ling:</b>",
                reply_markup=get_subscription_keyboard(missing),
                parse_mode="HTML",
            )
            return

        cache_key = f"yt_vid_{video_id}"

        # 2. Instant cache hit
        cached = await get_cached_media(cache_key)
        t.checkpoint("cache_lookup")

        if cached:
            try:
                sent = await message.answer_video(
                    video=cached["file_id"],
                    caption=cached.get("caption") or "⚡ @InstaOhang_bot",
                    reply_markup=get_media_inline_keyboard(),
                    parse_mode="HTML",
                )
                if sent and sent.video:
                    set_media_origin(sent.video.file_unique_id, url)
                await increment_user_downloads(user_id, url, "video")
                t.checkpoint("cache_send")
                return
            except Exception as cache_err:
                logger.warning(f"Cached YouTube send failed, downloading fresh: {cache_err}")

        # 3. Fresh download
        status_msg = await message.answer(
            "📥 <b>YouTube-dan video yuklanmoqda...</b>\n<i>Iltimos biroz kuting ⏳</i>",
            parse_mode="HTML",
        )

        try:
            media_data = await download_youtube_video(url)
            t.checkpoint("download")

            filepath = media_data["filepath"]
            title = clean_html(media_data["title"])
            author = clean_html(media_data["author"])

            title_display = title[:100] + "..." if len(title) > 100 else title
            author_display = author[:50] if len(author) > 50 else author
            caption = f"🎬 <b>{author_display}</b>\n\n{title_display}\n\n🤖 @InstaOhang_bot"

            is_valid, size_mb = check_file_size(filepath)
            if not is_valid:
                await status_msg.edit_text(
                    f"⚠️ <b>Video hajmi juda katta ({size_mb} MB). "
                    f"Telegram orqali maksimal 200 MB yuborish mumkin.</b>",
                    parse_mode="HTML",
                )
                safe_remove_files(filepath)
                return

            video_input = FSInputFile(filepath)
            try:
                sent_msg = await message.answer_video(
                    video=video_input,
                    caption=caption,
                    reply_markup=get_media_inline_keyboard(),
                    parse_mode="HTML",
                )
                if sent_msg and sent_msg.video:
                    set_media_origin(sent_msg.video.file_unique_id, url)
                    await save_cached_media(cache_key, sent_msg.video.file_id, "video", caption)
            except Exception as send_err:
                logger.error(f"Telegram YouTube video send error: {send_err}")
                await status_msg.edit_text(
                    f"⚠️ <b>Video hajmi ({size_mb} MB) Telegram serveri cheklovidan yuqori bo'lgani sababli yuborib bo'lmadi.</b>",
                    parse_mode="HTML",
                )
                safe_remove_files(filepath)
                return

            t.checkpoint("telegram_send")
            await increment_user_downloads(user_id, url, "video")
            await status_msg.delete()
            safe_remove_files(filepath)

        except Exception as e:
            logger.error(f"YouTube download error: {e}")
            await status_msg.edit_text(
                "❌ <b>YouTube videosini yuklashda xatolik yuz berdi.</b>\n\n"
                "Havola to'g'riligini tekshiring yoki birozdan keyin qayta urinib ko'ring.",
                parse_mode="HTML",
            )
