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
