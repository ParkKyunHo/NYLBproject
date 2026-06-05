from datetime import datetime, timezone

from nylb.core.schema import Item, ScanResult
from nylb.report.board import build_board

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _series(values: list[float]) -> list[dict]:
    return [{"date": f"2026-05-{i+1:02d}", "value": v} for i, v in enumerate(values)]


def _trend_item(source: str, term: str, values: list[float]) -> Item:
    return Item(source=source, lens="menu", type="search_term", title=term,
                collected_at=NOW, raw={"series": _series(values)})


def _rising(query: str, value: float) -> Item:
    return Item(source="google_trends", lens="menu", type="rising_query",
                title=query, collected_at=NOW,
                metrics={"value": value}, raw={"seed": "베이글"})


def _result(items: list[Item]) -> ScanResult:
    return ScanResult(run_id="2026-06-06-menu-test", store_id="nylb", lens="menu",
                      query={"keywords": ["베이글", "소금빵"], "synonyms": {}},
                      items=items, dropped_by_source={"naver": 2},
                      started_at=NOW, finished_at=NOW)


def test_board_has_core_signals_with_captions_and_no_verdict_keys():
    from nylb.report.chart_data import extract_chart_data
    items = [
        _trend_item("naver_datalab", "베이글", [80, 82, 85, 87]),
        _trend_item("naver_datalab", "소금빵", [60, 50, 40, 30]),
        _trend_item("naver_datalab", "두바이초콜릿", [20, 22, 23, 23]),
        _rising("비키 베이글", 10250),
    ]
    board = build_board(_result(items), extract_chart_data(_result(items)))

    assert {c["term"] for c in board["core_signals"]} == {"베이글", "소금빵"}
    assert all(c["caption"] for c in board["core_signals"])
    assert "비키 베이글" in {u["query"] for u in board["unverified_raw"]}
    assert "비키 베이글" not in {r["term"] for r in board["radar"]}
    for forbidden in ("action_plan", "risks", "menu_opportunities",
                      "top_insights", "trend_verdicts", "syn", "synthesis"):
        assert forbidden not in board
    assert any("naver" in d["note"] for d in board["data_trust"])
    assert board["chart"]["dates"] and board["chart"]["series"]


def test_build_dashboard_is_data_driven_two_args():
    from nylb.report.chart_data import extract_chart_data
    from nylb.report.html import build_dashboard
    items = [_trend_item("naver_datalab", "베이글", [80, 82, 85, 87]),
             _rising("비키 베이글", 10250)]
    result = _result(items)
    html = build_dashboard(result, extract_chart_data(result))
    assert "<!DOCTYPE html>" in html
    assert '"core_signals"' in html
    assert '"unverified_raw"' in html
    assert '"syn"' not in html
    assert "비키 베이글" in html
