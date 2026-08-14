"""
Favorites handler for @InstaOhang_bot.
Allows users to save/remove music tracks and browse their favorites with pagination.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from database.db import (
    get_user_favorites,
    add_favorite,
    remove_favorite,
    is_favorite,
    get_music_by_file_unique_id,
)
from database.postgres import get_pool
from utils.helpers import clean_html, check_user_subscriptions, get_subscription_keyboard

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE = 8  # Favorites per page


def build_favorites_keyboard(
    items: list[dict],
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    """Builds an inline keyboard for the favorites list with pagination."""
    buttons = []

    for item in items:
        title = item["title"][:35] + "..." if len(item["title"]) > 35 else item["title"]
        artist = item["artist"] or "Unknown"
        buttons.append([
            InlineKeyboardButton(
                text=f"🎵 {title} — {artist}",
                callback_data=f"fav_play:{item['id']}",
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=f"fav_remove:{item['id']}:{page}",
            ),
        ])

    # Pagination row
    nav_buttons = []
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"fav_page:{page - 1}")
        )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"fav_page:{page + 1}")
        )

    if nav_buttons:
        buttons.append(nav_buttons)

    if total_pages > 1:
        buttons.append([
            InlineKeyboardButton(
                text=f"📄 {page + 1}/{total_pages}",
                callback_data="noop",
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_favorites_page(message: Message, user_id: int, page: int = 0):
    """Fetches and sends a paginated favorites list to the user."""
    items, total = await get_user_favorites(user_id, page=page, page_size=PAGE_SIZE)

    if total == 0:
        await message.answer(
            "❤️ <b>Sevimlilar ro'yxatingiz bo'sh.</b>\n\n"
            "Musiqani sevimliga qo'shish uchun musiqa qidiring va "
            "<b>❤️ Sevimliga qo'shish</b> tugmasini bosing!",
            parse_mode="HTML",
        )
        return

    text_lines = [f"❤️ <b>Sevimli musiqalaringiz</b> (jami: {total}):\n"]
    for idx, item in enumerate(items, start=page * PAGE_SIZE + 1):
        title = clean_html(item["title"])
        artist = clean_html(item["artist"] or "Unknown")
        views = item["views"]
        text_lines.append(f"<b>{idx}.</b> 🎵 {title} — <i>{artist}</i>  👁 {views}")

    text_lines.append("\n💡 <i>O'chirish uchun 🗑 tugmasini bosing.</i>")

    await message.answer(
        "\n".join(text_lines),
        reply_markup=build_favorites_keyboard(items, page, total),
        parse_mode="HTML",
    )


@router.message(F.text == "❤️ Sevimlilar")
@router.message(Command("favorites"))
async def cmd_favorites(message: Message):
    user_id = message.from_user.id

    is_subbed, missing = await check_user_subscriptions(message.bot, user_id)
    if not is_subbed:
        await message.answer(
            "🔒 <b>Botdan foydalanish uchun kanallarga obuna bo'ling:</b>",
            reply_markup=get_subscription_keyboard(missing),
            parse_mode="HTML",
        )
        return

    await send_favorites_page(message, user_id, page=0)


@router.callback_query(F.data.startswith("fav_page:"))
async def cb_favorites_page(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    items, total = await get_user_favorites(user_id, page=page, page_size=PAGE_SIZE)

    if total == 0:
        await callback.answer("Sevimlilar bo'sh!", show_alert=True)
        return

    text_lines = [f"❤️ <b>Sevimli musiqalaringiz</b> (jami: {total}):\n"]
    for idx, item in enumerate(items, start=page * PAGE_SIZE + 1):
        title = clean_html(item["title"])
        artist = clean_html(item["artist"] or "Unknown")
        views = item["views"]
        text_lines.append(f"<b>{idx}.</b> 🎵 {title} — <i>{artist}</i>  👁 {views}")

    text_lines.append("\n💡 <i>O'chirish uchun 🗑 tugmasini bosing.</i>")

    await callback.answer()
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=build_favorites_keyboard(items, page, total),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("fav_remove:"))
async def cb_favorite_remove(callback: CallbackQuery):
    parts = callback.data.split(":")
    music_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0
    user_id = callback.from_user.id

    removed = await remove_favorite(user_id, music_id)
    if removed:
        await callback.answer("🗑 Sevimlilardan o'chirildi!", show_alert=False)
    else:
        await callback.answer("Allaqachon o'chirilgan.", show_alert=True)

    # Refresh the current page
    items, total = await get_user_favorites(user_id, page=page, page_size=PAGE_SIZE)
    if total == 0:
        await callback.message.edit_text(
            "❤️ <b>Sevimlilar ro'yxatingiz bo'sh.</b>",
            parse_mode="HTML",
        )
        return

    # Adjust page if current page is now empty
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    if page >= total_pages:
        page = max(0, total_pages - 1)
        items, total = await get_user_favorites(user_id, page=page, page_size=PAGE_SIZE)

    text_lines = [f"❤️ <b>Sevimli musiqalaringiz</b> (jami: {total}):\n"]
    for idx, item in enumerate(items, start=page * PAGE_SIZE + 1):
        title = clean_html(item["title"])
        artist = clean_html(item["artist"] or "Unknown")
        views = item["views"]
        text_lines.append(f"<b>{idx}.</b> 🎵 {title} — <i>{artist}</i>  👁 {views}")

    text_lines.append("\n💡 <i>O'chirish uchun 🗑 tugmasini bosing.</i>")
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=build_favorites_keyboard(items, page, total),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("fav_play:"))
async def cb_favorite_play(callback: CallbackQuery):
    """Handler for playing a music from favorites list using cached file_id from DB."""
    music_id = int(callback.data.split(":")[1])
    await callback.answer("🎵 Yuklanmoqda...")

    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT title, artist, file_id FROM music WHERE id = $1 AND is_active = TRUE",
                music_id,
            )
        if not row:
            await callback.answer("❌ Musiqa topilmadi!", show_alert=True)
            return

        await callback.message.answer_audio(
            audio=row["file_id"],
            title=clean_html(row["title"]),
            performer=clean_html(row["artist"] or "Unknown"),
            caption="🎧 <b>InstaOhang Music</b> — Sevimlilaringizdan\n🤖 @InstaOhang_bot",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"fav_play error (music_id={music_id}): {e}")
        await callback.answer("❌ Yuklashda xatolik yuz berdi!", show_alert=True)


@router.callback_query(F.data.startswith("fav_add:"))
async def cb_favorite_add(callback: CallbackQuery):
    """Handler for adding a music to favorites (called from music search results)."""
    music_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    added = await add_favorite(user_id, music_id)
    if added:
        await callback.answer("❤️ Sevimlilar ro'yxatiga qo'shildi!", show_alert=False)
    else:
        await callback.answer("Allaqachon sevimlilar ro'yxatida!", show_alert=True)


@router.callback_query(F.data.startswith("fav_toggle:"))
async def cb_favorite_toggle(callback: CallbackQuery):
    """Toggles favorite status (add/remove) for a music track."""
    music_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    already = await is_favorite(user_id, music_id)
    if already:
        await remove_favorite(user_id, music_id)
        await callback.answer("💔 Sevimlilardan o'chirildi.", show_alert=False)
    else:
        await add_favorite(user_id, music_id)
        await callback.answer("❤️ Sevimlilar ro'yxatiga qo'shildi!", show_alert=False)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    """No-operation callback for informational buttons (e.g., page indicator)."""
    await callback.answer()
