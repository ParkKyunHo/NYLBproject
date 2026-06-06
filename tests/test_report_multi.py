from nylb.report.multi import build_lenses_dashboard


def test_build_lenses_dashboard_two_lenses():
    html = build_lenses_dashboard(["menu", "beverage"], settings={}, collectors={})
    assert "const LENSES" in html
    assert "메뉴" in html and "음료" in html      # labels from config
    assert "🥯" in html and "🥤" in html          # icons from config
