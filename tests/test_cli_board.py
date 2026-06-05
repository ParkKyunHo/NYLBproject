from datetime import datetime, timezone

from nylb.cli import _build_parser, main
from nylb.core.schema import Item, ScanResult
from nylb.core.store import LocalJsonStore

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def test_report_html_needs_no_synthesis(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    item = Item(source="naver_datalab", lens="menu", type="search_term", title="베이글",
                collected_at=NOW,
                raw={"series": [{"date": "2026-05-01", "value": 80.0},
                                 {"date": "2026-05-02", "value": 85.0}]})
    result = ScanResult(run_id="2026-06-06-menu-cli", store_id="nylb", lens="menu",
                        query={"keywords": ["베이글"]}, items=[item],
                        started_at=NOW, finished_at=NOW)
    LocalJsonStore().save(result)
    rc = main(["report-html", "--run", "2026-06-06-menu-cli"])
    assert rc == 0
    assert "html=" in capsys.readouterr().out


def test_dashboard_subcommand_is_registered():
    ns = _build_parser().parse_args(["dashboard", "--lens", "menu", "--port", "9999"])
    assert ns.cmd == "dashboard" and ns.port == 9999
