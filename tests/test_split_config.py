from nylb.config import get_lens_config, load_lenses


def test_expanded_product_categories():
    L = load_lenses("config/lenses.yaml")
    b = get_lens_config(L, "nylb", "beverage")
    assert {"coffee", "tea", "blended", "trend", "brands"} <= set(b["radar"].keys())
    assert "카푸치노" in b["radar"]["coffee"] and "할리스" in b["radar"]["brands"]
    m = get_lens_config(L, "nylb", "menu")
    assert {"flavor", "pastry", "bread", "adjacent", "brands"} <= set(m["radar"].keys())
    assert "크루아상" in m["radar"]["pastry"] and "이성당" in m["radar"]["brands"]
