import os
import shutil
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ─────────────────────────────────────────────
# Telegram Bot Tokens (loaded from .env)
# ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ASSISTANT_BOT_TOKEN = os.getenv("ASSISTANT_BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise ValueError("CRITICAL ERROR: BOT_TOKEN is missing! Please set BOT_TOKEN in .env file.")

# ─────────────────────────────────────────────
# PostgreSQL Connection
# ─────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:1234@localhost:5432/instaohang"
)

# ─────────────────────────────────────────────
# Admin Telegram IDs
# ─────────────────────────────────────────────
raw_admin_ids = os.getenv("ADMIN_IDS", "5246861200")
ADMIN_IDS = [int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()]

# ─────────────────────────────────────────────
# Limits & Safeguards
# ─────────────────────────────────────────────
MAX_FILE_SIZE_MB = 50

# ─────────────────────────────────────────────
# Directory Paths
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
BIN_DIR = os.path.join(BASE_DIR, "bin")

# Legacy SQLite path (kept for backward compat if needed)
DB_PATH = os.path.join(BASE_DIR, "database", "insta_ohang.db")

# ─────────────────────────────────────────────
# Executables (FFmpeg)
# ─────────────────────────────────────────────
if os.name == 'nt' and os.path.exists(os.path.join(BIN_DIR, "ffmpeg.exe")):
    FFMPEG_PATH = os.path.join(BIN_DIR, "ffmpeg.exe")
    FFPROBE_PATH = os.path.join(BIN_DIR, "ffprobe.exe")
else:
    FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
    FFPROBE_PATH = shutil.which("ffprobe") or "ffprobe"

# ─────────────────────────────────────────────
# Create required directories if not exist
# ─────────────────────────────────────────────
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
