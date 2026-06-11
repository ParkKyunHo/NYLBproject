from __future__ import annotations

import httpx

from nylb.collectors.base import strip_html
from nylb.core.signal import normalize

_URL = "https://openapi.naver.com/v1/search/news.json"
_FETCH = 30  # over-fetch, then gate — wrong news is worse than no news

# Generic F&B context words (no brand/product literals). A headline must carry
# at least one of these to count as food-business news; lens config can
# override via `news_context_terms`.
_FNB_CONTEXT = [
    "디저트", "카페", "베이커리", "빵", "베이킹", "메뉴", "신메뉴", "출시",
    "맛집", "음료", "케이크", "프랜차이즈", "외식", "편의점", "팝업",
    "콜라보", "시즌 한정", "시즌한정", "한정판", "레시피", "먹거리",
    "식품", "푸드", "브런치", "매장", "오픈런", "신제품",
]


def _passes(term: str, title: str, desc: str, context_terms: list[str]) -> bool:
    # Term gate is TITLE-only: a passing mention buried in the summary (drone
    # news listing 옥수수 once) is exactly the mismatch the owner flagged.
    if normalize(term) not in normalize(title):
        return False
    hay = normalize(f"{title} {desc}")
    return any(normalize(c) in hay for c in context_terms if c)


def collect(terms: list[str], *, settings: dict, max_per_term: int = 3,
            context_terms: list[str] | None = None) -> dict[str, list[dict]]:
    """Recent F&B-relevant Naver news per term (title/link/date). Deterministic
    context — NO summarization, NO verdict. Two gates: the term must appear in
    title+summary, and an F&B context word must too. Zero matches -> the term
    is simply absent (an empty slot beats a wrong headline). Best-effort:
    returns {} when creds/scope unavailable; never raises."""
    cid = settings.get("naver_client_id")
    csec = settings.get("naver_client_secret")
    if not (cid and csec):
        return {}
    ctx = list(context_terms) if context_terms else _FNB_CONTEXT
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
    out: dict[str, list[dict]] = {}
    for term in terms:
        try:
            # sort=sim (relevance): title-matching articles surface first; with
            # sort=date the term usually only grazes the body of recent items.
            r = httpx.get(_URL, params={"query": term, "display": _FETCH, "sort": "sim"},
                          headers=headers, timeout=15)
            r.raise_for_status()
            heads = []
            for it in r.json().get("items", []):
                title = strip_html(it.get("title", ""))
                desc = strip_html(it.get("description", ""))
                if not _passes(term, title, desc, ctx):
                    continue
                heads.append({"title": title, "link": it.get("link", ""),
                              "date": it.get("pubDate", "")})
                if len(heads) >= max_per_term:
                    break
            if heads:
                out[term] = heads
        except Exception:
            continue  # best-effort per term (scope disabled / rate / network)
    return out
