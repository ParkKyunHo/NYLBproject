from datetime import datetime, timezone
import nylb.collectors.naver_datalab as dl

NOW = datetime(2026, 6, 4, tzinfo=timezone.utc)
FIXTURE = {
    "results": [
        {"title": "베이글",
         "series": [{"date": "2026-05-30", "value": 40.0},
                    {"date": "2026-06-04", "value": 70.0}]},
        {"title": "두바이초콜릿",
         "series": [{"date": "2026-05-30", "value": 5.0},
                    {"date": "2026-06-04", "value": 12.0}]},
    ]
}


def test_parse_builds_search_terms():
    items = dl._parse(FIXTURE, {}, "menu", NOW)
    assert {it.title for it in items} == {"베이글", "두바이초콜릿"}
    bagel = next(it for it in items if it.title == "베이글")
    assert bagel.source == "naver_datalab" and bagel.type == "search_term"
    assert bagel.metrics["interest"] == 70.0      # latest ratio
    assert bagel.metrics["peak"] == 70.0          # max ratio
    assert bagel.raw["series"][0] == {"date": "2026-05-30", "value": 40.0}


def test_fetch_batches_into_groups_of_five(monkeypatch):
    calls = []

    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"results": []}

    def fake_post(url, json, headers, timeout):
        calls.append(json["keywordGroups"])
        return FakeResp()

    monkeypatch.setattr(dl.httpx, "post", fake_post)
    query = {"keywords": ["a", "b", "c"], "radar_watchlist": ["d", "e", "f", "g"]}
    dl._fetch(query, {"naver_client_id": "x", "naver_client_secret": "y"})
    assert len(calls) == 2                  # 7 terms -> 5 + 2
    assert len(calls[0]) == 5 and len(calls[1]) == 2


def test_collect_handles_error(monkeypatch):
    def boom(query, settings):
        raise RuntimeError("429 rate")
    monkeypatch.setattr(dl, "_fetch", boom)
    res = dl.collect({"keywords": ["베이글"]}, "menu", settings={}, collected_at=NOW)
    assert res.items == []
    assert res.errors[0].source == "naver_datalab"


def test_fetch_requires_credentials():
    import pytest
    with pytest.raises(RuntimeError):
        dl._fetch({"keywords": ["베이글"]}, {})
