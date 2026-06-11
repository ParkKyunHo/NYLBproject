from __future__ import annotations

from nylb.core import opportunity
from nylb.core.context import contextualize
from nylb.core.discover import discover_candidates
from nylb.core.schema import ScanResult
from nylb.core.season import monthly_profile, season_summary
from nylb.core.verify import verify_rising

_COLORS = {"베이글": "#33598f", "소금빵": "#c2562a", "크로플": "#8d7d67"}
_PALETTE = ["#7a5ca8", "#2e7d4f", "#bf4934", "#c2912e", "#496f5d"]
_BRAND_CAT = "brands"  # the single config↔engine coupling: the radar category treated as brands


def trend_source(chart: dict) -> str:
    return "naver_datalab" if chart["trends"].get("naver_datalab") else "google_trends"


def build_chart_block(chart: dict) -> dict:
    """Render-ready line-chart block (dates/series/ymax) for the core keywords.
    Moved verbatim from the old html._build_chart so html.py stays render-only."""
    source = trend_source(chart)
    tsrc = chart["trends"].get(source, {})
    core = set(chart.get("keywords", []))
    items = [(kw, info) for kw, info in tsrc.items() if not core or kw in core]
    dates: list[str] = sorted({d for _, info in items for d in info["daily"]})
    series: dict[str, dict] = {}
    spare = list(_PALETTE)
    for kw, info in items:
        color = _COLORS.get(kw) or (spare.pop(0) if spare else "#888")
        series[kw] = {
            "color": color,
            "v": [info["daily"].get(d, 0) for d in dates],
            "peak": info.get("peak", 0),
            "mom": info.get("momentum", 0),
        }
    ymax = max([v for s in series.values() for v in s["v"]] + [5])
    ymax = int((ymax // 5 + 1) * 5)
    return {"dates": dates, "series": series, "ymax": ymax, "source": source}


def build_board(result: ScanResult, chart: dict, news_context=None) -> dict:
    """Assemble the deterministic decision-support board. No verdicts."""
    core = list(chart.get("keywords", []))
    core_set = set(core)
    source = trend_source(chart)
    tstats = chart["trends"].get(source, {})

    ranked = sorted(tstats.items(),
                    key=lambda kv: kv[1].get("latest", 0.0), reverse=True)
    rank_of = {term: i + 1 for i, (term, _) in enumerate(ranked)}
    total = len(ranked)

    # chart_data always populates radar_categories; query fallback covers hand-built chart dicts.
    cats = chart.get("radar_categories", {}) or result.query.get("radar_categories", {})

    # Seasonality: 3-year monthly series (DataLab) -> per-term seasonal summary.
    monthly_src = chart.get("monthly", {}) or {}
    monthly = monthly_src.get(source, {}) or monthly_src.get("naver_datalab", {})
    month_now = result.finished_at.month
    season_of = {term: season_summary(monthly_profile(series), month_now)
                 for term, series in monthly.items()}

    def _ctx(term, st):
        cm = contextualize(term, st, rank_of.get(term), total)
        cm["category"] = cats.get(term, "core" if term in core_set else "radar")
        cm["spark"] = list(st.get("daily", {}).values())[-31:]
        cm["season"] = season_of.get(term)
        return cm

    core_signals = [_ctx(t, tstats[t]) for t in core if t in tstats]

    def _is_brand(term):
        return cats.get(term) == _BRAND_CAT

    radar = [_ctx(t, st) for t, st in ranked
             if t not in core_set and not _is_brand(t)]

    # Brands: rescale to "% of the top brand". All terms are already normalized to the
    # PRODUCT anchor, so the anchor cancels in brand-vs-brand ratios — no extra query.
    brand_terms = [(t, st) for t, st in ranked if _is_brand(t)]
    _max_brand = max((st.get("latest", 0.0) for _, st in brand_terms), default=0.0)
    _bf = (100.0 / _max_brand) if _max_brand > 0 else 1.0

    def _brand_ctx(term, st):
        scaled = {**st,
                  "latest": st.get("latest", 0.0) * _bf,
                  "peak": st.get("peak", 0.0) * _bf,
                  "recent_avg": st.get("recent_avg", 0.0) * _bf,
                  "base_avg": st.get("base_avg", 0.0) * _bf,
                  "momentum": st.get("momentum", 0.0) * _bf}
        cm = contextualize(term, scaled, None, len(brand_terms))
        cm["momentum"] = round(cm["momentum"], 1)
        cm["category"] = _BRAND_CAT
        cm["spark"] = list(st.get("daily", {}).values())[-31:]  # shape-only, scale-free
        cm["season"] = None
        return cm

    brand_signals = [_brand_ctx(t, st) for t, st in brand_terms]
    # brand_signals and brand_ranking both order by the same rescaled latest value.
    brand_signals.sort(key=lambda c: c["value"], reverse=True)
    for i, c in enumerate(brand_signals, 1):
        c["rank"] = i
    brand_ranking = [{"term": t, "interest": round(st.get("latest", 0.0) * _bf, 1)}
                     for t, st in brand_terms]
    brand_ranking.sort(key=lambda x: x["interest"], reverse=True)

    content_items = [it for it in result.items if it.source in ("youtube", "naver")]
    datalab_terms = set(chart["trends"].get("naver_datalab", {}).keys())
    known_terms = core_set | set(chart.get("radar_watchlist", []))
    for syns in (result.query.get("synonyms", {}) or {}).values():
        known_terms.update(syns)
    verdict = verify_rising(chart.get("rising", []), content_items,
                            datalab_terms, known_terms)

    movers = sorted(core_signals + radar,
                    key=lambda c: c.get("momentum", 0.0), reverse=True)
    biggest = movers[0] if movers else None
    n_dropped = sum(result.dropped_by_source.values())

    # 지금 뜨는 제품: positive-momentum products only (no brands), top 6.
    rising_products = [c for c in movers if c.get("momentum", 0.0) > 0][:6]

    # 신메뉴 기회 보드: radar(=not yet ours, not a brand) terms scored by the
    # disclosed deterministic formula. Ranking only — judgement stays with the owner.
    opportunities = sorted(
        ({**c, "opportunity": opportunity.score(c, c.get("season"))} for c in radar),
        key=lambda c: c["opportunity"]["score"], reverse=True)[:8]

    # 시즌 캘린더: every product term with a seasonal profile, prep-window first.
    _SEASON_ORDER = {"entering": 0, "in_season": 1, "off": 2, "no_data": 3}
    season_calendar = sorted(
        ({"term": c["term"], "category": c["category"], "value": c["value"],
          "season": c["season"]}
         for c in core_signals + radar if c.get("season")),
        key=lambda e: (_SEASON_ORDER.get(e["season"]["status"], 9),
                       -(e["season"].get("next_index") or 0.0),
                       -(e["season"].get("now_index") or 0.0)))

    label = {"naver_datalab": "네이버 데이터랩",
             "google_trends": "Google Trends"}.get(source, source)
    counts = chart["counts"]
    sources_status = [
        {"name": "YouTube", "on": counts.get("youtube", 0) > 0},
        {"name": "Naver 검색", "on": counts.get("naver", 0) > 0},
        {"name": "Google Trends", "on": counts.get("google_trends", 0) > 0},
        {"name": "Naver DataLab", "on": counts.get("naver_datalab", 0) > 0},
        {"name": "Instagram", "on": counts.get("instagram", 0) > 0},
    ]
    data_trust = [{"note": f"{src} {n}건 관련성 필터 제외", "severity": "info"}
                  for src, n in result.dropped_by_source.items()]
    anchor = result.query.get("anchor") or "앵커"
    data_trust.append({"note": f"제품 검색 관심도는 {anchor}의 30일 평균=100 기준 상대 지표 — "
                               f"100 초과는 {anchor}보다 검색량이 많다는 뜻. "
                               "절대 수요 우열로 단정 금지", "severity": "info"})
    if season_of:
        data_trust.append({"note": "시즌 지수는 약 3년 월별 평균(자기 평균=100) 기반 — "
                                   "표본 12개월 미만 용어는 저신뢰 표시", "severity": "info"})
        data_trust.append({"note": "기회 점수는 공개 공식의 결정론 합산"
                                   f"({opportunity.FORMULA_LABEL}) — 평결 아님",
                           "severity": "info"})

    return {
        "meta": {
            "brand": "NYLB · NEW YORK LOVE BAGEL",
            "run_id": result.run_id,
            "collected": f"{result.finished_at:%Y-%m-%d}",
            "lens": result.lens,
            "items": len(result.items),
            "errors": len(result.errors),
            "counts": counts,
            "trend_label": label,
            "anchor": result.query.get("anchor"),
            "sources_status": sources_status,
        },
        "headline": {
            "strongest_signal": next((t for t, _ in ranked if not _is_brand(t)), None),
            "biggest_mover": ({"term": biggest["term"],
                               "momentum": biggest["momentum"]} if biggest else None),
            "n_collected": len(result.items),
            "n_dropped": n_dropped,
            "freshness": f"{result.finished_at:%Y-%m-%d}",
        },
        "core_signals": core_signals,
        "radar": radar,
        "movers": rising_products,
        "opportunities": opportunities,
        "season_calendar": season_calendar,
        "brand_ranking": brand_ranking,
        "brand_signals": brand_signals,
        "unverified_raw": verdict["unverified"],
        "interest_ranking": [
            {"term": t, "interest": round(st.get("latest", 0.0), 1), "core": t in core_set}
            for t, st in ranked if not _is_brand(t)
        ],
        "chart": {**build_chart_block(chart),
                  "note": f"{label} 기준 검색 관심도 추이. {anchor}=100 상대 정규화 — "
                          f"100 초과는 {anchor}보다 검색 관심이 높다는 뜻. "
                          "절대 수요 우열로 단정하지 마세요."},
        "matrix": chart.get("matrix", {}),
        "competitors": chart.get("competitors", []),
        "comparisons": chart.get("comparisons", []),
        "data_trust": data_trust,
        "candidates": discover_candidates(result, top_n=10),
        "news_context": news_context or {},
    }
