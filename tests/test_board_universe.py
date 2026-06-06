from datetime import datetime, timezone

from nylb.core.schema import Item, ScanResult
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _series(vals):
    return [{"date": f"2026-05-{i+1:02d}", "value": v} for i, v in enumerate(vals)]


def _dl(term, vals):
    return Item(source="naver_datalab", lens="menu", type="search_term", title=term,
                collected_at=NOW, raw={"series": _series(vals)})


def _yt(title):
    return Item(source="youtube", lens="menu", type="video", title=title, collected_at=NOW)


def _result():
    items = [_dl("베이글", [80, 85, 90]), _dl("성심당", [200, 400, 800]),
             _yt("두바이 쫀득 쿠키 후기"), _yt("두바이 쫀득 쿠키 리뷰")]
    q = {"keywords": ["베이글"], "synonyms": {},
         "radar_categories": {"성심당": "brands"}, "anchor": "베이글"}
    return ScanResult(run_id="r", store_id="nylb", lens="menu", query=q,
                      items=items, started_at=NOW, finished_at=NOW)


def test_board_has_category_candidates_and_news_context():
    r = _result()
    chart = extract_chart_data(r)
    news = {"성심당": [{"title": "성심당 신메뉴", "link": "http://n", "date": "x"}]}
    board = build_board(r, chart, news_context=news)
    sansim = next(c for c in board["radar"] if c["term"] == "성심당")
    assert sansim["category"] == "brands"
    assert any("두바이" in c["term"] or "쫀득" in c["term"] for c in board["candidates"])
    assert board["news_context"]["성심당"][0]["title"] == "성심당 신메뉴"


def test_build_board_backward_compatible_two_args():
    r = _result()
    board = build_board(r, extract_chart_data(r))  # no news_context
    assert board["news_context"] == {}
    assert "candidates" in board
