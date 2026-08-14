from services.instagram_parser import parse_instagram_url


def test_parse_valid_reel_url_preserves_route_and_strips_query():
    parsed = parse_instagram_url(
        "https://www.instagram.com/reel/C1234567890/?utm_source=ig_web_copy_link"
    )
    assert parsed is not None
    assert parsed.shortcode == "C1234567890"
    assert parsed.canonical_url == "https://www.instagram.com/reel/C1234567890/"
    assert parsed.media_type == "reel"


def test_parse_reels_and_tv_routes():
    reels = parse_instagram_url("https://instagram.com/reels/ABC_123/?foo=bar")
    tv = parse_instagram_url("https://www.instagram.com/tv/XYZ_123/")
    assert reels and reels.media_type == "reel"
    assert reels.canonical_url.endswith("/reels/ABC_123/")
    assert tv and tv.media_type == "tv"
    assert tv.canonical_url.endswith("/tv/XYZ_123/")


def test_parse_valid_post_url():
    parsed = parse_instagram_url("https://instagram.com/p/DB_xyz123/")
    assert parsed is not None
    assert parsed.shortcode == "DB_xyz123"
    assert parsed.canonical_url == "https://www.instagram.com/p/DB_xyz123/"
    assert parsed.media_type == "p"


def test_reject_wrong_host_and_malformed_path():
    assert parse_instagram_url("https://google.com/p/ABC123") is None
    assert parse_instagram_url("https://instagram.com/p/") is None
    assert parse_instagram_url("https://instagram.com/profile/p/ABC123") is None
    assert parse_instagram_url("javascript:https://instagram.com/p/ABC123") is None
