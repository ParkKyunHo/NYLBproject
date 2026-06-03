from datetime import datetime, timezone
from nylb.collectors.base import strip_html, parse_iso


def test_strip_html():
    assert strip_html("<b>베이글</b> 맛집") == "베이글 맛집"
    assert strip_html(None) == ""


def test_parse_iso_z_suffix():
    dt = parse_iso("2026-05-30T10:00:00Z")
    assert dt == datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)


def test_parse_iso_bad_returns_none():
    assert parse_iso("not-a-date") is None
    assert parse_iso(None) is None
