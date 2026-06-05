from nylb.core.context import caption, contextualize, direction


def test_direction_thresholds():
    assert direction(2.0) == "up"
    assert direction(-2.0) == "down"
    assert direction(0.1) == "steady"


def test_contextualize_computes_vs_baseline_and_rank():
    stats = {"latest": 87.0, "recent_avg": 80.0, "base_avg": 70.0,
             "momentum": 10.0, "peak": 90.0, "daily": {}}
    cm = contextualize("소금빵", stats, rank=1, total=4)
    assert cm["term"] == "소금빵"
    assert cm["value"] == 87.0
    assert cm["direction"] == "up"
    assert cm["vs_baseline"] == 14.0  # 10/70*100 rounded
    assert cm["rank"] == 1 and cm["total"] == 4
    assert "관심도 87/100" in cm["caption"]
    assert "4개 중 1위" in cm["caption"]


def test_recent_drop_flag():
    stats = {"latest": 8.0, "recent_avg": 20.0, "base_avg": 30.0,
             "momentum": -10.0, "peak": 38.0, "daily": {}}
    cm = contextualize("소금빵", stats)
    assert cm["recent_drop"] is True
    assert cm["direction"] == "down"
    assert "단 최근 하락" in cm["caption"]


def test_caption_has_no_prescriptive_wording():
    banned = ["추천", "해야", "줄여", "늘려", "권장", "하세요", "전략", "투자"]
    for mom in (12.0, -12.0, 0.0):
        stats = {"latest": 50.0, "recent_avg": 50.0, "base_avg": 45.0,
                 "momentum": mom, "peak": 60.0, "daily": {}}
        cap = contextualize("베이글", stats, rank=2, total=3)["caption"]
        assert not any(w in cap for w in banned), cap
