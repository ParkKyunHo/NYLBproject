from __future__ import annotations

from collections import defaultdict

from nylb.core.schema import ScanResult

_TREND_SOURCES = ("google_trends", "naver_datalab")


def _trend_stats(series: list[dict]) -> dict:
    by_day: dict[str, list[float]] = defaultdict(list)
    for p in series:
        by_day[p["date"]].append(float(p["value"]))
    daily = {d: round(sum(v) / len(v), 1) for d, v in sorted(by_day.items())}
    days = list(daily)
    last = [daily[d] for d in days[-3:]] or [0.0]
    prev = [daily[d] for d in days[:-3]] or last
    recent_avg = sum(last) / len(last)
    base_avg = sum(prev) / len(prev)
    values = list(daily.values())
    return {
        "daily": daily,
        "peak": round(max(values, default=0.0), 1),
        "latest": values[-1] if values else 0.0,
        "recent_avg": round(recent_avg, 1),
        "base_avg": round(base_avg, 1),
        "momentum": round(recent_avg - base_avg, 1),
    }


def extract_chart_data(result: ScanResult) -> dict:
    counts: dict[str, int] = defaultdict(int)
    for it in result.items:
        counts[it.source] += 1

    trends: dict[str, dict] = {s: {} for s in _TREND_SOURCES}
    monthly: dict[str, dict] = {s: {} for s in _TREND_SOURCES}
    rising: list[dict] = []
    for it in result.items:
        if it.source in _TREND_SOURCES and it.type == "search_term":
            trends[it.source][it.title] = _trend_stats(it.raw.get("series", []))
        elif it.source in _TREND_SOURCES and it.type == "search_term_monthly":
            monthly[it.source][it.title] = it.raw.get("series", [])
        elif it.type == "rising_query":
            rising.append({"seed": it.raw.get("seed", ""), "query": it.title,
                           "value": it.metrics.get("value", 0.0)})

    keywords = list(result.query.get("keywords", []))
    matrix: dict[str, dict] = {}
    for kw in keywords:
        row: dict[str, int] = defaultdict(int)
        for it in result.items:
            hay = f"{it.title} {it.text or ''}"
            if kw in hay:
                row[it.source] += 1
        matrix[kw] = {s: row.get(s, 0) for s in ("youtube", "naver", "google_trends")}

    competitors = [
        {"brand": it.author, "product": it.title,
         "price": it.metrics.get("price"), "base_price": it.metrics.get("base_price"),
         "url": it.url}
        for it in result.items if it.source == "kurly"
    ]

    own_by_key: dict[str, list[dict]] = defaultdict(list)
    for op in result.query.get("own_products", []):
        own_by_key[op.get("match_key")].append(op)
    comp_cfg = {c.get("url"): c for c in result.query.get("competitor_products", [])}

    comparisons: list[dict] = []
    for it in result.items:
        if it.source != "kurly":
            continue
        cfg = comp_cfg.get(it.url, {})
        mk = cfg.get("match_key")
        comp_price = it.metrics.get("price")
        if not mk or mk not in own_by_key or not comp_price:
            continue
        for op in own_by_key[mk]:
            nylb_price = op.get("price")
            if nylb_price is None:
                continue
            diff = nylb_price - comp_price
            comparisons.append({
                "match_key": mk,
                "category": op.get("category", mk),
                "nylb_product": op.get("product"),
                "nylb_price": nylb_price,
                "competitor_brand": it.author,
                "competitor_product": it.title,
                "competitor_price": comp_price,
                "competitor_basis": cfg.get("basis"),
                "diff": diff,
                "diff_pct": round(diff / comp_price * 100, 1),
                "position": "above" if diff > 0 else "below" if diff < 0 else "equal",
            })

    return {
        "counts": dict(counts),
        "trends": {s: trends[s] for s in _TREND_SOURCES},
        "monthly": {s: monthly[s] for s in _TREND_SOURCES},
        "matrix": matrix,
        "rising": rising,
        "competitors": competitors,
        "comparisons": comparisons,
        "keywords": keywords,
        "radar_watchlist": list(result.query.get("radar_watchlist", [])),
        "radar_categories": dict(result.query.get("radar_categories", {})),
    }
