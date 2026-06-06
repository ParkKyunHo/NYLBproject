from nylb.config import get_lens_config, load_lenses


def test_beverage_lens_loads_with_anchor_and_categories():
    lenses = load_lenses("config/lenses.yaml")
    c = get_lens_config(lenses, "nylb", "beverage")
    assert c["anchor"] == "아메리카노"
    assert set(c["radar"].keys()) == {"coffee", "noncoffee", "blended", "trend", "brands"}
    assert "스타벅스" in c["radar"]["brands"]


def test_menu_and_beverage_have_label_icon():
    lenses = load_lenses("config/lenses.yaml")
    m = get_lens_config(lenses, "nylb", "menu")
    b = get_lens_config(lenses, "nylb", "beverage")
    assert m["label"] == "메뉴" and m["icon"] == "🥯"
    assert b["label"] == "음료" and b["icon"] == "🥤"
