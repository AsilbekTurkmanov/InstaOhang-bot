import asyncio
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_IDS
from database.db import (
    get_stats, get_all_user_ids,
    add_channel, remove_channel, get_channels,
    get_user_rank, get_portfolio_messages,
)
from utils.helpers import clean_html

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio messages
# ─────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "📩 Portfolio xabarlari")
@router.message(Command("portfolio"))
async def cmd_portfolio_messages(message: Message):
    if not is_admin(message.from_user.id):
        return

    messages_list = []

    # Try fetching from C# Portfolio API backend first
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://localhost:5056/api/contact",
                timeout=aiohttp.ClientTimeout(total=3),
            ) as resp:
                if resp.status == 200:
                    messages_list = await resp.json()
    except Exception as e:
        logger.warning(f"Could not fetch portfolio messages from API: {e}")

    # Fallback to PostgreSQL
    if not messages_list:
        messages_list = await get_portfolio_messages(limit=100)

    if not messages_list:
        await message.answer(
            "📭 <b>Portfolio veb-saytidan hali hech qanday xabar kelgani yo'q.</b>",
            parse_mode="HTML",
        )
        return

    intro_header = (
        f"📩 <b>Portfolio Veb-saytidan Kelgan Barcha Xabarlar "
        f"(Jami: {len(messages_list)} ta):</b>"
    )
    await message.answer(intro_header, parse_mode="HTML")

    for idx, msg in enumerate(messages_list, 1):
        msg_id   = msg.get("id") or msg.get("Id") or idx
        name     = msg.get("name")    or msg.get("Name")    or "Noma'lum"
        email    = msg.get("email")   or msg.get("Email")   or "-"
        subject  = msg.get("subject") or msg.get("Subject") or "Mavzuga ega emas"
        content  = msg.get("message") or msg.get("Message") or "-"
        sent_at  = msg.get("sentAt")  or msg.get("created_at") or "-"

        card_text = (
            f"🆔 <b>ID: #{msg_id}</b>\n"
            f"👤 <b>Ism:</b> {clean_html(name)}\n"
            f"📧 <b>Email:</b> {clean_html(email)}\n"
            f"📌 <b>Mavzu:</b> {clean_html(subject)}\n"
            f"💬 <b>Xabar:</b>\n{clean_html(content)}\n\n"
            f"⏰ <b>Vaqt:</b> {clean_html(str(sent_at))}\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        await message.answer(card_text, parse_mode="HTML")
        await asyncio.sleep(0.05)


# ─────────────────────────────────────────────────────────────────────────────
# Admin panel
# ─────────────────────────────────────────────────────────────────────────────

@router.message(F.text == "📊 Admin Panel")
@router.message(Command("admin"))
async def cmd_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    stats = await get_stats()
    channels = await get_channels()

    ch_list = (
        "\n".join([f"• {ch['title']} ({ch['channel_id']})" for ch in channels])
        if channels
        else "Majburiy obuna kanallari yo'q."
    )

    admin_text = (
        "📊 <b>InstaOhang Admin Panel</b>\n\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {stats['total_users']} ta\n"
        f"📥 <b>Jami yuklanishlar:</b> {stats['total_downloads']} ta\n"
        f"⚡ <b>Bugungi faol foydalanuvchilar:</b> {stats['active_today']} ta\n"
        f"📅 <b>Haftalik faollar:</b> {stats['active_week']} ta\n\n"
        "📢 <b>Majburiy kanallar:</b>\n"
        f"{ch_list}\n\n"
        "⚙️ <b>Admin Buyruqlari:</b>\n"
        "• <code>/portfolio</code> — Portfolio-dan kelgan barcha xabarlar\n"
        "• <code>/send &lt;matn&gt;</code> — Barcha foydalanuvchilarga xabar\n"
        "• <code>/stat</code> — To'liq statistika\n"
        "• <code>/addchannel &lt;id&gt; &lt;sarlavha&gt; &lt;link&gt;</code> — Kanal qo'shish\n"
        "• <code>/delchannel &lt;id&gt;</code> — Kanalni o'chirish"
    )
    await message.answer(admin_text, parse_mode="HTML")


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
# Channel management
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
