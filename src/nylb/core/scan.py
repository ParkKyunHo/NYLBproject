from __future__ import annotations

from datetime import datetime
from typing import Callable

from nylb.collectors import google_trends, instagram, kurly, naver, naver_datalab, youtube
from nylb.core.schema import CollectError, ScanResult
from nylb.core.store import Store

Collector = Callable[..., "object"]

DEFAULT_COLLECTORS: dict[str, Collector] = {
    "youtube": youtube.collect,
    "naver": naver.collect,
    "google_trends": google_trends.collect,
    "naver_datalab": naver_datalab.collect,
    "kurly": kurly.collect,
    "instagram": instagram.collect,
}


def run_scan(
    lens: str,
    *,
    store_id: str,
    lens_config: dict,
    settings: dict,
    store: Store,
    run_id: str,
    collected_at: datetime,
    collectors: dict[str, Collector] | None = None,
) -> ScanResult:
    collectors = DEFAULT_COLLECTORS if collectors is None else collectors

    sources = list(lens_config.get("sources", []))
    if (lens_config.get("instagram_hashtags") or lens_config.get("instagram_accounts")) \
            and "instagram" not in sources:
        sources.append("instagram")

    query = {
        "keywords": lens_config.get("keywords", []),
        "radar_watchlist": lens_config.get("radar_watchlist", []),
        "radar_seeds": lens_config.get("radar_seeds", []),
        "competitor_products": lens_config.get("competitor_products", []),
        "instagram_hashtags": lens_config.get("instagram_hashtags", []),
        "instagram_accounts": lens_config.get("instagram_accounts", []),
    }

    items = []
    errors = []
    for source in sources:
        fn = collectors.get(source)
        if fn is None:
            errors.append(CollectError(source=source, message="unknown source"))
            continue
        try:
            res = fn(query, lens, settings=settings, collected_at=collected_at)
        except Exception as exc:  # belt-and-suspenders; collectors already guard
            errors.append(CollectError(source=source, message=str(exc)))
            continue
        for item in res.items:
            item.store_id = store_id      # 🏢 stamp tenancy centrally
        items.extend(res.items)
        errors.extend(res.errors)

    result = ScanResult(
        run_id=run_id, store_id=store_id, lens=lens, query=query,
        items=items, errors=errors, started_at=collected_at, finished_at=collected_at,
    )
    store.save(result)
    return result
