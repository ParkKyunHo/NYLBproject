from datetime import datetime, timezone
from nylb.core.schema import Item, CollectError, CollectResult, ScanResult


def test_item_accepts_kurly_source():
    it = Item(source="kurly", lens="competitor", type="product",
              title="크림치즈", collected_at=datetime(2026, 6, 4, tzinfo=timezone.utc))
    assert it.source == "kurly"


def _item():
    return Item(
        source="youtube", lens="menu", type="video", title="베이글",
        collected_at=datetime(2026, 6, 3, tzinfo=timezone.utc),
    )


def test_item_defaults():
    it = _item()
    assert it.store_id == "nylb"          # tenancy seam default
    assert it.metrics == {}
    assert it.url is None


def test_scanresult_roundtrip():
    now = datetime(2026, 6, 3, tzinfo=timezone.utc)
    sr = ScanResult(
        run_id="r1", store_id="nylb", lens="menu", query={"keywords": ["베이글"]},
        items=[_item()], errors=[CollectError(source="naver", message="boom")],
        started_at=now, finished_at=now,
    )
    dumped = sr.model_dump_json()
    loaded = ScanResult.model_validate_json(dumped)
    assert loaded.run_id == "r1"
    assert loaded.items[0].title == "베이글"
    assert loaded.errors[0].source == "naver"


def test_collectresult_defaults():
    cr = CollectResult()
    assert cr.items == [] and cr.errors == []


def test_item_accepts_naver_datalab_source():
    from datetime import datetime, timezone
    from nylb.core.schema import Item
    it = Item(source="naver_datalab", lens="menu", type="search_term",
              title="베이글", collected_at=datetime(2026, 6, 4, tzinfo=timezone.utc))
    assert it.source == "naver_datalab"
