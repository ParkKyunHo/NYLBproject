from __future__ import annotations

_EPS = 1e-9


def direction(momentum: float) -> str:
    if momentum > 0.5:
        return "up"
    if momentum < -0.5:
        return "down"
    return "steady"


def contextualize(term: str, stats: dict,
                  rank: int | None = None, total: int | None = None) -> dict:
    """Attach decision-support context to ONE trend metric. Pure, rule-based.
    `stats` is a chart_data._trend_stats dict (latest/recent_avg/base_avg/
    momentum/peak/daily). Describes what the numbers SAY — never prescribes."""
    latest = float(stats.get("latest", 0.0))
    base = float(stats.get("base_avg", 0.0))
    mom = float(stats.get("momentum", 0.0))
    vs_baseline = round((mom / base) * 100, 0) if abs(base) > _EPS else None
    recent_drop = latest < float(stats.get("recent_avg", 0.0))
    cm = {
        "term": term,
        "value": round(latest, 1),
        "peak": stats.get("peak", 0.0),
        "direction": direction(mom),
        "momentum": mom,
        "vs_baseline": vs_baseline,
        "recent_drop": recent_drop,
        "rank": rank,
        "total": total,
    }
    cm["caption"] = caption(cm)
    return cm


def caption(cm: dict) -> str:
    """One-line OBSERVATION (rule-based). Never contains prescriptive wording."""
    # Interest is anchor-relative (anchor's 30-day mean = 100), so values can
    # exceed 100 — never print a "/100" denominator here.
    parts = [f"관심도 {cm['value']:.0f}"]
    if cm.get("rank") is not None and cm.get("total"):
        parts.append(f"{cm['total']}개 중 {cm['rank']}위")
    if cm.get("vs_baseline") is not None:
        sign = "+" if cm["vs_baseline"] >= 0 else ""
        parts.append(f"30일 평균 {sign}{cm['vs_baseline']:.0f}%")
    if cm.get("recent_drop") and cm.get("direction") != "up":
        parts.append("단 최근 하락")
    return " · ".join(parts)
