import json
from datetime import datetime, timezone
from nylb.core.schema import Item, ScanResult
from nylb.report.chart_data import extract_chart_data
from nylb.report.html import build_dashboard

NOW = datetime(2026, 6, 4, tzinfo=timezone.utc)


def _result():
    items = [Item(source="naver_datalab", lens="menu", type="search_term", title="베이글",
                  metrics={"interest": 70, "peak": 90}, collected_at=NOW,
                  raw={"series": [{"date": "2026-06-03", "value": 90},
                                  {"date": "2026-06-04", "value": 70}]})]
    return ScanResult(run_id="2026-06-04-menu-abc123", store_id="nylb", lens="menu",
                      query={"keywords": ["베이글"]}, items=items,
                      started_at=NOW, finished_at=NOW)


def test_build_dashboard_returns_self_contained_html():
    result = _result()
    html = build_dashboard(result, extract_chart_data(result))
    assert html.startswith("<!DOCTYPE html>")
    assert "const LENSES" in html
    assert "__DATA__" not in html            # placeholder fully replaced
    assert "2026-06-04-menu-abc123" in html  # run id injected
    assert "<script" in html and "</script>" in html


def test_build_dashboard_embeds_chart_series():
    result = _result()
    html = build_dashboard(result, extract_chart_data(result))
    assert '"베이글"' in html                 # series keyword present in embedded JSON
    assert "naver_datalab" in html            # trend source label


def test_build_dashboard_has_no_stale_oneoff_hardcodes():
    """The template was ported from a one-off report; ensure no run-specific
    captions leak into every generated dashboard."""
    result = _result()
    html = build_dashboard(result, extract_chart_data(result))
    for stale in ["5/31 피크", "표본 2개", "(5 agents)", "2026-05-28 ~ 06-04",
                  "동시언급(15~18)", "(menu)</title>", "New York London"]:
        assert stale not in html, f"stale hardcode leaked: {stale}"


def test_build_dashboard_reports_error_count_and_channels():
    """Total-collected KPI must reflect real channel count + error count."""
    items = [
        Item(source="naver_datalab", lens="menu", type="search_term", title="베이글",
             metrics={"interest": 70, "peak": 90}, collected_at=NOW,
             raw={"series": [{"date": "2026-06-04", "value": 70}]}),
    ]
    from nylb.core.schema import CollectError
    result = ScanResult(run_id="r", store_id="nylb", lens="menu",
                        query={"keywords": ["베이글"]}, items=items,
                        errors=[CollectError(source="google_trends", message="429")],
                        started_at=NOW, finished_at=NOW)
    html = build_dashboard(result, extract_chart_data(result))
    assert '"errors": 1' in html


def test_radar_signals_and_rising_surface_but_stay_out_of_line_chart():
    """Watchlist + auto-discovered trends must show in the radar section,
    while the line chart stays limited to the core keywords."""
    items = [
        Item(source="naver_datalab", lens="menu", type="search_term", title="베이글",
             metrics={"interest": 87, "peak": 98}, collected_at=NOW,
             raw={"series": [{"date": "2026-06-04", "value": 87}]}),
        Item(source="naver_datalab", lens="menu", type="search_term", title="탕후루",
             metrics={"interest": 65, "peak": 65}, collected_at=NOW,
             raw={"series": [{"date": "2026-06-04", "value": 65}]}),
        Item(source="google_trends", lens="menu", type="rising_query", title="포비 베이글",
             metrics={"value": 21700}, collected_at=NOW, raw={"seed": "베이글"}),
    ]
    result = ScanResult(run_id="r", store_id="nylb", lens="menu",
                        query={"keywords": ["베이글"], "radar_watchlist": ["탕후루"]},
                        items=items, started_at=NOW, finished_at=NOW)
    html = build_dashboard(result, extract_chart_data(result))
    assert "트렌드 레이더" in html            # radar section rendered
    assert "탕후루" in html                    # watchlist signal surfaced
    assert "포비 베이글" in html               # auto-discovered rising surfaced
    chart_series = _embedded_data(html)["chart"]["series"]
    assert "베이글" in chart_series             # core keyword in the line chart
    assert "탕후루" not in chart_series         # watchlist term excluded from line chart


def test_dashboard_has_interest_ranking_and_correct_brand():
    result = _result()
    html = build_dashboard(result, extract_chart_data(result))
    assert "NEW YORK LOVE BAGEL" in html       # correct store name
    assert "New York London" not in html       # old wrong name gone
    assert "제품 관심도" in html           # ranking section present
    data = _embedded_data(html)
    ranking = data["interest_ranking"]
    assert any(r["term"] == "베이글" and r["core"] for r in ranking)


def _embedded_data(html):
    lenses = json.loads(html.split("const LENSES = ", 1)[1].split(";\n", 1)[0])
    return lenses[0]["board"]


def test_competitor_data_embedded_when_present():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="[포비베이글] 크림치즈", url="https://www.kurly.com/goods/5043336",
                  author="포비(FOURB)", metrics={"price": 8910, "base_price": 9900},
                  collected_at=NOW)]
    result = ScanResult(run_id="rc", store_id="nylb", lens="competitor",
                        query={"keywords": []}, items=items, started_at=NOW, finished_at=NOW)
    html = build_dashboard(result, extract_chart_data(result))
    assert "포비(FOURB)" in html                 # competitor data embedded for the section
    comp = _embedded_data(html)["competitors"]
    assert comp[0]["price"] == 8910 and comp[0]["brand"] == "포비(FOURB)"


def test_no_competitor_data_when_absent():
    result = _result()                       # menu result, no kurly items
    html = build_dashboard(result, extract_chart_data(result))
    assert _embedded_data(html)["competitors"] == []   # section self-hides on empty


def test_price_positioning_comparison_embedded_when_present():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="[포비베이글] 크림치즈", url="https://www.kurly.com/goods/5043336",
                  author="포비(FOURB)", metrics={"price": 8910, "base_price": 9900},
                  collected_at=NOW)]
    result = ScanResult(run_id="rc", store_id="nylb", lens="competitor",
        query={"own_products": [{"product": "플레인 크림치즈 베이글", "category": "크림치즈",
                                 "price": 4500, "match_key": "크림치즈"}],
               "competitor_products": [{"brand": "포비(FOURB)",
                   "url": "https://www.kurly.com/goods/5043336",
                   "match_key": "크림치즈", "basis": "리테일 200g"}]},
        items=items, started_at=NOW, finished_at=NOW)
    html = build_dashboard(result, extract_chart_data(result))
    comp = _embedded_data(html)["comparisons"]
    assert len(comp) == 1
    assert comp[0]["position"] == "below"
    assert comp[0]["competitor_basis"] == "리테일 200g"
    assert "syn" not in _embedded_data(html)   # board is data-driven, no synthesis key


def test_no_comparison_data_when_absent():
    result = _result()                       # menu result, no own/competitor
    html = build_dashboard(result, extract_chart_data(result))
    assert _embedded_data(html)["comparisons"] == []
