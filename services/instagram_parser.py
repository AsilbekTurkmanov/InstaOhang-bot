"""
Instagram URL Parser and Canonical Normalizer Service.
Handles shortcode validation, query param stripping, and URL canonicalization.
"""

import re
from typing import Optional, NamedTuple
from urllib.parse import urlparse

INSTAGRAM_REGEX = re.compile(
    r'https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)',
    re.IGNORECASE
)

class ParsedInstagramUrl(NamedTuple):
    raw_url: str
    canonical_url: str
    media_type: str
    shortcode: str


def parse_instagram_url(url: str) -> Optional[ParsedInstagramUrl]:
    """
    Parses and normalizes an Instagram URL.
    Returns ParsedInstagramUrl if valid, None if invalid.
    """
    if not url:
        return None

    url_str = str(url).strip()
    match = INSTAGRAM_REGEX.search(url_str)
    if not match:
        return None

    shortcode = match.group(1)
    if not shortcode or len(shortcode) < 3 or len(shortcode) > 40:
        return None

    # Detect media type from path
    path_lower = urlparse(url_str).path.lower()
    if "/reel/" in path_lower or "/reels/" in path_lower:
        media_type = "reel"
    elif "/tv/" in path_lower:
        media_type = "tv"
    else:
        media_type = "p"

    # Canonical URL format: https://www.instagram.com/p/{shortcode}/
    canonical_url = f"https://www.instagram.com/p/{shortcode}/"

    return ParsedInstagramUrl(
        raw_url=url_str,
        canonical_url=canonical_url,
        media_type=media_type,
        shortcode=shortcode,
    )
