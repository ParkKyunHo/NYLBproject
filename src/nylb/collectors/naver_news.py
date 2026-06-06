from __future__ import annotations

import httpx

from nylb.collectors.base import strip_html

_URL = "https://openapi.naver.com/v1/search/news.json"


def collect(terms: list[str], *, settings: dict, max_per_term: int = 3) -> dict[str, list[dict]]:
    """Recent Naver news headlines per term (title/link/date). Deterministic context
    for risers — NO summarization, NO verdict. Returns {} if creds/scope unavailable
    or on error (best-effort; never raises)."""
    cid = settings.get("naver_client_id")
    csec = settings.get("naver_client_secret")
    if not (cid and csec):
        return {}
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
    out: dict[str, list[dict]] = {}
    for term in terms:
        try:
            r = httpx.get(_URL, params={"query": term, "display": max_per_term, "sort": "date"},
                          headers=headers, timeout=15)
            r.raise_for_status()
            heads = [{"title": strip_html(it.get("title", "")),
                      "link": it.get("link", ""),
                      "date": it.get("pubDate", "")}
                     for it in r.json().get("items", [])[:max_per_term]]
            if heads:
                out[term] = heads
        except Exception:
            continue  # best-effort per term (scope disabled / rate / network)
    return out
