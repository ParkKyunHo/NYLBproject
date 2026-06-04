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
    rising: list[dict] = []
    for it in result.items:
        if it.source in _TREND_SOURCES and it.type == "search_term":
            trends[it.source][it.title] = _trend_stats(it.raw.get("series", []))
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
        matrix[kw] = dict(row)

    return {
        "counts": dict(counts),
        "trends": {s: trends[s] for s in _TREND_SOURCES},
        "matrix": matrix,
        "rising": rising,
        "keywords": keywords,
        "radar_watchlist": list(result.query.get("radar_watchlist", [])),
    }
