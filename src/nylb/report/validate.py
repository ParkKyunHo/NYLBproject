from __future__ import annotations

import uuid
from datetime import datetime, timezone

from nylb.collectors import naver_datalab, naver_news
from nylb.config import get_lens_config, load_lenses
from nylb.core import opportunity
from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data
from nylb.report.html import build_multi_dashboard

# Candidate validator: "should we even prototype <term>?" — one focused
# mini-scan turns an idea into evidence (demand vs our anchor, seasonality,
# age trend, content buzz, gated news) on the standard board. Deterministic;
# the verdict, as always, is the owner's. No history pollution (not saved).


def run_validation(term: str, *, lens: str = "menu",
                   lenses_file: str = "config/lenses.yaml", store_id: str = "nylb",
                   settings: dict, collectors=None) -> str:
    term = term.strip()
    if not term:
        raise ValueError("검증할 후보명이 비어 있습니다")
    base = get_lens_config(load_lenses(lenses_file), store_id, lens)
    anchor = base.get("anchor") or (base.get("keywords") or [term])[0]
    keywords = [term] if term == anchor else [term, anchor]
    lens_config = {
        "keywords": keywords,           # candidate side-by-side with the anchor
        "anchor": anchor,
        "sources": ["youtube", "naver", "naver_datalab"],
        "synonyms": {},
        "discover_stopwords": base.get("discover_stopwords", []),
        "news_context_terms": base.get("news_context_terms", []),
    }
    now = datetime.now(timezone.utc)
    run_id = f"{now:%Y-%m-%d}-validate-{uuid.uuid4().hex[:6]}"
    result = run_scan("validate", store_id=store_id, lens_config=lens_config,
                      settings=settings, store=LocalJsonStore(), run_id=run_id,
                      collected_at=now, collectors=collectors)
    board = build_board(result, extract_chart_data(result))

    # The candidate is a core keyword here, so promote ITS metric (not radar's)
    # to the opportunity slot — same disclosed formula as the main board.
    cm = next((c for c in board["core_signals"] if c["term"] == term), None)
    if cm is not None:
        board["opportunities"] = [
            {**cm, "opportunity": opportunity.score(cm, cm.get("season"))}]
    ages = naver_datalab.collect_age_trends([term], settings=settings)
    if ages:
        board["age_trends"] = ages
    news = naver_news.collect([term], settings=settings, max_per_term=3,
                              context_terms=base.get("news_context_terms") or None)
    if news:
        board["news_context"] = {**(board.get("news_context") or {}), **news}
    board["data_trust"].append({
        "note": f"후보 검증 모드 — {anchor}=100 기준의 단일 후보 집중 스캔. "
                "본 보드 이력(델타)에는 포함되지 않음", "severity": "info"})

    return build_multi_dashboard([{
        "key": "validate", "label": f"후보 검증 · {term}", "icon": "🔬",
        "board": board}])
