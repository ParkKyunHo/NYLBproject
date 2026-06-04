from __future__ import annotations

from datetime import datetime

from nylb.core.schema import CollectError, CollectResult, Item

SOURCE = "google_trends"


def _rising_value(v) -> int:
    """pytrends rising values are ints, except 'Breakout' (>5000% surge)."""
    s = str(v).strip()
    try:
        return int(s)
    except ValueError:
        return 9999 if s.lower() == "breakout" else 0


def _fetch(query: dict, settings: dict) -> dict:
    from pytrends.request import TrendReq

    keywords = query.get("keywords", [])[:5]
    out: dict = {"interest": {}, "rising": []}
    if not keywords:
        return out
    pytrends = TrendReq(hl="ko-KR", tz=540)
    pytrends.build_payload(keywords, timeframe="now 7-d", geo="KR")
    df = pytrends.interest_over_time()
    for kw in keywords:
        if kw in df.columns:
            out["interest"][kw] = [{"date": str(idx.date()), "value": int(val)}
                                   for idx, val in df[kw].items()]
    # rising adjacent-trend auto-discovery — best-effort, never break core interest
    try:
        related = pytrends.related_queries()
        for seed in keywords:
            block = related.get(seed) or {}
            rising_df = block.get("rising")
            if rising_df is not None:
                for _, row in rising_df.head(5).iterrows():
                    out["rising"].append({"seed": seed, "query": str(row["query"]),
                                          "value": _rising_value(row["value"])})
    except Exception:
        pass
    return out


def _parse(payload: dict, query: dict, lens: str, collected_at: datetime) -> list[Item]:
    items: list[Item] = []
    for keyword, series in payload.get("interest", {}).items():
        latest = float(series[-1]["value"]) if series else 0.0
        peak = float(max((p["value"] for p in series), default=0))
        items.append(Item(
            source=SOURCE, lens=lens, type="search_term",
            title=keyword, metrics={"interest": latest, "peak": peak},
            collected_at=collected_at, raw={"series": series},
        ))
    for r in payload.get("rising", []):
        items.append(Item(
            source=SOURCE, lens=lens, type="rising_query",
            title=r["query"], metrics={"value": float(r["value"])},
            collected_at=collected_at, raw={"seed": r["seed"]},
        ))
    return items


def collect(query: dict, lens: str, *, settings: dict, collected_at: datetime) -> CollectResult:
    try:
        interest = _fetch(query, settings)
        return CollectResult(items=_parse(interest, query, lens, collected_at))
    except Exception as exc:
        return CollectResult(errors=[CollectError(source=SOURCE, message=str(exc))])
