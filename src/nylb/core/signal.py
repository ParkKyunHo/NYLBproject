from __future__ import annotations

import re
from datetime import datetime

from nylb.core.schema import Item, ScanResult

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


# ---------------------------------------------------------------------------
# Recency × popularity scoring (Task 2)
# ---------------------------------------------------------------------------

_HALF_LIFE_DAYS = 30.0


def _item_key(item: Item) -> str:
    return item.url or f"{item.source}:{item.title}"


def popularity(item: Item) -> float:
    """Raw (un-normalized) popularity by source."""
    m = item.metrics
    if item.source == "youtube":
        return m.get("views", 0.0) + m.get("likes", 0.0) * 5 + m.get("comments", 0.0) * 10
    if item.source in ("google_trends", "naver_datalab"):
        return m.get("interest", m.get("value", 0.0))
    if item.source == "naver":
        return 1.0  # no popularity metric; low base so recency/relevance decide order
    return m.get("interest", 0.0)


def recency_weight(item: Item, now: datetime) -> float:
    """Exponential time-decay (≈30-day half-life). Undated items (trend signals) = 1.0."""
    pub = item.published_at
    if pub is None:
        return 1.0
    if pub.tzinfo is None and now.tzinfo is not None:
        pub = pub.replace(tzinfo=now.tzinfo)
    elif pub.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=pub.tzinfo)
    age_days = max(0.0, (now - pub).total_seconds() / 86400.0)
    return max(0.1, 0.5 ** (age_days / _HALF_LIFE_DAYS))


def score_items(result: ScanResult, now: datetime) -> dict[str, float]:
    """Per-item recency×popularity, normalized WITHIN each source so raw YouTube
    view counts don't swamp 0–100 trend interest."""
    max_pop: dict[str, float] = {}
    for it in result.items:
        p = popularity(it)
        if p > max_pop.get(it.source, 0.0):
            max_pop[it.source] = p
    scores: dict[str, float] = {}
    for it in result.items:
        mp = max_pop.get(it.source, 0.0)
        norm = (popularity(it) / mp) if mp > 0 else 0.0
        scores[_item_key(it)] = norm * recency_weight(it, now)
    return scores
