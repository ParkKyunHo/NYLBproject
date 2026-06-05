from datetime import datetime, timezone

from nylb.core.schema import Item
from nylb.core.verify import verify_rising


def _content(title: str) -> Item:
    return Item(source="naver", lens="menu", type="blog", title=title,
                collected_at=datetime(2026, 6, 6, tzinfo=timezone.utc))


def test_phantom_term_is_unverified():
    rising = [{"seed": "베이글", "query": "비키 베이글", "value": 10250.0}]
    content = [_content("소금빵 베이글 맛집"), _content("크로플 후기")]
    out = verify_rising(rising, content, datalab_terms=set(), known_terms={"베이글", "소금빵"})
    assert [r["query"] for r in out["verified"]] == []
    assert out["unverified"][0]["query"] == "비키 베이글"
    assert "why" in out["unverified"][0]


def test_known_keyword_is_verified():
    rising = [{"seed": "베이글", "query": "베이글", "value": 5.0}]
    out = verify_rising(rising, [], datalab_terms=set(), known_terms={"베이글"})
    assert out["verified"][0]["query"] == "베이글"
    assert out["unverified"] == []


def test_datalab_signal_makes_verified():
    rising = [{"seed": "디저트", "query": "두바이초콜릿", "value": 9.0}]
    out = verify_rising(rising, [], datalab_terms={"두바이초콜릿"}, known_terms=set())
    assert out["verified"][0]["query"] == "두바이초콜릿"


def test_content_corroboration_threshold():
    rising = [{"seed": "베이글", "query": "약과", "value": 8.0}]
    content = [_content("약과 베이글 변주"), _content("약과 디저트 인기")]
    out = verify_rising(rising, content, datalab_terms=set(), known_terms=set(),
                        min_corroboration=2)
    assert out["verified"][0]["query"] == "약과"
    out2 = verify_rising(rising, content[:1], datalab_terms=set(), known_terms=set(),
                         min_corroboration=2)
    assert out2["unverified"][0]["query"] == "약과"
