"""YouTube URL parsing and video ID extraction."""

import re
from typing import NamedTuple, Optional
from urllib.parse import urlparse, parse_qs

YOUTUBE_REGEX = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?(?:youtube\.com/(?:watch\?v=|shorts/|live/|embed/)|youtu\.be/)([a-zA-Z0-9_-]{11})",
    re.IGNORECASE,
)


class ParsedYouTubeUrl(NamedTuple):
    raw_url: str
    video_id: str
    canonical_url: str
    is_shorts: bool


def extract_youtube_url_from_text(text: str) -> Optional[str]:
    """Extracts first YouTube URL or video ID from text."""
    if not text:
        return None
    match = YOUTUBE_REGEX.search(text)
    if match:
        return match.group(0)
    return None


def parse_youtube_url(url: str) -> Optional[ParsedYouTubeUrl]:
    """Validates and extracts video ID and canonical URL from YouTube link or text."""
    if not url:
        return None

    match = YOUTUBE_REGEX.search(str(url).strip())
    if not match:
        return None

    video_id = match.group(1)
    raw = match.group(0)
    is_shorts = "/shorts/" in raw.lower()
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"

    return ParsedYouTubeUrl(
        raw_url=raw,
        video_id=video_id,
        canonical_url=canonical_url,
        is_shorts=is_shorts,
    )
