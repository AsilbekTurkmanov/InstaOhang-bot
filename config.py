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
# PostgreSQL Database URL
# ─────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise ValueError("CRITICAL ERROR: DATABASE_URL is missing! Please set DATABASE_URL in .env file.")

# ─────────────────────────────────────────────
# Admin Telegram IDs
# ─────────────────────────────────────────────
raw_admin_ids = os.getenv("ADMIN_IDS", "").strip()
if not raw_admin_ids:
    raise ValueError("CRITICAL ERROR: ADMIN_IDS is missing! Please set ADMIN_IDS in .env file.")

ADMIN_IDS = [int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()]

# ─────────────────────────────────────────────
# Redis Connection URL
# ─────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()

# ─────────────────────────────────────────────
# Limits & Worker Safeguards
# ─────────────────────────────────────────────
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "200"))
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "300"))
DOWNLOAD_WORKERS = int(os.getenv("DOWNLOAD_WORKERS", "4"))

# ─────────────────────────────────────────────
# AI Provider Configuration
# ─────────────────────────────────────────────
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini").strip()
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").strip()

# ─────────────────────────────────────────────
# Portfolio API Integration
# ─────────────────────────────────────────────
PORTFOLIO_API_URL = os.getenv("PORTFOLIO_API_URL", "http://localhost:5056/api/contact").strip()
PORTFOLIO_API_TOKEN = os.getenv("PORTFOLIO_API_TOKEN", "").strip()

# ─────────────────────────────────────────────
# Directory Paths
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
BIN_DIR = os.path.join(BASE_DIR, "bin")

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

