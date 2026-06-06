from nylb.collectors import naver_news


class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def test_collect_returns_headlines_per_term(monkeypatch):
    def fake_get(url, params, headers, timeout):
        return _Resp({"items": [
            {"title": "<b>아우어</b> 신메뉴 출시", "link": "http://n/1",
             "pubDate": "Mon, 02 Jun 2026 09:00:00 +0900"},
            {"title": "두 번째 기사", "link": "http://n/2", "pubDate": ""},
        ]})
    monkeypatch.setattr(naver_news.httpx, "get", fake_get)
    out = naver_news.collect(["아우어베이커리"],
                             settings={"naver_client_id": "x", "naver_client_secret": "y"},
                             max_per_term=3)
    assert "아우어베이커리" in out
    first = out["아우어베이커리"][0]
    assert first["title"] == "아우어 신메뉴 출시"
    assert first["link"] == "http://n/1"


def test_missing_credentials_returns_empty(monkeypatch):
    out = naver_news.collect(["x"], settings={}, max_per_term=3)
    assert out == {}


def test_error_is_swallowed_per_term(monkeypatch):
    def boom(url, params, headers, timeout):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(naver_news.httpx, "get", boom)
    out = naver_news.collect(["a", "b"],
                             settings={"naver_client_id": "x", "naver_client_secret": "y"})
    assert out == {}  # all errored → empty, no raise
