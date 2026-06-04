from datetime import datetime, timezone
from nylb.core.schema import Item, ScanResult, CollectError
from nylb.core.analyzer import ClaudeCodeAnalyzer, cross_channel_terms

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)


def _result():
    items = [
        Item(source="youtube", lens="menu", type="video", title="low view",
             metrics={"views": 100}, collected_at=NOW),
        Item(source="youtube", lens="menu", type="video", title="high view",
             metrics={"views": 9000}, collected_at=NOW),
        Item(source="naver", lens="menu", type="blog", title="blog post",
             collected_at=NOW),
    ]
    return ScanResult(run_id="r1", store_id="nylb", lens="menu", query={},
                      items=items, errors=[CollectError(source="instagram", message="skipped")],
                      started_at=NOW, finished_at=NOW)


def test_prepare_groups_and_sorts():
    digest = ClaudeCodeAnalyzer().prepare(_result())
    assert "## youtube" in digest
    assert "## naver" in digest
    # higher-engagement item appears before lower one
    assert digest.index("high view") < digest.index("low view")
    # collection errors surfaced
    assert "instagram" in digest and "skipped" in digest


def test_prepare_respects_top_n():
    digest = ClaudeCodeAnalyzer().prepare(_result(), top_n=1)
    assert "high view" in digest
    assert "low view" not in digest


def _cross_result():
    items = [
        Item(source="youtube", lens="menu", type="video", title="베이글 신메뉴 리뷰",
             metrics={"views": 5000}, collected_at=NOW),
        Item(source="naver", lens="menu", type="blog", title="베이글 맛집 후기",
             collected_at=NOW),
        Item(source="google_trends", lens="menu", type="search_term", title="베이글",
             metrics={"interest": 80}, collected_at=NOW),
        Item(source="youtube", lens="menu", type="video", title="소금빵 만들기",
             metrics={"views": 3000}, collected_at=NOW),
    ]
    return ScanResult(
        run_id="rc", store_id="nylb", lens="menu",
        query={"keywords": ["베이글", "소금빵"], "instagram_hashtags": ["베이글맛집"]},
        items=items, started_at=NOW, finished_at=NOW,
    )


def test_cross_channel_terms_ranks_by_channel_count():
    rows = cross_channel_terms(_cross_result())
    assert rows[0]["term"] == "베이글"
    assert rows[0]["channel_count"] == 3
    assert set(rows[0]["channels"]) == {"youtube", "naver", "google_trends"}
    soup = next(r for r in rows if r["term"] == "소금빵")
    assert soup["channel_count"] == 1


def test_prepare_includes_cross_channel_section():
    digest = ClaudeCodeAnalyzer().prepare(_cross_result())
    assert "채널 교차 핫 키워드" in digest
    assert "베이글" in digest
    # cross-channel section appears before the per-source sections
    assert digest.index("채널 교차 핫 키워드") < digest.index("## youtube")


def test_prepare_notes_when_no_multi_channel():
    res = ScanResult(
        run_id="rs", store_id="nylb", lens="menu", query={"keywords": ["베이글"]},
        items=[Item(source="youtube", lens="menu", type="video",
                    title="베이글 영상", collected_at=NOW)],
        started_at=NOW, finished_at=NOW,
    )
    digest = ClaudeCodeAnalyzer().prepare(res)
    assert "2개 이상 채널" in digest


def test_prepare_shows_dropped_section():
    res = ScanResult(
        run_id="rd", store_id="nylb", lens="menu", query={"keywords": ["베이글"]},
        items=[Item(source="youtube", lens="menu", type="video", title="베이글 영상",
                    collected_at=NOW)],
        dropped_by_source={"youtube": 2, "naver": 3},
        started_at=NOW, finished_at=NOW,
    )
    digest = ClaudeCodeAnalyzer().prepare(res)
    assert "관련성 필터" in digest
    assert "youtube: 2" in digest and "naver: 3" in digest


def test_prepare_ranks_recent_over_old_same_views():
    items = [
        Item(source="youtube", lens="menu", type="video", title="옛날 베이글", url="o",
             metrics={"views": 1000},
             published_at=datetime(2026, 4, 4, tzinfo=timezone.utc), collected_at=NOW),
        Item(source="youtube", lens="menu", type="video", title="최신 베이글", url="f",
             metrics={"views": 1000}, published_at=NOW, collected_at=NOW),
    ]
    res = ScanResult(run_id="rr", store_id="nylb", lens="menu", query={"keywords": ["베이글"]},
                     items=items, started_at=NOW, finished_at=NOW)
    digest = ClaudeCodeAnalyzer().prepare(res)
    assert digest.index("최신 베이글") < digest.index("옛날 베이글")   # recency wins the tie
