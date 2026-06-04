from datetime import datetime, timezone
from nylb.core.schema import Item, ScanResult
from nylb.report.chart_data import extract_chart_data
from nylb.report.html import build_dashboard

NOW = datetime(2026, 6, 4, tzinfo=timezone.utc)

SYN = {
    "headline": "베이글이 앵커",
    "executive_summary": "요약 문장.",
    "trend_verdicts": [{"keyword": "베이글", "stage": "스테디", "momentum": "up", "summary": "꾸준"}],
    "top_insights": [{"title": "인사이트1", "detail": "내용"}],
    "menu_opportunities": [], "pricing_benchmark": [], "content_ideas": [],
    "action_plan": [{"priority": 1, "action": "행동", "rationale": "근거",
                     "impact": "high", "effort": "low", "timeframe": "이번 주"}],
    "risks": [], "data_gaps": [],
}


def _result():
    items = [Item(source="naver_datalab", lens="menu", type="search_term", title="베이글",
                  metrics={"interest": 70, "peak": 90}, collected_at=NOW,
                  raw={"series": [{"date": "2026-06-03", "value": 90},
                                  {"date": "2026-06-04", "value": 70}]})]
    return ScanResult(run_id="2026-06-04-menu-abc123", store_id="nylb", lens="menu",
                      query={"keywords": ["베이글"]}, items=items,
                      started_at=NOW, finished_at=NOW)


def test_build_dashboard_returns_self_contained_html():
    result = _result()
    html = build_dashboard(result, SYN, extract_chart_data(result))
    assert html.startswith("<!DOCTYPE html>")
    assert "const DATA" in html
    assert "__DATA__" not in html            # placeholder fully replaced
    assert "베이글이 앵커" in html            # headline injected
    assert "2026-06-04-menu-abc123" in html  # run id injected
    assert "<script" in html and "</script>" in html


def test_build_dashboard_embeds_chart_series():
    result = _result()
    html = build_dashboard(result, SYN, extract_chart_data(result))
    assert '"베이글"' in html                 # series keyword present in embedded JSON
    assert "naver_datalab" in html            # trend source label


def test_build_dashboard_has_no_stale_oneoff_hardcodes():
    """The template was ported from a one-off report; ensure no run-specific
    captions leak into every generated dashboard."""
    result = _result()
    html = build_dashboard(result, SYN, extract_chart_data(result))
    for stale in ["5/31 피크", "표본 2개", "(5 agents)", "2026-05-28 ~ 06-04",
                  "동시언급(15~18)", "(menu)</title>"]:
        assert stale not in html, f"stale hardcode leaked: {stale}"


def test_build_dashboard_reports_error_count_and_channels():
    """Total-collected KPI must reflect real channel count + error count."""
    items = [
        Item(source="naver_datalab", lens="menu", type="search_term", title="베이글",
             metrics={"interest": 70, "peak": 90}, collected_at=NOW,
             raw={"series": [{"date": "2026-06-04", "value": 70}]}),
    ]
    from nylb.core.schema import CollectError
    result = ScanResult(run_id="r", store_id="nylb", lens="menu",
                        query={"keywords": ["베이글"]}, items=items,
                        errors=[CollectError(source="google_trends", message="429")],
                        started_at=NOW, finished_at=NOW)
    html = build_dashboard(result, SYN, extract_chart_data(result))
    assert '"errors": 1' in html
