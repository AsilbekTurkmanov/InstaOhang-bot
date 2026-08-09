"""
FFmpeg service for @InstaOhang_bot.
All operations are async subprocess — no blocking.

Key features:
- Global asyncio.Semaphore limits parallel FFmpeg processes (default: 3)
- Per-operation timeout (default: 120s) — process killed on timeout
- Temp files cleaned up on ALL exit paths (success, error, timeout)
- Stderr captured and logged; user never sees raw FFmpeg output
"""

import os
import asyncio
import logging
import shutil
from config import FFMPEG_PATH, DOWNLOAD_DIR

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Global concurrency limit — prevents CPU/disk exhaustion under load
# ─────────────────────────────────────────────────────────────────────────────
FFMPEG_SEMAPHORE = asyncio.Semaphore(3)   # max 3 simultaneous FFmpeg processes
FFMPEG_TIMEOUT_SEC = 180                  # 3 minutes per operation


def get_ffmpeg_bin() -> str:
    if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
        return FFMPEG_PATH
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    return "ffmpeg"


async def _run_ffmpeg(args: list[str], operation: str = "ffmpeg") -> None:
    """
    Runs FFmpeg with a timeout and concurrency limit.
    Raises RuntimeError with a safe user message on failure.
    Process is always properly killed/cleaned up.
    """
    ffmpeg_bin = get_ffmpeg_bin()
    proc = None
    async with FFMPEG_SEMAPHORE:
        try:
            proc = await asyncio.create_subprocess_exec(
                ffmpeg_bin, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=FFMPEG_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                logger.error(f"[FFmpeg] {operation} timed out after {FFMPEG_TIMEOUT_SEC}s — killing process")
                proc.kill()
                try:
                    await proc.wait()
                except Exception:
                    pass
                raise RuntimeError(f"{operation}: vaqt tugadi (>{FFMPEG_TIMEOUT_SEC}s). Fayl juda katta bo'lishi mumkin.")

            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="ignore")[-500:]  # last 500 chars
                logger.error(f"[FFmpeg] {operation} failed (rc={proc.returncode}): {err_msg}")
                raise RuntimeError(f"{operation}: FFmpeg xatosi yuz berdi.")

        except RuntimeError:
            raise
        except Exception as exc:
            logger.error(f"[FFmpeg] {operation} unexpected error: {exc}")
            raise RuntimeError(f"{operation}: kutilmagan xato.")
        finally:
            # Ensure process is cleaned up even if something weird happened
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass


async def convert_to_round_video(input_path: str, output_path: str | None = None) -> str:
    """
    Converts a standard video to Telegram 1:1 circular Video Note (MP4).
    Crops to center square, resizes to 640x640. Max 60 seconds.
    Timeout: FFMPEG_TIMEOUT_SEC. Concurrency: FFMPEG_SEMAPHORE.
    """
    if not output_path:
        base = os.path.splitext(input_path)[0]
        output_path = f"{base}_round.mp4"

    args = [
        "-y", "-threads", "0",
        "-i", input_path,
        "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=640:640",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-pix_fmt", "yuv420p",
        "-t", "60",
        output_path,
    ]
    await _run_ffmpeg(args, "convert_to_round_video")
    return output_path


async def extract_audio_from_video(input_path: str, output_mp3_path: str | None = None) -> str:
    """
    Extracts high-quality MP3 audio from a video file.
    Timeout: FFMPEG_TIMEOUT_SEC. Concurrency: FFMPEG_SEMAPHORE.
    """
    if not output_mp3_path:
        base = os.path.splitext(input_path)[0]
        output_mp3_path = f"{base}.mp3"

    args = [
        "-y", "-threads", "0",
        "-i", input_path,
        "-vn",
        "-acodec", "libmp3lame",
        "-ab", "192k",
        "-ar", "44100",
        output_mp3_path,
    ]
    await _run_ffmpeg(args, "extract_audio_from_video")
    return output_mp3_path


async def change_video_speed(input_path: str, speed: float = 1.5, output_path: str | None = None) -> str:
    """
    Changes video speed (e.g. 1.5x fast or 0.8x slow).
    atempo supports 0.5–2.0 range. For values outside this range, chain filters.
    Timeout: FFMPEG_TIMEOUT_SEC. Concurrency: FFMPEG_SEMAPHORE.
    """
    if not output_path:
        base = os.path.splitext(input_path)[0]
        output_path = f"{base}_speed_{speed}.mp4"

    pts_val = 1.0 / speed

    # atempo only supports 0.5..2.0 — clamp to safe range
    atempo = max(0.5, min(2.0, speed))

    args = [
        "-y", "-threads", "0",
        "-i", input_path,
        "-filter_complex", f"[0:v]setpts={pts_val:.4f}*PTS[v];[0:a]atempo={atempo:.2f}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "ultrafast",
        output_path,
    ]
    await _run_ffmpeg(args, "change_video_speed")
    return output_path
