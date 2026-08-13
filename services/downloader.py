"""
Media downloader service for @InstaOhang_bot.
- Instagram: yt-dlp primary, Instaloader fallback
- YouTube: yt-dlp search + download
- All operations via asyncio.to_thread() — no event loop blocking

Fixes:
- Single User-Agent per request (no double random.choice)
- HTTPS certificate verification enabled (nocheckcertificate removed)
- Per-operation timeout via asyncio.wait_for
- Download semaphore limits simultaneous heavy downloads
- In-flight deduplication (URL → asyncio.Future) to prevent duplicate downloads
"""

import os
import uuid
import logging
import asyncio
import random
import yt_dlp
import instaloader
from config import DOWNLOAD_DIR, FFMPEG_PATH, BIN_DIR

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# User-Agent pool
# ─────────────────────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
]

# ─────────────────────────────────────────────────────────────────────────────
# Concurrency — max simultaneous downloads (Instagram + YouTube combined)
# Heavy download operations are gated through this semaphore
# ─────────────────────────────────────────────────────────────────────────────
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(4)       # max 4 simultaneous downloads
DOWNLOAD_TIMEOUT_SEC = 300                       # 5 minutes per download

# ─────────────────────────────────────────────────────────────────────────────
# In-flight deduplication
# Maps canonical_url → asyncio.Future so concurrent identical requests
# share the same download result instead of launching duplicate processes.
# ─────────────────────────────────────────────────────────────────────────────
_IN_FLIGHT: dict[str, asyncio.Future] = {}


def _get_user_agent() -> str:
    """Returns a single consistent User-Agent for the current request."""
    return random.choice(USER_AGENTS)


def get_yt_dlp_options(extra_opts: dict | None = None) -> dict:
    """
    Builds yt-dlp options with a single consistent User-Agent.
    HTTPS certificate verification is ENABLED (no nocheckcertificate).
    """
    ffmpeg_bin = FFMPEG_PATH if (FFMPEG_PATH and os.path.exists(FFMPEG_PATH)) else None
    ffmpeg_dir = BIN_DIR if (os.name == "nt" and os.path.exists(FFMPEG_PATH)) else (os.path.dirname(ffmpeg_bin) if ffmpeg_bin else None)
    ua = _get_user_agent()   # single UA for this call — used consistently below

    opts: dict = {
        "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s_%(title).30s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "merge_output_format": "mp4",
        "concurrent_fragment_downloads": 8,
        "socket_timeout": 30,
        "buffersize": 1048576,
        "http_chunk_size": 10485760,
        "noplaylist": True,
        "max_filesize": 200 * 1024 * 1024,
        # Single User-Agent used consistently in both places
        "user_agent": ua,
        "http_headers": {
            "User-Agent": ua,   # same UA — no inconsistency
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["mweb", "android", "ios", "web"]
            }
        },
    }
    if ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir
    elif ffmpeg_bin:
        opts["ffmpeg_location"] = ffmpeg_bin
    if extra_opts:
        opts.update(extra_opts)
    return opts


# ─────────────────────────────────────────────────────────────────────────────
# Instagram — Instaloader fallback
# ─────────────────────────────────────────────────────────────────────────────

def _download_via_instaloader(url: str) -> dict:
    """Fallback Instagram parser using Instaloader library (runs in thread)."""
    logger.info("Attempting Instagram download via Instaloader fallback engine...")
    L = instaloader.Instaloader(
        download_pictures=True,
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        dirname_pattern=DOWNLOAD_DIR,
    )

    parts = [p for p in url.split("/") if p]
    if len(parts) < 2:
        raise ValueError("Invalid Instagram URL format")
    shortcode = parts[-1]

    post = instaloader.Post.from_shortcode(L.context, shortcode)
    unique_name = f"insta_{shortcode}_{str(uuid.uuid4())[:6]}"

    items = []
    if post.is_video:
        target_path = os.path.join(DOWNLOAD_DIR, f"{unique_name}.mp4")
        L.download_pic(target_path, post.video_url, post.date_utc)
        items.append({"type": "video", "filepath": target_path})
    else:
        target_path = os.path.join(DOWNLOAD_DIR, f"{unique_name}.jpg")
        L.download_pic(target_path, post.url, post.date_utc)
        items.append({"type": "photo", "filepath": target_path})

    return {
        "type": "video" if post.is_video else "photo",
        "filepath": items[0]["filepath"],
        "items": items,
        "title": post.caption[:150] if post.caption else "Instagram Media",
        "author": post.owner_username or "Instagram User",
        "duration": int(post.video_duration) if post.is_video and post.video_duration else 0,
        "thumbnail": post.url,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Instagram download — primary + fallback
# ─────────────────────────────────────────────────────────────────────────────

async def download_instagram_media(url: str) -> dict:
    """
    Downloads media from Instagram (Reels, Posts, Carousel, Stories).
    - yt-dlp primary; Instaloader fallback
    - Semaphore(4) limits simultaneous downloads
    - DOWNLOAD_TIMEOUT_SEC overall timeout
    - In-flight deduplication: same URL → same result (no duplicate downloads)
    """
    # Normalize URL for deduplication (strip trailing slash, utm params)
    canonical = _normalize_url(url)

    # In-flight deduplication
    loop = asyncio.get_event_loop()
    if canonical in _IN_FLIGHT:
        logger.info(f"[Dedup] Joining in-flight download for: {canonical}")
        return await _IN_FLIGHT[canonical]

    fut: asyncio.Future = loop.create_future()
    _IN_FLIGHT[canonical] = fut

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_do_instagram_download, url),
            timeout=DOWNLOAD_TIMEOUT_SEC,
        )
        fut.set_result(result)
        return result
    except asyncio.TimeoutError:
        exc = RuntimeError(f"Instagram yuklab olish vaqti tugadi (>{DOWNLOAD_TIMEOUT_SEC}s). Havola mavjud yoki video juda kattadir.")
        fut.set_exception(exc)
        raise exc
    except Exception as exc:
        if not fut.done():
            fut.set_exception(exc)
        raise
    finally:
        _IN_FLIGHT.pop(canonical, None)


def _do_instagram_download(url: str) -> dict:
    """Blocking Instagram download (runs in thread pool)."""
    opts = get_yt_dlp_options()
    try:
        with yt_dlp.YoutubeDL(opts) as ytdl:
            info = ytdl.extract_info(url, download=True)

            title = info.get("title") or info.get("description") or "InstaOhang Media"
            author = info.get("uploader") or info.get("uploader_id") or "Instagram User"

            if "entries" in info and info["entries"]:
                items = []
                for entry in info["entries"]:
                    if not entry:
                        continue
                    fn = ytdl.prepare_filename(entry)
                    if not os.path.exists(fn):
                        base = os.path.splitext(fn)[0]
                        if os.path.exists(f"{base}.mp4"):
                            fn = f"{base}.mp4"
                    is_v = fn.endswith((".mp4", ".mkv", ".mov", ".webm"))
                    items.append({"type": "video" if is_v else "photo", "filepath": fn})

                first_fn = items[0]["filepath"] if items else ""
                first_is_v = first_fn.endswith((".mp4", ".mkv", ".mov", ".webm"))
                return {
                    "type": "carousel" if len(items) > 1 else ("video" if first_is_v else "photo"),
                    "filepath": first_fn,
                    "items": items,
                    "title": title,
                    "author": author,
                    "duration": int(info.get("duration") or 0),
                    "thumbnail": info.get("thumbnail"),
                }
            else:
                filename = ytdl.prepare_filename(info)
                if not os.path.exists(filename):
                    base = os.path.splitext(filename)[0]
                    if os.path.exists(f"{base}.mp4"):
                        filename = f"{base}.mp4"
                is_video = filename.endswith((".mp4", ".mkv", ".mov", ".webm"))
                return {
                    "type": "video" if is_video else "photo",
                    "filepath": filename,
                    "items": [{"type": "video" if is_video else "photo", "filepath": filename}],
                    "title": title,
                    "author": author,
                    "duration": int(info.get("duration") or 0),
                    "thumbnail": info.get("thumbnail"),
                }
    except Exception as primary_err:
        logger.warning(f"[Instagram] yt-dlp failed ({primary_err}), trying Instaloader fallback...")
        try:
            return _download_via_instaloader(url)
        except Exception as secondary_err:
            logger.error(f"[Instagram] Both download methods failed: {secondary_err}")
            raise RuntimeError("Instagram-dan media yuklab bo'lmadi. Havola to'g'riligini tekshiring.")


# ─────────────────────────────────────────────────────────────────────────────
# YouTube — search and download
# ─────────────────────────────────────────────────────────────────────────────

async def search_music_results(query: str, max_results: int = 10) -> list:
    """
    Searches YouTube for up to max_results songs (metadata only, fast).
    Uses android/ios primary player clients and tvhtml5/mweb fallback to bypass bot checks.
    Timeout: 30 seconds.
    """
    def _search() -> list:
        ua = _get_user_agent()
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "user_agent": ua,
            "http_headers": {"User-Agent": ua},
            "socket_timeout": 12,
            "nocheckcertificate": True,
            "geo_bypass": True,
            "extractor_args": {
                "youtube": {"player_client": ["android", "ios"]}
            },
        }
        search_query = f"ytsearch{max_results}:{query}"
        results = []
        try:
            with yt_dlp.YoutubeDL(opts) as ytdl:
                info = ytdl.extract_info(search_query, download=False)
                if info and "entries" in info and info["entries"]:
                    for entry in info["entries"]:
                        if not entry:
                            continue
                        video_id = entry.get("id")
                        if not video_id:
                            continue
                        title = entry.get("title") or query
                        uploader = entry.get("uploader") or entry.get("channel") or "Unknown Artist"
                        duration = entry.get("duration") or 0
                        mins, secs = divmod(int(duration), 60)
                        results.append({
                            "id": video_id,
                            "title": title,
                            "performer": uploader,
                            "duration": int(duration),
                            "duration_str": f"{mins:02d}:{secs:02d}",
                        })
                    if results:
                        return results
        except Exception as err1:
            logger.warning(f"[Music Search] Primary search failed ({err1}), trying fallback player clients...")

        # Fallback search using tvhtml5 & mweb
        opts["extractor_args"] = {"youtube": {"player_client": ["tvhtml5", "mweb"]}}
        try:
            with yt_dlp.YoutubeDL(opts) as ytdl:
                info = ytdl.extract_info(search_query, download=False)
                if info and "entries" in info and info["entries"]:
                    for entry in info["entries"]:
                        if not entry:
                            continue
                        video_id = entry.get("id")
                        if not video_id:
                            continue
                        title = entry.get("title") or query
                        uploader = entry.get("uploader") or entry.get("channel") or "Unknown Artist"
                        duration = entry.get("duration") or 0
                        mins, secs = divmod(int(duration), 60)
                        results.append({
                            "id": video_id,
                            "title": title,
                            "performer": uploader,
                            "duration": int(duration),
                            "duration_str": f"{mins:02d}:{secs:02d}",
                        })
        except Exception as err2:
            logger.error(f"[Music Search] Fallback search failed: {err2}")

        return results

    return await asyncio.wait_for(
        asyncio.to_thread(_search),
        timeout=30,
    )



async def download_music_by_id(video_id: str) -> dict:
    """
    Downloads YouTube track by video ID as MP3 (async, semaphore-gated).
    Timeout: DOWNLOAD_TIMEOUT_SEC.
    """
    async with DOWNLOAD_SEMAPHORE:
        return await asyncio.wait_for(
            asyncio.to_thread(_do_music_download, video_id),
            timeout=DOWNLOAD_TIMEOUT_SEC,
        )


def _ensure_mp3_file(unique_id: str) -> str:
    """
    Locates any downloaded file matching music_{unique_id}.* in DOWNLOAD_DIR.
    Ensures a valid MP3 output file exists via FFmpeg fallback if needed.
    """
    prefix = f"music_{unique_id}"
    mp3_path = os.path.join(DOWNLOAD_DIR, f"{prefix}.mp3")

    if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
        return mp3_path

    found_path = None
    for f in os.listdir(DOWNLOAD_DIR):
        if f.startswith(prefix):
            full_p = os.path.join(DOWNLOAD_DIR, f)
            if os.path.isfile(full_p) and os.path.getsize(full_p) > 0:
                found_path = full_p
                if f.endswith(".mp3"):
                    return full_p
                break

    if not found_path:
        raise RuntimeError("Musiqa audio fayli yuklanmadi.")

    # Convert found_path (e.g. .m4a, .webm, .opus, .mp4) to .mp3 using FFmpeg
    try:
        from services.ffmpeg_service import get_ffmpeg_bin
        import subprocess

        ffmpeg_bin = get_ffmpeg_bin()
        cmd = [
            ffmpeg_bin, "-y", "-i", found_path,
            "-vn", "-acodec", "libmp3lame", "-ab", "192k", "-ar", "44100",
            mp3_path,
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if res.returncode == 0 and os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
            try:
                os.remove(found_path)
            except Exception:
                pass
            return mp3_path
    except Exception as conv_err:
        logger.warning(f"FFmpeg MP3 fallback conversion error: {conv_err}")

    if os.path.exists(found_path):
        return found_path

    raise RuntimeError("MP3 audio faylini yaratishda xatolik yuz berdi.")


def _do_music_download(video_id: str) -> dict:
    """Blocking MP3 download (runs in thread pool)."""
    unique_id = str(uuid.uuid4())[:8]
    output_template = os.path.join(DOWNLOAD_DIR, f"music_{unique_id}.%(ext)s")
    url = f"https://www.youtube.com/watch?v={video_id}"

    opts = get_yt_dlp_options({
        "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    })

    info = None
    try:
        with yt_dlp.YoutubeDL(opts) as ytdl:
            info = ytdl.extract_info(url, download=True)
    except Exception as primary_err:
        logger.warning(f"[Music] Primary download failed ({primary_err}), trying fallback player...")
        opts["extractor_args"] = {"youtube": {"player_client": ["android", "tvhtml5", "ios"]}}
        try:
            with yt_dlp.YoutubeDL(opts) as ytdl:
                info = ytdl.extract_info(url, download=True)
        except Exception as fallback_err:
            logger.warning(f"[Music] Fallback failed ({fallback_err}), trying ytsearch...")
            try:
                with yt_dlp.YoutubeDL(opts) as ytdl:
                    search_res = ytdl.extract_info(f"ytsearch1:{video_id}", download=True)
                    if search_res and "entries" in search_res and search_res["entries"]:
                        info = search_res["entries"][0]
                    else:
                        raise RuntimeError(f"Musiqani yuklab bo'lmadi: {fallback_err}")
            except Exception as final_err:
                raise RuntimeError(f"Musiqa yuklanmadi: {final_err}")

    if not info:
        raise RuntimeError("Musiqa ma'lumotlari topilmadi.")

    title = info.get("title", "Music")
    uploader = info.get("uploader") or info.get("channel") or "Unknown Artist"
    duration = info.get("duration", 0)

    # Locate generated file & guarantee MP3 format
    file_mp3 = _ensure_mp3_file(unique_id)

    return {
        "filepath": file_mp3,
        "title": title,
        "performer": uploader,
        "duration": int(duration),
    }


async def search_and_download_music(query: str) -> dict:
    """Searches and downloads music by query string (async, semaphore-gated)."""
    async with DOWNLOAD_SEMAPHORE:
        return await asyncio.wait_for(
            asyncio.to_thread(_do_search_and_download, query),
            timeout=DOWNLOAD_TIMEOUT_SEC,
        )


def _do_search_and_download(query: str) -> dict:
    """Blocking search+download (runs in thread pool)."""
    unique_id = str(uuid.uuid4())[:8]
    output_template = os.path.join(DOWNLOAD_DIR, f"music_{unique_id}.%(ext)s")

    opts = get_yt_dlp_options({
        "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    })

    search_query = f"ytsearch1:{query} audio song"
    with yt_dlp.YoutubeDL(opts) as ytdl:
        info = ytdl.extract_info(search_query, download=True)
        if "entries" in info and info["entries"]:
            entry = info["entries"][0]
            title = entry.get("title", query)
            uploader = entry.get("uploader", "Unknown Artist")
            duration = entry.get("duration", 0)
            file_mp3 = _ensure_mp3_file(unique_id)
            return {
                "filepath": file_mp3,
                "title": title,
                "performer": uploader,
                "duration": int(duration),
            }
        raise RuntimeError("Musiqa topilmadi.")



# ─────────────────────────────────────────────────────────────────────────────
# URL normalization (for cache deduplication)
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """
    Normalizes Instagram/YouTube URL for cache key consistency.
    Strips trailing slash, UTM params, and query string noise.
    """
    import re
    # Remove query string (utm_source, etc.) but keep the path
    url = url.strip().rstrip("/")
    url = re.sub(r"\?.*$", "", url)  # remove ?everything
    url = re.sub(r"https?://www\.", "https://", url)  # normalize www.
    url = re.sub(r"https?://", "https://", url)  # normalize http → https
    return url.lower()
