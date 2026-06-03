from datetime import datetime, timezone
import nylb.collectors.youtube as yt

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)
FIXTURE = {
    "items": [
        {
            "id": {"videoId": "abc123"},
            "snippet": {
                "title": "베이글 신메뉴 리뷰",
                "description": "요즘 핫한 베이글",
                "channelTitle": "빵튜브",
                "publishedAt": "2026-05-30T10:00:00Z",
            },
        },
        {"id": {"kind": "channel"}, "snippet": {"title": "skip me"}},  # no videoId
    ]
}


def test_parse_extracts_videos():
    items = yt._parse(FIXTURE, {"keywords": ["베이글"]}, "menu", NOW)
    assert len(items) == 1
    it = items[0]
    assert it.source == "youtube" and it.type == "video"
    assert it.title == "베이글 신메뉴 리뷰"
    assert it.url == "https://youtu.be/abc123"
    assert it.author == "빵튜브"
    assert it.published_at == datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)


def test_collect_handles_fetch_error(monkeypatch):
    def boom(query, settings):
        raise RuntimeError("quota exceeded")
    monkeypatch.setattr(yt, "_fetch", boom)
    res = yt.collect({"keywords": ["베이글"]}, "menu", settings={}, collected_at=NOW)
    assert res.items == []
    assert res.errors[0].source == "youtube"
    assert "quota" in res.errors[0].message


def test_collect_success(monkeypatch):
    monkeypatch.setattr(yt, "_fetch", lambda query, settings: FIXTURE)
    res = yt.collect({"keywords": ["베이글"]}, "menu", settings={}, collected_at=NOW)
    assert len(res.items) == 1 and res.errors == []
