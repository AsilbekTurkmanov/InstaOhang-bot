import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from utils.helpers import clean_html
from services.ai_service import process_ai_request, clear_conversation

router = Router()
logger = logging.getLogger(__name__)

AGENT_NAME = "InstaOhang AI Agent 🤖⚡"
AGENT_VERSION = "v3.0 Production Sub-Agent"


@router.message(Command("agent"))
@router.message(Command("ai"))
@router.message(F.text == "🤖 AI Agent")
async def cmd_agent_status(message: Message):
    """Triggers AI Agent prompt response."""
    status_msg = await message.answer("🧠 <b>Sun'iy Intellekt AI Agent javob tayyorlamoqda... ⏳</b>", parse_mode="HTML")
    
    prompt = (
        "O'zbek tilida InstaOhang boti foydalanuvchilariga xushmuomala salom ber, "
        "o'zingni AI Agent deb tanishtir va bot imkoniyatlarini (Instagram video yuklash, "
        "MP3 audio ajratib olish, musiqa izlash va videolarni /round bilan dumaloq formatga o'tkazish) "
        "juda chiroyli, qisqa va qiziqarli ko'rinishda tushuntirib ber."
    )
    
    ai_reply = await process_ai_request(message.from_user.id, prompt)
    
    response_text = (
        f"🤖 <b>{AGENT_NAME}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{clean_html(ai_reply)}\n\n"
        f"💡 <i>AI suhbat xotirasini tozalash uchun <code>/clear_ai</code> buyrug'ini yuboring.</i>\n"
        f"👨‍💻 <i>CREATED BY: @htpAsilbek</i>"
    )
    await status_msg.edit_text(response_text, parse_mode="HTML")


@router.message(Command("clear_ai"))
async def cmd_clear_ai_memory(message: Message):
    """Clears user's AI conversation memory in PostgreSQL."""
    success = await clear_conversation(message.from_user.id)
    if success:
        await message.answer("🧹 <b>AI suhbat xotirasi muvaffaqiyatli tozalandi!</b>", parse_mode="HTML")
    else:
        await message.answer("⚠️ AI suhbat xotirasini tozalashda xatolik yuz berdi.", parse_mode="HTML")


@router.message(Command("agent_info"))
@router.message(F.text == "⚙️ AI Agent-Info")
async def cmd_agent_info(message: Message):
    """Technical info about AI agent system."""
    info_text = (
        "⚙️ <b>AI Sub-Agent System Architecture:</b>\n\n"
        "• <b>Status:</b> 🟢 ONLINE & ACTIVE\n"
        "• <b>AI Model Engine:</b> GPT-4o-Mini / Provider Engine\n"
        "• <b>Memory Storage:</b> PostgreSQL DB (User-Isolated)\n"
        "• <b>Language:</b> Uzbek / Multi-language support\n"
        "• <b>Commands:</b> <code>/agent</code>, <code>/ask</code>, <code>/clear_ai</code>\n"
        "• <b>Developer:</b> @htpAsilbek"
    )
    await message.answer(info_text, parse_mode="HTML")


@router.message(Command("ask"))
async def cmd_ask_agent(message: Message):
    """Optional /ask handler for direct queries."""
    question = message.text.replace("/ask", "").strip()
    if not question:
        question = "Instagramdan video va musiqa qanday yuklanadi?"
        
    status_msg = await message.answer("🧠 <b>Sun'iy Intellekt javob o'ylamoqda... ⏳</b>", parse_mode="HTML")
    ai_reply = await process_ai_request(message.from_user.id, question)
    
    response_text = (
        f"🤖 <b>AI Agent Javobi:</b>\n\n"
        f"{clean_html(ai_reply)}\n\n"
        f"👨‍💻 <i>CREATED BY: @htpAsilbek</i>"
    )
    await status_msg.edit_text(response_text, parse_mode="HTML")
