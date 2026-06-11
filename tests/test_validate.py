"""Candidate validator + brand-launch news + server /validate route."""
import json
from datetime import datetime, timezone

from nylb.core.schema import CollectResult, Item, ScanResult
from nylb.report.validate import run_validation

NOW = datetime(2026, 6, 11, tzinfo=timezone.utc)


def _series(values, prefix="2026-05"):
    return [{"date": f"{prefix}-{i+1:02d}", "value": v} for i, v in enumerate(values)]


def _fake_datalab(query, lens, *, settings, collected_at):
    items = []
    for t in query.get("keywords", []):
        items.append(Item(source="naver_datalab", lens=lens, type="search_term",
                          title=t, collected_at=collected_at,
                          raw={"series": _series([50, 60, 70, 80])}))
        items.append(Item(source="naver_datalab", lens=lens, type="search_term_monthly",
                          title=t, collected_at=collected_at,
                          raw={"series": [{"date": f"2025-{m:02d}-01", "value": 100.0}
                                          for m in range(1, 13)]}))
    return CollectResult(items=items)


def _fake_youtube(query, lens, *, settings, collected_at):
    return CollectResult(items=[Item(
        source="youtube", lens=lens, type="video",
        title=f"{query['keywords'][0]} 만들기", metrics={"views": 900},
        collected_at=collected_at)])


def _fake_naver(query, lens, *, settings, collected_at):
    return CollectResult(items=[])


_COLLECTORS = {"naver_datalab": _fake_datalab, "youtube": _fake_youtube,
               "naver": _fake_naver}


def _embedded(html):
    return json.loads(html.split("const LENSES = ", 1)[1].split(";\n", 1)[0])[0]["board"]


def test_run_validation_builds_candidate_board(monkeypatch):
    from nylb.report import validate as v
    monkeypatch.setattr(v.naver_datalab, "collect_age_trends",
                        lambda terms, settings: {terms[0]: {"20대": {"momentum": 2.0,
                                                                     "direction": "up"}}})
    monkeypatch.setattr(v.naver_news, "collect",
                        lambda terms, **kw: {terms[0]: [{"title": terms[0] + " 디저트 출시",
                                                         "link": "http://n", "date": ""}]})
    html = run_validation("복숭아 크림치즈", lens="menu", settings={},
                          collectors=_COLLECTORS)
    board = _embedded(html)
    assert board["meta"]["anchor"] == "베이글"
    terms = {c["term"] for c in board["core_signals"]}
    assert terms == {"복숭아 크림치즈", "베이글"}        # 후보 vs 앵커 나란히
    assert len(board["opportunities"]) == 1
    opp = board["opportunities"][0]
    assert opp["term"] == "복숭아 크림치즈"
    assert 0 <= opp["opportunity"]["score"] <= 100
    assert board["age_trends"]["복숭아 크림치즈"]["20대"]["direction"] == "up"
    assert "복숭아 크림치즈 디저트 출시" in html
    assert any("후보 검증 모드" in d["note"] for d in board["data_trust"])


def test_run_validation_rejects_empty_term():
    import pytest
    with pytest.raises(ValueError):
        run_validation("   ", settings={})


def test_gather_brand_launches_uses_launch_context(monkeypatch):
    from nylb.report import news as news_mod
    captured = {}

    def fake_collect(terms, *, settings, max_per_term=3, context_terms=None):
        captured["terms"] = terms
        captured["ctx"] = context_terms
        return {t: [{"title": t + " 신메뉴 출시", "link": "http://x", "date": ""}]
                for t in terms}
    monkeypatch.setattr(news_mod.naver_news, "collect", fake_collect)
    result = ScanResult(run_id="r", store_id="nylb", lens="menu",
                        query={"radar_categories": {"노티드": "brands", "말차": "flavor",
                                                    "성심당": "brands"}},
                        items=[], started_at=NOW, finished_at=NOW)
    out = news_mod.gather_brand_launches(result, settings={"naver_client_id": "x"})
    assert set(captured["terms"]) == {"노티드", "성심당"}   # 브랜드만
    assert "신메뉴" in captured["ctx"] and "출시" in captured["ctx"]
    assert "노티드" in out


def test_server_validate_route(monkeypatch):
    import threading
    import urllib.request

    from nylb.report.server import make_server
    server = make_server(port=0, render_fn=lambda: "x",
                         validate_fn=lambda term: f"<html>OK {term}</html>")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address
    from urllib.parse import quote
    body = urllib.request.urlopen(
        f"http://127.0.0.1:{port}/validate?term={quote('복숭아 크림치즈')}").read().decode("utf-8")
    import urllib.error
    status = None
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/validate")
    except urllib.error.HTTPError as e:
        status = e.code
    server.shutdown()
    assert "OK 복숭아 크림치즈" in body
    assert status == 400
