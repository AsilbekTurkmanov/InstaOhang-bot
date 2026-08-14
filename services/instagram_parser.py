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


def parse_instagram_url(url: str) -> Optional[ParsedInstagramUrl]:
    """Validate an Instagram URL and preserve its actual media route."""
    if not url:
        return None

    raw = str(url).strip()
    parsed = urlparse(raw)
    host = parsed.netloc.lower().split(":", 1)[0]
    if parsed.scheme.lower() not in {"http", "https"} or host not in {"instagram.com", "www.instagram.com"}:
        return None

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) != 2 or parts[0].lower() not in {"p", "reel", "reels", "tv"}:
        return None

    route = parts[0].lower()
    shortcode = parts[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,40}", shortcode):
        return None

    media_type = "reel" if route in {"reel", "reels"} else route
    canonical_url = f"https://www.instagram.com/{route}/{shortcode}/"
    return ParsedInstagramUrl(raw, canonical_url, media_type, shortcode)
