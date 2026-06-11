from __future__ import annotations

from nylb.collectors import naver_news
from nylb.report.board import trend_source

# Launch-specific context: a brand headline only counts as "new product news"
# when it carries one of these. Tighter than the F&B default list on purpose.
_LAUNCH_CONTEXT = ["신메뉴", "출시", "신제품", "콜라보", "한정판", "시즌 한정",
                   "시즌한정", "리뉴얼", "팝업", "첫선", "선보여", "선보인다"]


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


def gather_brand_launches(result, settings: dict, *, max_brands: int = 10,
                          max_per_brand: int = 3) -> dict:
    """Competitor new-product intel: per tracked brand, recent news that passes
    the launch-context gate (신메뉴/출시/콜라보...). Deterministic feed — what
    competitors are shipping, no interpretation. {} on no creds/brands."""
    cats = (getattr(result, "query", None) or {}).get("radar_categories", {}) or {}
    brands = [t for t, c in cats.items() if c == "brands"][:max_brands]
    if not brands:
        return {}
    return naver_news.collect(brands, settings=settings, max_per_term=max_per_brand,
                              context_terms=_LAUNCH_CONTEXT)
