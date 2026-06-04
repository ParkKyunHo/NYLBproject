from __future__ import annotations

import re

from nylb.core.schema import Item

_WS = re.compile(r"\s+")

# Free-text content sources that the relevance gate applies to.
FILTERABLE_SOURCES = {"youtube", "naver", "instagram"}
# Sources NOT in FILTERABLE_SOURCES are intentionally exempt from the gate:
#   google_trends, naver_datalab — they ARE the keyword (interest signal)
#   kurly                        — competitor products matched by URL, not text
# When adding a new Source in schema.py, decide which bucket it belongs to.


def _norm(text: str | None) -> str:
    return _WS.sub(" ", (text or "").lower()).strip()


def is_relevant(item: Item, keywords: list[str],
                synonyms: dict[str, list[str]] | None = None) -> bool:
    """True if any lens keyword (or a configured synonym) appears in title+text.

    Deliberately a loose substring match (case/whitespace-normalized) to favor
    recall — the design goal is "drop clearly off-topic", not precision ranking.
    Revisit with word-boundary matching only if short/ambiguous Latin keywords
    are ever added to a lens (current keywords are multi-char and unambiguous).
    """
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
