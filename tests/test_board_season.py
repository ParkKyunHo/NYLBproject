from datetime import datetime, timezone

from nylb.core.schema import Item, ScanResult
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data

NOW = datetime(2026, 6, 11, tzinfo=timezone.utc)  # June


def _daily(values):
    return [{"date": f"2026-05-{i+1:02d}", "value": v} for i, v in enumerate(values)]


def _monthly(month_values: dict[int, float], years=(2024, 2025)) -> list[dict]:
    return [{"date": f"{y}-{m:02d}-01", "value": v}
            for y in years for m, v in month_values.items()]


def _item(term, values, item_type="search_term"):
    return Item(source="naver_datalab", lens="menu", type=item_type, title=term,
                collected_at=NOW, raw={"series": values})


def _result(items):
    return ScanResult(
        run_id="2026-06-11-menu-test", store_id="nylb", lens="menu",
        query={"keywords": ["베이글"], "synonyms": {},
               "radar_categories": {"옥수수": "seasonal", "말차": "flavor",
                                    "노티드": "brands"}},
        items=items, dropped_by_source={}, started_at=NOW, finished_at=NOW)


def _board():
    flat = {m: 100.0 for m in range(1, 13)}
    corn = {m: (180.0 if m in (7, 8) else 80.0) for m in range(1, 13)}
    items = [
        _item("베이글", _daily([80, 82, 85, 87])),
        _item("말차", _daily([20, 25, 30, 40])),
        _item("옥수수", _daily([10, 11, 12, 12])),
        _item("노티드", _daily([50, 50, 50, 50])),
        _item("베이글", _monthly(flat), "search_term_monthly"),
        _item("말차", _monthly(flat), "search_term_monthly"),
        _item("옥수수", _monthly(corn), "search_term_monthly"),
    ]
    r = _result(items)
    return build_board(r, extract_chart_data(r))


def test_season_calendar_orders_entering_first():
    board = _board()
    cal = board["season_calendar"]
    assert cal, "season_calendar should not be empty"
    corn = next(e for e in cal if e["term"] == "옥수수")
    assert corn["season"]["status"] == "entering"        # June -> July/Aug peak
    assert cal[0]["term"] == "옥수수"                     # prep-window first
    assert 7 in corn["season"]["peak_months"]


def test_opportunities_scored_excluding_core_and_brands():
    board = _board()
    opps = board["opportunities"]
    terms = {o["term"] for o in opps}
    assert "베이글" not in terms and "노티드" not in terms
    assert {"말차", "옥수수"} <= terms
    for o in opps:
        assert 0 <= o["opportunity"]["score"] <= 100
        assert set(o["opportunity"]["parts"]) == {"interest", "growth",
                                                  "season", "direction"}
    scores = [o["opportunity"]["score"] for o in opps]
    assert scores == sorted(scores, reverse=True)


def test_movers_positive_momentum_products_only():
    board = _board()
    movers = board["movers"]
    assert all(m["momentum"] > 0 for m in movers)
    assert "노티드" not in {m["term"] for m in movers}
    moms = [m["momentum"] for m in movers]
    assert moms == sorted(moms, reverse=True)


def test_metrics_carry_spark_and_season():
    board = _board()
    for c in board["core_signals"] + board["radar"]:
        assert isinstance(c["spark"], list) and len(c["spark"]) <= 31
    bagel = next(c for c in board["core_signals"] if c["term"] == "베이글")
    assert bagel["season"] is not None


def test_no_verdict_keys_still_absent():
    board = _board()
    for forbidden in ("action_plan", "risks", "menu_opportunities",
                      "top_insights", "trend_verdicts", "synthesis"):
        assert forbidden not in board
    assert any("기회 점수" in d["note"] for d in board["data_trust"])
