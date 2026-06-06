from datetime import datetime, timezone

from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore
from nylb.core.discover import discover_candidates
from nylb.core.schema import Item, ScanResult

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def test_scan_flatten_works_for_a_chicken_shop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = {"keywords": ["치킨", "교촌"], "anchor": "치킨", "sources": [],
           "radar": {"flavor": ["양념", "마라"], "brands": ["bbq", "굽네"]}}
    r = run_scan("menu", store_id="s", lens_config=cfg, settings={},
                 store=LocalJsonStore(), run_id="r", collected_at=NOW, collectors={})
    assert r.query["anchor"] == "치킨"
    assert r.query["radar_categories"]["bbq"] == "brands"
    items = [Item(source="youtube", lens="menu", type="video", title="마라 치킨 먹방", collected_at=NOW),
             Item(source="youtube", lens="menu", type="video", title="마라 치킨 후기", collected_at=NOW)]
    res = ScanResult(run_id="r", store_id="s", lens="menu",
                     query={"keywords": ["치킨"], "radar_categories": {}, "synonyms": {}},
                     items=items, started_at=NOW, finished_at=NOW)
    cands = [c["term"] for c in discover_candidates(res)]
    assert "치킨" not in cands  # known excluded; engine carries no bakery/chicken bias
