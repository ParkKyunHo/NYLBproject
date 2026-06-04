from datetime import datetime, timezone
import nylb.collectors.google_trends as gt

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)
PAYLOAD = {
    "interest": {
        "베이글": [{"date": "2026-05-28", "value": 40}, {"date": "2026-05-30", "value": 80}],
        "소금빵": [{"date": "2026-05-28", "value": 10}, {"date": "2026-05-30", "value": 15}],
    },
    "rising": [{"seed": "베이글", "query": "베이글 샌드위치", "value": 250}],
}


def test_parse_builds_search_terms():
    items = gt._parse(PAYLOAD, {}, "menu", NOW)
    terms = [it for it in items if it.type == "search_term"]
    assert {it.title for it in terms} == {"베이글", "소금빵"}
    bagel = next(it for it in terms if it.title == "베이글")
    assert bagel.source == "google_trends"
    assert bagel.metrics["interest"] == 80.0   # latest
    assert bagel.metrics["peak"] == 80.0


def test_parse_emits_rising_queries():
    items = gt._parse(PAYLOAD, {}, "menu", NOW)
    rising = [it for it in items if it.type == "rising_query"]
    assert len(rising) == 1
    assert rising[0].title == "베이글 샌드위치"
    assert rising[0].metrics["value"] == 250.0
    assert rising[0].raw["seed"] == "베이글"


def test_parse_handles_missing_keys():
    items = gt._parse({}, {}, "menu", NOW)
    assert items == []


def test_rising_value_coercion():
    assert gt._rising_value(250) == 250
    assert gt._rising_value("90") == 90
    assert gt._rising_value("Breakout") == 9999
    assert gt._rising_value("breakout") == 9999
    assert gt._rising_value("n/a") == 0


def test_collect_handles_error(monkeypatch):
    def boom(query, settings):
        raise RuntimeError("trends blocked")
    monkeypatch.setattr(gt, "_fetch", boom)
    res = gt.collect({"keywords": ["베이글"]}, "menu", settings={}, collected_at=NOW)
    assert res.items == []
    assert res.errors[0].source == "google_trends"
