from __future__ import annotations

from nylb.collectors import naver_news
from nylb.report.board import trend_source


def gather_riser_news(result, chart, settings: dict, top_n: int = 5) -> dict:
    """Pick the top risers (by momentum) across the tracked trend universe and fetch
    recent Naver news headlines for them. I/O lives here so build_board stays pure.
    Returns {} on no creds (best-effort)."""
    source = trend_source(chart)
    tstats = chart["trends"].get(source, {})
    risers = sorted(tstats.items(), key=lambda kv: kv[1].get("momentum", 0.0), reverse=True)
    terms = [t for t, st in risers if st.get("momentum", 0.0) > 0][:top_n]
    if not terms:
        return {}
    ctx = (getattr(result, "query", None) or {}).get("news_context_terms") or None
    return naver_news.collect(terms, settings=settings, max_per_term=3,
                              context_terms=ctx)
