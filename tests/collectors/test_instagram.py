from datetime import datetime, timezone
import nylb.collectors.instagram as ig

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)
MEDIA = {
    "data": [
        {
            "id": "1", "caption": "베이글 신상 출시!", "like_count": 120,
            "comments_count": 8, "media_type": "IMAGE",
            "permalink": "https://instagram.com/p/1", "timestamp": "2026-05-30T09:00:00+0000",
        }
    ]
}


def test_parse_hashtag_media():
    items = ig._parse(MEDIA, {"instagram_hashtags": ["베이글"]}, "content", NOW)
    assert len(items) == 1
    it = items[0]
    assert it.source == "instagram" and it.type == "hashtag_media"
    assert it.metrics["likes"] == 120.0
    assert it.metrics["comments"] == 8.0
    assert it.url == "https://instagram.com/p/1"


def test_collect_no_token_skips():
    res = ig.collect({"instagram_hashtags": ["베이글"]}, "content",
                     settings={}, collected_at=NOW)
    assert res.items == []
    assert res.errors[0].source == "instagram"
    assert "token" in res.errors[0].message.lower()


def test_collect_success(monkeypatch):
    monkeypatch.setattr(ig, "_fetch", lambda query, settings: MEDIA)
    res = ig.collect({"instagram_hashtags": ["베이글"]}, "content",
                     settings={"instagram_graph_token": "t"}, collected_at=NOW)
    assert len(res.items) == 1 and res.errors == []
