from datetime import datetime, timezone
import nylb.collectors.google_trends as gt

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)
INTEREST = {
    "베이글": [{"date": "2026-05-28", "value": 40}, {"date": "2026-05-30", "value": 80}],
    "소금빵": [{"date": "2026-05-28", "value": 10}, {"date": "2026-05-30", "value": 15}],
}


def test_parse_builds_search_terms():
    items = gt._parse(INTEREST, {}, "menu", NOW)
    assert {it.title for it in items} == {"베이글", "소금빵"}
    bagel = next(it for it in items if it.title == "베이글")
    assert bagel.source == "google_trends" and bagel.type == "search_term"
    assert bagel.metrics["interest"] == 80.0   # latest
    assert bagel.metrics["peak"] == 80.0


def test_collect_handles_error(monkeypatch):
    def boom(query, settings):
        raise RuntimeError("trends blocked")
    monkeypatch.setattr(gt, "_fetch", boom)
    res = gt.collect({"keywords": ["베이글"]}, "menu", settings={}, collected_at=NOW)
    assert res.items == []
    assert res.errors[0].source == "google_trends"
