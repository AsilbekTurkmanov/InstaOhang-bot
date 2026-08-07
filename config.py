import os

# Telegram Bot Tokens (reads from env or uses default)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8594937535:AAGz9v-Bbq4yx-B63Sxlg-VSPNgEhWdH_6E")
ASSISTANT_BOT_TOKEN = os.getenv("ASSISTANT_BOT_TOKEN", "")

# Admin Telegram IDs
ADMIN_IDS = [5246861200]

# Limits & Safeguards
MAX_FILE_SIZE_MB = 50

# Directory Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
BIN_DIR = os.path.join(BASE_DIR, "bin")
DB_PATH = os.path.join(BASE_DIR, "database", "insta_ohang.db")

# Executables
FFMPEG_PATH = os.path.join(BIN_DIR, "ffmpeg.exe")
FFPROBE_PATH = os.path.join(BIN_DIR, "ffprobe.exe")

# Create directories if not exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
