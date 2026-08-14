import pytest
from services.instagram_parser import parse_instagram_url


def test_parse_valid_reel_url():
    url = "https://www.instagram.com/reel/C1234567890/?utm_source=ig_web_copy_link"
    parsed = parse_instagram_url(url)
    assert parsed is not None
    assert parsed.shortcode == "C1234567890"
    assert parsed.canonical_url == "https://www.instagram.com/p/C1234567890/"
    assert parsed.media_type == "reel"


def test_parse_valid_post_url():
    url = "https://instagram.com/p/DB_xyz123/"
    parsed = parse_instagram_url(url)
    assert parsed is not None
    assert parsed.shortcode == "DB_xyz123"
    assert parsed.canonical_url == "https://www.instagram.com/p/DB_xyz123/"
    assert parsed.media_type == "p"


def test_parse_invalid_url():
    assert parse_instagram_url("https://google.com") is None
    assert parse_instagram_url("not_a_url") is None
    assert parse_instagram_url("https://instagram.com/p/") is None
