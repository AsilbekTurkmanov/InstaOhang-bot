import os
import uuid
import logging
import asyncio
import random
import yt_dlp
import instaloader
from config import DOWNLOAD_DIR, FFMPEG_PATH, BIN_DIR

logger = logging.getLogger(__name__)

# User-Agent rotation list to prevent Instagram IP/bot blocking
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1'
]

def get_yt_dlp_options(extra_opts=None):
    ffmpeg_dir = BIN_DIR if os.path.exists(FFMPEG_PATH) else None
    opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s_%(title).30s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
        'merge_output_format': 'mp4',
        'nocheckcertificate': True,
        'user_agent': random.choice(USER_AGENTS),
        'http_headers': {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['mweb', 'android', 'ios', 'web']
            }
        }
    }
    if ffmpeg_dir:
        opts['ffmpeg_location'] = ffmpeg_dir
    if extra_opts:
        opts.update(extra_opts)
    return opts

def _download_via_instaloader(url: str) -> dict:
    """Fallback Instagram parser using Instaloader library."""
    logger.info("Attempting Instagram download via Instaloader fallback engine...")
    L = instaloader.Instaloader(
        download_pictures=True,
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        dirname_pattern=DOWNLOAD_DIR
    )
    
    # Extract shortcode from url (e.g. instagram.com/p/SHORTCODE or instagram.com/reel/SHORTCODE)
    parts = [p for p in url.split('/') if p]
    if len(parts) < 2:
        raise ValueError("Invalid Instagram URL format")
    shortcode = parts[-1]
    if shortcode.startswith("p") or shortcode.startswith("reel") or shortcode.startswith("reels"):
        shortcode = parts[-1] if not parts[-1].startswith(("p", "reel")) else parts[-1]
        
    post = instaloader.Post.from_shortcode(L.context, shortcode)
    unique_name = f"insta_{shortcode}_{str(uuid.uuid4())[:6]}"
    
    items = []
    if post.is_video:
        target_path = os.path.join(DOWNLOAD_DIR, f"{unique_name}.mp4")
        L.download_pic(target_path, post.video_url, post.date_utc)
        items.append({'type': 'video', 'filepath': target_path})
    else:
        target_path = os.path.join(DOWNLOAD_DIR, f"{unique_name}.jpg")
        L.download_pic(target_path, post.url, post.date_utc)
        items.append({'type': 'photo', 'filepath': target_path})
        
    first_file = items[0]['filepath']
    return {
        'type': 'video' if post.is_video else 'photo',
        'filepath': first_file,
        'items': items,
        'title': post.caption[:150] if post.caption else "Instagram Media",
        'author': post.owner_username or "Instagram User",
        'duration': int(post.video_duration) if post.is_video and post.video_duration else 0,
        'thumbnail': post.url
    }

async def download_instagram_media(url: str) -> dict:
    """
    Downloads media from Instagram (Reels, Posts, Carousel, Stories).
    Employs dual-tier fallback (yt-dlp -> Instaloader) with exception handling.
    """
    def _download():
        opts = get_yt_dlp_options()
        try:
            with yt_dlp.YoutubeDL(opts) as ytdl:
                info = ytdl.extract_info(url, download=True)
                
                title = info.get('title') or info.get('description') or "InstaOhang Media"
                author = info.get('uploader') or info.get('uploader_id') or "Instagram User"
                
                if 'entries' in info and info['entries']:
                    items = []
                    for entry in info['entries']:
                        if not entry:
                            continue
                        fn = ytdl.prepare_filename(entry)
                        if not os.path.exists(fn):
                            base = os.path.splitext(fn)[0]
                            if os.path.exists(f"{base}.mp4"):
                                fn = f"{base}.mp4"
                        is_v = fn.endswith(('.mp4', '.mkv', '.mov', '.webm'))
                        items.append({
                            'type': 'video' if is_v else 'photo',
                            'filepath': fn
                        })
                    
                    first_fn = items[0]['filepath'] if items else ""
                    first_is_v = first_fn.endswith(('.mp4', '.mkv', '.mov', '.webm'))
                    
                    return {
                        'type': 'carousel' if len(items) > 1 else ('video' if first_is_v else 'photo'),
                        'filepath': first_fn,
                        'items': items,
                        'title': title,
                        'author': author,
                        'duration': int(info.get('duration') or 0),
                        'thumbnail': info.get('thumbnail')
                    }
                else:
                    filename = ytdl.prepare_filename(info)
                    if not os.path.exists(filename):
                        base = os.path.splitext(filename)[0]
                        if os.path.exists(f"{base}.mp4"):
                            filename = f"{base}.mp4"

                    is_video = filename.endswith(('.mp4', '.mkv', '.mov', '.webm'))
                    
                    return {
                        'type': 'video' if is_video else 'photo',
                        'filepath': filename,
                        'items': [{'type': 'video' if is_video else 'photo', 'filepath': filename}],
                        'title': title,
                        'author': author,
                        'duration': int(info.get('duration') or 0),
                        'thumbnail': info.get('thumbnail')
                    }
        except Exception as primary_err:
            logger.warning(f"Primary yt-dlp download failed ({primary_err}), trying Instaloader fallback...")
            try:
                return _download_via_instaloader(url)
            except Exception as secondary_err:
                logger.error(f"Secondary fallback failed: {secondary_err}")
                raise RuntimeError(f"Instagram-dan media yuklab bo'lmadi. Havola to'g'riligini tekshiring.")

    return await asyncio.to_thread(_download)

async def search_music_results(query: str, max_results: int = 10) -> list:
    """
    Searches YouTube for up to max_results songs (metadata only, fast & async).
    """
    def _search():
        opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'nocheckcertificate': True,
            'user_agent': random.choice(USER_AGENTS),
            'extractor_args': {
                'youtube': {
                    'player_client': ['mweb', 'android', 'ios', 'web']
                }
            }
        }
        search_query = f"ytsearch{max_results}:{query}"
        with yt_dlp.YoutubeDL(opts) as ytdl:
            info = ytdl.extract_info(search_query, download=False)
            results = []
            if info and 'entries' in info and info['entries']:
                for entry in info['entries']:
                    if not entry:
                        continue
                    video_id = entry.get('id')
                    if not video_id:
                        continue
                    title = entry.get('title') or query
                    uploader = entry.get('uploader') or entry.get('channel') or "Unknown Artist"
                    duration = entry.get('duration') or 0
                    
                    mins, secs = divmod(int(duration), 60)
                    duration_str = f"{mins:02d}:{secs:02d}"
                    
                    results.append({
                        'id': video_id,
                        'title': title,
                        'performer': uploader,
                        'duration': int(duration),
                        'duration_str': duration_str
                    })
            return results

    return await asyncio.to_thread(_search)

async def download_music_by_id(video_id: str) -> dict:
    """
    Downloads YouTube track by video ID as MP3 audio (async).
    """
    def _download():
        unique_id = str(uuid.uuid4())[:8]
        output_template = os.path.join(DOWNLOAD_DIR, f"music_{unique_id}.%(ext)s")
        
        opts = get_yt_dlp_options({
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        info = None
        
        try:
            with yt_dlp.YoutubeDL(opts) as ytdl:
                info = ytdl.extract_info(url, download=True)
        except Exception as primary_err:
            logger.warning(f"Primary download failed ({primary_err}), trying fallback player clients...")
            opts['extractor_args'] = {'youtube': {'player_client': ['android', 'tvhtml5', 'ios']}}
            try:
                with yt_dlp.YoutubeDL(opts) as ytdl:
                    info = ytdl.extract_info(url, download=True)
            except Exception as fallback_err:
                logger.warning(f"Fallback download failed ({fallback_err}), searching via ytsearch...")
                with yt_dlp.YoutubeDL(opts) as ytdl:
                    search_res = ytdl.extract_info(f"ytsearch1:{video_id}", download=True)
                    if search_res and 'entries' in search_res and search_res['entries']:
                        info = search_res['entries'][0]
                    else:
                        raise RuntimeError(f"Musiqani yuklab bo'lmadi: {fallback_err}")

        if not info:
            raise RuntimeError("Musiqa ma'lumotlari topilmadi.")

        title = info.get('title', 'Music')
        uploader = info.get('uploader') or info.get('channel') or 'Unknown Artist'
        duration = info.get('duration', 0)
        file_mp3 = os.path.join(DOWNLOAD_DIR, f"music_{unique_id}.mp3")
        
        if not os.path.exists(file_mp3):
            base = os.path.splitext(file_mp3)[0]
            if os.path.exists(f"{base}.mp3"):
                file_mp3 = f"{base}.mp3"
                
        if not os.path.exists(file_mp3):
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(f"music_{unique_id}") and f.endswith('.mp3'):
                    file_mp3 = os.path.join(DOWNLOAD_DIR, f)
                    break

        if not os.path.exists(file_mp3):
            raise RuntimeError("MP3 audio faylini yaratishda xatolik yuz berdi.")

        return {
            'filepath': file_mp3,
            'title': title,
            'performer': uploader,
            'duration': int(duration)
        }

    return await asyncio.to_thread(_download)

async def search_and_download_music(query: str) -> dict:
    """
    Searches song by title/keyword and downloads MP3 (async).
    """
    def _search():
        unique_id = str(uuid.uuid4())[:8]
        output_template = os.path.join(DOWNLOAD_DIR, f"music_{unique_id}.%(ext)s")
        
        opts = get_yt_dlp_options({
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
        
        search_query = f"ytsearch1:{query} audio song"
        with yt_dlp.YoutubeDL(opts) as ytdl:
            info = ytdl.extract_info(search_query, download=True)
            if 'entries' in info and info['entries']:
                entry = info['entries'][0]
                title = entry.get('title', query)
                uploader = entry.get('uploader', 'Unknown Artist')
                duration = entry.get('duration', 0)
                file_mp3 = os.path.join(DOWNLOAD_DIR, f"music_{unique_id}.mp3")
                
                return {
                    'filepath': file_mp3,
                    'title': title,
                    'performer': uploader,
                    'duration': int(duration)
                }
            raise RuntimeError("Musiqa topilmadi.")

    return await asyncio.to_thread(_search)
