from __future__ import annotations

import re

from nylb.core.schema import ScanResult
from nylb.core.signal import item_key, score_items

_CONTENT_SOURCES = {"youtube", "naver"}
_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")

# F&B-generic stopwords (NO specific food/brand literals — works across verticals).
_BASE_STOPWORDS = {
    "맛집", "카페", "후기", "추천", "먹방", "브이로그", "신상", "메뉴", "매장",
    "리뷰", "만들기", "레시피", "asmr", "vlog", "shorts", "the", "in", "of",
    "내돈내산", "존맛", "꿀팁", "방문", "오픈", "위치", "가격",
}


def _ngrams(tokens: list[str]) -> list[str]:
    grams = list(tokens)
    grams += [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]
    return grams


def discover_candidates(result: ScanResult, top_n: int = 10) -> list[dict]:
    """Mine candidate (not-yet-tracked) terms from Tier-A content titles + Google
    rising. Pure, heuristic, NO LLM — surfaced as board data for owner approval."""
    q = result.query
    known = {t.lower() for t in q.get("keywords", [])}
    known |= {t.lower() for t in q.get("radar_categories", {})}
    for syns in (q.get("synonyms", {}) or {}).values():
        known |= {s.lower() for s in syns}
    stop = set(_BASE_STOPWORDS) | {s.lower() for s in q.get("discover_stopwords", [])}

    scores = score_items(result, result.finished_at)

    freq: dict[str, int] = {}
    sig: dict[str, float] = {}
    srcs: dict[str, set] = {}
    sample: dict[str, str] = {}
    rising: dict[str, float] = {}

    for it in result.items:
        if it.type == "rising_query":
            term = it.title.strip()
            if term and term.lower() not in known:
                rising[term] = max(rising.get(term, 0.0), it.metrics.get("value", 0.0))
            continue
        if it.source not in _CONTENT_SOURCES:
            continue
        tokens = _TOKEN.findall(it.title)
        for g in _ngrams(tokens):
            k = g.lower()
            toks = k.split()
            if any(tok in known or tok in stop for tok in toks):
                continue
            if k in known or k in stop or len(g) < 2 or g.isdigit():
                continue
            freq[g] = freq.get(g, 0) + 1
            sig[g] = sig.get(g, 0.0) + scores.get(item_key(it), 0.0)
            srcs.setdefault(g, set()).add(it.source)
            sample.setdefault(g, it.title)

    cands = [{"term": g, "freq": freq[g], "signal": round(sig[g], 3),
              "sources": sorted(srcs[g]), "sample_title": sample[g], "from_rising": False}
             for g in freq if freq[g] >= 2]
    for term, val in rising.items():
        cands.append({"term": term, "freq": 0, "signal": round(val, 1),
                      "sources": ["google_trends"], "sample_title": "",
                      "from_rising": True})
    cands.sort(key=lambda c: (c["freq"], c["signal"]), reverse=True)
    return cands[:top_n]
