from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from nylb.core.schema import CollectError, CollectResult, Item

SOURCE = "naver_datalab"
_URL = "https://openapi.naver.com/v1/datalab/search"
# Seasonality needs multi-year context: a second pass fetches ~3 years of
# monthly data (timeUnit=month) on top of the 30-day daily pass.
MONTHLY_LOOKBACK_DAYS = 1095
_PASSES = (("date", 30, "search_term"),
           ("month", MONTHLY_LOOKBACK_DAYS, "search_term_monthly"))


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _rescale(series: list[dict], factor: float) -> list[dict]:
    return [{"date": p["date"], "value": round(p["value"] * factor, 2)} for p in series]


def _fetch(query: dict, settings: dict, *,
           time_unit: str = "date", days: int = 30) -> dict:
    cid = settings.get("naver_client_id")
    csec = settings.get("naver_client_secret")
    if not (cid and csec):
        raise RuntimeError("NAVER credentials missing")
    terms = list(query.get("keywords", [])) + list(query.get("radar_watchlist", []))
    terms = [t for t in dict.fromkeys(terms) if t]
    if not terms:
        return {"results": []}
    anchor = query.get("anchor")
    if anchor not in terms:
        anchor = None  # anchor must be queryable to rescale; else legacy
    others = [t for t in terms if t != anchor]
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec,
               "Content-Type": "application/json"}
    out: list[dict] = []
    seen: set[str] = set()
    errs: list[str] = []
    # anchor + 4 others per request (5 = DataLab max). The anchor is in every
    # batch so terms rescale to a common scale; per-batch try/except below keeps
    # successful batches if one request fails (resilience). ~9 calls for a 30-term universe.
    batch_size = 4 if anchor else 5
    for group in _chunks(others, batch_size):
        names = ([anchor] + list(group)) if anchor else list(group)
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(),
                "timeUnit": time_unit,
                "keywordGroups": [{"groupName": t, "keywords": [t]} for t in names]}
        try:
            r = httpx.post(_URL, json=body, headers=headers, timeout=30)
            r.raise_for_status()
            raw = {res.get("title", ""): [{"date": d["period"], "value": float(d["ratio"])}
                                          for d in res.get("data", [])]
                   for res in r.json().get("results", [])}
        except Exception as exc:
            errs.append(f"batch {names}: {exc}")
            continue
        factor = 1.0
        if anchor:
            avals = [p["value"] for p in raw.get(anchor, [])]
            amean = sum(avals) / len(avals) if avals else 0.0
            factor = (100.0 / amean) if amean > 0 else 1.0
        for name, series in raw.items():
            if name in seen:
                continue
            seen.add(name)
            out.append({"title": name,
                        "series": _rescale(series, factor) if anchor else series})
    return {"results": out, "errors": errs}


def _parse(payload: dict, query: dict, lens: str, collected_at: datetime,
           item_type: str = "search_term") -> list[Item]:
    items: list[Item] = []
    for res in payload.get("results", []):
        series = res["series"]
        latest = series[-1]["value"] if series else 0.0
        peak = max((p["value"] for p in series), default=0.0)
        items.append(Item(
            source=SOURCE, lens=lens, type=item_type, title=res["title"],
            metrics={"interest": latest, "peak": peak},
            collected_at=collected_at, raw={"series": series},
        ))
    return items


def collect(query: dict, lens: str, *, settings: dict, collected_at: datetime) -> CollectResult:
    items: list[Item] = []
    errors: list[CollectError] = []
    for time_unit, days, item_type in _PASSES:
        try:
            payload = _fetch(query, settings, time_unit=time_unit, days=days)
        except Exception as exc:
            errors.append(CollectError(source=SOURCE, message=f"{time_unit}: {exc}"))
            continue
        items.extend(_parse(payload, query, lens, collected_at, item_type=item_type))
        errors.extend(CollectError(source=SOURCE, message=f"{time_unit}: {m}")
                      for m in payload.get("errors", []))
    return CollectResult(items=items, errors=errors)
