from datetime import datetime, timezone

from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _run(lens_config, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return run_scan("menu", store_id="nylb", lens_config=lens_config, settings={},
                    store=LocalJsonStore(), run_id="r1", collected_at=NOW, collectors={})


def test_categorized_radar_flattens_with_categories_and_anchor(tmp_path, monkeypatch):
    cfg = {"keywords": ["베이글"], "anchor": "베이글", "sources": [],
           "radar": {"flavor": ["말차", "흑임자"], "brands": ["성심당"]}}
    r = _run(cfg, tmp_path, monkeypatch)
    assert set(r.query["radar_watchlist"]) == {"말차", "흑임자", "성심당"}
    assert r.query["radar_categories"] == {"말차": "flavor", "흑임자": "flavor", "성심당": "brands"}
    assert r.query["anchor"] == "베이글"


def test_legacy_flat_radar_still_works_and_anchor_defaults_to_first_keyword(tmp_path, monkeypatch):
    cfg = {"keywords": ["베이글", "소금빵"], "sources": [],
           "radar_watchlist": ["탕후루"]}
    r = _run(cfg, tmp_path, monkeypatch)
    assert r.query["radar_watchlist"] == ["탕후루"]
    assert r.query["radar_categories"] == {}
    assert r.query["anchor"] == "베이글"


def test_discover_stopwords_threaded_into_query(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = {"keywords": ["베이글"], "sources": [],
           "discover_stopwords": ["디저트", "빵집"]}
    r = run_scan("menu", store_id="nylb", lens_config=cfg, settings={},
                 store=LocalJsonStore(), run_id="r2", collected_at=NOW, collectors={})
    assert r.query["discover_stopwords"] == ["디저트", "빵집"]
