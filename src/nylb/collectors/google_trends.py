from __future__ import annotations

from datetime import datetime

from nylb.core.schema import CollectError, CollectResult, Item

SOURCE = "google_trends"


def _fetch(query: dict, settings: dict) -> dict:
    from pytrends.request import TrendReq

    keywords = query.get("keywords", [])[:5]
    if not keywords:
        return {}
    pytrends = TrendReq(hl="ko-KR", tz=540)
    pytrends.build_payload(keywords, timeframe="now 7-d", geo="KR")
    df = pytrends.interest_over_time()
    out: dict[str, list[dict]] = {}
    for kw in keywords:
        if kw in df.columns:
            out[kw] = [{"date": str(idx.date()), "value": int(val)}
                       for idx, val in df[kw].items()]
    return out


def _parse(interest: dict, query: dict, lens: str, collected_at: datetime) -> list[Item]:
    items: list[Item] = []
    for keyword, series in interest.items():
        latest = float(series[-1]["value"]) if series else 0.0
        peak = float(max((p["value"] for p in series), default=0))
        items.append(Item(
            source=SOURCE, lens=lens, type="search_term",
            title=keyword, metrics={"interest": latest, "peak": peak},
            collected_at=collected_at, raw={"series": series},
        ))
    return items


def collect(query: dict, lens: str, *, settings: dict, collected_at: datetime) -> CollectResult:
    try:
        interest = _fetch(query, settings)
        return CollectResult(items=_parse(interest, query, lens, collected_at))
    except Exception as exc:
        return CollectResult(errors=[CollectError(source=SOURCE, message=str(exc))])
