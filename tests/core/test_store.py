from datetime import datetime, timezone
from nylb.core.schema import Item, ScanResult
from nylb.core.store import LocalJsonStore


def _result(run_id="r1"):
    now = datetime(2026, 6, 3, tzinfo=timezone.utc)
    return ScanResult(
        run_id=run_id, store_id="nylb", lens="menu", query={},
        items=[Item(source="youtube", lens="menu", type="video",
                    title="베이글", collected_at=now)],
        started_at=now, finished_at=now,
    )


def test_save_then_load_roundtrip(tmp_path):
    store = LocalJsonStore(base_dir=tmp_path)
    path = store.save(_result("abc"))
    assert path.exists()
    loaded = store.load("abc")
    assert loaded.run_id == "abc"
    assert loaded.items[0].title == "베이글"


def test_save_creates_dir(tmp_path):
    target = tmp_path / "nested" / "raw"
    store = LocalJsonStore(base_dir=target)
    store.save(_result("x"))
    assert (target / "x.json").exists()
