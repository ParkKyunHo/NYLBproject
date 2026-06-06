from datetime import datetime, timezone

from nylb.collectors import naver

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def test_searches_each_keyword_and_dedupes(monkeypatch):
    seen = []

    def fake_get(url, params, headers, timeout):
        seen.append(params["query"])
        return _Resp({"items": [
            {"title": params["query"], "link": "http://shared", "description": "", "postdate": ""},
            {"title": params["query"] + " uniq", "link": "http://" + params["query"],
             "description": "", "postdate": ""},
        ]})
    monkeypatch.setattr(naver.httpx, "get", fake_get)
    res = naver.collect({"keywords": ["베이글", "소금빵"]}, "menu",
                        settings={"naver_client_id": "x", "naver_client_secret": "y"},
                        collected_at=NOW)
    assert seen == ["베이글", "소금빵"]
    links = [it.url for it in res.items]
    assert links.count("http://shared") == 1


def test_one_keyword_failure_tolerated(monkeypatch):
    def fake_get(url, params, headers, timeout):
        if params["query"] == "소금빵":
            raise RuntimeError("boom")
        return _Resp({"items": [{"title": "t", "link": "http://ok",
                                 "description": "", "postdate": ""}]})
    monkeypatch.setattr(naver.httpx, "get", fake_get)
    res = naver.collect({"keywords": ["베이글", "소금빵"]}, "menu",
                        settings={"naver_client_id": "x", "naver_client_secret": "y"},
                        collected_at=NOW)
    assert [it.url for it in res.items] == ["http://ok"]
    assert res.errors == []


def test_all_keywords_fail_surfaces_errors(monkeypatch):
    def boom(url, params, headers, timeout):
        raise RuntimeError("down")
    monkeypatch.setattr(naver.httpx, "get", boom)
    res = naver.collect({"keywords": ["베이글", "소금빵"]}, "menu",
                        settings={"naver_client_id": "x", "naver_client_secret": "y"},
                        collected_at=NOW)
    assert res.items == [] and len(res.errors) == 2
