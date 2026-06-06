from __future__ import annotations

from datetime import datetime, timezone

from nylb.config import get_lens_config, load_lenses
from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data
from nylb.report.html import build_multi_dashboard
from nylb.report.news import gather_riser_news


def build_lenses_dashboard(
    lens_keys: list[str],
    *,
    lenses_file: str = "config/lenses.yaml",
    store_id: str = "nylb",
    settings: dict,
    collectors=None,
) -> str:
    """Scan each lens, build its board (+ riser news), assemble a tabbed dashboard.
    Lens label/icon come from config (industry-agnostic)."""
    from nylb.cli import build_run_id

    lenses_cfg = load_lenses(lenses_file)
    now = datetime.now(timezone.utc)
    out: list[dict] = []
    for key in lens_keys:
        lc = get_lens_config(lenses_cfg, store_id, key)
        result = run_scan(
            key,
            store_id=store_id,
            lens_config=lc,
            settings=settings,
            store=LocalJsonStore(),
            run_id=build_run_id(key, now),
            collected_at=now,
            collectors=collectors,
        )
        chart = extract_chart_data(result)
        news = gather_riser_news(result, chart, settings)
        out.append(
            {
                "key": key,
                "label": lc.get("label", key),
                "icon": lc.get("icon", "🍽"),
                "board": build_board(result, chart, news_context=news),
            }
        )
    return build_multi_dashboard(out)
