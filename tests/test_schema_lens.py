from datetime import datetime, timezone

from nylb.core.schema import Item

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def test_item_accepts_arbitrary_lens_name():
    # lens names are config-driven (industry-agnostic) — any string must validate
    for lens in ["menu", "beverage", "chicken", "whatever"]:
        it = Item(source="naver_datalab", lens=lens, type="search_term",
                  title="x", collected_at=NOW)
        assert it.lens == lens
