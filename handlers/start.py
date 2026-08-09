import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from database.db import upsert_user
from config import ADMIN_IDS
from utils.helpers import (
    get_main_reply_keyboard,
    check_user_subscriptions,
    get_subscription_keyboard,
)
from utils.performance import Timer

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    user_id = user.id

    async with Timer("/start") as t:
        # Upsert user in PostgreSQL (async, race-condition safe)
        await upsert_user(
            telegram_id=user_id,
            first_name=user.first_name or "",
            last_name=user.last_name,
            username=user.username,
            language_code=user.language_code,
            is_bot=user.is_bot,
        )
        t.checkpoint("db_upsert")

        # Check mandatory channel subscriptions
        is_subbed, missing = await check_user_subscriptions(message.bot, user_id)
        t.checkpoint("sub_check")

        if not is_subbed:
            await message.answer(
                f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
                "🤖 Botdan foydalanish uchun iltimos quyidagi kanallarga obuna bo'ling:",
                reply_markup=get_subscription_keyboard(missing),
                parse_mode="HTML",
            )
            return

        is_admin = user_id in ADMIN_IDS
        welcome_text = (
            f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
            f"🎧 <b>InstaOhang Bot</b>ga xush kelibsiz!\n\n"
            f"⚡ <b>Imkoniyatlar:</b>\n"
            f"1️⃣ Instagram-dan video yoki Reels havolasini (link) yuboring — bot darhol yuklab beradi.\n"
            f"2️⃣ Yuklangan videoga javoban <code>/round</code> deb yozing yoki tugmani bosib ⭕ <b>Dumaloq Video Note</b>ga aylantiring!\n"
            f"3️⃣ Videolardan 🎵 MP3 musiqasini 1 bosishda ajratib oling.\n"
            f"4️⃣ Qo'shiq nomi yoki xonanda ismini shunchaki matn sifatida yuboring va musiqani oling.\n"
            f"5️⃣ ❤️ <b>Sevimlilar</b> tugmasi orqali o'zingizga yoqqan musiqalarni saqlang!\n\n"
            f"🔗 <i>Boshlash uchun Instagram havolasi yoki qo'shiq nomini yuboring!</i>"
        )
        await message.answer(
            welcome_text,
            reply_markup=get_main_reply_keyboard(is_admin),
            parse_mode="HTML",
        )
        t.checkpoint("send_welcome")


@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Invalidate cache to force fresh check
    from utils.helpers import SUB_CACHE
    SUB_CACHE.pop(user_id, None)

    is_subbed, missing = await check_user_subscriptions(callback.bot, user_id)

    if is_subbed:
        await callback.message.delete()
        is_admin = user_id in ADMIN_IDS
        await callback.message.answer(
            "✅ Obuna tasdiqlandi! Endi botdan to'liq foydalanishingiz mumkin.\n"
            "🔗 Instagram havolasini yuboring!",
            reply_markup=get_main_reply_keyboard(is_admin),
        )
    else:
        await callback.answer(
            "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True
        )


@router.message(F.text == "ℹ️ Bot haqida")
async def cmd_about(message: Message):
    about_text = (
        "🤖 <b>InstaOhang Bot</b>\n\n"
        "✨ Instagram-dan yuqori sifatli video, reels va musiqalarni yuklovchi hamda "
        "videolarni Telegram Dumaloq formatiga (<code>/round</code>) o'tkazuvchi professional bot.\n\n"
        "🤖 Bot: @InstaOhang_bot\n"
        "👨‍💻 CREATED BY: @htpAsilbek"
    )
    await message.answer(about_text, parse_mode="HTML")


@router.message(F.text == "⭕ Dumaloq Video haqida")
async def cmd_round_info(message: Message):
    info_text = (
        "⭕ <b>Dumaloq Video (/round) qanday ishlaydi?</b>\n\n"
        "1. Bot sizga yuborgan videoga (yoki o'zingiz botga yuborgan videoga) <b>Reply (Otvetit)</b> qiling.\n"
        "2. Javob matniga <code>/round</code> deb yozing.\n"
        "3. Bot videoni avtomatik 1:1 formatda kesib, dumaloq video note shaklida yuboradi!\n\n"
        "💡 Shuningdek yuklangan video ostidagi ⭕ <b>Dumaloq Video</b> tugmasini bosishingiz ham mumkin!"
    )
    await message.answer(info_text, parse_mode="HTML")
