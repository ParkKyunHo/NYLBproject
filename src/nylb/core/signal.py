from __future__ import annotations

import re

from nylb.core.schema import Item

_WS = re.compile(r"\s+")

# Trend sources (google_trends, naver_datalab) ARE the keyword, and kurly is
# competitor products matched by URL — all exempt from the relevance gate.
FILTERABLE_SOURCES = {"youtube", "naver", "instagram"}


def _norm(text: str | None) -> str:
    return _WS.sub(" ", (text or "").lower()).strip()


def is_relevant(item: Item, keywords: list[str],
                synonyms: dict[str, list[str]] | None = None) -> bool:
    """True if any lens keyword (or a configured synonym) appears in title+text."""
    synonyms = synonyms or {}
    hay = _norm(f"{item.title} {item.text or ''}")
    terms: list[str] = []
    for kw in keywords:
        terms.append(kw)
        terms.extend(synonyms.get(kw, []))
    return any(_norm(t) in hay for t in terms if t)


def filter_relevant(items: list[Item], keywords: list[str],
                    synonyms: dict[str, list[str]] | None = None
                    ) -> tuple[list[Item], dict[str, int]]:
    """Drop off-topic items from FILTERABLE_SOURCES; return (kept, dropped_by_source).
    No-op when keywords is empty (e.g. competitor lens)."""
    if not keywords:
        return list(items), {}
    kept: list[Item] = []
    dropped: dict[str, int] = {}
    for it in items:
        if it.source in FILTERABLE_SOURCES and not is_relevant(it, keywords, synonyms):
            dropped[it.source] = dropped.get(it.source, 0) + 1
            continue
        kept.append(it)
    return kept, dropped
