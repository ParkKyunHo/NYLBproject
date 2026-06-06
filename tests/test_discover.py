from datetime import datetime, timezone

from nylb.core.schema import Item, ScanResult
from nylb.core.discover import discover_candidates

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _yt(title):
    return Item(source="youtube", lens="menu", type="video", title=title, collected_at=NOW)


def _result(items, query):
    return ScanResult(run_id="r", store_id="nylb", lens="menu", query=query,
                      items=items, started_at=NOW, finished_at=NOW)


def test_discovers_repeated_unknown_term_excludes_known_and_stopwords():
    items = [_yt("두바이 쫀득 쿠키 리뷰"), _yt("두바이 쫀득 쿠키 후기"),
             _yt("베이글 맛집 추천")]
    q = {"keywords": ["베이글"], "radar_categories": {}, "synonyms": {}}
    out = discover_candidates(_result(items, q), top_n=10)
    terms = [c["term"] for c in out]
    assert "두바이" in terms or "쫀득" in terms or "두바이 쫀득" in terms
    assert "베이글" not in terms
    assert "맛집" not in terms and "추천" not in terms


def test_bigram_with_known_or_stopword_token_dropped():
    items = [_yt("크로플 맛집 추천"), _yt("크로플 맛집 후기")]  # 크로플=known(below), 맛집=stop
    q = {"keywords": ["크로플"], "radar_categories": {}, "synonyms": {}}
    out = discover_candidates(_result(items, q), top_n=10)
    terms = [c["term"] for c in out]
    assert "크로플 맛집" not in terms and "맛집 추천" not in terms


def test_single_occurrence_dropped_and_rising_merged():
    items = [_yt("말차 라떼")]
    rising = Item(source="google_trends", lens="menu", type="rising_query",
                  title="버터떡", collected_at=NOW, metrics={"value": 9000.0},
                  raw={"seed": "디저트"})
    q = {"keywords": [], "radar_categories": {}, "synonyms": {}}
    out = discover_candidates(_result([items[0], rising], q), top_n=10)
    terms = {c["term"]: c for c in out}
    assert "말차" not in terms
    assert "버터떡" in terms and terms["버터떡"]["from_rising"] is True
