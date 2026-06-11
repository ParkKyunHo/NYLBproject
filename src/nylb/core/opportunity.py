from __future__ import annotations

# Transparent, deterministic opportunity score. NOT a verdict: a disclosed
# weighted sum of observed signals — the board shows the formula and every
# part, and the owner judges. No LLM, no prescriptive wording anywhere.

WEIGHTS = {"interest": 0.30, "growth": 0.30, "season": 0.25, "direction": 0.15}
FORMULA_LABEL = "관심도 30% · 30일 성장 30% · 시즌 25% · 방향 15%"

_PART_LABELS = {"interest": "검색 관심도", "growth": "30일 성장",
                "season": "시즌 근접", "direction": "추세 방향"}
_DIRECTION_PTS = {"up": 100.0, "steady": 60.0, "down": 20.0}
_SEASON_NEUTRAL = 50.0


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def score(cm: dict, season: dict | None) -> dict:
    """Composite 0-100 opportunity score for one ContextualizedMetric.

    interest  : latest interest as-is (already 0-100 anchored scale).
    growth    : vs_baseline % mapped from [-50%, +100%] onto [0, 100].
    season    : best of (now, next-month) seasonal index mapped from
                [50, 200] onto [0, 100]; neutral 50 when no monthly data.
    direction : up=100 / steady=60 / down=20.
    """
    interest = _clamp(float(cm.get("value") or 0.0))

    vsb = cm.get("vs_baseline")
    vsb = 0.0 if vsb is None else float(vsb)
    growth = _clamp((vsb + 50.0) / 150.0 * 100.0)

    if season and season.get("status") not in (None, "no_data"):
        idx = max(float(season.get("now_index") or 0.0),
                  float(season.get("next_index") or 0.0))
        season_pts = _clamp((idx - 50.0) / 150.0 * 100.0)
    else:
        season_pts = _SEASON_NEUTRAL

    direction_pts = _DIRECTION_PTS.get(cm.get("direction"), _SEASON_NEUTRAL)

    raw = {"interest": interest, "growth": growth,
           "season": season_pts, "direction": direction_pts}
    parts = {k: {"label": _PART_LABELS[k], "points": round(v, 1),
                 "weight": WEIGHTS[k]} for k, v in raw.items()}
    total = sum(raw[k] * WEIGHTS[k] for k in raw)
    return {"score": round(total, 1), "parts": parts, "formula": FORMULA_LABEL}
