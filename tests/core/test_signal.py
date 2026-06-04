from datetime import datetime, timezone

import pytest

from nylb.core.schema import Item, ScanResult
from nylb.core.signal import is_relevant, filter_relevant, popularity, recency_weight, score_items, item_key

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)


def _yt(title, text=None):
    return Item(source="youtube", lens="menu", type="video", title=title,
                text=text, collected_at=NOW)


def test_is_relevant_matches_keyword_in_title():
    assert is_relevant(_yt("베이글 신메뉴 리뷰"), ["베이글", "소금빵"]) is True


def test_is_relevant_matches_in_text():
    assert is_relevant(_yt("디저트 브이로그", "오늘은 소금빵 먹방"), ["소금빵"]) is True


def test_is_relevant_false_when_unrelated():
    assert is_relevant(_yt("20만 기념 만칼로리 챌린지"), ["베이글", "소금빵"]) is False


def test_is_relevant_synonym_match():
    syn = {"베이글": ["bagel"]}
    assert is_relevant(_yt("Best BAGEL in Seoul"), ["베이글"], syn) is True


def test_filter_relevant_drops_off_topic_and_counts():
    items = [_yt("베이글 리뷰"), _yt("먹방 챌린지"), _yt("소금빵 만들기")]
    kept, dropped = filter_relevant(items, ["베이글", "소금빵"])
    assert [it.title for it in kept] == ["베이글 리뷰", "소금빵 만들기"]
    assert dropped == {"youtube": 1}


def test_filter_relevant_exempts_trend_and_kurly_sources():
    items = [
        Item(source="google_trends", lens="menu", type="search_term", title="탕후루", collected_at=NOW),
        Item(source="kurly", lens="competitor", type="product", title="포비 크림치즈", collected_at=NOW),
    ]
    kept, dropped = filter_relevant(items, ["베이글"])
    assert len(kept) == 2          # trend/kurly are exempt from the gate
    assert dropped == {}


def test_filter_relevant_noop_without_keywords():
    items = [_yt("아무 제목")]
    kept, dropped = filter_relevant(items, [])
    assert len(kept) == 1 and dropped == {}


def test_popularity_by_source():
    yt = Item(source="youtube", lens="menu", type="video", title="t",
              metrics={"views": 1000, "likes": 10, "comments": 2}, collected_at=NOW)
    assert popularity(yt) == 1000 + 10 * 5 + 2 * 10
    gt = Item(source="google_trends", lens="menu", type="search_term", title="베이글",
              metrics={"interest": 80}, collected_at=NOW)
    assert popularity(gt) == 80
    nv = Item(source="naver", lens="menu", type="blog", title="t", collected_at=NOW)
    assert popularity(nv) == 1.0


def test_recency_weight_decays_with_age():
    fresh = Item(source="youtube", lens="menu", type="video", title="t",
                 published_at=NOW, collected_at=NOW)
    old = Item(source="youtube", lens="menu", type="video", title="t",
               published_at=datetime(2026, 4, 4, tzinfo=timezone.utc), collected_at=NOW)
    undated = Item(source="google_trends", lens="menu", type="search_term", title="t",
                   collected_at=NOW)
    assert recency_weight(fresh, NOW) == 1.0
    assert recency_weight(old, NOW) < recency_weight(fresh, NOW)   # ~60 days → decayed
    assert recency_weight(undated, NOW) == 1.0                     # undated = neutral


def test_recency_weight_floors_at_0_1():
    ancient = Item(source="youtube", lens="menu", type="video", title="t",
                   published_at=datetime(2020, 1, 1, tzinfo=timezone.utc), collected_at=NOW)
    assert recency_weight(ancient, NOW) == pytest.approx(0.1)       # clamped, never below floor


def test_score_items_normalizes_within_source():
    # YouTube raw views are huge vs trends interest 0-100; normalization must
    # keep them comparable (each source's max → 1.0).
    yt_big = Item(source="youtube", lens="menu", type="video", title="big",
                  url="y1", metrics={"views": 500000}, collected_at=NOW)
    gt = Item(source="google_trends", lens="menu", type="search_term", title="베이글",
              url="g1", metrics={"interest": 100}, collected_at=NOW)
    res = ScanResult(run_id="r", store_id="nylb", lens="menu", query={},
                     items=[yt_big, gt], started_at=NOW, finished_at=NOW)
    scores = score_items(res, NOW)
    # both undated → recency 1.0, so normalized popularity IS the final score
    assert scores[item_key(yt_big)] == pytest.approx(1.0)    # source-max → 1.0, not swamping
    assert scores[item_key(gt)] == pytest.approx(1.0)


def test_score_items_recency_breaks_ties():
    fresh = Item(source="youtube", lens="menu", type="video", title="fresh", url="f",
                 metrics={"views": 1000}, published_at=NOW, collected_at=NOW)
    old = Item(source="youtube", lens="menu", type="video", title="old", url="o",
               metrics={"views": 1000}, published_at=datetime(2026, 4, 4, tzinfo=timezone.utc),
               collected_at=NOW)
    res = ScanResult(run_id="r", store_id="nylb", lens="menu", query={},
                     items=[fresh, old], started_at=NOW, finished_at=NOW)
    scores = score_items(res, NOW)
    assert scores[item_key(fresh)] > scores[item_key(old)]


def test_score_items_rising_query_does_not_crush_interest():
    # google_trends emits both search_term (interest 0-100) and rising_query
    # (value up to 9999 for "Breakout"). Normalizing per (source, type) keeps a
    # real interest term meaningful instead of being divided by 9999.
    interest = Item(source="google_trends", lens="menu", type="search_term",
                    title="베이글", url="g1", metrics={"interest": 80}, collected_at=NOW)
    breakout = Item(source="google_trends", lens="menu", type="rising_query",
                    title="베이글 래빗", url="g2", metrics={"value": 9999}, collected_at=NOW)
    res = ScanResult(run_id="r", store_id="nylb", lens="menu", query={},
                     items=[interest, breakout], started_at=NOW, finished_at=NOW)
    scores = score_items(res, NOW)
    assert scores[item_key(interest)] == pytest.approx(1.0)   # not crushed by the 9999
    assert scores[item_key(breakout)] == pytest.approx(1.0)
