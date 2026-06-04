from datetime import datetime, timezone
import pytest
import nylb.collectors.kurly as k

NOW = datetime(2026, 6, 4, tzinfo=timezone.utc)

# Synthetic page: main product (goods 5043336) + a recommendation node.
# Both carry name/basePrice/discountedPrice; the parser must pick the main one by goods id.
FIXTURE = ('<html><head>'
           '<meta property="og:title" content="[포비베이글] 크림치즈 200g 8종 (택1) - 마켓컬리">'
           '</head><body>'
           '<script id="__NEXT_DATA__" type="application/json">'
           '{"props":{"pageProps":{'
           '"product":{"no":5043336,"name":"[포비베이글] 크림치즈 200g 8종 (택1)",'
           '"basePrice":9900,"discountedPrice":8910},'
           '"recommends":[{"no":111,"name":"다른상품","basePrice":5000,"discountedPrice":4500}]'
           '}}}'
           '</script></body></html>')


def test_parse_picks_product_by_goods_id():
    pages = [{"brand": "포비(FOURB)", "url": "https://www.kurly.com/goods/5043336", "html": FIXTURE}]
    items = k._parse(pages, "competitor", NOW)
    assert len(items) == 1
    it = items[0]
    assert it.source == "kurly" and it.type == "product" and it.lens == "competitor"
    assert it.title == "[포비베이글] 크림치즈 200g 8종 (택1)"
    assert it.metrics["price"] == 8910.0
    assert it.metrics["base_price"] == 9900.0
    assert it.author == "포비(FOURB)"
    assert it.url == "https://www.kurly.com/goods/5043336"


def test_parse_skips_page_without_next_data():
    pages = [{"brand": "x", "url": "https://www.kurly.com/goods/9", "html": "<html>no data</html>"}]
    assert k._parse(pages, "competitor", NOW) == []


def test_collect_handles_error(monkeypatch):
    def boom(query, settings):
        raise RuntimeError("blocked")
    monkeypatch.setattr(k, "_fetch", boom)
    res = k.collect({"competitor_products": [{"url": "x"}]}, "competitor",
                    settings={}, collected_at=NOW)
    assert res.items == []
    assert res.errors[0].source == "kurly"


@pytest.mark.live
def test_kurly_live_smoke():
    q = {"competitor_products": [
        {"brand": "포비(FOURB)", "url": "https://www.kurly.com/goods/5043336"}]}
    res = k.collect(q, "competitor", settings={},
                    collected_at=datetime.now(timezone.utc))
    assert res.items and res.items[0].metrics["price"] > 0
