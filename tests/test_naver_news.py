from nylb.collectors import naver_news


class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


_SETTINGS = {"naver_client_id": "x", "naver_client_secret": "y"}


def test_collect_returns_gated_headlines(monkeypatch):
    def fake_get(url, params, headers, timeout):
        return _Resp({"items": [
            {"title": "<b>아우어베이커리</b> 신메뉴 출시", "link": "http://n/1",
             "description": "베이커리 신제품", "pubDate": "Mon, 02 Jun 2026 09:00:00 +0900"},
            {"title": "두 번째 기사", "link": "http://n/2", "description": "", "pubDate": ""},
        ]})
    monkeypatch.setattr(naver_news.httpx, "get", fake_get)
    out = naver_news.collect(["아우어베이커리"], settings=_SETTINGS, max_per_term=3)
    assert out["아우어베이커리"][0]["title"] == "아우어베이커리 신메뉴 출시"
    assert out["아우어베이커리"][0]["link"] == "http://n/1"
    assert len(out["아우어베이커리"]) == 1   # 무관 기사("두 번째 기사")는 게이트 탈락


def test_term_gate_drops_articles_not_mentioning_term(monkeypatch):
    def fake_get(url, params, headers, timeout):
        return _Resp({"items": [
            {"title": "오늘의 디저트 카페 소식", "link": "http://n/1",
             "description": "디저트 트렌드", "pubDate": ""},   # 용어 '복숭아' 없음
        ]})
    monkeypatch.setattr(naver_news.httpx, "get", fake_get)
    assert naver_news.collect(["복숭아"], settings=_SETTINGS) == {}


def test_context_gate_drops_non_fnb_articles(monkeypatch):
    def fake_get(url, params, headers, timeout):
        return _Resp({"items": [
            {"title": "복숭아 농가 시세 급등", "link": "http://n/1",
             "description": "올해 작황 부진으로 도매가 상승", "pubDate": ""},  # F&B 맥락어 없음
            {"title": "복숭아 디저트 신메뉴 출시한 카페", "link": "http://n/2",
             "description": "여름 시즌 한정", "pubDate": ""},
        ]})
    monkeypatch.setattr(naver_news.httpx, "get", fake_get)
    out = naver_news.collect(["복숭아"], settings=_SETTINGS)
    assert [h["link"] for h in out["복숭아"]] == ["http://n/2"]


def test_custom_context_terms_override_default(monkeypatch):
    def fake_get(url, params, headers, timeout):
        return _Resp({"items": [
            {"title": "말차 원두 로스팅 업계 동향", "link": "http://n/1",
             "description": "스페셜티", "pubDate": ""},
        ]})
    monkeypatch.setattr(naver_news.httpx, "get", fake_get)
    out = naver_news.collect(["말차"], settings=_SETTINGS, context_terms=["로스팅"])
    assert out["말차"][0]["link"] == "http://n/1"
    # 기본 F&B 리스트로는 탈락
    assert naver_news.collect(["말차"], settings=_SETTINGS) == {}


def test_over_fetch_then_caps_at_max_per_term(monkeypatch):
    captured = {}

    def fake_get(url, params, headers, timeout):
        captured.update(params)
        return _Resp({"items": [
            {"title": f"말차 디저트 {i}", "link": f"http://n/{i}",
             "description": "카페 신메뉴", "pubDate": ""} for i in range(10)]})
    monkeypatch.setattr(naver_news.httpx, "get", fake_get)
    out = naver_news.collect(["말차"], settings=_SETTINGS, max_per_term=3)
    assert captured["display"] == naver_news._FETCH   # 넉넉히 받고
    assert len(out["말차"]) == 3                       # 게이트 후 상한


def test_missing_credentials_returns_empty(monkeypatch):
    assert naver_news.collect(["x"], settings={}, max_per_term=3) == {}


def test_error_is_swallowed_per_term(monkeypatch):
    def boom(url, params, headers, timeout):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(naver_news.httpx, "get", boom)
    assert naver_news.collect(["a", "b"], settings=_SETTINGS) == {}
