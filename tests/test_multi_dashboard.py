from datetime import datetime, timezone
from nylb.core.schema import Item, ScanResult
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data
from nylb.report.html import build_multi_dashboard, build_dashboard

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _board(term):
    it = Item(source="naver_datalab", lens="menu", type="search_term", title=term,
              collected_at=NOW, raw={"series": [{"date": "2026-05-01", "value": 80.0},
                                                  {"date": "2026-05-02", "value": 85.0}]})
    r = ScanResult(run_id="r", store_id="nylb", lens="menu", query={"keywords": [term]},
                   items=[it], started_at=NOW, finished_at=NOW)
    return build_board(r, extract_chart_data(r))


def test_multi_dashboard_has_tabs_and_both_boards():
    lenses = [{"key": "menu", "label": "메뉴", "icon": "🥯", "board": _board("베이글")},
              {"key": "beverage", "label": "음료", "icon": "🥤", "board": _board("아메리카노")}]
    html = build_multi_dashboard(lenses)
    assert "const LENSES" in html
    assert "메뉴" in html and "음료" in html
    assert "renderBoard" in html
    assert "베이글" in html and "아메리카노" in html


def test_single_build_dashboard_backward_compatible():
    it = Item(source="naver_datalab", lens="menu", type="search_term", title="베이글",
              collected_at=NOW, raw={"series": [{"date": "2026-05-01", "value": 80.0}]})
    r = ScanResult(run_id="r", store_id="nylb", lens="menu", query={"keywords": ["베이글"]},
                   items=[it], started_at=NOW, finished_at=NOW)
    html = build_dashboard(r, extract_chart_data(r))
    assert "const LENSES" in html and "베이글" in html
