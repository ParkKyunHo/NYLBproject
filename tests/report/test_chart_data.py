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


def test_competitors_extracted():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="[포비베이글] 크림치즈", url="https://www.kurly.com/goods/5043336",
                  author="포비(FOURB)", metrics={"price": 8910, "base_price": 9900},
                  collected_at=NOW)]
    result = ScanResult(run_id="rc", store_id="nylb", lens="competitor",
                        query={}, items=items, started_at=NOW, finished_at=NOW)
    data = extract_chart_data(result)
    assert data["competitors"][0]["brand"] == "포비(FOURB)"
    assert data["competitors"][0]["price"] == 8910
    assert data["competitors"][0]["base_price"] == 9900


def _competitor_result(own_products, competitor_products, items):
    return ScanResult(run_id="rc", store_id="nylb", lens="competitor",
                      query={"own_products": own_products,
                             "competitor_products": competitor_products},
                      items=items, started_at=NOW, finished_at=NOW)


def test_comparison_row_built_on_match_key():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="[포비베이글] 크림치즈", url="https://www.kurly.com/goods/5043336",
                  author="포비(FOURB)", metrics={"price": 8910, "base_price": 9900},
                  collected_at=NOW)]
    data = extract_chart_data(_competitor_result(
        own_products=[{"product": "플레인 크림치즈 베이글", "category": "크림치즈",
                       "price": 4500, "match_key": "크림치즈"}],
        competitor_products=[{"brand": "포비(FOURB)",
                              "url": "https://www.kurly.com/goods/5043336",
                              "match_key": "크림치즈", "basis": "리테일 200g"}],
        items=items))
    rows = data["comparisons"]
    assert len(rows) == 1
    r = rows[0]
    assert r["category"] == "크림치즈"
    assert r["nylb_product"] == "플레인 크림치즈 베이글"
    assert r["nylb_price"] == 4500
    assert r["competitor_brand"] == "포비(FOURB)"
    assert r["competitor_price"] == 8910
    assert r["competitor_basis"] == "리테일 200g"
    assert r["diff"] == 4500 - 8910
    assert r["diff_pct"] == -49.5
    assert r["position"] == "below"


def test_no_comparison_when_match_key_absent():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="LBM 세트", url="https://www.kurly.com/goods/1000773557",
                  author="런던베이글뮤지엄", metrics={"price": 40200, "base_price": 40200},
                  collected_at=NOW)]
    data = extract_chart_data(_competitor_result(
        own_products=[{"product": "플레인 크림치즈 베이글", "category": "크림치즈",
                       "price": 4500, "match_key": "크림치즈"}],
        competitor_products=[{"brand": "런던베이글뮤지엄",
                              "url": "https://www.kurly.com/goods/1000773557",
                              "basis": "냉동 세트"}],          # match_key 없음
        items=items))
    assert data["comparisons"] == []
    assert len(data["competitors"]) == 1          # 경쟁사는 원시 목록에 잔존


def test_position_above_when_nylb_more_expensive():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="경쟁 베이글", url="u1", author="경쟁사",
                  metrics={"price": 3000}, collected_at=NOW)]
    data = extract_chart_data(_competitor_result(
        own_products=[{"product": "NYLB 베이글", "category": "베이글",
                       "price": 3500, "match_key": "베이글"}],
        competitor_products=[{"brand": "경쟁사", "url": "u1", "match_key": "베이글"}],
        items=items))
    r = data["comparisons"][0]
    assert r["position"] == "above"
    assert r["diff_pct"] > 0
    assert r["competitor_basis"] is None          # basis는 선택


def test_zero_competitor_price_skipped():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="이상치", url="u1", author="X",
                  metrics={"price": 0}, collected_at=NOW)]
    data = extract_chart_data(_competitor_result(
        own_products=[{"product": "P", "category": "C", "price": 4500, "match_key": "C"}],
        competitor_products=[{"brand": "X", "url": "u1", "match_key": "C"}],
        items=items))
    assert data["comparisons"] == []
