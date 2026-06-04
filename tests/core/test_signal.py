from datetime import datetime, timezone

from nylb.core.schema import Item
from nylb.core.signal import is_relevant, filter_relevant

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
