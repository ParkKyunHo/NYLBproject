"""v4 decision-intelligence: buzz, pairings, history/delta, age trends wiring."""
from datetime import datetime, timezone

from nylb.core.schema import Item, ScanResult
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data
from nylb.report.history import compare_boards, load_previous, save_board

NOW = datetime(2026, 6, 11, tzinfo=timezone.utc)


def _daily(values):
    return [{"date": f"2026-05-{i+1:02d}", "value": v} for i, v in enumerate(values)]


def _trend(term, values):
    return Item(source="naver_datalab", lens="menu", type="search_term", title=term,
                collected_at=NOW, raw={"series": _daily(values)})


def _content(source, title, views=0.0):
    metrics = {"views": views} if source == "youtube" else {}
    return Item(source=source, lens="menu", type="video" if source == "youtube" else "blog",
                title=title, collected_at=NOW, metrics=metrics)


def _result(items, *, pairing_categories=None, run_id="2026-06-11-menu-aaa001"):
    return ScanResult(
        run_id=run_id, store_id="nylb", lens="menu",
        query={"keywords": ["베이글"], "synonyms": {"베이글": ["bagel"]},
               "radar_categories": {"말차": "flavor", "옥수수": "seasonal",
                                    "크루아상": "pastry"},
               "pairing_categories": pairing_categories or []},
        items=items, dropped_by_source={}, started_at=NOW, finished_at=NOW)


def _items():
    return [
        _trend("베이글", [80, 82, 85, 87]),
        _trend("말차", [20, 25, 30, 40]),
        _trend("옥수수", [10, 11, 12, 12]),
        _trend("크루아상", [30, 30, 29, 28]),
        _content("youtube", "Bagel 굽기 브이로그", views=1200),
        _content("youtube", "말차 디저트 레시피", views=500),
        _content("naver", "말차 라떼 후기"),
    ]


# ── buzz ────────────────────────────────────────────────────────────────────

def test_buzz_counts_mentions_with_synonyms():
    r = _result(_items())
    board = build_board(r, extract_chart_data(r))
    bagel = next(c for c in board["core_signals"] if c["term"] == "베이글")
    assert bagel["buzz"] == {"youtube": 1, "naver": 0, "views": 1200}  # 'Bagel' 동의어 매칭
    matcha = next(c for c in board["radar"] if c["term"] == "말차")
    assert matcha["buzz"]["youtube"] == 1 and matcha["buzz"]["naver"] == 1
    corn = next(c for c in board["radar"] if c["term"] == "옥수수")
    assert corn["buzz"] == {"youtube": 0, "naver": 0, "views": 0}


# ── pairings ────────────────────────────────────────────────────────────────

def test_pairings_only_for_whitelisted_categories():
    r = _result(_items(), pairing_categories=["flavor", "seasonal"])
    board = build_board(r, extract_chart_data(r))
    opp = {o["term"]: o for o in board["opportunities"]}
    assert opp["말차"]["pairings"] == ["말차×베이글"]      # 코어 1개뿐 → 1조합
    assert "pairings" in opp["옥수수"]
    assert "pairings" not in opp["크루아상"]               # pastry는 화이트리스트 밖


def test_pairings_absent_when_not_configured():
    r = _result(_items())
    board = build_board(r, extract_chart_data(r))
    assert all("pairings" not in o for o in board["opportunities"])


# ── history / delta ─────────────────────────────────────────────────────────

def _board_with_run(run_id):
    r = _result(_items(), run_id=run_id)
    return build_board(r, extract_chart_data(r))


def test_history_roundtrip_and_previous_selection(tmp_path):
    b1 = _board_with_run("2026-06-10-menu-aaa001")
    b2 = _board_with_run("2026-06-11-menu-bbb002")
    save_board(b1, out_dir=tmp_path)
    save_board(b2, out_dir=tmp_path)
    prev = load_previous("menu", "2026-06-11-menu-bbb002", out_dir=tmp_path)
    assert prev["meta"]["run_id"] == "2026-06-10-menu-aaa001"
    assert load_previous("beverage", "x", out_dir=tmp_path) is None


def test_compare_boards_rank_and_score_moves():
    prev = {"meta": {"run_id": "r1", "collected": "2026-06-10"},
            "interest_ranking": [{"term": "베이글"}, {"term": "말차"}, {"term": "옥수수"}],
            "opportunities": [{"term": "말차", "opportunity": {"score": 50.0}}]}
    cur = {"meta": {"run_id": "r2", "collected": "2026-06-11"},
           "interest_ranking": [{"term": "말차"}, {"term": "베이글"}, {"term": "딸기"}],
           "opportunities": [{"term": "말차", "opportunity": {"score": 57.5}},
                             {"term": "딸기", "opportunity": {"score": 70.0}}]}
    d = compare_boards(prev, cur)
    assert d["rank_moves"]["말차"] == {"prev": 2, "cur": 1, "move": 1, "new": False}
    assert d["rank_moves"]["베이글"]["move"] == -1
    assert d["rank_moves"]["딸기"]["new"] is True
    assert d["score_moves"] == {"말차": 7.5}        # 딸기는 전회 점수 없음 → 제외
    assert d["prev_date"] == "2026-06-10"
    assert compare_boards(None, cur) is None


# ── age trends collector ────────────────────────────────────────────────────

def test_collect_age_trends_buckets_and_direction(monkeypatch):
    from nylb.collectors import naver_datalab as dl
    sent = []

    class _Resp:
        def __init__(self, names): self._names = names
        def raise_for_status(self): pass
        def json(self):
            rising = [{"period": f"2026-06-{i+1:02d}", "ratio": float(10 + i * 5)}
                      for i in range(7)]
            return {"results": [{"title": n, "data": rising} for n in self._names]}

    def fake_post(url, json, headers, timeout):
        sent.append(json)
        return _Resp([g["groupName"] for g in json["keywordGroups"]])

    monkeypatch.setattr(dl.httpx, "post", fake_post)
    out = dl.collect_age_trends(["말차", "옥수수"],
                                settings={"naver_client_id": "x", "naver_client_secret": "y"})
    assert len(sent) == len(dl.AGE_BUCKETS)            # 2 terms fit one batch per bucket
    assert all("ages" in b for b in sent)
    assert set(out["말차"]) == set(dl.AGE_BUCKETS)
    assert out["말차"]["20대"]["direction"] == "up"     # rising fixture


def test_collect_age_trends_no_creds_returns_empty():
    from nylb.collectors import naver_datalab as dl
    assert dl.collect_age_trends(["말차"], settings={}) == {}


# ── multi wiring ────────────────────────────────────────────────────────────

def test_build_board_full_attaches_delta_on_second_scan(tmp_path, monkeypatch):
    import nylb.report.history as hist
    import nylb.report.multi as multi
    monkeypatch.setattr(hist, "_DIR", tmp_path)
    monkeypatch.setattr(multi.naver_datalab, "collect_age_trends",
                        lambda terms, settings: {"말차": {"20대": {"momentum": 1.0,
                                                                   "direction": "up"}}})
    r1 = _result(_items(), run_id="2026-06-10-menu-aaa001")
    b1 = multi.build_board_full(r1, settings={})
    assert "delta" not in b1                           # 첫 스캔 — 비교 대상 없음
    assert b1["age_trends"]["말차"]["20대"]["direction"] == "up"
    r2 = _result(_items(), run_id="2026-06-11-menu-bbb002")
    b2 = multi.build_board_full(r2, settings={})
    assert b2["delta"]["prev_run_id"] == "2026-06-10-menu-aaa001"
    assert "rank_moves" in b2["delta"]
