from datetime import datetime, timezone
from nylb.core.schema import Item, ScanResult
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _dl(term, vals):
    return Item(source="naver_datalab", lens="beverage", type="search_term", title=term,
                collected_at=NOW, raw={"series": [{"date": f"2026-05-{i+1:02d}", "value": v}
                                                    for i, v in enumerate(vals)]})


def _result():
    items = [_dl("아메리카노", [90, 95, 100]),
             _dl("콜드브루", [70, 72, 78]),
             _dl("메가커피", [700, 750, 800]),
             _dl("스타벅스", [380, 390, 400])]
    q = {"keywords": ["아메리카노"], "synonyms": {}, "anchor": "아메리카노",
         "radar_categories": {"콜드브루": "coffee", "메가커피": "brands", "스타벅스": "brands"}}
    return ScanResult(run_id="r", store_id="nylb", lens="beverage", query=q,
                      items=items, started_at=NOW, finished_at=NOW)


def test_products_and_brands_are_split_and_brands_rescaled():
    b = build_board(_result(), extract_chart_data(_result()))
    assert "메가커피" not in {x["term"] for x in b["interest_ranking"]}
    assert "메가커피" not in {c["term"] for c in b["radar"]}
    assert "콜드브루" in {x["term"] for x in b["interest_ranking"]}
    br = {x["term"]: x["interest"] for x in b["brand_ranking"]}
    assert abs(br["메가커피"] - 100) < 0.5
    assert abs(br["스타벅스"] - 50) < 0.5
    bs = {c["term"]: c for c in b["brand_signals"]}
    assert "메가커피" in bs and bs["메가커피"]["caption"]
    assert abs(bs["메가커피"]["value"] - 100) < 0.5


def test_no_brands_yields_empty_brand_lists():
    items = [_dl("아메리카노", [100, 100, 100]), _dl("콜드브루", [50, 50, 50])]
    q = {"keywords": ["아메리카노"], "synonyms": {}, "anchor": "아메리카노",
         "radar_categories": {"콜드브루": "coffee"}}
    r = ScanResult(run_id="r", store_id="nylb", lens="beverage", query=q,
                   items=items, started_at=NOW, finished_at=NOW)
    b = build_board(r, extract_chart_data(r))
    assert b["brand_ranking"] == [] and b["brand_signals"] == []
