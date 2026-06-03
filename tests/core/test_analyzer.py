from datetime import datetime, timezone
from nylb.core.schema import Item, ScanResult, CollectError
from nylb.core.analyzer import ClaudeCodeAnalyzer

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
