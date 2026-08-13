import os
import re
import logging
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InputMediaPhoto, InputMediaVideo,
)

from services.downloader import download_instagram_media
from services.ffmpeg_service import extract_audio_from_video, convert_to_round_video, change_video_speed
from database.db import increment_user_downloads, get_cached_media, save_cached_media
from utils.helpers import (
    get_media_inline_keyboard, safe_remove_files, check_user_subscriptions,
    get_subscription_keyboard, clean_html, check_file_size,
)
from utils.performance import Timer

router = Router()
logger = logging.getLogger(__name__)

INSTAGRAM_REGEX = r'https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/[A-Za-z0-9_-]+'


@router.message(F.text.regexp(INSTAGRAM_REGEX))
async def handle_instagram_link(message: Message):
    user_id = message.from_user.id
    url_match = re.search(INSTAGRAM_REGEX, message.text)
    if not url_match:
        return

    url = url_match.group(0)

    async with Timer("instagram_download") as t:
        # Subscription check
        is_subbed, missing = await check_user_subscriptions(message.bot, user_id)
        t.checkpoint("sub_check")

        if not is_subbed:
            await message.answer(
                "🔒 <b>Botdan foydalanish uchun kanallarga obuna bo'ling:</b>",
                reply_markup=get_subscription_keyboard(missing),
                parse_mode="HTML",
            )
            return

        # Instant cache hit
        cached = await get_cached_media(url)
        t.checkpoint("cache_lookup")

        if cached:
            try:
                if cached["media_type"] == "video":
                    await message.answer_video(
                        video=cached["file_id"],
                        caption=cached.get("caption") or "⚡ @InstaOhang_bot",
                        reply_markup=get_media_inline_keyboard(),
                        parse_mode="HTML",
                    )
                else:
                    await message.answer_photo(
                        photo=cached["file_id"],
                        caption=cached.get("caption") or "⚡ @InstaOhang_bot",
                        parse_mode="HTML",
                    )
                await increment_user_downloads(user_id, url, cached["media_type"])
                t.checkpoint("cache_send")
                return
            except Exception as cache_err:
                logger.warning(f"Cached send failed, falling back to fresh download: {cache_err}")

        # Fresh download
        status_msg = await message.answer(
            "📥 <b>Instagram-dan yuklanmoqda...</b>\n<i>Iltimos biroz kuting ⏳</i>",
            parse_mode="HTML",
        )

        try:
            media_data = await download_instagram_media(url)
            t.checkpoint("download")

            title      = clean_html(media_data["title"])
            author     = clean_html(media_data["author"])
            media_type = media_data["type"]
            items      = media_data.get("items", [])

            caption = f"🎬 <b>{author}</b>\n\n{title[:150]}...\n\n🤖 @InstaOhang_bot"
            all_files_to_clean = []

            if media_type == "carousel" and len(items) > 1:
                media_group = []
                for idx, item in enumerate(items[:10]):
                    fp = item["filepath"]
                    all_files_to_clean.append(fp)
                    is_valid, size_mb = check_file_size(fp)
                    if not is_valid:
                        continue
                    input_file  = FSInputFile(fp)
                    item_caption = caption if idx == 0 else ""
                    if item["type"] == "video":
                        media_group.append(
                            InputMediaVideo(media=input_file, caption=item_caption, parse_mode="HTML")
                        )
                    else:
                        media_group.append(
                            InputMediaPhoto(media=input_file, caption=item_caption, parse_mode="HTML")
                        )

                if media_group:
                    try:
                        await message.answer_media_group(media=media_group)
                    except Exception as send_err:
                        logger.error(f"Telegram media group send error: {send_err}")
                        await status_msg.edit_text(
                            "⚠️ <b>Fayl hajmi juda kattaligi sababli Telegram orqali yuborib bo'lmadi.</b>",
                            parse_mode="HTML",
                        )
                        safe_remove_files(*all_files_to_clean)
                        return
                else:
                    await status_msg.edit_text(
                        "⚠️ <b>Fayl hajmi 200 MB dan katta bo'lgani uchun Telegram orqali yuborib bo'lmadi.</b>",
                        parse_mode="HTML",
                    )

            elif media_type == "video":
                filepath  = media_data["filepath"]
                all_files_to_clean.append(filepath)
                is_valid, size_mb = check_file_size(filepath)
                if not is_valid:
                    await status_msg.edit_text(
                        f"⚠️ <b>Video hajmi juda katta ({size_mb} MB). "
                        f"Maksimal 200 MB ruxsat berilgan.</b>",
                        parse_mode="HTML",
                    )
                    safe_remove_files(*all_files_to_clean)
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
                        await save_cached_media(url, sent_msg.video.file_id, "video", caption)
                except Exception as send_err:
                    logger.error(f"Telegram video send error: {send_err}")
                    await status_msg.edit_text(
                        f"⚠️ <b>Video hajmi ({size_mb} MB) Telegram serveri cheklovidan yuqori bo'lgani sababli yuborib bo'lmadi.</b>",
                        parse_mode="HTML",
                    )
                    safe_remove_files(*all_files_to_clean)
                    return

            else:  # photo
                filepath = media_data["filepath"]
                all_files_to_clean.append(filepath)
                photo_input = FSInputFile(filepath)
                sent_msg = await message.answer_photo(
                    photo=photo_input,
                    caption=caption,
                    parse_mode="HTML",
                )
                if sent_msg and sent_msg.photo:
                    await save_cached_media(url, sent_msg.photo[-1].file_id, "photo", caption)

            t.checkpoint("telegram_send")
            await increment_user_downloads(user_id, url, media_type)
            await status_msg.delete()
            safe_remove_files(*all_files_to_clean)

        except Exception as e:
            logger.error(f"Instagram download error: {e}")
            await status_msg.edit_text(
                "❌ <b>Xatolik yuz berdi.</b>\n\n"
                "Havola to'g'riligini tekshiring yoki birozdan keyin qayta urinib ko'ring.",
                parse_mode="HTML",
            )



# ─────────────────────────────────────────────────────────────────────────────
# Inline callback handlers (attached to downloaded videos)
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "extract_mp3")
async def cb_extract_mp3(callback: CallbackQuery):
    msg = callback.message
    if not msg.video:
        await callback.answer("❌ Ushbu xabarda video topilmadi!", show_alert=True)
        return

    await callback.answer("🎵 Musiqa ajratib olinmoqda...")
    status_msg = await msg.reply("🎧 <b>Audio ajratib olinmoqda...</b>", parse_mode="HTML")

    video_file    = await callback.bot.get_file(msg.video.file_id)
    download_path = f"downloads/temp_{msg.video.file_unique_id}.mp4"
    await callback.bot.download_file(video_file.file_path, download_path)

    try:
        mp3_path = await extract_audio_from_video(download_path)
        is_valid, size_mb = check_file_size(mp3_path)
        if not is_valid:
            await status_msg.edit_text(
                f"⚠️ <b>Audio hajmi juda katta ({size_mb} MB).</b>", parse_mode="HTML"
            )
            safe_remove_files(download_path, mp3_path)
            return

        audio_file = FSInputFile(mp3_path)
        await msg.reply_audio(
            audio=audio_file,
            caption="🎵 <b>Videodan ajratib olingan MP3</b>\n\n🤖 @InstaOhang_bot",
            parse_mode="HTML",
        )
        await status_msg.delete()
        safe_remove_files(download_path, mp3_path)

    except Exception as e:
        logger.error(f"Extract MP3 error: {e}")
        await status_msg.edit_text("❌ Musiqani ajratishda xatolik yuz berdi.")
        safe_remove_files(download_path)


@router.callback_query(F.data == "make_round_from_msg")
async def cb_make_round_inline(callback: CallbackQuery):
    msg = callback.message
    if not msg.video:
        await callback.answer("❌ Video topilmadi!", show_alert=True)
        return

    await callback.answer("⭕ Dumaloq video tayyorlanmoqda...")
    status_msg = await msg.reply(
        "⭕ <b>Videoni dumaloq shaklga keltirish qilinmoqda...</b>", parse_mode="HTML"
    )

    video_file    = await callback.bot.get_file(msg.video.file_id)
    download_path = f"downloads/temp_round_{msg.video.file_unique_id}.mp4"
    await callback.bot.download_file(video_file.file_path, download_path)

    try:
        round_path = await convert_to_round_video(download_path)
        is_valid, size_mb = check_file_size(round_path)
        if not is_valid:
            await status_msg.edit_text(
                f"⚠️ <b>Video hajmi juda katta ({size_mb} MB).</b>", parse_mode="HTML"
            )
            safe_remove_files(download_path, round_path)
            return

        video_note = FSInputFile(round_path)
        await msg.reply_video_note(video_note=video_note)
        await status_msg.delete()
        safe_remove_files(download_path, round_path)

    except Exception as e:
        logger.error(f"Make round error: {e}")
        await status_msg.edit_text("❌ Dumaloq video yaratishda xatolik yuz berdi.")
        safe_remove_files(download_path)


@router.callback_query(F.data == "speed_1.5")
async def cb_speed_video(callback: CallbackQuery):
    msg = callback.message
    if not msg.video:
        await callback.answer("❌ Video topilmadi!", show_alert=True)
        return

    await callback.answer("⏩ 1.5x Tezlashtirilmoqda...")
    status_msg = await msg.reply(
        "⚡ <b>Video 1.5x tezlashtirilmoqda...</b>", parse_mode="HTML"
    )

    video_file    = await callback.bot.get_file(msg.video.file_id)
    download_path = f"downloads/temp_speed_{msg.video.file_unique_id}.mp4"
    await callback.bot.download_file(video_file.file_path, download_path)

    try:
        fast_path = await change_video_speed(download_path, speed=1.5)
        is_valid, size_mb = check_file_size(fast_path)
        if not is_valid:
            await status_msg.edit_text(
                f"⚠️ <b>Video hajmi juda katta ({size_mb} MB).</b>", parse_mode="HTML"
            )
            safe_remove_files(download_path, fast_path)
            return

        fast_video = FSInputFile(fast_path)
        await msg.reply_video(
            video=fast_video,
            caption="⚡ <b>1.5x Tezlashtirilgan Video</b>\n\n🤖 @InstaOhang_bot",
            parse_mode="HTML",
        )
        await status_msg.delete()
        safe_remove_files(download_path, fast_path)

    except Exception as e:
        logger.error(f"Speed change error: {e}")
        await status_msg.edit_text("❌ Video tezlashtirishda xatolik yuz berdi.")
        safe_remove_files(download_path)


@router.callback_query(F.data == "reload_media")
async def cb_reload_media(callback: CallbackQuery):
    """Inform user to resend the Instagram link for re-download."""
    await callback.answer(
        "🔄 Qayta yuklash uchun Instagram havolasini yana bir marta yuboring.",
        show_alert=True,
    )
