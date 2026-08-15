import os
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from services.downloader import search_music_results, download_music_by_id
from services.ffmpeg_service import extract_audio_from_video, change_video_speed
from config import DOWNLOAD_DIR
from database.db import (
    get_cached_media, save_cached_media,
    get_or_create_music, increment_music_views,
)
from utils.helpers import (
    safe_remove_files, check_user_subscriptions, get_subscription_keyboard,
    clean_html, check_file_size,
)
from utils.performance import measure_time

router = Router()
logger = logging.getLogger(__name__)

# Buttons that should NOT trigger a music search
MENU_BUTTONS = {
    "🎵 Musiqa izlash", "ℹ️ Bot haqida", "⭕ Dumaloq Video haqida",
    "🤖 AI Agent", "⚙️ AI Agent-Info", "📊 Admin Panel",
    "📩 Portfolio xabarlari", "❤️ Sevimlilar",
}


def build_music_result_keyboard(results: list) -> InlineKeyboardMarkup:
    """Builds inline keyboard for music search results."""
    buttons = []
    for idx, item in enumerate(results, start=1):
        title = item["title"]
        display = title[:40] + "..." if len(title) > 40 else title
        btn_text = f"{idx}. 🎵 {display}"
        buttons.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"dl_music:{item['id']}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_audio_action_keyboard(music_id: int) -> InlineKeyboardMarkup:
    """Keyboard attached to sent audio: add-to-favorites button."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="❤️ Sevimlilar ro'yxatiga qo'shish",
            callback_data=f"fav_add:{music_id}",
        )
    ]])


@measure_time("music_search")
async def process_music_search(message: Message, query: str):
    user_id = message.from_user.id

    is_subbed, missing = await check_user_subscriptions(message.bot, user_id)
    if not is_subbed:
        await message.answer(
            "🔒 <b>Botdan foydalanish uchun kanallarga obuna bo'ling:</b>",
            reply_markup=get_subscription_keyboard(missing),
            parse_mode="HTML",
        )
        return

    clean_q = clean_html(query)
    status_msg = await message.answer(
        f"🔍 <b>'{clean_q}' bo'yicha musiqalar qidirilmoqda...</b>",
        parse_mode="HTML",
    )

    try:
        results = await search_music_results(query, max_results=10)
        if not results:
            await status_msg.edit_text(
                f"❌ <b>'{clean_q}'</b> bo'yicha musiqa topilmadi. Qayta urinib ko'ring!",
                parse_mode="HTML",
            )
            return

        text_lines = [f"🔍 <b>'{clean_q}' bo'yicha topilgan musiqalar:</b>\n"]
        for idx, item in enumerate(results, start=1):
            title = clean_html(item["title"])
            duration = item["duration_str"]
            display_title = title[:45] + "..." if len(title) > 45 else title
            text_lines.append(
                f"<b>{idx}.</b> 🎵 {display_title} <i>({duration})</i>"
            )
        text_lines.append("\n👇 <i>Yuklab olish uchun quyidagi tugmalardan birini tanlang:</i>")

        await status_msg.edit_text(
            "\n".join(text_lines),
            reply_markup=build_music_result_keyboard(results),
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f"Music search error: {e}")
        await status_msg.edit_text(
            f"❌ Musiqa qidirishda xatolik yuz berdi. Qayta urinib ko'ring."
        )


@router.callback_query(F.data.startswith("dl_music:"))
async def cb_download_music(callback: CallbackQuery):
    user_id = callback.from_user.id

    is_subbed, missing = await check_user_subscriptions(callback.bot, user_id)
    if not is_subbed:
        await callback.answer(
            "🔒 Botdan foydalanish uchun kanallarga obuna bo'ling!", show_alert=True
        )
        return

    video_id = callback.data.split("dl_music:")[1]
    cache_key = f"yt_{video_id}"

    # ── Instant cache hit ──────────────────────────────────────────────────
    cached = await get_cached_media(cache_key)
    if cached:
        try:
            await callback.answer("⚡ Keshdan yuklanmoqda...")
            await callback.message.answer_audio(
                audio=cached["file_id"],
                caption="🎧 <b>InstaOhang Music Engine</b>\n🤖 @InstaOhang_bot",
                parse_mode="HTML",
            )
            return
        except Exception as cache_err:
            logger.warning(f"Cached audio send failed: {cache_err}")

    # ── Fresh download ─────────────────────────────────────────────────────
    await callback.answer("📥 Musiqa yuklanmoqda...")
    status_msg = await callback.message.reply(
        "⏳ <b>Musiqa yuklab olinmoqda...</b>", parse_mode="HTML"
    )

    try:
        music_data = await download_music_by_id(video_id)
        mp3_path = music_data["filepath"]
        title = clean_html(music_data["title"])
        performer = clean_html(music_data["performer"])
        duration = music_data["duration"]

        is_valid, size_mb = check_file_size(mp3_path)
        if not is_valid:
            await status_msg.edit_text(
                f"⚠️ <b>Audio hajmi juda katta ({size_mb} MB). "
                f"Maksimal 200 MB ruxsat berilgan.</b>",
                parse_mode="HTML",
            )
            safe_remove_files(mp3_path)
            return


        audio_file = FSInputFile(mp3_path)
        sent_audio = await callback.message.answer_audio(
            audio=audio_file,
            title=title,
            performer=performer,
            duration=duration,
            caption="🎧 <b>InstaOhang Music Engine</b>\n🤖 @InstaOhang_bot",
            parse_mode="HTML",
        )

        # ── Save to cache + Music table ────────────────────────────────────
        if sent_audio and sent_audio.audio:
            await save_cached_media(cache_key, sent_audio.audio.file_id, "audio", title)

            # Save to music table and get music_id for favorites
            try:
                music_id = await get_or_create_music(
                    title=music_data["title"],
                    artist=music_data["performer"],
                    file_id=sent_audio.audio.file_id,
                    file_unique_id=sent_audio.audio.file_unique_id,
                )
                await increment_music_views(music_id)

                # Edit caption to add favorites button
                await sent_audio.edit_caption(
                    caption="🎧 <b>InstaOhang Music Engine</b>\n🤖 @InstaOhang_bot",
                    reply_markup=build_audio_action_keyboard(music_id),
                    parse_mode="HTML",
                )
            except Exception as db_err:
                logger.warning(f"Could not save music to DB or add fav button: {db_err}")

        await status_msg.delete()
        safe_remove_files(mp3_path)

    except Exception as e:
        logger.error(f"Download music by id error: {e}")
        await status_msg.edit_text(
            "❌ Musiqani yuklashda xatolik yuz berdi. Qayta urinib ko'ring."
        )


@router.message(F.text == "🎵 Musiqa izlash")
async def music_btn_prompt(message: Message):
    await message.answer(
        "🎵 <b>Musiqa izlash uchun:</b>\n\n"
        "Shunchaki qo'shiq nomini yoki xonanda ismini matn ko'rinishida yuboring!\n"
        "<i>Misol:</i> <code>Konsta O'zbekiston</code>",
        parse_mode="HTML",
    )


@router.message(Command("music"))
async def cmd_music_search(message: Message):
    query = message.text.replace("/music", "").strip()
    if not query:
        await message.answer(
            "⚠️ Iltimos, qo'shiq nomini yozing!\n<i>Misol:</i> <code>Konsta</code>",
            parse_mode="HTML",
        )
        return
    await process_music_search(message, query)


@router.message(F.text & ~F.text.startswith("/"))
async def text_music_search(message: Message):
    query = message.text.strip()
    if not query or query in MENU_BUTTONS:
        return
    await process_music_search(message, query)


# ─────────────────────────────────────────────────────────────────────────────
# Audio / Video processing commands
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("audio"))
async def cmd_audio_extract(message: Message):
    """Replies to a video message and extracts MP3 audio."""
    target_msg = message.reply_to_message if message.reply_to_message else message
    if not (target_msg and target_msg.video):
        await message.answer(
            "⚠️ Musiqani ajratish uchun videoga javoban <code>/audio</code> deb yozing!",
            parse_mode="HTML",
        )
        return

    status_msg = await message.answer("🎧 <b>Audio ajratib olinmoqda...</b>", parse_mode="HTML")
    temp_video = os.path.join(DOWNLOAD_DIR, f"audio_ext_{message.message_id}.mp4")

    try:
        file_info = await message.bot.get_file(target_msg.video.file_id)
        await message.bot.download_file(file_info.file_path, temp_video)

        mp3_path = await extract_audio_from_video(temp_video)
        is_valid, size_mb = check_file_size(mp3_path)
        if not is_valid:
            await status_msg.edit_text(
                f"⚠️ <b>Audio hajmi juda katta ({size_mb} MB).</b>", parse_mode="HTML"
            )
            safe_remove_files(temp_video, mp3_path)
            return

        audio_file = FSInputFile(mp3_path)
        await message.answer_audio(
            audio=audio_file,
            caption="🎵 <b>MP3 Audio</b>\n🤖 @InstaOhang_bot",
            parse_mode="HTML",
        )
        await status_msg.delete()
        safe_remove_files(temp_video, mp3_path)

    except Exception as e:
        logger.error(f"Cmd audio extract error: {e}")
        await status_msg.edit_text("❌ Audio ajratishda xatolik yuz berdi.")
        safe_remove_files(temp_video)


@router.message(Command("fast"))
async def cmd_video_fast(message: Message):
    target_msg = message.reply_to_message if message.reply_to_message else message
    if not (target_msg and target_msg.video):
        await message.answer(
            "⚠️ Videoga reply qilib <code>/fast</code> deb yozing!", parse_mode="HTML"
        )
        return

    status_msg = await message.answer("⚡ <b>Video 1.5x tezlashtirilmoqda...</b>", parse_mode="HTML")
    temp_video = os.path.join(DOWNLOAD_DIR, f"fast_{message.message_id}.mp4")
    try:
        file_info = await message.bot.get_file(target_msg.video.file_id)
        await message.bot.download_file(file_info.file_path, temp_video)

        fast_path = await change_video_speed(temp_video, speed=1.5)
        is_valid, size_mb = check_file_size(fast_path)
        if not is_valid:
            await status_msg.edit_text(
                f"⚠️ <b>Video hajmi juda katta ({size_mb} MB).</b>", parse_mode="HTML"
            )
            safe_remove_files(temp_video, fast_path)
            return

        video_file = FSInputFile(fast_path)
        await message.answer_video(
            video=video_file,
            caption="⚡ <b>1.5x Tezlashtirilgan Video</b>",
            parse_mode="HTML",
        )
        await status_msg.delete()
        safe_remove_files(temp_video, fast_path)

    except Exception as e:
        logger.error(f"Cmd fast error: {e}")
        await status_msg.edit_text("❌ Video tezlashtirishda xatolik yuz berdi.")
        safe_remove_files(temp_video)


@router.message(Command("slow"))
async def cmd_video_slow(message: Message):
    target_msg = message.reply_to_message if message.reply_to_message else message
    if not (target_msg and target_msg.video):
        await message.answer(
            "⚠️ Videoga reply qilib <code>/slow</code> deb yozing!", parse_mode="HTML"
        )
        return

    status_msg = await message.answer("🐢 <b>Video 0.8x sekinlashtirilmoqda...</b>", parse_mode="HTML")
    temp_video = os.path.join(DOWNLOAD_DIR, f"slow_{message.message_id}.mp4")
    try:
        file_info = await message.bot.get_file(target_msg.video.file_id)
        await message.bot.download_file(file_info.file_path, temp_video)

        slow_path = await change_video_speed(temp_video, speed=0.8)
        is_valid, size_mb = check_file_size(slow_path)
        if not is_valid:
            await status_msg.edit_text(
                f"⚠️ <b>Video hajmi juda katta ({size_mb} MB).</b>", parse_mode="HTML"
            )
            safe_remove_files(temp_video, slow_path)
            return

        video_file = FSInputFile(slow_path)
        await message.answer_video(
            video=video_file,
            caption="🐢 <b>0.8x Sekinlashtirilgan Video</b>",
            parse_mode="HTML",
        )
        await status_msg.delete()
        safe_remove_files(temp_video, slow_path)

    except Exception as e:
        logger.error(f"Cmd slow error: {e}")
        await status_msg.edit_text("❌ Video sekinlashtirishda xatolik yuz berdi.")
        safe_remove_files(temp_video)
