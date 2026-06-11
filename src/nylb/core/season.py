from __future__ import annotations

from collections import defaultdict

# A calendar month is a "peak" when its seasonal index is >= this threshold
# (index 100 = the term's own all-period average).
PEAK_INDEX = 115.0
# Fewer observed months than this -> flag the profile as low-coverage.
MIN_COVERAGE_MONTHS = 12


def monthly_profile(series: list[dict]) -> dict[int, float]:
    """Calendar-month seasonal index from a multi-year monthly series.

    Averages each calendar month (1-12) across years, then normalizes so the
    mean over observed months = 100. Pure; index is per-term (scale-free), so
    anchor rescaling upstream does not affect it.
    """
    by_month: dict[int, list[float]] = defaultdict(list)
    for p in series:
        date = str(p.get("date", ""))
        if len(date) < 7:
            continue
        by_month[int(date[5:7])].append(float(p.get("value", 0.0)))
    if not by_month:
        return {}
    avgs = {m: sum(v) / len(v) for m, v in by_month.items()}
    overall = sum(avgs.values()) / len(avgs)
    if overall <= 0:
        return {m: 0.0 for m in avgs}
    return {m: round(a / overall * 100, 1) for m, a in avgs.items()}


def season_summary(profile: dict[int, float], month_now: int) -> dict:
    """Classify where `month_now` sits in a term's season. Pure, rule-based.

    status: in_season (now is a peak month) / entering (a peak month is 1-2
    months ahead — preparation window) / off / no_data. Observation only —
    carries no prescriptive wording.
    """
    if not profile:
        return {"status": "no_data", "peak_months": [], "now_index": None,
                "next_index": None, "coverage_months": 0, "low_coverage": True,
                "profile": {}}
    peaks = sorted(m for m, v in profile.items() if v >= PEAK_INDEX)
    nxt1 = month_now % 12 + 1
    nxt2 = nxt1 % 12 + 1
    if month_now in peaks:
        status = "in_season"
    elif nxt1 in peaks or nxt2 in peaks:
        status = "entering"
    else:
        status = "off"
    coverage = len(profile)
    return {
        "status": status,
        "peak_months": peaks,
        "now_index": profile.get(month_now),
        "next_index": profile.get(nxt1),
        "coverage_months": coverage,
        "low_coverage": coverage < MIN_COVERAGE_MONTHS,
        "profile": dict(profile),
    }
