from nylb.core.opportunity import FORMULA_LABEL, score


def _cm(value=50.0, vs_baseline=0.0, direction="steady"):
    return {"term": "말차", "value": value, "vs_baseline": vs_baseline,
            "direction": direction}


def _season(status="in_season", now_index=150.0, next_index=150.0):
    return {"status": status, "now_index": now_index, "next_index": next_index}


def test_score_parts_weighted_sum_equals_score():
    o = score(_cm(value=80, vs_baseline=40, direction="up"), _season())
    total = sum(p["points"] * p["weight"] for p in o["parts"].values())
    assert abs(o["score"] - round(total, 1)) < 0.05
    assert set(o["parts"]) == {"interest", "growth", "season", "direction"}
    assert abs(sum(p["weight"] for p in o["parts"].values()) - 1.0) < 1e-9


def test_score_monotonic_in_each_factor():
    base = score(_cm(), None)["score"]
    assert score(_cm(value=90), None)["score"] > base
    assert score(_cm(vs_baseline=80), None)["score"] > base
    assert score(_cm(direction="up"), None)["score"] > base
    assert score(_cm(direction="down"), None)["score"] < base
    neutral = score(_cm(), None)
    hot_season = score(_cm(), _season(next_index=200.0, now_index=200.0))
    assert hot_season["score"] > neutral["score"]


def test_score_clamps_extremes_to_0_100():
    lo = score(_cm(value=0, vs_baseline=-500, direction="down"),
               _season(status="off", now_index=0.0, next_index=0.0))
    hi = score(_cm(value=100, vs_baseline=900, direction="up"),
               _season(now_index=400.0, next_index=400.0))
    assert 0.0 <= lo["score"] <= 100.0
    assert 0.0 <= hi["score"] <= 100.0
    assert all(0.0 <= p["points"] <= 100.0 for p in lo["parts"].values())
    assert all(0.0 <= p["points"] <= 100.0 for p in hi["parts"].values())


def test_no_season_data_is_neutral_50():
    assert score(_cm(), None)["parts"]["season"]["points"] == 50.0
    assert score(_cm(), {"status": "no_data"})["parts"]["season"]["points"] == 50.0


def test_missing_vs_baseline_is_neutral():
    cm = _cm()
    cm["vs_baseline"] = None
    o = score(cm, None)
    # vs_baseline=None maps to growth midpoint (same as 0%)
    assert o["parts"]["growth"]["points"] == score(_cm(vs_baseline=0), None)["parts"]["growth"]["points"]


def test_formula_disclosed_and_no_prescriptive_wording():
    o = score(_cm(), _season())
    assert o["formula"] == FORMULA_LABEL
    text = str(o)
    for word in ("하세요", "줄여", "늘려", "추천", "해야"):
        assert word not in text
