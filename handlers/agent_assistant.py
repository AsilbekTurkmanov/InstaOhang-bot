import logging
import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from utils.helpers import clean_html

router = Router()
logger = logging.getLogger(__name__)

# AI Agent Knowledge Base & Engine
AGENT_NAME = "InstaOhang AI Agent 🤖⚡"
AGENT_VERSION = "v2.0 GPT-AI Sub-Agent"

def fetch_ai_reply_sync(prompt: str) -> str:
    """Executes AI completion via g4f engine synchronously."""
    try:
        from g4f.client import Client
        client = Client()
        system_prompt = (
            "Siz InstaOhang Telegram botining rasmiy Sun'iy Intellekt AI Agent yordamchisiz. "
            "Foydalanuvchilarning barcha savollariga o'zbek tilida juda xushmuomala, aniq, qisqa va chiroyli javob bering. "
            "Bot imkoniyatlari: Instagram Reels/Post yuklash, MP3 audio ajratish, musiqa qidirish, /round bilan dumaloq video yaratish, /fast va /slow bilan tezlashtirish. "
            "Dasturchi va muallif: @htpAsilbek."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        if response and response.choices and response.choices[0].message.content:
            return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"G4F AI completion error: {e}")
    return ""

async def get_ai_response(prompt: str) -> str:
    """Async wrapper for AI completion with fallback knowledge base."""
    try:
        reply = await asyncio.to_thread(fetch_ai_reply_sync, prompt)
        if reply:
            return reply
    except Exception as e:
        logger.error(f"AI response task error: {e}")

    # Fallback Smart Response if offline
    return (
        "🤖 <b>Assalomu alaykum! Men InstaOhang Sun'iy Intellekt (AI Agent) yordamchisiman!</b>\n\n"
        "✨ Menga har qanday savolingizni yuborishingiz mumkin.\n"
        "📥 Instagram-dan video yuklash, 🎵 musiqalar izlash yoki ⭕ videolarni <code>/round</code> bilan dumaloq Video Note'ga aylantirish bo'yicha yordam beraman!"
    )

@router.message(Command("agent"))
@router.message(Command("ai"))
@router.message(F.text == "🤖 AI Agent")
async def cmd_agent_status(message: Message):
    """
    Directly triggers AI Agent response when '🤖 AI Agent' button is clicked.
    No need for /ask prefix!
    """
    status_msg = await message.answer("🧠 <b>Sun'iy Intellekt AI Agent javob tayyorlamoqda... ⏳</b>", parse_mode="HTML")
    
    prompt = (
        "O'zbek tilida InstaOhang boti foydalanuvchilariga xushmuomala salom ber, "
        "o'zingni AI Agent deb tanishtir va bot imkoniyatlarini (Instagram video yuklash, "
        "MP3 audio ajratib olish, musiqa izlash va videolarni /round bilan dumaloq formatga o'tkazish) "
        "juda chiroyli, qisqa va qiziqarli ko'rinishda tushuntirib ber."
    )
    
    ai_reply = await get_ai_response(prompt)
    
    response_text = (
        f"🤖 <b>{AGENT_NAME}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{clean_html(ai_reply)}\n\n"
        f"👨‍💻 <i>CREATED BY: @htpAsilbek</i>"
    )
    await status_msg.edit_text(response_text, parse_mode="HTML")

@router.message(Command("agent_info"))
@router.message(F.text == "⚙️ AI Agent-Info")
async def cmd_agent_info(message: Message):
    """
    Technical info about AI agent system.
    """
    info_text = (
        "⚙️ <b>AI Sub-Agent System Architecture:</b>\n\n"
        "• <b>Status:</b> 🟢 ONLINE & ACTIVE\n"
        "• <b>AI Model Engine:</b> GPT-4o-Mini AI Neural Core\n"
        "• <b>Language:</b> Uzbek / Multi-language support\n"
        "• <b>Multi-Bot Architecture:</b> Enabled\n"
        "• <b>Primary Bot:</b> @InstaOhang_bot\n"
        "• <b>Developer:</b> @htpAsilbek"
    )
    await message.answer(info_text, parse_mode="HTML")

@router.message(Command("ask"))
async def cmd_ask_agent(message: Message):
    """
    Optional /ask handler fallback if used.
    """
    question = message.text.replace("/ask", "").strip()
    if not question:
        question = "Instagramdan video va musiqa qanday yuklanadi?"
        
    status_msg = await message.answer("🧠 <b>Sun'iy Intellekt javob o'ylamoqda... ⏳</b>", parse_mode="HTML")
    ai_reply = await get_ai_response(question)
    
    response_text = (
        f"🤖 <b>AI Agent Javobi:</b>\n\n"
        f"{clean_html(ai_reply)}\n\n"
        f"👨‍💻 <i>CREATED BY: @htpAsilbek</i>"
    )
    await status_msg.edit_text(response_text, parse_mode="HTML")
