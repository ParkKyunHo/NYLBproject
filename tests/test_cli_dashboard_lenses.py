from nylb.cli import _build_parser


def test_dashboard_lenses_flag_parses():
    ns = _build_parser().parse_args(["dashboard", "--lenses", "menu,beverage", "--port", "0"])
    assert ns.cmd == "dashboard" and ns.lenses == "menu,beverage"


def test_dashboard_lenses_default_is_menu_beverage():
    ns = _build_parser().parse_args(["dashboard"])
    assert ns.lenses == "menu,beverage"


def test_lens_keys_split_strips_and_drops_empties():
    raw = " menu , beverage ,, "
    keys = [s.strip() for s in raw.split(",") if s.strip()]
    assert keys == ["menu", "beverage"]
