from datetime import datetime, timezone
from nylb.core.schema import Item, CollectResult, CollectError
from nylb.core.store import LocalJsonStore
from nylb.core.scan import run_scan

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)


def fake_youtube(query, lens, *, settings, collected_at):
    return CollectResult(items=[Item(source="youtube", lens=lens, type="video",
                                     title="vid", collected_at=collected_at)])


def fake_naver_fail(query, lens, *, settings, collected_at):
    raise RuntimeError("naver down")


def test_run_scan_aggregates_and_tolerates_failure(tmp_path):
    store = LocalJsonStore(base_dir=tmp_path)
    lens_config = {"keywords": ["베이글"], "sources": ["youtube", "naver"]}
    result = run_scan(
        "menu", store_id="nylb", lens_config=lens_config, settings={},
        store=store, run_id="run1", collected_at=NOW,
        collectors={"youtube": fake_youtube, "naver": fake_naver_fail},
    )
    assert len(result.items) == 1                      # youtube succeeded
    assert result.items[0].store_id == "nylb"          # tenancy stamped
    assert any(e.source == "naver" for e in result.errors)  # naver failure captured
    assert (tmp_path / "run1.json").exists()           # persisted


def test_run_scan_adds_instagram_when_hashtags_present(tmp_path):
    calls = []
    def fake_ig(query, lens, *, settings, collected_at):
        calls.append(query.get("instagram_hashtags"))
        return CollectResult()
    store = LocalJsonStore(base_dir=tmp_path)
    lens_config = {"keywords": ["베이글"], "sources": [], "instagram_hashtags": ["베이글맛집"]}
    run_scan("content", store_id="nylb", lens_config=lens_config, settings={},
             store=store, run_id="r2", collected_at=NOW,
             collectors={"instagram": fake_ig})
    assert calls == [["베이글맛집"]]


def test_run_scan_unknown_source_recorded(tmp_path):
    store = LocalJsonStore(base_dir=tmp_path)
    lens_config = {"sources": ["bogus"]}
    result = run_scan("menu", store_id="nylb", lens_config=lens_config, settings={},
                      store=store, run_id="r3", collected_at=NOW, collectors={})
    assert any("unknown" in e.message for e in result.errors)


def test_run_scan_passes_radar_terms_in_query(tmp_path):
    seen = {}
    def fake_dl(query, lens, *, settings, collected_at):
        seen["watchlist"] = query.get("radar_watchlist")
        seen["seeds"] = query.get("radar_seeds")
        return CollectResult()
    store = LocalJsonStore(base_dir=tmp_path)
    lens_config = {"keywords": ["베이글"], "sources": ["naver_datalab"],
                   "radar_watchlist": ["두바이초콜릿"], "radar_seeds": ["디저트"]}
    run_scan("menu", store_id="nylb", lens_config=lens_config, settings={},
             store=store, run_id="r4", collected_at=NOW,
             collectors={"naver_datalab": fake_dl})
    assert seen["watchlist"] == ["두바이초콜릿"]
    assert seen["seeds"] == ["디저트"]


def test_default_collectors_include_naver_datalab():
    from nylb.core.scan import DEFAULT_COLLECTORS
    assert "naver_datalab" in DEFAULT_COLLECTORS
