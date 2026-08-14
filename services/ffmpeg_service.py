"""Async FFmpeg service with bounded concurrency and safe fallbacks."""

import asyncio
import logging
import os
import shutil

from config import DOWNLOAD_DIR, FFMPEG_PATH

logger = logging.getLogger(__name__)
FFMPEG_SEMAPHORE = asyncio.Semaphore(3)
FFMPEG_TIMEOUT_SEC = 180


def get_ffmpeg_bin() -> str:
    if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
        return FFMPEG_PATH
    return shutil.which("ffmpeg") or "ffmpeg"


async def _run_ffmpeg(args: list[str], operation: str = "ffmpeg") -> None:
    proc = None
    async with FFMPEG_SEMAPHORE:
        try:
            proc = await asyncio.create_subprocess_exec(
                get_ffmpeg_bin(), *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=FFMPEG_TIMEOUT_SEC)
            except asyncio.TimeoutError as exc:
                proc.kill()
                await proc.wait()
                raise RuntimeError(f"{operation}: vaqt tugadi.") from exc
            if proc.returncode != 0:
                detail = stderr.decode("utf-8", errors="ignore")[-500:]
                logger.error("FFmpeg %s failed: %s", operation, detail)
                raise RuntimeError(f"{operation}: FFmpeg xatosi yuz berdi.")
        finally:
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass


async def convert_to_round_video(input_path: str, output_path: str | None = None) -> str:
    if not output_path:
        output_path = f"{os.path.splitext(input_path)[0]}_round.mp4"
    args = [
        "-y", "-threads", "0", "-i", input_path,
        "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", "crop=min(iw\,ih):min(iw\,ih),scale=640:640,setsar=1",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-pix_fmt", "yuv420p",
        "-t", "60", output_path,
    ]
    try:
        await _run_ffmpeg(args, "convert_to_round_video")
    except RuntimeError:
        # Silent videos must still become valid Video Notes.
        fallback = [
            "-y", "-threads", "0", "-i", input_path, "-an",
            "-vf", "crop=min(iw\,ih):min(iw\,ih),scale=640:640,setsar=1",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
            "-pix_fmt", "yuv420p", "-t", "60", output_path,
        ]
        await _run_ffmpeg(fallback, "convert_to_round_video_fallback")
    return output_path


async def extract_audio_from_video(input_path: str, output_mp3_path: str | None = None) -> str:
    if not output_mp3_path:
        output_mp3_path = f"{os.path.splitext(input_path)[0]}.mp3"
    await _run_ffmpeg([
        "-y", "-threads", "0", "-i", input_path, "-vn",
        "-acodec", "libmp3lame", "-ab", "192k", "-ar", "44100", output_mp3_path,
    ], "extract_audio_from_video")
    return output_mp3_path


async def change_video_speed(input_path: str, speed: float = 1.5, output_path: str | None = None) -> str:
    if speed <= 0:
        raise ValueError("speed must be greater than zero")
    if not output_path:
        output_path = f"{os.path.splitext(input_path)[0]}_speed_{speed}.mp4"

    pts = 1.0 / speed
    atempo = max(0.5, min(2.0, speed))
    args = [
        "-y", "-threads", "0", "-i", input_path,
        "-filter_complex", f"[0:v]setpts={pts:.4f}*PTS[v];[0:a]atempo={atempo:.2f}[a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast", output_path,
    ]
    try:
        await _run_ffmpeg(args, "change_video_speed")
    except RuntimeError:
        # A video may have no audio stream. In that case process video only.
        fallback = [
            "-y", "-threads", "0", "-i", input_path,
            "-an", "-vf", f"setpts={pts:.4f}*PTS",
            "-c:v", "libx264", "-preset", "ultrafast", output_path,
        ]
        await _run_ffmpeg(fallback, "change_video_speed_video_only")
    return output_path
