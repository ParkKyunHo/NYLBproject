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


def test_collect_handles_error(monkeypatch):
    def boom(query, settings):
        raise RuntimeError("401 auth")
    monkeypatch.setattr(nv, "_fetch", boom)
    res = nv.collect({"keywords": ["베이글"]}, "menu", settings={}, collected_at=NOW)
    assert res.items == []
    assert res.errors[0].source == "naver"
