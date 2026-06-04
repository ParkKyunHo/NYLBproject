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
