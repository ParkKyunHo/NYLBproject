from datetime import datetime, timezone
from nylb.core.schema import Item, ScanResult
from nylb.report.chart_data import extract_chart_data

NOW = datetime(2026, 6, 4, tzinfo=timezone.utc)


def _result():
    items = [
        Item(source="youtube", lens="menu", type="video", title="베이글 영상", collected_at=NOW),
        Item(source="naver", lens="menu", type="blog", title="소금빵 후기",
             text="베이글도 맛있다", collected_at=NOW),
        Item(source="google_trends", lens="menu", type="search_term", title="베이글",
             metrics={"interest": 80, "peak": 80}, collected_at=NOW,
             raw={"series": [{"date": "2026-06-03", "value": 40},
                             {"date": "2026-06-03", "value": 60},
                             {"date": "2026-06-04", "value": 80}]}),
        Item(source="naver_datalab", lens="menu", type="search_term", title="베이글",
             metrics={"interest": 70, "peak": 90}, collected_at=NOW,
             raw={"series": [{"date": "2026-06-03", "value": 90},
                             {"date": "2026-06-04", "value": 70}]}),
        Item(source="google_trends", lens="menu", type="rising_query",
             title="베이글 샌드위치", metrics={"value": 250}, collected_at=NOW,
             raw={"seed": "베이글"}),
    ]
    return ScanResult(run_id="r", store_id="nylb", lens="menu",
                      query={"keywords": ["베이글", "소금빵"],
                             "radar_watchlist": ["두바이초콜릿"]},
                      items=items, started_at=NOW, finished_at=NOW)


def test_counts_per_source():
    data = extract_chart_data(_result())
    assert data["counts"]["google_trends"] == 2
    assert data["counts"]["naver_datalab"] == 1


def test_daily_average_and_sources_split():
    data = extract_chart_data(_result())
    gt = data["trends"]["google_trends"]["베이글"]
    assert gt["daily"]["2026-06-03"] == 50.0      # (40+60)/2
    assert gt["daily"]["2026-06-04"] == 80.0
    assert gt["peak"] == 80.0
    assert "베이글" in data["trends"]["naver_datalab"]


def test_matrix_counts_text_presence():
    data = extract_chart_data(_result())
    # 베이글 appears in youtube title + naver text
    assert data["matrix"]["베이글"]["youtube"] == 1
    assert data["matrix"]["베이글"]["naver"] == 1


def test_matrix_fills_zero_for_unmatched_channels():
    data = extract_chart_data(_result())
    # 소금빵 appears only in the naver blog text, not youtube/google_trends
    row = data["matrix"]["소금빵"]
    assert set(row) == {"youtube", "naver", "google_trends"}
    assert row["youtube"] == 0 and row["google_trends"] == 0


def test_rising_collected():
    data = extract_chart_data(_result())
    assert data["rising"][0]["query"] == "베이글 샌드위치"
    assert data["rising"][0]["value"] == 250.0
