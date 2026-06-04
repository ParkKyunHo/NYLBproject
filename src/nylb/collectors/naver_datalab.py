from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from nylb.core.schema import CollectError, CollectResult, Item

SOURCE = "naver_datalab"
_URL = "https://openapi.naver.com/v1/datalab/search"


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _fetch(query: dict, settings: dict) -> dict:
    cid = settings.get("naver_client_id")
    csec = settings.get("naver_client_secret")
    if not (cid and csec):
        raise RuntimeError("NAVER credentials missing")
    terms = list(query.get("keywords", [])) + list(query.get("radar_watchlist", []))
    terms = [t for t in dict.fromkeys(terms) if t]   # dedupe, keep order, drop empties
    if not terms:
        return {"results": []}
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=30)
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec,
               "Content-Type": "application/json"}
    results: list[dict] = []
    for group in _chunks(terms, 5):
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "timeUnit": "date",
            "keywordGroups": [{"groupName": t, "keywords": [t]} for t in group],
        }
        r = httpx.post(_URL, json=body, headers=headers, timeout=20)
        r.raise_for_status()
        results.extend(r.json().get("results", []))
    return {"results": results}


def _parse(payload: dict, query: dict, lens: str, collected_at: datetime) -> list[Item]:
    items: list[Item] = []
    for res in payload.get("results", []):
        series = [{"date": d["period"], "value": float(d["ratio"])}
                  for d in res.get("data", [])]
        latest = series[-1]["value"] if series else 0.0
        peak = max((p["value"] for p in series), default=0.0)
        items.append(Item(
            source=SOURCE, lens=lens, type="search_term",
            title=res.get("title", ""),
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
