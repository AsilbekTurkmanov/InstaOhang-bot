"""Instagram URL parsing and canonicalization."""

import re
from typing import NamedTuple, Optional
from urllib.parse import urlparse

INSTAGRAM_REGEX = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)(?:[/?#]|$)",
    re.IGNORECASE,
)


class ParsedInstagramUrl(NamedTuple):
    raw_url: str
    canonical_url: str
    media_type: str
    shortcode: str


def extract_instagram_url_from_text(text: str) -> Optional[str]:
    """Extracts first Instagram URL from text."""
    if not text:
        return None
    match = INSTAGRAM_REGEX.search(text)
    if match:
        return match.group(0)
    return None


def parse_instagram_url(url: str) -> Optional[ParsedInstagramUrl]:
    """Validate an Instagram URL and preserve its actual media route."""
    if not url:
        return None

    raw_text = str(url).strip()
    parsed_raw = urlparse(raw_text)
    if parsed_raw.scheme not in {"http", "https"}:
        return None

    match = INSTAGRAM_REGEX.search(raw_text)
    if not match:
        return None

    matched_url = match.group(0)
    parsed = urlparse(matched_url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2 or parts[0].lower() not in {"p", "reel", "reels", "tv"}:
        return None

    route = parts[0].lower()
    shortcode = parts[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,40}", shortcode):
        return None

    media_type = "reel" if route in {"reel", "reels"} else route
    canonical_url = f"https://www.instagram.com/{route}/{shortcode}/"
    return ParsedInstagramUrl(matched_url, canonical_url, media_type, shortcode)

