# 🎧 InstaOhang Bot

**@InstaOhang_bot** — Professional, production-ready Telegram bot.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-green.svg)](https://aiogram.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)](https://postgresql.org)
[![asyncpg](https://img.shields.io/badge/asyncpg-0.29+-orange.svg)](https://github.com/MagicStack/asyncpg)

---

## 📋 Loyiha haqida

**InstaOhang** — Instagram dan video va Reels yuklovchi, YouTube dan musiqa qidiruvchi,
MP3 ajratuvchi va ko'plab media funksiyalariga ega professional Telegram bot.

### ✨ Features

| Funksiya | Tavsif |
|---------|--------|
| 📥 Instagram Video | Reels, Post, Carousel, TV yuklash |
| 🎵 Musiqa qidirish | YouTube orqali istalgan qo'shiqni izlash |
| 🎧 MP3 Ajratish | Videolardan yuqori sifatli MP3 audio |
| ⭕ Dumaloq Video | `/round` buyrug'i bilan Telegram Video Note |
| ⚡ Video Tezlashtirish | `/fast` (1.5x) va `/slow` (0.8x) |
| ❤️ Sevimlilar | Musiqalarni saqlash va boshqarish |
| 🤖 AI Agent | GPT-4o-Mini asosidagi yordamchi |
| 📢 Broadcast | Admin orqali barcha userlarga xabar |
| 📊 Admin Panel | Statistika, kanal boshqaruvi |

---

## 🏗 Architecture

```
InstaOhangBot/
│
├── bot.py                  ← Entry point (asyncpg pool init, router registration)
├── config.py               ← Environment variables & constants
│
├── database/
│   ├── postgres.py         ← asyncpg connection pool + schema init
│   └── db.py               ← Async data access layer (all queries)
│
├── handlers/
│   ├── start.py            ← /start, subscription check
│   ├── instagram.py        ← Instagram link download
│   ├── music_search.py     ← Music search & download
│   ├── favorites.py        ← Favorites CRUD + pagination
│   ├── round_video.py      ← /round command
│   ├── admin.py            ← Admin commands + broadcast
│   └── agent_assistant.py  ← AI Agent (/agent)
│
├── services/
│   ├── downloader.py       ← yt-dlp + Instaloader (async)
│   └── ffmpeg_service.py   ← FFmpeg operations (async subprocess)
│
└── utils/
    ├── helpers.py          ← Keyboards, sub check, file utils
    ├── middleware.py       ← Throttling middleware
    ├── performance.py      ← @measure_time + Timer
    └── error_handler.py    ← Global exception handler
```

### Database Tables

```
users            — Telegram foydalanuvchilar (telegram_id UNIQUE)
channels         — Majburiy obuna kanallari
downloads        — Yuklanishlar tarixi
media_cache      — Telegram file_id cache (instant re-send)
music_categories — Musiqa kategoriyalari
music            — Musiqalar (file_unique_id UNIQUE)
favorites        — User ↔ Music many-to-many (user_id+music_id UNIQUE)
portfolio_messages — Portfolio veb-saytidan kelgan xabarlar
```

---

## 🔧 Technologies

- **Python 3.11+**
- **aiogram 3.x** — Telegram Bot Framework
- **asyncpg** — PostgreSQL async driver (connection pool)
- **PostgreSQL 15+** — Production database
- **yt-dlp** — YouTube/Instagram media downloader
- **FFmpeg** — Audio/video processing
- **aiohttp** — Async HTTP client
- **instaloader** — Instagram fallback downloader
- **g4f** — AI Agent (GPT-4o-Mini)

---

## 📦 Requirements

- Python 3.11 yoki undan yuqori
- PostgreSQL 15+
- FFmpeg (system yoki `bin/` papkasida)
- Telegram Bot Token (`@BotFather` dan)

---

## 🐘 PostgreSQL Setup

### Local (Windows / Linux / Mac)

1. **PostgreSQL o'rnating** → [postgresql.org/download](https://www.postgresql.org/download/)

2. **Database yarating:**
```sql
CREATE DATABASE instaohang;
```

3. **Yoki psql orqali:**
```bash
psql -U postgres -c "CREATE DATABASE instaohang;"
```

### Railway / Render / Supabase

Railway yoki Supabase dan PostgreSQL olib, `DATABASE_URL` ni `.env` ga qo'ying.

---

## ⚙️ Environment Variables

`.env.example` faylini `.env` ga nusxalang:

```bash
cp .env.example .env
```

`.env` faylini tahrirlang:

```env
# Telegram
BOT_TOKEN=your_bot_token_from_botfather
ASSISTANT_BOT_TOKEN=optional_second_bot_token

# Admin Telegram IDs (vergul bilan ajrating)
ADMIN_IDS=5246861200

# PostgreSQL
DATABASE_URL=postgresql://postgres:1234@localhost:5432/instaohang
```

> ⚠️ **Muhim:** `.env` faylini Git ga commit qilmang! `.gitignore` da allaqachon mavjud.

---

## 🤖 Telegram Bot Token Setup

1. Telegramda `@BotFather` ga yozing
2. `/newbot` buyrug'ini yuboring
3. Bot nomini va username ni kiriting
4. Token ni `.env` ga qo'ying: `BOT_TOKEN=...`

---

## 🚀 Run

### 1. Dependencies o'rnating

```bash
pip install -r requirements.txt
```

### 2. Bot ishga tushiring

```bash
python bot.py
```

Bot muvaffaqiyatli ishga tushganda:
```
2026-08-09 | database.postgres      | INFO     | PostgreSQL pool initialized (min=2, max=10)
2026-08-09 | database.postgres      | INFO     | Database schema initialized successfully
2026-08-09 | __main__               | INFO     | ✅ Bot launched as @InstaOhang_bot (ID: ...)
```

---

## 📊 Performance Monitoring

Bot har bir muhim operatsiya uchun execution time loglaydi:

```
[PERFORMANCE] ✅ /start → db_upsert: 12ms | sub_check: 8ms | send_welcome: 110ms | Total: 130ms
[PERFORMANCE] ✅ music_search → Time: 342ms
[PERFORMANCE] ⚠️  instagram_download → Total: 1450ms  ← exceeded 1s target
```

Target: **< 1 second** oddiy operatsiyalar uchun.

---

## 🔐 Security

- ✅ Bot token faqat `.env` da
- ✅ Database password faqat `.env` da
- ✅ Stack trace hech qachon userlarga ko'rsatilmaydi
- ✅ SQL injection yo'q (asyncpg parameterized queries)
- ✅ Admin authorization faqat `ADMIN_IDS` orqali
- ✅ Logs da hech qachon token/password yo'q

---

## 🐳 Docker (optional)

```bash
# PostgreSQL + Bot
docker-compose up -d
```

`docker-compose.yml` yaratish:
```yaml
version: '3.8'
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: instaohang
      POSTGRES_PASSWORD: 1234
    ports:
      - "5432:5432"
  
  bot:
    build: .
    depends_on:
      - db
    env_file:
      - .env
```

---

## 🚢 Deployment (VPS / Linux)

```bash
# 1. Clone repository
git clone https://github.com/AsilbekTurkmanov/InstaOhang-bot.git
cd InstaOhang-bot

# 2. Virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure .env
cp .env.example .env
nano .env   # BOT_TOKEN va DATABASE_URL ni to'ldiring

# 5. Run with systemd (production)
# /etc/systemd/system/instaohang.service
# ExecStart=/path/to/venv/bin/python /path/to/bot.py

sudo systemctl enable instaohang
sudo systemctl start instaohang
```

---

## 🧪 Testing

```bash
# Bot imports va DB connection test
python -c "
import asyncio
from database.postgres import init_pool, init_db_schema
async def test():
    await init_pool()
    await init_db_schema()
    print('✅ PostgreSQL OK')
asyncio.run(test())
"
```

---

## ❓ Troubleshooting

| Muammo | Yechim |
|--------|--------|
| `CRITICAL: Could not connect to PostgreSQL` | `DATABASE_URL` ni `.env` da tekshiring. PostgreSQL ishlayotganligini tekshiring |
| `BOT_TOKEN is missing` | `.env` da `BOT_TOKEN` borligini tekshiring |
| FFmpeg topilmaydi | FFmpeg ni o'rnating yoki `bin/ffmpeg.exe` ni joylashtiring |
| `asyncpg not found` | `pip install asyncpg` |
| Instagram yuklanmaydi | Instagram URL to'g'riligini tekshiring. Cookies kerak bo'lishi mumkin |

---

## 👨‍💻 Developer

**Created by:** [@htpAsilbek](https://t.me/htpAsilbek)

**Bot:** [@InstaOhang_bot](https://t.me/InstaOhang_bot)
