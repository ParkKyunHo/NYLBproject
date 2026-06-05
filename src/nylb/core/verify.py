from __future__ import annotations

from nylb.core.schema import Item
from nylb.core.signal import is_relevant


def _corroboration(term: str, content_items: list[Item]) -> int:
    """Count free-text items whose title/text contains `term` (same normalized
    substring matcher as the relevance gate)."""
    return sum(1 for it in content_items if is_relevant(it, [term]))


def verify_rising(
    rising: list[dict],
    content_items: list[Item],
    datalab_terms: set[str],
    known_terms: set[str],
    *,
    min_corroboration: int = 2,
) -> dict[str, list[dict]]:
    """Split google rising_query terms into verified vs unverified (phantom).

    VERIFIED if ANY of: the term equals a known keyword/synonym/radar term,
    it has a DataLab interest signal, or >= min_corroboration content items
    mention it. Otherwise UNVERIFIED -> quarantine (never promoted to a
    radar/competitor card). Each entry carries corroboration evidence.
    """
    norm_known = {t.lower().strip() for t in known_terms}
    norm_datalab = {t.lower().strip() for t in datalab_terms}
    verified: list[dict] = []
    unverified: list[dict] = []
    for r in rising:
        term = r.get("query", "")
        key = term.lower().strip()
        corr = _corroboration(term, content_items)
        in_known = key in norm_known
        in_datalab = key in norm_datalab
        entry = {**r, "corroboration": corr,
                 "in_datalab": in_datalab, "in_known": in_known}
        if in_known or in_datalab or corr >= min_corroboration:
            verified.append(entry)
        else:
            entry["why"] = "실존 미확인 — 콘텐츠·데이터랩 뒷받침 없음"
            unverified.append(entry)
    return {"verified": verified, "unverified": unverified}
