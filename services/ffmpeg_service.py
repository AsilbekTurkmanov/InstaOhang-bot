import os
import asyncio
import logging
from config import FFMPEG_PATH, DOWNLOAD_DIR

logger = logging.getLogger(__name__)

import shutil

def get_ffmpeg_bin():
    if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
        return FFMPEG_PATH
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    return "ffmpeg"

async def convert_to_round_video(input_path: str, output_path: str = None) -> str:
    """
    Converts a standard video to Telegram 1:1 circular Video Note (MP4).
    Crops to center square and resizes to 640x640 asynchronously with ultrafast encoding.
    """
    if not output_path:
        base = os.path.splitext(input_path)[0]
        output_path = f"{base}_round.mp4"
    
    ffmpeg_bin = get_ffmpeg_bin()
    filter_complex = "crop='min(iw,ih)':'min(iw,ih)',scale=640:640"
    
    args = [
        "-y",
        "-threads", "0",
        "-i", input_path,
        "-vf", filter_complex,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "24",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-pix_fmt", "yuv420p",
        "-t", "60",
        output_path
    ]
    
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_bin, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='ignore')
        logger.error(f"FFmpeg error: {err_msg}")
        raise RuntimeError("Dumaloq video aylantirishda xatolik yuz berdi.")
        
    return output_path

async def extract_audio_from_video(input_path: str, output_mp3_path: str = None) -> str:
    """
    Extracts high quality MP3 audio from a video file asynchronously with multithreading.
    """
    if not output_mp3_path:
        base = os.path.splitext(input_path)[0]
        output_mp3_path = f"{base}.mp3"
        
    ffmpeg_bin = get_ffmpeg_bin()
    
    args = [
        "-y",
        "-threads", "0",
        "-i", input_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-ab", "192k",
        "-ar", "44100",
        output_mp3_path
    ]
    
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_bin, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='ignore')
        logger.error(f"Audio extraction failed: {err_msg}")
        raise RuntimeError("Videodan audio ajratib olishda xatolik yuz berdi.")
        
    return output_mp3_path

async def change_video_speed(input_path: str, speed: float = 1.5, output_path: str = None) -> str:
    """
    Changes video speed (e.g. 1.5x fast or 0.8x slow) asynchronously with ultrafast encoding.
    """
    if not output_path:
        base = os.path.splitext(input_path)[0]
        output_path = f"{base}_speed_{speed}.mp4"
        
    ffmpeg_bin = get_ffmpeg_bin()
    pts_val = 1.0 / speed
    
    args = [
        "-y",
        "-threads", "0",
        "-i", input_path,
        "-filter_complex", f"[0:v]setpts={pts_val}*PTS[v];[0:a]atempo={speed}[a]",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        output_path
    ]
    
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_bin, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='ignore')
        logger.error(f"Speed change failed: {err_msg}")
        raise RuntimeError("Video tezligini o'zgartirishda xatolik yuz berdi.")
        
    return output_path
