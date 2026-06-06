from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from nylb.core.schema import CollectError, CollectResult, Item

SOURCE = "naver_datalab"
_URL = "https://openapi.naver.com/v1/datalab/search"


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _rescale(series: list[dict], factor: float) -> list[dict]:
    return [{"date": p["date"], "value": round(p["value"] * factor, 2)} for p in series]


def _fetch(query: dict, settings: dict) -> dict:
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
    start = end - timedelta(days=30)
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec,
               "Content-Type": "application/json"}
    out: list[dict] = []
    seen: set[str] = set()
    batch_size = 1 if anchor else 5
    for group in _chunks(others, batch_size):
        names = ([anchor] + list(group)) if anchor else list(group)
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(),
                "timeUnit": "date",
                "keywordGroups": [{"groupName": t, "keywords": [t]} for t in names]}
        r = httpx.post(_URL, json=body, headers=headers, timeout=20)
        r.raise_for_status()
        raw = {res.get("title", ""): [{"date": d["period"], "value": float(d["ratio"])}
                                      for d in res.get("data", [])]
               for res in r.json().get("results", [])}
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
                        "series": _rescale(series, factor) if anchor else
                                  [{"date": p["date"], "value": p["value"]} for p in series]})
    return {"results": out}


def _parse(payload: dict, query: dict, lens: str, collected_at: datetime) -> list[Item]:
    items: list[Item] = []
    for res in payload.get("results", []):
        series = res["series"]
        latest = series[-1]["value"] if series else 0.0
        peak = max((p["value"] for p in series), default=0.0)
        items.append(Item(
            source=SOURCE, lens=lens, type="search_term", title=res["title"],
            metrics={"interest": latest, "peak": peak},
            collected_at=collected_at, raw={"series": series},
        ))
    return items


def collect(query: dict, lens: str, *, settings: dict, collected_at: datetime) -> CollectResult:
    try:
        payload = _fetch(query, settings)
        return CollectResult(items=_parse(payload, query, lens, collected_at))
    except Exception as exc:
        return CollectResult(errors=[CollectError(source=SOURCE, message=str(exc))])
