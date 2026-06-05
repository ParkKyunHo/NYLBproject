import os
from datetime import datetime, timezone
import nylb.core.scan as scan_mod
from nylb.core.schema import CollectResult, Item
from nylb.cli import build_run_id, main


def test_build_run_id_format():
    rid = build_run_id("menu", datetime(2026, 6, 3, tzinfo=timezone.utc))
    assert rid.startswith("2026-06-03-menu-")
    assert len(rid.split("-")[-1]) == 6


def test_scan_end_to_end(tmp_path, monkeypatch):
    # arrange: run inside a temp cwd with a minimal lenses file
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "lenses.yaml").write_text(
        "nylb:\n  lenses:\n    menu:\n      keywords: [베이글]\n      sources: [youtube]\n",
        encoding="utf-8",
    )

    def fake_youtube(query, lens, *, settings, collected_at):
        return CollectResult(items=[Item(source="youtube", lens=lens, type="video",
                                         title="베이글 영상", collected_at=collected_at)])
    monkeypatch.setattr(scan_mod, "DEFAULT_COLLECTORS", {"youtube": fake_youtube})

    # act
    code = main(["scan", "--lens", "menu"])

    # assert
    assert code == 0
    raw_files = list((tmp_path / "data" / "raw").glob("*.json"))
    digests = list((tmp_path / "data" / "raw").glob("*.digest.md"))
    assert len(raw_files) == 1 and len(digests) == 1
    assert "베이글 영상" in digests[0].read_text(encoding="utf-8")


def test_report_html_subcommand(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from pathlib import Path
    from nylb.core.schema import Item, ScanResult
    from nylb.core.store import LocalJsonStore
    from nylb import cli

    NOW = datetime(2026, 6, 4, tzinfo=timezone.utc)
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    result = ScanResult(run_id="run-x", store_id="nylb", lens="menu",
                        query={"keywords": ["베이글"]},
                        items=[Item(source="naver_datalab", lens="menu", type="search_term",
                                    title="베이글", metrics={"interest": 70, "peak": 90},
                                    collected_at=NOW,
                                    raw={"series": [{"date": "2026-06-04", "value": 70}]})],
                        started_at=NOW, finished_at=NOW)
    LocalJsonStore(base_dir=raw).save(result)

    monkeypatch.chdir(tmp_path)
    rc = cli.main(["report-html", "--run", "run-x"])
    assert rc == 0
    out = Path("reports/run-x.analysis.html")
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content      # well-formed HTML generated
    assert "run-x" in content               # run_id embedded in board data
    assert "베이글" in content              # keyword embedded in board data


def test_make_store_local_is_default():
    from nylb.cli import _make_store
    from nylb.core.store import LocalJsonStore
    assert isinstance(_make_store("local", "nylb", {}), LocalJsonStore)


def test_make_store_supabase_passes_settings(monkeypatch):
    from nylb import cli
    captured = {}

    class FakeSB:
        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr(cli, "SupabaseStore", FakeSB)
    store = cli._make_store("supabase", "nylb",
                            {"supabase_url": "u", "supabase_service_key": "k"})
    assert isinstance(store, FakeSB)
    assert captured == {"url": "u", "service_key": "k", "store_key": "nylb"}
