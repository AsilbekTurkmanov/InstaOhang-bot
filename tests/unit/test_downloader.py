import pytest
from services.downloader import get_yt_dlp_options, USER_AGENTS


def test_get_yt_dlp_options():
    opts = get_yt_dlp_options()
    assert "user_agent" in opts
    assert "http_headers" in opts
    assert opts["user_agent"] in USER_AGENTS
    # Check consistent User-Agent between top level and http_headers
    assert opts["user_agent"] == opts["http_headers"]["User-Agent"]
    # Check HTTPS verification is NOT disabled
    assert "nocheckcertificate" not in opts
