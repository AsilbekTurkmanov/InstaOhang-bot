from services.youtube_parser import parse_youtube_url, extract_youtube_url_from_text


def test_parse_valid_youtube_watch_url():
    parsed = parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert parsed is not None
    assert parsed.video_id == "dQw4w9WgXcQ"
    assert parsed.canonical_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert parsed.is_shorts is False


def test_parse_valid_youtu_be_url():
    parsed = parse_youtube_url("https://youtu.be/6VC1kCodFtI?si=abc123xyz")
    assert parsed is not None
    assert parsed.video_id == "6VC1kCodFtI"
    assert parsed.canonical_url == "https://www.youtube.com/watch?v=6VC1kCodFtI"
    assert parsed.is_shorts is False


def test_parse_valid_shorts_url():
    parsed = parse_youtube_url("https://www.youtube.com/shorts/3f5gH7jK9lm")
    assert parsed is not None
    assert parsed.video_id == "3f5gH7jK9lm"
    assert parsed.is_shorts is True


def test_extract_youtube_from_text():
    text = "Buni ko'ring https://youtu.be/dQw4w9WgXcQ juda ajoyib qo'shiq!"
    extracted = extract_youtube_url_from_text(text)
    assert extracted is not None
    assert "dQw4w9WgXcQ" in extracted
    parsed = parse_youtube_url(text)
    assert parsed is not None
    assert parsed.video_id == "dQw4w9WgXcQ"


def test_reject_invalid_youtube_urls():
    assert parse_youtube_url("https://google.com") is None
    assert parse_youtube_url("https://youtube.com/channel/123") is None
    assert parse_youtube_url("not a url at all") is None
