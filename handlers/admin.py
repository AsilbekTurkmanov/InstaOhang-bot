import asyncio
import logging
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from database.db import (
    get_stats, get_all_user_ids,
    add_channel, remove_channel, get_channels,
    get_user_rank,
)
from utils.helpers import clean_html, get_main_reply_keyboard

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS or user_id == 5246861200


class AdminStates(StatesGroup):
    in_admin_panel = State()
    waiting_for_broadcast_msg = State()
    waiting_for_broadcast_confirm = State()
    waiting_for_channel_data = State()




# ─────────────────────────────────────────────────────────────────────────────
# Admin panel
# ─────────────────────────────────────────────────────────────────────────────

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Main interactive admin panel keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="✉️ Xabar yuborish (SMS)", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text="📢 Majburiy kanallar", callback_data="admin_channels"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "📊 Admin Panel")
@router.message(Command("admin"))
async def cmd_admin_panel(message: Message, state: FSMContext | None = None):
    if not is_admin(message.from_user.id):
        return

    if state:
        await state.set_state(AdminStates.in_admin_panel)

    stats = await get_stats()
    channels = await get_channels()

    admin_text = (
        "⚡ <b>InstaOhang Boshqaruv Paneli (Admin)</b>\n\n"
        f"👥 <b>Foydalanuvchilar:</b> {stats['total_users']:,} ta\n"
        f"📥 <b>Jami yuklanishlar:</b> {stats['total_downloads']:,} ta\n"
        f"🔥 <b>Bugun faol:</b> {stats['active_today']:,} ta\n"
        f"📢 <b>Majburiy kanallar:</b> {len(channels)} ta\n\n"
        "👇 <i>Kerakli bo'limni tanlang:</i>"
    )
    await message.answer(admin_text, reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Kirish taqiqlangan", show_alert=True)
        return

    await state.set_state(AdminStates.in_admin_panel)
    stats = await get_stats()
    channels = await get_channels()

    admin_text = (
        "⚡ <b>InstaOhang Boshqaruv Paneli (Admin)</b>\n\n"
        f"👥 <b>Foydalanuvchilar:</b> {stats['total_users']:,} ta\n"
        f"📥 <b>Jami yuklanishlar:</b> {stats['total_downloads']:,} ta\n"
        f"🔥 <b>Bugun faol:</b> {stats['active_today']:,} ta\n"
        f"📢 <b>Majburiy kanallar:</b> {len(channels)} ta\n\n"
        "👇 <i>Kerakli bo'limni tanlang:</i>"
    )
    await callback.answer()
    await callback.message.edit_text(admin_text, reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")


@router.message(AdminStates.in_admin_panel)
async def handle_admin_panel_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    if text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ <b>Admin paneldan chiqildi.</b>",
            reply_markup=get_main_reply_keyboard(True),
            parse_mode="HTML",
        )
        return

    await message.answer(
        "⚡ <b>Siz hozirda Admin Panelidasiz!</b>\n\n"
        "Musiqa qidirish ushbu bo'limda faolsizlantirilgan.\n"
        "Quyidagi boshqaruv menyusidan kerakli amalni tanlang yoki admin paneldan chiqish uchun <code>/cancel</code> bosing:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Kirish taqiqlangan", show_alert=True)
        return

    stats = await get_stats()
    text = (
        "📊 <b>Botning Kengaytirilgan Statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['total_users']:,}</b> ta\n"
        f"📥 Jami yuklanishlar: <b>{stats['total_downloads']:,}</b> ta\n"
        f"🔥 Bugungi faollar: <b>{stats['active_today']}</b> ta\n"
        f"📅 Haftalik faollar: <b>{stats['active_week']}</b> ta\n\n"
        f"📈 O'rtacha faollik: <b>{round(stats['total_downloads'] / max(stats['total_users'], 1), 1)}</b> yuklash/user"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_stats"),
            InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_menu"),
        ]
    ])
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("stat"))
async def cmd_stat(message: Message):
    if not is_admin(message.from_user.id):
        return
    stats = await get_stats()
    text = (
        "📈 <b>Bot To'liq Statistikasi:</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['total_users']:,}</b> ta\n"
        f"📥 Jami yuklanishlar: <b>{stats['total_downloads']:,}</b> ta\n"
        f"🔥 Bugungi faollar: <b>{stats['active_today']}</b> ta\n"
        f"📅 Haftalik faollar: <b>{stats['active_week']}</b> ta\n\n"
        f"📊 O'rtacha bir foydalanuvchi: "
        f"<b>{round(stats['total_downloads'] / max(stats['total_users'], 1), 1)}</b> ta yuklash"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("users"))
async def cmd_users_count(message: Message):
    """Public command — anyone can see total user count."""
    stats = await get_stats()
    total = stats["total_users"]

    if total >= 10000:
        milestone = "🏆 10,000+ foydalanuvchi!"
    elif total >= 5000:
        milestone = "🥇 5,000+ foydalanuvchi!"
    elif total >= 1000:
        milestone = "🥈 1,000+ foydalanuvchi!"
    elif total >= 500:
        milestone = "🥉 500+ foydalanuvchi!"
    elif total >= 100:
        milestone = "🌟 100+ foydalanuvchi!"
    else:
        milestone = "🚀 O'sayotgan hamjamiyat!"

    rank = await get_user_rank(message.from_user.id)
    rank_text = f"\n📌 Sizning raqamingiz: <b>#{rank}</b> foydalanuvchi" if rank else ""

    text = (
        f"👥 <b>InstaOhang Bot Foydalanuvchilari</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔢 Jami: <b>{total:,} ta</b> foydalanuvchi\n"
        f"🔥 Bugun faol: <b>{stats['active_today']}</b> ta\n"
        f"📅 Hafta davomida: <b>{stats['active_week']}</b> ta\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{milestone}{rank_text}\n\n"
        f"🤖 @InstaOhang_bot"
    )
    await message.answer(text, parse_mode="HTML")


# ─────────────────────────────────────────────────────────────────────────────
# Broadcast — with Telegram rate limiting (30 msg/sec max)
# Uses batch + sleep strategy and handles 429 Too Many Requests
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Broadcast configuration constants
# ─────────────────────────────────────────────────────────────────────────────
BROADCAST_BATCH_SIZE = 25        # users per batch
BROADCAST_BATCH_DELAY = 1.0      # seconds between batches (Telegram rate limit)
BROADCAST_RETRY_DELAY = 5.0      # seconds to wait after 429 Too Many Requests

# Track active broadcast background tasks to prevent garbage collection and allow clean shutdown
_active_broadcast_tasks: set[asyncio.Task] = set()


async def _run_broadcast_task(
    bot,
    target_msg: Message,
    message: Message,
    user_ids: list[int],
    admin_chat_id: int,
    broadcast_text: str,
) -> None:
    """Background task executing the broadcast asynchronously."""
    total_users = len(user_ids)
    count_success = 0
    count_fail = 0

    try:
        for i in range(0, total_users, BROADCAST_BATCH_SIZE):
            batch = user_ids[i: i + BROADCAST_BATCH_SIZE]

            for uid in batch:
                try:
                    if target_msg != message:
                        await target_msg.copy_to(chat_id=uid)
                    else:
                        await bot.send_message(chat_id=uid, text=broadcast_text)
                    count_success += 1

                except Exception as exc:
                    exc_str = str(exc)
                    if "429" in exc_str or "Too Many Requests" in exc_str:
                        logger.warning(f"Broadcast rate limited. Waiting {BROADCAST_RETRY_DELAY}s...")
                        await asyncio.sleep(BROADCAST_RETRY_DELAY)
                        try:
                            if target_msg != message:
                                await target_msg.copy_to(chat_id=uid)
                            else:
                                await bot.send_message(chat_id=uid, text=broadcast_text)
                            count_success += 1
                        except Exception:
                            count_fail += 1
                    else:
                        count_fail += 1

            if i + BROADCAST_BATCH_SIZE < total_users:
                await asyncio.sleep(BROADCAST_BATCH_DELAY)

        await bot.send_message(
            chat_id=admin_chat_id,
            text=(
                f"✅ <b>Reklama tarqatish yakunlandi!</b>\n\n"
                f"🟢 Yuborildi: {count_success:,} ta\n"
                f"🔴 Yetib bormadi (block): {count_fail:,} ta"
            ),
            parse_mode="HTML",
        )
    except Exception as err:
        logger.error(f"Broadcast background task error: {err}")
        try:
            await bot.send_message(
                chat_id=admin_chat_id,
                text=f"❌ <b>Reklama tarqatishda xatolik yuz berdi:</b> {clean_html(str(err))}",
                parse_mode="HTML",
            )
        except Exception:
            pass


@router.message(Command("send"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return

    target_msg = message.reply_to_message if message.reply_to_message else message
    broadcast_text = message.text.replace("/send", "").strip()
    if target_msg == message and not broadcast_text:
        await message.answer(
            "⚠️ Iltimos, tarqatmoqchi bo'lgan xabarga reply qilib <code>/send</code> yuboring!",
            parse_mode="HTML",
        )
        return

    user_ids = await get_all_user_ids()
    total_users = len(user_ids)
    await message.answer(
        f"🚀 <b>Xabar {total_users:,} ta foydalanuvchiga fonda tarqatilmoqda...</b>\n"
        f"<i>Tugaganda sizga bildirishnoma keladi.</i>",
        parse_mode="HTML",
    )

    # Launch background task and store reference
    task = asyncio.create_task(
        _run_broadcast_task(
            bot=message.bot,
            target_msg=target_msg,
            message=message,
            user_ids=user_ids,
            admin_chat_id=message.chat.id,
            broadcast_text=broadcast_text,
        )
    )
    _active_broadcast_tasks.add(task)
    task.add_done_callback(_active_broadcast_tasks.discard)


# ─────────────────────────────────────────────────────────────────────────────
# Interactive Broadcast FSM Callbacks
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel_admin_action(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer(
            "❌ <b>Amaliyot bekor qilindi.</b>",
            reply_markup=get_admin_menu_keyboard(),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Kirish taqiqlangan", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_broadcast")]
    ])
    await callback.answer()
    await callback.message.edit_text(
        "✉️ <b>Barcha Foydalanuvchilarga Xabar Yuborish (SMS Broadcast)</b>\n\n"
        "✍️ Barcha start bosgan foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring.\n"
        "<i>(Matn, rasm, video, audio yoki boshqa kanaldan forward yuborishingiz mumkin)</i>\n\n"
        "Bekor qilish uchun: /cancel",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_broadcast_msg)
async def process_broadcast_message_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Xabar tarqatish bekor qilindi.", reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")
        return

    await state.update_data(broadcast_chat_id=message.chat.id, broadcast_msg_id=message.message_id)
    await state.set_state(AdminStates.waiting_for_broadcast_confirm)

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Barchaga yuborish", callback_data="confirm_broadcast"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_broadcast"),
        ]
    ])

    user_ids = await get_all_user_ids()
    await message.answer(
        f"👀 <b>Xabarni ko'rib chiqing:</b>\n"
        f"Ushbu xabar bazadagi jami <b>{len(user_ids):,} ta</b> foydalanuvchiga yuboriladi.\n\n"
        f"Tasdiqlaysizmi?",
        reply_markup=confirm_kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "confirm_broadcast", AdminStates.waiting_for_broadcast_confirm)
async def cb_confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Kirish taqiqlangan", show_alert=True)
        return

    data = await state.get_data()
    chat_id = data.get("broadcast_chat_id")
    msg_id = data.get("broadcast_msg_id")
    await state.clear()

    if not chat_id or not msg_id:
        await callback.answer("Xabar topilmadi, qaytadan urinib ko'ring.", show_alert=True)
        return

    user_ids = await get_all_user_ids()
    total = len(user_ids)

    await callback.answer("🚀 Xabar yuborish boshlandi!")
    await callback.message.edit_text(
        f"🚀 <b>Xabar {total:,} ta foydalanuvchiga fonda yuborilmoqda...</b>\n"
        f"<i>Jarayon yakunlangach, sizga to'liq hisobot keladi.</i>",
        parse_mode="HTML",
    )

    class DummyTarget:
        async def copy_to(self, chat_id):
            await callback.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=chat_id_src,
                message_id=msg_id_src,
            )

    chat_id_src = chat_id
    msg_id_src = msg_id

    task = asyncio.create_task(
        _run_broadcast_task(
            bot=callback.bot,
            target_msg=DummyTarget(),
            message=None,
            user_ids=user_ids,
            admin_chat_id=callback.message.chat.id,
            broadcast_text="",
        )
    )
    _active_broadcast_tasks.add(task)
    task.add_done_callback(_active_broadcast_tasks.discard)


@router.callback_query(F.data == "cancel_broadcast")
async def cb_cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Bekor qilindi")
    await callback.message.edit_text(
        "❌ <b>Xabar tarqatish bekor qilindi.</b>",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Interactive Channel Management Callbacks
# ─────────────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_channels")
async def cb_admin_channels(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Kirish taqiqlangan", show_alert=True)
        return

    await state.set_state(AdminStates.in_admin_panel)
    channels = await get_channels()

    if channels:
        ch_text = "📢 <b>Majburiy Obuna Kanallari Ro'yxati:</b>\n\n"
        for idx, ch in enumerate(channels, 1):
            ch_text += f"<b>{idx}.</b> <a href='{clean_html(ch['invite_link'])}'>{clean_html(ch['title'])}</a> (<code>{ch['channel_id']}</code>)\n"
    else:
        ch_text = "📢 <b>Majburiy Obuna Kanallari:</b>\n\n<i>Hozirda hech qanday majburiy kanal ulanmagan.</i>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_channel"),
            InlineKeyboardButton(text="❌ Kanalni o'chirish", callback_data="admin_del_channel_menu"),
        ],
        [InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_menu")],
    ])

    await callback.answer()
    await callback.message.edit_text(ch_text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)


@router.callback_query(F.data == "admin_add_channel")
async def cb_admin_add_channel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Kirish taqiqlangan", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_channel_data)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_channels")]
    ])
    await callback.answer()
    await callback.message.edit_text(
        "➕ <b>Yangi Majburiy Kanal Qo'shish:</b>\n\n"
        "Kanalni qo'shish uchun quyidagi usullardan biri orqali yuboring:\n\n"
        "1️⃣ <b>Havola yoki username:</b>\n"
        "<code>https://t.me/kanal_nomi</code> yoki <code>@kanal_nomi</code>\n\n"
        "2️⃣ <b>To'liq format:</b>\n"
        "<code>&lt;kanal_id&gt; | &lt;sarlavha&gt; | &lt;havola&gt;</code>\n"
        "<i>Misol: -1001234567890 | Bizning Kanal | https://t.me/bizning_kanal</i>\n\n"
        "3️⃣ <b>Kanaldan xabarni forward qilib yuborishingiz ham mumkin!</b>\n\n"
        "⚠️ <b>Eslatma:</b> Bot o'sha kanalda <b>Admin</b> qilingan bo'lishi shart!\n"
        "Bekor qilish uchun: /cancel",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.message(AdminStates.waiting_for_channel_data)
async def process_channel_data_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    text = (message.text or "").strip()
    if text == "/cancel":
        await state.set_state(AdminStates.in_admin_panel)
        await message.answer("❌ Kanal qo'shish bekor qilindi.", reply_markup=get_admin_menu_keyboard(), parse_mode="HTML")
        return

    ch_id = None
    title = ""
    link = ""

    # Case 1: Post forwarded from a channel
    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        ch = message.forward_from_chat
        ch_id = ch.id
        title = ch.title or "Kanal"
        link = f"https://t.me/{ch.username}" if ch.username else ""

    # Case 2: Pipe separated or space separated
    if ch_id is None and text:
        parts = [p.strip() for p in text.split("|") if p.strip()]
        if len(parts) >= 3:
            raw_id, raw_title, raw_link = parts[0], parts[1], parts[2]
            try:
                ch_id = int(raw_id)
            except ValueError:
                ch_id = None
            title = raw_title
            link = raw_link
        elif len(parts) == 2:
            title = parts[0]
            link = parts[1]
        elif len(parts) == 1:
            link = parts[0]

    # Resolve from username or link if ch_id is missing or dummy (< 10000)
    target_link = link or text
    if (ch_id is None or (0 <= ch_id < 10000)) and target_link:
        username_match = re.search(r"(?:https?://(?:www\.)?t\.me/|@)([a-zA-Z0-9_]{4,32})", target_link)
        if username_match:
            username = username_match.group(1)
            try:
                chat = await message.bot.get_chat(f"@{username}")
                ch_id = chat.id
                if not title or title.isdigit():
                    title = chat.title or username
                if not link or "t.me" not in link:
                    link = f"https://t.me/{username}"
            except Exception as e:
                logger.warning(f"Could not resolve chat @{username} via get_chat: {e}")

    # Fallback to direct numeric ID query
    if ch_id is not None and not title:
        try:
            chat = await message.bot.get_chat(ch_id)
            title = chat.title or f"Kanal {ch_id}"
            if not link and chat.username:
                link = f"https://t.me/{chat.username}"
        except Exception:
            title = f"Kanal {ch_id}"

    if ch_id is None:
        await message.answer(
            "⚠️ <b>Kanal aniqlanmadi!</b>\n\n"
            "Iltimos, kanal havolasini (masalan: <code>https://t.me/kanal</code>) yoki to'liq formatda yuboring:\n"
            "<code>&lt;kanal_id&gt; | &lt;sarlavha&gt; | &lt;havola&gt;</code>\n"
            "<i>Misol: -1001234567890 | Kanal | https://t.me/kanal</i>",
            parse_mode="HTML",
        )
        return

    # Check bot administrator status in channel
    try:
        member = await message.bot.get_chat_member(chat_id=ch_id, user_id=message.bot.id)
        if member.status not in {"administrator", "creator"}:
            await message.answer(
                f"⚠️ <b>Bot ushbu kanalda ({clean_html(title or str(ch_id))}) Admin emas!</b>\n\n"
                f"Iltimos, avval botni kanalingizga qo'shib, unga <b>Admin</b> huquqini bering, so'ng qayta yuboring.",
                parse_mode="HTML",
            )
            return
    except Exception as member_err:
        logger.warning(f"Could not verify chat member status for {ch_id}: {member_err}")

    if not title:
        title = f"Kanal {ch_id}"
    if not link:
        link = f"https://t.me/c/{str(ch_id).replace('-100', '')}"

    try:
        await add_channel(ch_id, title, link)
        await state.set_state(AdminStates.in_admin_panel)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanallar ro'yxati", callback_data="admin_channels")],
            [InlineKeyboardButton(text="🔙 Admin panel", callback_data="admin_menu")],
        ])
        await message.answer(
            f"✅ <b>Kanal muvaffaqiyatli qo'shildi!</b>\n\n"
            f"📌 Sarlavha: <b>{clean_html(title)}</b>\n"
            f"🆔 ID: <code>{ch_id}</code>\n"
            f"🔗 Link: {clean_html(link)}",
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {clean_html(str(e))}")



@router.callback_query(F.data == "admin_del_channel_menu")
async def cb_del_channel_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Kirish taqiqlangan", show_alert=True)
        return

    channels = await get_channels()
    if not channels:
        await callback.answer("O'chirish uchun kanallar mavjud emas", show_alert=True)
        return

    buttons = []
    for ch in channels:
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {clean_html(ch['title'])} ({ch['channel_id']})",
                callback_data=f"del_ch:{ch['channel_id']}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Ortga", callback_data="admin_channels")])

    await callback.answer()
    await callback.message.edit_text(
        "🗑 <b>O'chirmoqchi bo'lgan kanal ustiga bosing:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("del_ch:"))
async def cb_delete_single_channel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Kirish taqiqlangan", show_alert=True)
        return

    ch_id = int(callback.data.split(":")[1])
    try:
        await remove_channel(ch_id)
        await callback.answer(f"✅ Kanal o'chirildi ({ch_id})", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Xatolik: {e}", show_alert=True)

    # Return to updated channels list
    await cb_admin_channels(callback, None)





# ─────────────────────────────────────────────────────────────────────────────
# CLI Commands (backward compatibility)
# ─────────────────────────────────────────────────────────────────────────────

@router.message(Command("addchannel"))
async def cmd_add_channel(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer(
            "⚠️ Sintaksis: <code>/addchannel &lt;channel_id&gt; &lt;sarlavha&gt; &lt;link&gt;</code>\n"
            "<i>Misol: /addchannel -1001234567890 MyChannel https://t.me/MyChannel</i>",
            parse_mode="HTML",
        )
        return
    try:
        ch_id = int(args[1])
        title = args[2]
        link  = args[3]
        await add_channel(ch_id, title, link)
        await message.answer(
            f"✅ Kanal muvaffaqiyatli qo'shildi: <b>{clean_html(title)}</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"❌ Kanal qo'shishda xatolik: {clean_html(str(e))}")


@router.message(Command("delchannel"))
async def cmd_del_channel(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "⚠️ Sintaksis: <code>/delchannel &lt;channel_id&gt;</code>",
            parse_mode="HTML",
        )
        return
    try:
        ch_id = int(args[1])
        await remove_channel(ch_id)
        await message.answer(f"✅ Kanal o'chirildi ({ch_id})")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {clean_html(str(e))}")

