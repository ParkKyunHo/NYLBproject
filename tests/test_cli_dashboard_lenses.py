from nylb.cli import _build_parser


def test_dashboard_lenses_flag_parses():
    ns = _build_parser().parse_args(["dashboard", "--lenses", "menu,beverage", "--port", "0"])
    assert ns.cmd == "dashboard" and ns.lenses == "menu,beverage"
