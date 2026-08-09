import os
import sys
import logging
import asyncio

# Ensure current working directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix Windows console UTF-8 encoding (prevents emoji UnicodeEncodeError)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand

from config import BOT_TOKEN, ASSISTANT_BOT_TOKEN, BIN_DIR, FFMPEG_PATH
from database.postgres import init_pool, close_pool, init_db_schema
from handlers import start, instagram, round_video, music_search, admin, agent_assistant, favorites
from utils.middleware import ThrottlingMiddleware
from utils.helpers import cleanup_old_temp_files
from utils.error_handler import error_router

# ─────────────────────────────────────────────────────────────────────────────
# Add BIN_DIR to PATH so yt-dlp & subprocess find ffmpeg easily
# ─────────────────────────────────────────────────────────────────────────────
if os.path.exists(BIN_DIR):
    os.environ["PATH"] = BIN_DIR + os.pathsep + os.environ.get("PATH", "")

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Periodic cleanup task
# ─────────────────────────────────────────────────────────────────────────────
async def periodic_temp_cleanup():
    """Periodically purges old temporary files in downloads/ every 30 minutes."""
    while True:
        try:
            cleanup_old_temp_files(max_age_seconds=1800)
        except Exception as e:
            logger.error(f"Periodic cleanup error: {e}")
        await asyncio.sleep(1800)


# ─────────────────────────────────────────────────────────────────────────────
# Bot commands setup
# ─────────────────────────────────────────────────────────────────────────────
BOT_COMMANDS = [
    BotCommand(command="start",     description="Botni ishga tushirish ▶️"),
    BotCommand(command="round",     description="Videoni dumaloq shaklga keltirish ⭕"),
    BotCommand(command="music",     description="Musiqa qidirish 🎵"),
    BotCommand(command="favorites", description="Sevimli musiqalar ❤️"),
    BotCommand(command="audio",     description="Videodan audio ajratib olish 🎧"),
    BotCommand(command="fast",      description="Videoni 1.5x tezlashtiring ⚡"),
    BotCommand(command="slow",      description="Videoni 0.8x sekinlashtiring 🐢"),
    BotCommand(command="agent",     description="AI Agent yordamchisi 🤖"),
    BotCommand(command="users",     description="Foydalanuvchilar soni 👥"),
    BotCommand(command="admin",     description="Admin panel 📊"),
    BotCommand(command="portfolio", description="Portfolio xabarlari (Admin) 📩"),
]

BOT_DESCRIPTION = (
    "🎧 InstaOhang — Instagram Media Yuklovchi Bot\n\n"
    "✅ Instagram Reels & Postlardan video yuklash.\n"
    "🎵 Videolardan MP3 musiqani ajratib olish.\n"
    "⭕ Videoni dumaloq Video Note'ga o'tkazish (/round).\n"
    "🎵 Qo'shiq nomi bo'yicha musiqa izlash.\n"
    "❤️ Sevimli musiqalar ro'yxati.\n"
    "⚡ Videoni tezlashtirish (/fast, /slow).\n"
    "🤖 Sub-Agent yordamchisi (/agent).\n\n"
    "📲 Boshlash uchun havola yoki qo'shiq nomini yuboring!\n\n"
    "👨‍💻 CREATED BY: @htpAsilbek"
)

BOT_SHORT_DESCRIPTION = (
    "Instagram'dan video, musiqa yuklovchi, ❤️ sevimlilar, AI agent va dumaloq video bot! 🎵⭕🤖"
)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    # 1. Initialize PostgreSQL connection pool
    logger.info("Connecting to PostgreSQL...")
    try:
        await init_pool(min_size=2, max_size=10)
        await init_db_schema()
        logger.info("PostgreSQL connected and schema ready.")
    except Exception as db_err:
        logger.critical(
            f"FATAL: Could not connect to PostgreSQL! "
            f"Check DATABASE_URL in .env\nError: {db_err}"
        )
        sys.exit(1)

    # 2. Startup file cleanup & managed background task
    cleanup_old_temp_files(max_age_seconds=1800)
    cleanup_task = asyncio.create_task(periodic_temp_cleanup())

    # 3. Create bot and dispatcher
    logger.info("Starting @InstaOhang_bot...")
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # 4. Register global error handler FIRST
    dp.include_router(error_router)

    # 5. Register throttling middleware (memory-safe, operation-aware)
    throttle_mw = ThrottlingMiddleware()
    dp.message.middleware(throttle_mw)
    dp.callback_query.middleware(throttle_mw)

    # 6. Register feature routers
    dp.include_router(start.router)
    dp.include_router(agent_assistant.router)
    dp.include_router(instagram.router)
    dp.include_router(round_video.router)
    dp.include_router(admin.router)
    dp.include_router(favorites.router)
    dp.include_router(music_search.router)  # Last: catches all non-command text

    # 7. Delete existing webhooks before long polling
    await bot.delete_webhook(drop_pending_updates=True)

    # 8. Set bot description and commands
    try:
        await bot.set_my_description(description=BOT_DESCRIPTION, language_code="")
        await bot.set_my_short_description(short_description=BOT_SHORT_DESCRIPTION, language_code="")
        await bot.set_my_commands(BOT_COMMANDS)
        logger.info("Bot description and commands set successfully.")
    except Exception as e:
        logger.warning(f"Could not set bot description/commands: {e}")

    bot_info = await bot.get_me()
    logger.info(f"✅ Bot launched as @{bot_info.username} (ID: {bot_info.id})")

    # 9. Optional secondary (assistant) bot
    bots_to_poll = [bot]
    if ASSISTANT_BOT_TOKEN.strip():
        try:
            assistant_bot = Bot(
                token=ASSISTANT_BOT_TOKEN.strip(),
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
            assistant_info = await assistant_bot.get_me()
            logger.info(
                f"Assistant Sub-Agent Bot launched as @{assistant_info.username} (ID: {assistant_info.id})"
            )
            await assistant_bot.delete_webhook(drop_pending_updates=True)
            bots_to_poll.append(assistant_bot)
        except Exception as e:
            logger.error(f"Could not start secondary assistant bot: {e}")

    # 10. Start polling with graceful shutdown
    try:
        await dp.start_polling(*bots_to_poll)
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        for b in bots_to_poll:
            await b.session.close()
        await close_pool()
        logger.info("Bot stopped. PostgreSQL pool and background tasks closed cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
