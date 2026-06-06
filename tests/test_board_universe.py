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
    # brands are now in brand_signals, not radar
    sansim = next(c for c in board["brand_signals"] if c["term"] == "성심당")
    assert sansim["category"] == "brands"
    assert "성심당" not in {c["term"] for c in board["radar"]}
    assert any("두바이" in c["term"] or "쫀득" in c["term"] for c in board["candidates"])
    assert board["news_context"]["성심당"][0]["title"] == "성심당 신메뉴"


def test_build_board_backward_compatible_two_args():
    r = _result()
    board = build_board(r, extract_chart_data(r))  # no news_context
    assert board["news_context"] == {}
    assert "candidates" in board


def test_gather_riser_news_selects_positive_momentum_terms(monkeypatch):
    from nylb.report import news as news_mod
    captured = {}
    def fake_collect(terms, *, settings, max_per_term=3):
        captured["terms"] = terms
        return {t: [{"title": t + " 기사", "link": "http://x", "date": ""}] for t in terms}
    monkeypatch.setattr(news_mod.naver_news, "collect", fake_collect)
    chart = {"trends": {"naver_datalab": {
        "라이저": {"momentum": 12.0}, "하락": {"momentum": -5.0}, "보합": {"momentum": 0.0}}}}
    out = news_mod.gather_riser_news(result=None, chart=chart, settings={"naver_client_id": "x"})
    assert captured["terms"] == ["라이저"]          # only positive momentum, sorted desc
    assert out["라이저"][0]["title"] == "라이저 기사"


def test_board_candidates_is_a_list():
    board = build_board(_result(), extract_chart_data(_result()))
    assert isinstance(board["candidates"], list)


def test_dashboard_renders_candidates_and_news():
    from nylb.report.html import build_dashboard
    r = _result()
    chart = extract_chart_data(r)
    news = {"성심당": [{"title": "성심당 신메뉴", "link": "http://n", "date": "x"}]}
    html = build_dashboard(r, chart, news_context=news)
    assert '"candidates"' in html and '"news_context"' in html
    assert "발굴 후보" in html
    assert "관련 뉴스" in html
