import asyncio
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from config import ADMIN_IDS
from database.db import get_stats, get_all_users, add_channel, remove_channel, get_channels, get_user_rank

router = Router()
logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(F.text == "📊 Admin Panel")
@router.message(Command("admin"))
async def cmd_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
        
    stats = get_stats()
    channels = get_channels()
    
    ch_list = "\n".join([f"• {ch['title']} ({ch['channel_id']})" for ch in channels]) if channels else "Majburiy obuna kanallari yo'q."
    
    admin_text = (
        "📊 <b>InstaOhang Admin Panel</b>\n\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {stats['total_users']} ta\n"
        f"📥 <b>Jami yuklanishlar:</b> {stats['total_downloads']} ta\n"
        f"⚡ <b>Bugungi faol foydalanuvchilar:</b> {stats['active_today']} ta\n\n"
        "📢 <b>Majburiy kanallar:</b>\n"
        f"{ch_list}\n\n"
        "⚙️ <b>Admin Buyruqlari:</b>\n"
        "• <code>/send &lt;matn&gt;</code> - Barcha foydalanuvchilarga xabar tarqatish\n"
        "• <code>/addchannel &lt;channel_id&gt; &lt;sarlavha&gt; &lt;link&gt;</code> - Kanal qo'shish\n"
        "• <code>/delchannel &lt;channel_id&gt;</code> - Kanalni o'chirish"
    )
    await message.answer(admin_text, parse_mode="HTML")

@router.message(Command("stat"))
async def cmd_stat(message: Message):
    if not is_admin(message.from_user.id):
        return
    stats = get_stats()
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
    stats = get_stats()
    total = stats['total_users']
    
    # Fun milestone emoji
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
    
    # User's own rank
    rank = get_user_rank(message.from_user.id)
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

@router.message(Command("send"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return
        
    target_msg = message.reply_to_message if message.reply_to_message else message
    if target_msg == message and not message.text.replace("/send", "").strip():
        await message.answer("⚠️ Iltimos, tarqatmoqchi bo'lgan xabarga reply qilib <code>/send</code> yuboring!", parse_mode="HTML")
        return
        
    users = get_all_users()
    await message.answer(f"🚀 Xabar <b>{len(users)}</b> ta foydalanuvchiga yuborilmoqda...", parse_mode="HTML")
    
    count_success = 0
    count_fail = 0
    
    for uid in users:
        try:
            if target_msg != message:
                await target_msg.copy_to(chat_id=uid)
            else:
                broadcast_text = message.text.replace("/send", "").strip()
                await message.bot.send_message(chat_id=uid, text=broadcast_text)
            count_success += 1
            await asyncio.sleep(0.04) # Telegram rate limits
        except Exception:
            count_fail += 1
            
    await message.answer(
        f"✅ <b>Reklama tarqatish yakunlandi!</b>\n\n"
        f"🟢 Yuborildi: {count_success} ta\n"
        f"🔴 Yetib bormadi (block): {count_fail} ta",
        parse_mode="HTML"
    )

@router.message(Command("addchannel"))
async def cmd_add_channel(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer("⚠️ Sintaksis: <code>/addchannel &lt;channel_id&gt; &lt;sarlavha&gt; &lt;link&gt;</code>\n<i>Misol: /addchannel -1001234567890 MyChannel https://t.me/MyChannel</i>", parse_mode="HTML")
        return
    try:
        ch_id = int(args[1])
        title = args[2]
        link = args[3]
        add_channel(ch_id, title, link)
        await message.answer(f"✅ Kanal muvaffaqiyatli qo'shildi: <b>{title}</b>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Kanal qo'shishda xatolik: {e}")

@router.message(Command("delchannel"))
async def cmd_del_channel(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Sintaksis: <code>/delchannel &lt;channel_id&gt;</code>", parse_mode="HTML")
        return
    try:
        ch_id = int(args[1])
        remove_channel(ch_id)
        await message.answer(f"✅ Kanal o'chirildi ({ch_id})", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
