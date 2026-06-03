import textwrap
from nylb.config import load_lenses, get_lens_config


def test_load_lenses_and_get(tmp_path):
    f = tmp_path / "lenses.yaml"
    f.write_text(textwrap.dedent("""
        nylb:
          industry: bakery
          lenses:
            menu:
              keywords: [베이글]
              sources: [youtube]
    """), encoding="utf-8")
    lenses = load_lenses(f)
    cfg = get_lens_config(lenses, "nylb", "menu")
    assert cfg["keywords"] == ["베이글"]
    assert cfg["sources"] == ["youtube"]


def test_get_lens_config_missing_raises(tmp_path):
    f = tmp_path / "lenses.yaml"
    f.write_text("nylb:\n  lenses: {}\n", encoding="utf-8")
    lenses = load_lenses(f)
    try:
        get_lens_config(lenses, "nylb", "menu")
        assert False, "expected KeyError"
    except KeyError:
        pass
