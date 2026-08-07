import os
import sys

# Ensure current working directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, ASSISTANT_BOT_TOKEN, BIN_DIR, FFMPEG_PATH
from database.db import init_db
from handlers import start, instagram, round_video, music_search, admin, agent_assistant
from utils.middleware import ThrottlingMiddleware
from utils.helpers import cleanup_old_temp_files

# Add BIN_DIR to PATH env variable so yt-dlp & subprocess find ffmpeg.exe easily
if os.path.exists(BIN_DIR):
    os.environ["PATH"] = BIN_DIR + os.pathsep + os.environ.get("PATH", "")

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def periodic_temp_cleanup():
    """Periodically purges old temporary files in downloads/ every 30 mins."""
    while True:
        try:
            cleanup_old_temp_files(max_age_seconds=1800)
        except Exception as e:
            logger.error(f"Periodic cleanup error: {e}")
        await asyncio.sleep(1800)

async def main():
    logger.info("Initializing Database...")
    init_db()

    # Initial cleanup of old files on startup
    cleanup_old_temp_files(max_age_seconds=1800)
    asyncio.create_task(periodic_temp_cleanup())

    logger.info("Starting InstaOhang Telegram Bot...")
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    
    # Register Throttling Middleware
    dp.message.middleware(ThrottlingMiddleware(limit_seconds=1.5))
    dp.callback_query.middleware(ThrottlingMiddleware(limit_seconds=1.0))

    # Register Routers
    dp.include_router(start.router)
    dp.include_router(agent_assistant.router)
    dp.include_router(instagram.router)
    dp.include_router(round_video.router)
    dp.include_router(admin.router)
    dp.include_router(music_search.router)

    # Delete existing webhooks before long polling
    await bot.delete_webhook(drop_pending_updates=True)

    # ✅ Bot tavsifi — Telegram'da "What can this bot do?" bo'limida ko'rinadi
    try:
        await bot.set_my_description(
            description=(
                "🎧 InstaOhang — Instagram Media Yuklovchi Bot\n\n"
                "✅ Instagram Reels & Postlardan video yuklash.\n"
                "🎵 Videolardan MP3 musiqani ajratib olish.\n"
                "⭕ Videoni dumaloq Video Note'ga o'tkazish (/round).\n"
                "🎵 Qo'shiq nomi bo'yicha musiqa izlash.\n"
                "⚡ Videoni tezlashtirish (/fast, /slow).\n"
                "🤖 Sub-Agent yordamchisi (/agent).\n\n"
                "📲 Boshlash uchun havola yoki qo'shiq nomini yuboring!\n\n"
                "👨‍💻 CREATED BY: @htpAsilbek"
            ),
            language_code=""
        )
        await bot.set_my_short_description(
            short_description="Instagram'dan video, musiqa yuklovchi, AI agent va dumaloq video (/round) bot! 🎵⭕🤖",
            language_code=""
        )
        # Bot buyruqlar ro'yxati (/ menyusi)
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="start",  description="Botni ishga tushirish ▶️"),
            BotCommand(command="round",  description="Videoni dumaloq shaklga keltirish ⭕"),
            BotCommand(command="music",  description="Musiqa qidirish 🎵"),
            BotCommand(command="audio",  description="Videodan audio ajratib olish 🎧"),
            BotCommand(command="fast",   description="Videoni 1.5x tezlashtiring ⚡"),
            BotCommand(command="slow",   description="Videoni 0.8x sekinlashtiring 🐢"),
            BotCommand(command="agent",  description="AI Agent yordamchisi 🤖"),
            BotCommand(command="users",  description="Foydalanuvchilar soni 👥"),
            BotCommand(command="admin",  description="Admin panel 📊"),
        ])
        logger.info("Bot description and commands set successfully.")
    except Exception as e:
        logger.warning(f"Could not set bot description/commands: {e}")

    bot_info = await bot.get_me()
    logger.info(f"Bot successfully launched as @{bot_info.username} (ID: {bot_info.id})")

    bots_to_poll = [bot]
    if ASSISTANT_BOT_TOKEN.strip():
        try:
            assistant_bot = Bot(token=ASSISTANT_BOT_TOKEN.strip(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            assistant_info = await assistant_bot.get_me()
            logger.info(f"Assistant Sub-Agent Bot launched as @{assistant_info.username} (ID: {assistant_info.id})")
            await assistant_bot.delete_webhook(drop_pending_updates=True)
            bots_to_poll.append(assistant_bot)
        except Exception as e:
            logger.error(f"Could not start secondary assistant bot: {e}")
    
    try:
        await dp.start_polling(*bots_to_poll)
    finally:
        for b in bots_to_poll:
            await b.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
