from datetime import datetime, timezone
import httpx
import nylb.collectors.youtube as yt

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)

_SEARCH_RESP = {"items": [
    {"id": {"videoId": "abc123"}, "snippet": {"title": "베이글 신메뉴 리뷰",
        "description": "요즘 핫한 베이글", "channelTitle": "빵튜브",
        "publishedAt": "2026-05-30T10:00:00Z"}},
    {"id": {"kind": "channel"}, "snippet": {"title": "skip me"}},  # no videoId
]}
_VIDEOS_RESP = {"items": [
    {"id": "abc123", "snippet": {"title": "베이글 신메뉴 리뷰",
        "description": "요즘 핫한 베이글", "channelTitle": "빵튜브",
        "publishedAt": "2026-05-30T10:00:00Z"},
     "statistics": {"viewCount": "12345", "likeCount": "678", "commentCount": "90"}},
]}


class _Resp:
    def __init__(self, data): self._data = data
    def raise_for_status(self): pass
    def json(self): return self._data


def _fake_get(search=_SEARCH_RESP, videos=_VIDEOS_RESP, fail_videos=False):
    def get(url, params=None, timeout=None, headers=None):
        if url == yt._SEARCH_URL:
            return _Resp(search)
        if url == yt._VIDEOS_URL:
            if fail_videos:
                raise httpx.HTTPError("videos boom")
            return _Resp(videos)
        raise AssertionError(f"unexpected url {url}")
    return get


def test_collect_enriches_with_statistics(monkeypatch):
    monkeypatch.setattr(yt.httpx, "get", _fake_get())
    res = yt.collect({"keywords": ["베이글"]}, "menu",
                     settings={"youtube_api_key": "k"}, collected_at=NOW)
    assert len(res.items) == 1 and res.errors == []
    it = res.items[0]
    assert it.source == "youtube" and it.type == "video"
    assert it.url == "https://youtu.be/abc123"
    assert it.author == "빵튜브"
    assert it.metrics["views"] == 12345
    assert it.metrics["likes"] == 678
    assert it.metrics["comments"] == 90
    assert it.published_at == datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)


def test_collect_graceful_when_videos_list_fails(monkeypatch):
    monkeypatch.setattr(yt.httpx, "get", _fake_get(fail_videos=True))
    res = yt.collect({"keywords": ["베이글"]}, "menu",
                     settings={"youtube_api_key": "k"}, collected_at=NOW)
    assert len(res.items) == 1                 # search results survive
    assert res.items[0].metrics["views"] == 0  # no stats → zero
    assert res.errors == []


def test_collect_missing_key_errors(monkeypatch):
    res = yt.collect({"keywords": ["베이글"]}, "menu", settings={}, collected_at=NOW)
    assert res.items == []
    assert res.errors[0].source == "youtube"
    assert "YOUTUBE_API_KEY" in res.errors[0].message
