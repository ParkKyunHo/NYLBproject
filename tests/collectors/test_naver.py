from datetime import datetime, timezone
import nylb.collectors.naver as nv

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)
FIXTURE = {
    "items": [
        {
            "title": "<b>베이글</b> 맛집 후기",
            "link": "https://blog.naver.com/x/1",
            "description": "요즘 <b>핫한</b> 곳",
            "bloggername": "빵순이",
            "postdate": "20260530",
        }
    ]
}


def test_parse_strips_html():
    items = nv._parse(FIXTURE, {"keywords": ["베이글"]}, "menu", NOW)
    assert len(items) == 1
    it = items[0]
    assert it.source == "naver" and it.type == "blog"
    assert it.title == "베이글 맛집 후기"
    assert it.text == "요즘 핫한 곳"
    assert it.url == "https://blog.naver.com/x/1"
    assert it.author == "빵순이"
    assert it.published_at == datetime(2026, 5, 30, tzinfo=timezone.utc)


def test_fetch_uses_relevance_sort(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"items": []}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update(params or {})
        return _Resp()

    monkeypatch.setattr(nv.httpx, "get", fake_get)
    nv._fetch({"keywords": ["베이글"]},
              {"naver_client_id": "a", "naver_client_secret": "b"})
    assert captured.get("sort") == "sim"


def test_parse_postdate_invalid_values_do_not_crash():
    assert nv._parse_postdate("20261340") is None   # 8 digits but month 13 / day 40
    assert nv._parse_postdate("20260500") is None   # day 00
    assert nv._parse_postdate("2026053") is None    # 7 chars
    assert nv._parse_postdate("2026ab30") is None   # non-digit
    assert nv._parse_postdate(None) is None
    assert nv._parse_postdate("") is None
    assert nv._parse_postdate("20260530") == datetime(2026, 5, 30, tzinfo=timezone.utc)


def test_collect_handles_error(monkeypatch):
    def boom(query, settings):
        raise RuntimeError("401 auth")
    monkeypatch.setattr(nv, "_fetch", boom)
    res = nv.collect({"keywords": ["베이글"]}, "menu", settings={}, collected_at=NOW)
    assert res.items == []
    assert res.errors[0].source == "naver"
