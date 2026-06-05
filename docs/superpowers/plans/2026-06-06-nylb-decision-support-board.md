# Decision-Support Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Claude-written `synthesis` dependency in the dashboard with a 100% data-driven, deterministic **decision-support board** — verifying away phantom terms (비키 베이글) and adding per-metric context — that the owner runs locally with one button, no LLM, ₩0.

**Architecture:** Two new pure modules (`core/verify.py` gate, `core/context.py` contextualization) + a board assembler (`report/board.py`) feed a reworked renderer (`report/html.py`, `build_dashboard` drops its `synthesis` arg) and a local one-click web runner (`report/server.py` + `nylb dashboard`). The board model is clean JSON so a future serverless web app (GitHub Actions + Supabase + Next.js) renders the same data. The engine stays industry-agnostic (bagel specifics live only in `config/lenses.yaml` keywords/synonyms).

**Tech Stack:** Python 3.11+, Pydantic v2, stdlib `http.server`, pytest. No new dependencies. No LLM/API.

**Setup note:** Run Python via the venv: `.\.venv\Scripts\python.exe` (Windows). All `pytest` commands below are `.\.venv\Scripts\python.exe -m pytest ...`. Live tests are excluded by default (`addopts = -m 'not live'`).

**Spec:** `docs/superpowers/specs/2026-06-06-nylb-decision-support-board-design.md`

---

## File Structure

| File | Responsibility | New/Modify |
|---|---|---|
| `src/nylb/core/verify.py` | Verification gate: split google rising terms into verified vs phantom (pure) | Create |
| `src/nylb/core/context.py` | Per-metric context + templated caption (pure, no prescriptive wording) | Create |
| `src/nylb/report/board.py` | Assemble the data-driven board model (incl. render-ready chart block) | Create |
| `src/nylb/report/html.py` | `build_dashboard(result, chart)` — drop `synthesis`, render board model | Modify |
| `src/nylb/report/server.py` | Local one-click web runner (`GET /`, `POST /run`) | Create |
| `src/nylb/cli.py` | Add `nylb dashboard`; `report-html` drops `--synthesis` | Modify |
| `.claude/commands/trend-scan.md` | Repoint to data-driven board (no synthesis, no verdicts) | Modify |
| `tests/test_verify.py` `tests/test_context.py` `tests/test_board.py` `tests/test_server.py` | Unit tests | Create |

**Interface contracts (used across tasks — keep names identical):**
- `verify.verify_rising(rising, content_items, datalab_terms, known_terms, *, min_corroboration=2) -> {"verified": [...], "unverified": [...]}`
- `context.contextualize(term: str, stats: dict, rank: int|None=None, total: int|None=None) -> dict` with keys `term, value, peak, direction, momentum, vs_baseline, recent_drop, rank, total, caption`
- `context.caption(cm: dict) -> str` ; `context.direction(momentum: float) -> str` (`"up"|"down"|"steady"`)
- `board.build_chart_block(chart: dict) -> dict` → `{dates, series, ymax, source}`
- `board.build_board(result, chart) -> dict` (board model; no verdict keys)
- `html.build_dashboard(result, chart) -> str` (2 args — `synthesis` removed)

---

### Task 1: Verification gate (`core/verify.py`)

**Files:**
- Create: `src/nylb/core/verify.py`
- Test: `tests/test_verify.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_verify.py
from datetime import datetime, timezone

from nylb.core.schema import Item
from nylb.core.verify import verify_rising


def _content(title: str) -> Item:
    return Item(source="naver", lens="menu", type="blog", title=title,
                collected_at=datetime(2026, 6, 6, tzinfo=timezone.utc))


def test_phantom_term_is_unverified():
    rising = [{"seed": "베이글", "query": "비키 베이글", "value": 10250.0}]
    content = [_content("소금빵 베이글 맛집"), _content("크로플 후기")]  # never mentions 비키
    out = verify_rising(rising, content, datalab_terms=set(), known_terms={"베이글", "소금빵"})
    assert [r["query"] for r in out["verified"]] == []
    assert out["unverified"][0]["query"] == "비키 베이글"
    assert "why" in out["unverified"][0]


def test_known_keyword_is_verified():
    rising = [{"seed": "베이글", "query": "베이글", "value": 5.0}]
    out = verify_rising(rising, [], datalab_terms=set(), known_terms={"베이글"})
    assert out["verified"][0]["query"] == "베이글"
    assert out["unverified"] == []


def test_datalab_signal_makes_verified():
    rising = [{"seed": "디저트", "query": "두바이초콜릿", "value": 9.0}]
    out = verify_rising(rising, [], datalab_terms={"두바이초콜릿"}, known_terms=set())
    assert out["verified"][0]["query"] == "두바이초콜릿"


def test_content_corroboration_threshold():
    rising = [{"seed": "베이글", "query": "약과", "value": 8.0}]
    content = [_content("약과 베이글 변주"), _content("약과 디저트 인기")]  # 2 mentions
    out = verify_rising(rising, content, datalab_terms=set(), known_terms=set(),
                        min_corroboration=2)
    assert out["verified"][0]["query"] == "약과"
    # one mention is below threshold → unverified
    out2 = verify_rising(rising, content[:1], datalab_terms=set(), known_terms=set(),
                         min_corroboration=2)
    assert out2["unverified"][0]["query"] == "약과"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_verify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nylb.core.verify'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/nylb/core/verify.py
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
    mention it. Otherwise UNVERIFIED → quarantine (never promoted to a
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_verify.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nylb/core/verify.py tests/test_verify.py
git commit -m "feat: rising-term verification gate (drops phantom terms)"
```

---

### Task 2: Contextualization layer (`core/context.py`)

**Files:**
- Create: `src/nylb/core/context.py`
- Test: `tests/test_context.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_context.py
from nylb.core.context import caption, contextualize, direction


def test_direction_thresholds():
    assert direction(2.0) == "up"
    assert direction(-2.0) == "down"
    assert direction(0.1) == "steady"


def test_contextualize_computes_vs_baseline_and_rank():
    stats = {"latest": 87.0, "recent_avg": 80.0, "base_avg": 70.0,
             "momentum": 10.0, "peak": 90.0, "daily": {}}
    cm = contextualize("소금빵", stats, rank=1, total=4)
    assert cm["term"] == "소금빵"
    assert cm["value"] == 87.0
    assert cm["direction"] == "up"
    assert cm["vs_baseline"] == 14.0  # 10/70*100 rounded
    assert cm["rank"] == 1 and cm["total"] == 4
    assert "관심도 87/100" in cm["caption"]
    assert "4개 중 1위" in cm["caption"]


def test_recent_drop_flag():
    stats = {"latest": 8.0, "recent_avg": 20.0, "base_avg": 30.0,
             "momentum": -10.0, "peak": 38.0, "daily": {}}
    cm = contextualize("소금빵", stats)
    assert cm["recent_drop"] is True
    assert cm["direction"] == "down"
    assert "단 최근 하락" in cm["caption"]


def test_caption_has_no_prescriptive_wording():
    banned = ["추천", "해야", "줄여", "늘려", "권장", "하세요", "전략", "투자"]
    for mom in (12.0, -12.0, 0.0):
        stats = {"latest": 50.0, "recent_avg": 50.0, "base_avg": 45.0,
                 "momentum": mom, "peak": 60.0, "daily": {}}
        cap = contextualize("베이글", stats, rank=2, total=3)["caption"]
        assert not any(w in cap for w in banned), cap
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nylb.core.context'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/nylb/core/context.py
from __future__ import annotations

_EPS = 1e-9


def direction(momentum: float) -> str:
    if momentum > 0.5:
        return "up"
    if momentum < -0.5:
        return "down"
    return "steady"


def contextualize(term: str, stats: dict,
                  rank: int | None = None, total: int | None = None) -> dict:
    """Attach decision-support context to ONE trend metric. Pure, rule-based.
    `stats` is a chart_data._trend_stats dict (latest/recent_avg/base_avg/
    momentum/peak/daily). Describes what the numbers SAY — never prescribes."""
    latest = float(stats.get("latest", 0.0))
    base = float(stats.get("base_avg", 0.0))
    mom = float(stats.get("momentum", 0.0))
    vs_baseline = round((mom / base) * 100, 0) if abs(base) > _EPS else None
    recent_drop = latest < float(stats.get("recent_avg", 0.0))
    cm = {
        "term": term,
        "value": round(latest, 1),
        "peak": stats.get("peak", 0.0),
        "direction": direction(mom),
        "momentum": mom,
        "vs_baseline": vs_baseline,
        "recent_drop": recent_drop,
        "rank": rank,
        "total": total,
    }
    cm["caption"] = caption(cm)
    return cm


def caption(cm: dict) -> str:
    """One-line OBSERVATION (rule-based). Never contains prescriptive wording."""
    parts = [f"관심도 {cm['value']:.0f}/100"]
    if cm.get("rank") and cm.get("total"):
        parts.append(f"{cm['total']}개 중 {cm['rank']}위")
    if cm.get("vs_baseline") is not None:
        sign = "+" if cm["vs_baseline"] >= 0 else ""
        parts.append(f"30일 평균 {sign}{cm['vs_baseline']:.0f}%")
    if cm.get("recent_drop") and cm.get("direction") != "up":
        parts.append("단 최근 하락")
    return " · ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_context.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nylb/core/context.py tests/test_context.py
git commit -m "feat: per-metric contextualization + observation caption (no verdicts)"
```

---

### Task 3: Board assembler (`report/board.py`)

**Files:**
- Create: `src/nylb/report/board.py`
- Test: `tests/test_board.py`

This module also owns the render-ready chart block (`build_chart_block`), moved out of `html.py` so `board.py` is self-contained and `html.py` becomes render-only.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_board.py
from datetime import datetime, timezone

from nylb.core.schema import Item, ScanResult
from nylb.report.board import build_board

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _series(values: list[float]) -> list[dict]:
    return [{"date": f"2026-05-{i+1:02d}", "value": v} for i, v in enumerate(values)]


def _trend_item(source: str, term: str, values: list[float]) -> Item:
    return Item(source=source, lens="menu", type="search_term", title=term,
                collected_at=NOW, raw={"series": _series(values)})


def _rising(query: str, value: float) -> Item:
    return Item(source="google_trends", lens="menu", type="rising_query",
                title=query, collected_at=NOW,
                metrics={"value": value}, raw={"seed": "베이글"})


def _result(items: list[Item]) -> ScanResult:
    return ScanResult(run_id="2026-06-06-menu-test", store_id="nylb", lens="menu",
                      query={"keywords": ["베이글", "소금빵"], "synonyms": {}},
                      items=items, dropped_by_source={"naver": 2},
                      started_at=NOW, finished_at=NOW)


def test_board_has_core_signals_with_captions_and_no_verdict_keys():
    from nylb.report.chart_data import extract_chart_data
    items = [
        _trend_item("naver_datalab", "베이글", [80, 82, 85, 87]),
        _trend_item("naver_datalab", "소금빵", [60, 50, 40, 30]),
        _trend_item("naver_datalab", "두바이초콜릿", [20, 22, 23, 23]),  # non-core radar
        _rising("비키 베이글", 10250),  # phantom: no datalab, no content
    ]
    board = build_board(_result(items), extract_chart_data(_result(items)))

    assert {c["term"] for c in board["core_signals"]} == {"베이글", "소금빵"}
    assert all(c["caption"] for c in board["core_signals"])
    # phantom isolated in unverified, NOT in radar
    assert "비키 베이글" in {u["query"] for u in board["unverified_raw"]}
    assert "비키 베이글" not in {r["term"] for r in board["radar"]}
    # verdict keys must be absent (judgment stays with the owner)
    for forbidden in ("action_plan", "risks", "menu_opportunities",
                      "top_insights", "trend_verdicts", "syn", "synthesis"):
        assert forbidden not in board
    # data trust reflects dropped_by_source
    assert any("naver" in d["note"] for d in board["data_trust"])
    # render-ready chart block
    assert board["chart"]["dates"] and board["chart"]["series"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_board.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nylb.report.board'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/nylb/report/board.py
from __future__ import annotations

from nylb.core.context import contextualize
from nylb.core.schema import ScanResult
from nylb.core.verify import verify_rising

_COLORS = {"소금빵": "var(--salt)", "베이글": "var(--bagel)", "크로플": "var(--croffle)"}
_PALETTE = ["#7c5cff", "#2f9e5b", "#d24b4b", "#e2a32f", "#1f9d57"]


def _trend_source(chart: dict) -> str:
    return "naver_datalab" if chart["trends"].get("naver_datalab") else "google_trends"


def build_chart_block(chart: dict) -> dict:
    """Render-ready line-chart block (dates/series/ymax) for the core keywords.
    Moved verbatim from the old html._build_chart so html.py stays render-only."""
    source = _trend_source(chart)
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


def build_board(result: ScanResult, chart: dict) -> dict:
    """Assemble the deterministic decision-support board. No verdicts."""
    core = list(chart.get("keywords", []))
    core_set = set(core)
    source = _trend_source(chart)
    tstats = chart["trends"].get(source, {})

    ranked = sorted(tstats.items(),
                    key=lambda kv: kv[1].get("latest", 0.0), reverse=True)
    rank_of = {term: i + 1 for i, (term, _) in enumerate(ranked)}
    total = len(ranked)

    core_signals = [contextualize(t, tstats[t], rank_of.get(t), total)
                    for t in core if t in tstats]
    radar = [contextualize(t, st, rank_of.get(t), total)
             for t, st in ranked if t not in core_set]

    # verification gate over google rising terms
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
    data_trust.append({"note": "검색 관심도는 0~100 상대 정규화 지표 — "
                               "절대 수요 우열로 단정 금지", "severity": "info"})

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
            "sources_status": sources_status,
        },
        "headline": {
            "strongest_signal": ranked[0][0] if ranked else None,
            "biggest_mover": ({"term": biggest["term"],
                               "momentum": biggest["momentum"]} if biggest else None),
            "n_collected": len(result.items),
            "n_dropped": n_dropped,
            "freshness": f"{result.finished_at:%Y-%m-%d}",
        },
        "core_signals": core_signals,
        "radar": radar,
        "unverified_raw": verdict["unverified"],
        "interest_ranking": [
            {"term": t, "interest": round(st.get("latest", 0.0), 1),
             "core": t in core_set} for t, st in ranked
        ],
        "chart": {**build_chart_block(chart),
                  "note": f"{label} 기준 검색 관심도 추이. 상대 정규화(0~100) — "
                          "절대 수요 우열로 단정하지 마세요."},
        "matrix": chart.get("matrix", {}),
        "competitors": chart.get("competitors", []),
        "comparisons": chart.get("comparisons", []),
        "data_trust": data_trust,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_board.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nylb/report/board.py tests/test_board.py
git commit -m "feat: data-driven decision-support board assembler (no verdicts)"
```

---

### Task 4: Render the board (`report/html.py` rework)

**Files:**
- Modify: `src/nylb/report/html.py` (replace the `<script>` body; replace `_build_chart`/`build_dashboard`)
- Test: `tests/test_board.py` (append a render test)

Keep the existing `<style>...</style>` block **unchanged** (dead classes from removed sections are harmless). Replace three things: the JS `<script>` body, delete `_build_chart` (moved to `board.py`), and rewrite `build_dashboard`.

- [ ] **Step 1: Write the failing test (append to tests/test_board.py)**

```python
def test_build_dashboard_is_data_driven_two_args():
    from nylb.report.chart_data import extract_chart_data
    from nylb.report.html import build_dashboard
    items = [_trend_item("naver_datalab", "베이글", [80, 82, 85, 87]),
             _rising("비키 베이글", 10250)]
    result = _result(items)
    html = build_dashboard(result, extract_chart_data(result))  # 2 args, no synthesis
    assert "<!DOCTYPE html>" in html
    assert '"core_signals"' in html          # board embedded
    assert '"unverified_raw"' in html
    assert '"syn"' not in html               # Claude synthesis gone
    assert "비키 베이글" in html             # present, but only in unverified card
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_board.py::test_build_dashboard_is_data_driven_two_args -v`
Expected: FAIL — current `build_dashboard` requires 3 args (`synthesis`) → `TypeError`.

- [ ] **Step 3: Rewrite `html.py`**

3a. At the top of `html.py`, replace the import line and the `_COLORS`/`_PALETTE` constants — they now live in `board.py`:

```python
# src/nylb/report/html.py  (top of file)
from __future__ import annotations

import json

from nylb.core.schema import ScanResult
from nylb.report.board import build_board  # noqa: F401
from nylb.report.chart_data import extract_chart_data  # noqa: F401  (re-export convenience)
```

(Delete the old `_COLORS` / `_PALETTE` module constants and the entire `_build_chart` function — both are now in `board.py`.)

3b. Replace the entire `<script> ... </script>` block inside `_TEMPLATE` with this board renderer:

```html
<script>
const DATA = __DATA__;
function h(tag, attrs, kids){
  const e=document.createElement(tag);
  if(attrs) for(const k in attrs){ if(k==="class")e.className=attrs[k]; else if(k==="html")e.innerHTML=attrs[k]; else e.setAttribute(k,attrs[k]); }
  if(kids!=null){ (Array.isArray(kids)?kids:[kids]).forEach(c=>{ if(c==null)return; e.appendChild(typeof c==="string"?document.createTextNode(c):c); }); }
  return e;
}
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function sect(icon,title,sub){const s=h("section");s.appendChild(h("h2",null,[h("span",{class:"ic"},icon),title]));if(sub)s.appendChild(h("p",{class:"sub"},sub));return s;}
const app=document.getElementById("app");
const M=DATA.meta, HL=DATA.headline;
const ARROW={up:"▲",down:"▼",steady:"→"}, DCOL={up:"var(--up)",down:"var(--down)",steady:"var(--steady)"};
document.title = "NYLB 의사결정 상황판 · "+M.collected+" ("+M.lens+")";

/* HERO */
const hero=h("div",{class:"hero"});
hero.appendChild(h("div",{class:"brand"},M.brand));
hero.appendChild(h("h1",null,"📋 의사결정 상황판"));
const meta=h("div",{class:"meta"});
const chanStr=Object.entries(M.counts).map(([s,n])=>s+" "+n).join("·");
["수집일 "+M.collected,"렌즈 "+M.lens,"스캔 "+M.run_id,"수집 "+M.items+"건 ("+chanStr+")"].forEach(t=>meta.appendChild(h("span",null,t)));
hero.appendChild(meta); app.appendChild(hero);

/* SUMMARY — data-derived pointers, explicitly NOT a verdict */
const mv=HL.biggest_mover;
app.appendChild(h("div",{class:"summary",html:
  "<b>한눈에.</b> 검색 관심도 최상위 = <b>"+esc(HL.strongest_signal||"-")+"</b> · 모멘텀 최대 변화 = "+
  (mv?("<b>"+esc(mv.term)+"</b> ("+(mv.momentum>=0?"+":"")+mv.momentum+")"):"-")+
  " · 수집 "+HL.n_collected+"건/제외 "+HL.n_dropped+"건. <i>아래는 신호일 뿐 — 판단은 사장님 몫입니다.</i>"}));

/* KPIs */
const k=sect("📈","한눈에 보기","수집 현황과 최대 변화 (평결 아님, 데이터 산출)");
const kp=h("div",{class:"grid kpis"});
function kpi(lab,val,sub2,col){const c=h("div",{class:"kpi"});c.appendChild(h("div",{class:"lab"},lab));
  const vv=h("div",{class:"val"},val); if(col)vv.style.color=col; c.appendChild(vv);
  if(sub2)c.appendChild(h("div",{class:"sub2"},sub2)); return c;}
kp.appendChild(kpi("총 수집", M.items+"건", Object.keys(M.counts).length+"개 채널 · 실패 "+M.errors));
kp.appendChild(kpi("관련성 제외", HL.n_dropped+"건", "노이즈 게이트로 제외"));
kp.appendChild(kpi("최상위 관심", esc(HL.strongest_signal||"-"), "검색 관심도 1위"));
kp.appendChild(kpi("최대 변화", mv?esc(mv.term):"-", mv?((mv.momentum>=0?"▲ +":"▼ ")+mv.momentum+" 모멘텀"):"", mv?DCOL[mv.momentum>=0?"up":"down"]:null));
k.appendChild(kp); app.appendChild(k);

/* INTEREST RANKING */
(function(){const rk=DATA.interest_ranking||[]; if(!rk.length)return;
  const sec=sect("🍞","검색 관심도 랭킹","사람들이 지금 어떤 베이커리·디저트를 검색하나 (0~100)");
  const card=h("div",{class:"card"});
  const maxv=Math.max.apply(null, rk.map(x=>x.interest).concat([1]));
  rk.forEach(x=>{const row=h("div",{style:"display:grid;grid-template-columns:130px 1fr 40px;align-items:center;gap:10px;margin:7px 0"});
    row.appendChild(h("div",{style:"font-weight:700;font-size:13px"+(x.core?";color:var(--accent)":"")}, x.term+(x.core?" ★":"")));
    const bar=h("div",{class:"bar",style:"height:15px;background:#f0e7da"});
    bar.appendChild(h("i",{style:"width:"+(x.interest/maxv*100)+"%;background:"+(x.core?"var(--bagel)":"var(--salt)")}));
    row.appendChild(bar);
    row.appendChild(h("div",{style:"font-weight:800;font-size:13px;text-align:right"},String(Math.round(x.interest))));
    card.appendChild(row);});
  card.appendChild(h("div",{class:"note"},"★ = 우리 코어(파란 막대). 주황 = 레이더 인접 트렌드. 막대가 길수록 지금 검색 관심이 높음."));
  sec.appendChild(card); app.appendChild(sec);})();

/* CHART */
(function(){if(!DATA.chart.dates.length)return;
  const cs=sect("📉","검색 관심도 추이",M.trend_label+" 일별 지수 (0~100, 상대 정규화)");
  const cc=h("div",{class:"card chartcard"}); cc.appendChild(buildChart());
  const lg=h("div",{class:"legend"});
  for(const name in DATA.chart.series){const sr=DATA.chart.series[name];
    lg.appendChild(h("span",null,[h("i",{style:"background:"+sr.color}),name+" (피크 "+sr.peak+")"]));}
  cc.appendChild(lg); cc.appendChild(h("div",{class:"note"}, DATA.chart.note));
  cs.appendChild(cc); app.appendChild(cs);})();

function buildChart(){
  const W=760,H=340,L=48,R=24,T=24,B=44, pw=W-L-R, ph=H-T-B, ymax=DATA.chart.ymax;
  const dates=DATA.chart.dates, n=dates.length;
  const X=i=>L+pw*(i/(n-1)), Y=v=>T+ph*(1-v/ymax);
  const NS="http://www.w3.org/2000/svg";
  const svg=document.createElementNS(NS,"svg");
  svg.setAttribute("viewBox","0 0 "+W+" "+H); svg.setAttribute("width","100%");
  function sv(tag,a){const e=document.createElementNS(NS,tag);for(const k in a)e.setAttribute(k,a[k]);return e;}
  [0,1,2,3].map(i=>Math.round(ymax*i/3)).forEach(g=>{
    svg.appendChild(sv("line",{x1:L,y1:Y(g),x2:W-R,y2:Y(g),stroke:"#ece3d8","stroke-width":1}));
    const t=sv("text",{x:L-8,y:Y(g)+4,"text-anchor":"end","font-size":11,fill:"#9b8f80"});t.textContent=g;svg.appendChild(t);});
  const step=Math.max(1,Math.ceil(n/8));
  dates.forEach((d,i)=>{ if(i%step!==0 && i!==n-1) return;
    const lab=(d.length>5)?d.slice(5).replace("-","/"):d;
    const t=sv("text",{x:X(i),y:H-16,"text-anchor":"middle","font-size":11,fill:"#9b8f80"});t.textContent=lab;svg.appendChild(t);});
  for(const name in DATA.chart.series){const sr=DATA.chart.series[name];
    const pts=sr.v.map((v,i)=>X(i)+","+Y(v)).join(" ");
    svg.appendChild(sv("polyline",{points:pts,fill:"none",stroke:sr.color,"stroke-width":3,"stroke-linejoin":"round","stroke-linecap":"round"}));
    sr.v.forEach((v,i)=>svg.appendChild(sv("circle",{cx:X(i),cy:Y(v),r:3.2,fill:sr.color})));}
  return svg;
}

/* CORE SIGNALS */
(function(){const cs=DATA.core_signals||[]; if(!cs.length)return;
  const sec=sect("🥯","핵심 메뉴 신호","코어 키워드 — 맥락 붙인 수치 (관찰만, 처방 없음)");
  const g=h("div",{class:"grid verdicts"});
  cs.forEach(c=>{const card=h("div",{class:"vc"});card.style.borderTopColor=DCOL[c.direction];
    card.appendChild(h("h3",null,[document.createTextNode(c.term),
      h("span",{class:"mom "+c.direction},ARROW[c.direction]+" "+(c.momentum>=0?"+":"")+c.momentum)]));
    card.appendChild(h("div",{class:"stage"},"검증됨 ✓ · 피크 "+c.peak));
    card.appendChild(h("p",null,c.caption)); g.appendChild(card);});
  sec.appendChild(g); app.appendChild(sec);})();

/* RADAR (verified only) */
(function(){const rd=DATA.radar||[]; if(!rd.length)return;
  const sec=sect("🛰️","트렌드 레이더 — 인접 관심사","검증된 인접 트렌드만 (접목 판단은 사장님 몫)");
  const g=h("div",{class:"grid verdicts"});
  rd.forEach(c=>{const card=h("div",{class:"vc"});card.style.borderTopColor=DCOL[c.direction];
    card.appendChild(h("h3",null,[document.createTextNode(c.term),
      h("span",{class:"mom "+c.direction},ARROW[c.direction]+" "+(c.momentum>=0?"+":"")+c.momentum)]));
    card.appendChild(h("div",{class:"stage"},"검증됨 ✓"));
    card.appendChild(h("p",null,c.caption)); g.appendChild(card);});
  sec.appendChild(g); app.appendChild(sec);})();

/* UNVERIFIED RAW — quarantine (비키 베이글 lands here) */
(function(){const uv=DATA.unverified_raw||[]; if(!uv.length)return;
  const sec=sect("🚧","미검증 원시신호","구글 자동발견 급상승어 — 실존 미확인. 절대 경쟁사/레이더로 취급 금지, 참고만.");
  const card=h("div",{class:"card"});
  card.appendChild(h("div",{style:"font-size:11.5px;color:#b08968;margin-bottom:8px"},"※ 콘텐츠·데이터랩 뒷받침이 없어 격리된 용어입니다(없는 브랜드/오타 가능). 검증 전엔 판단 근거로 쓰지 마세요."));
  const ul=h("ul",{class:"gaps"});
  uv.slice(0,15).forEach(x=>ul.appendChild(h("li",null, x.query+"  ·  "+(x.seed||"")+" 연관  ·  뒷받침 "+(x.corroboration||0)+"건")));
  card.appendChild(ul); sec.appendChild(card); app.appendChild(sec);})();

/* PRICE POSITIONING */
(function(){const cmp=DATA.comparisons||[]; if(!cmp.length)return;
  const sec=sect("📊","가격 포지셔닝","NYLB 매장가 vs 경쟁사 — 차이(%) (위=비쌈·빨강, 아래=쌈·초록)");
  const card=h("div",{class:"card"});const tb=h("table");
  tb.appendChild(h("tr",null,["카테고리","NYLB","경쟁사","경쟁가","차이"].map(t=>h("th",null,t))));
  cmp.forEach(c=>{const color=c.position==="above"?"var(--down)":c.position==="below"?"var(--up)":"var(--muted)";
    const arrow=c.position==="above"?"▲":c.position==="below"?"▼":"→";
    tb.appendChild(h("tr",null,[
      h("td",null,h("b",null,c.category||"-")),
      h("td",null,(c.nylb_price!=null?Math.round(c.nylb_price).toLocaleString()+"원":"-")),
      h("td",null,[h("b",null,c.competitor_brand||"-"),document.createTextNode(" "+(c.competitor_product||""))]),
      h("td",null,(c.competitor_price!=null?Math.round(c.competitor_price).toLocaleString()+"원":"-")),
      h("td",null,h("b",{style:"color:"+color},arrow+" "+(c.diff_pct>0?"+":"")+c.diff_pct+"%"))]));});
  card.appendChild(tb);
  card.appendChild(h("div",{class:"note"},"※ 컬리 리테일가는 매장 단품가와 기준이 달라 직접 비교 주의(기준 라벨 참고). 시점·프로모션에 따라 변동."));
  sec.appendChild(card); app.appendChild(sec);})();

/* COMPETITORS */
(function(){const comp=DATA.competitors||[]; if(!comp.length)return;
  const sec=sect("🏷️","경쟁사 가격 (마켓컬리)","공개 상품페이지 크롤링 — 리테일 SKU 기준(매장가와 다를 수 있음)");
  const card=h("div",{class:"card"});const tb=h("table");
  tb.appendChild(h("tr",null,["브랜드","상품","판매가","정가"].map(t=>h("th",null,t))));
  comp.forEach(c=>tb.appendChild(h("tr",null,[
    h("td",null,h("b",null,c.brand||"-")), h("td",null,c.product||"-"),
    h("td",null,h("b",null,c.price!=null?Math.round(c.price).toLocaleString()+"원":"-")),
    h("td",{style:"color:#9b8f80;text-decoration:line-through"},c.base_price!=null?Math.round(c.base_price).toLocaleString()+"원":"")])));
  card.appendChild(tb); sec.appendChild(card); app.appendChild(sec);})();

/* DATA TRUST */
(function(){const dt=DATA.data_trust||[]; if(!dt.length)return;
  const sec=sect("🧪","데이터 신뢰도 & 한계","각 수치를 얼마나 믿을지 — 판단 보정용");
  const card=h("div",{class:"card"});const ul=h("ul",{class:"gaps"});
  dt.forEach(d=>ul.appendChild(h("li",null,d.note))); card.appendChild(ul);
  sec.appendChild(card); app.appendChild(sec);})();

/* FOOTER */
const ft=h("div",{class:"foot"}); ft.appendChild(h("div",null,"데이터 출처 상태"));
const src=h("div",{class:"src"});
(M.sources_status||[]).forEach(s=>src.appendChild(h("span",{class:"pill "+(s.on?"on":"off")},(s.on?"✓ ":"⏸ ")+s.name)));
ft.appendChild(src);
ft.appendChild(h("div",{style:"margin-top:12px"},"NYLB 의사결정 상황판 · 결정론 데이터 자동생성(LLM 없음) · 원본 data/raw/"+M.run_id+".json"));
app.appendChild(ft);
</script>
```

3c. Replace `build_dashboard` at the bottom of `html.py`:

```python
def build_dashboard(result: ScanResult, chart: dict) -> str:
    """Render the deterministic decision-support board to self-contained HTML.
    No `synthesis` — the board is 100% data-driven (build_board)."""
    board = build_board(result, chart)
    return _TEMPLATE.replace("__DATA__", json.dumps(board, ensure_ascii=False))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_board.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nylb/report/html.py tests/test_board.py
git commit -m "feat: render data-driven board; drop synthesis from build_dashboard"
```

---

### Task 5: Local one-click runner (`report/server.py`)

**Files:**
- Create: `src/nylb/report/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server.py
import threading
import urllib.request

from nylb.report.server import make_server


def _serve(server):
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return t


def test_get_serves_board_with_run_button():
    calls = {"n": 0}
    server = make_server(port=0, render_fn=lambda: "<html><body>BOARD</body></html>",
                         on_count=calls)
    _serve(server)
    host, port = server.server_address
    body = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode("utf-8")
    server.shutdown()
    assert "스캔 실행" in body          # button injected
    assert "fetch('/run'" in body


def test_post_run_invokes_render_fn():
    state = {"n": 0}
    def render():
        state["n"] += 1
        return f"<html><body>RUN {state['n']}</body></html>"
    server = make_server(port=0, render_fn=render)
    _serve(server)
    host, port = server.server_address
    req = urllib.request.Request(f"http://127.0.0.1:{port}/run", method="POST")
    body = urllib.request.urlopen(req).read().decode("utf-8")
    server.shutdown()
    assert "RUN 1" in body
    assert state["n"] == 1
```

(`on_count` is an optional unused hook in the first test only to keep signatures simple; the impl below ignores extra kwargs via `**_`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nylb.report.server'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/nylb/report/server.py
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nylb.config import get_lens_config, load_lenses, load_settings
from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore
from nylb.report.chart_data import extract_chart_data
from nylb.report.html import build_dashboard

_BUTTON = (
    "<div style=\"position:fixed;right:20px;bottom:20px;z-index:9999\">"
    "<button id=\"nylb-run\" style=\"background:#c8742f;color:#fff;border:0;"
    "border-radius:999px;padding:13px 22px;font-size:15px;font-weight:800;"
    "box-shadow:0 6px 20px rgba(45,38,32,.3);cursor:pointer\">🔄 스캔 실행</button></div>"
    "<script>document.getElementById('nylb-run').onclick=function(){"
    "this.textContent='⏳ 수집 중...';this.disabled=true;"
    "fetch('/run',{method:'POST'}).then(function(){location.reload();});};</script>"
)
_PLACEHOLDER = ("<!DOCTYPE html><html lang=ko><body style=\"font-family:sans-serif;"
                "padding:40px\"><h2>NYLB 의사결정 상황판</h2>"
                "<p>아직 스캔이 없습니다. 오른쪽 아래 <b>스캔 실행</b> 버튼을 누르세요.</p>"
                "</body></html>")


def _with_button(html: str) -> str:
    if "</body>" in html:
        return html.replace("</body>", _BUTTON + "</body>", 1)
    return html + _BUTTON


def run_scan_and_render(lens: str = "menu", *, lenses_file: str = "config/lenses.yaml",
                        store_id: str = "nylb", collectors=None) -> str:
    """Run a local scan and return the rendered board HTML (no synthesis, no LLM)."""
    from nylb.cli import build_run_id
    now = datetime.now(timezone.utc)
    settings = load_settings()
    lenses = load_lenses(lenses_file)
    lens_config = get_lens_config(lenses, store_id, lens)
    run_id = build_run_id(lens, now)
    result = run_scan(lens, store_id=store_id, lens_config=lens_config,
                      settings=settings, store=LocalJsonStore(), run_id=run_id,
                      collected_at=now, collectors=collectors)
    return build_dashboard(result, extract_chart_data(result))


def make_server(host: str = "127.0.0.1", port: int = 8765, *,
                lens: str = "menu", render_fn=None, **_) -> ThreadingHTTPServer:
    render = render_fn or (lambda: run_scan_and_render(lens))
    state = {"html": _PLACEHOLDER}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/board"):
                self._send(200, _with_button(state["html"]))
            else:
                self._send(404, "not found")

        def do_POST(self):
            if self.path == "/run":
                state["html"] = render()
                self._send(200, _with_button(state["html"]))
            else:
                self._send(404, "not found")

        def log_message(self, *a):  # silence default stderr logging
            pass

    return ThreadingHTTPServer((host, port), Handler)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_server.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/nylb/report/server.py tests/test_server.py
git commit -m "feat: local one-click dashboard server (button -> scan -> board)"
```

---

### Task 6: CLI wiring (`cli.py`)

**Files:**
- Modify: `src/nylb/cli.py`
- Test: `tests/test_cli_board.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_board.py
from datetime import datetime, timezone

from nylb.cli import main
from nylb.core.schema import Item, ScanResult
from nylb.core.store import LocalJsonStore

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def test_report_html_needs_no_synthesis(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    item = Item(source="naver_datalab", lens="menu", type="search_term", title="베이글",
                collected_at=NOW,
                raw={"series": [{"date": "2026-05-01", "value": 80.0},
                                 {"date": "2026-05-02", "value": 85.0}]})
    result = ScanResult(run_id="2026-06-06-menu-cli", store_id="nylb", lens="menu",
                        query={"keywords": ["베이글"]}, items=[item],
                        started_at=NOW, finished_at=NOW)
    LocalJsonStore().save(result)  # writes data/raw/<run>.json under tmp_path
    rc = main(["report-html", "--run", "2026-06-06-menu-cli"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "html=" in out


def test_dashboard_subcommand_is_registered():
    import argparse
    import pytest
    # `dashboard` must parse without error (we don't start the server here)
    from nylb.cli import _build_parser
    parser = _build_parser()
    ns = parser.parse_args(["dashboard", "--lens", "menu", "--port", "9999"])
    assert ns.cmd == "dashboard" and ns.port == 9999
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_cli_board.py -v`
Expected: FAIL — `_build_parser` doesn't exist and `report-html` still loads synthesis.

- [ ] **Step 3: Edit `cli.py`**

3a. Factor parser construction into `_build_parser()` and add the `dashboard` subcommand. Replace the top of `main` (the parser block) so `main` calls `_build_parser()`:

```python
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nylb")
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan_p = sub.add_parser("scan", help="collect trend data for a lens")
    scan_p.add_argument("--lens", required=True)
    scan_p.add_argument("--store", default="nylb")
    scan_p.add_argument("--lenses-file", default="config/lenses.yaml")
    scan_p.add_argument("--store-backend", choices=["local", "supabase"], default="local")
    rh_p = sub.add_parser("report-html", help="render the data-driven board HTML")
    rh_p.add_argument("--run", required=True)
    rh_p.add_argument("--store", default="nylb")
    dash_p = sub.add_parser("dashboard", help="local one-click board server")
    dash_p.add_argument("--lens", default="menu")
    dash_p.add_argument("--lenses-file", default="config/lenses.yaml")
    dash_p.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.cmd == "report-html":
        return _report_html(args)
    if args.cmd == "dashboard":
        return _dashboard(args)
    if args.cmd != "scan":
        return 1
    # ... (rest of the scan branch unchanged) ...
```

3b. Replace `_report_html` (drop synthesis) and add `_dashboard`. Also remove the now-unused `import json` and `from pathlib import Path` if nothing else uses them (the scan branch does not):

```python
def _report_html(args) -> int:
    result = LocalJsonStore().load(args.run)
    chart = extract_chart_data(result)
    html = build_dashboard(result, chart)
    path = write_text_report(html, args.run, out_dir="reports", suffix=".analysis.html")
    print(f"html={path}")
    return 0


def _dashboard(args) -> int:
    from nylb.report.server import make_server
    server = make_server(port=args.port, lens=args.lens)
    host, port = server.server_address
    print(f"dashboard http://127.0.0.1:{port}  ('스캔 실행' 버튼으로 수집)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0
```

(`build_dashboard` import at top stays; it is now called with 2 args. The `import json` / `from pathlib import Path` lines at the top of `cli.py` are no longer used by `_report_html` — delete them if no other code references them.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_cli_board.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (all prior tests + the new ones; the old `report-html --synthesis` path is gone, so confirm no test referenced it — if one does, update it to the 2-arg call).

- [ ] **Step 6: Commit**

```bash
git add src/nylb/cli.py tests/test_cli_board.py
git commit -m "feat: nylb dashboard subcommand; report-html drops synthesis"
```

---

### Task 7: `/trend-scan` command + final live verification

**Files:**
- Modify: `.claude/commands/trend-scan.md`
- (No test file — this is a docs/command change + a manual live check.)

- [ ] **Step 1: Rewrite `.claude/commands/trend-scan.md`**

Replace the whole file with the data-driven flow (no synthesis, no verdict report):

```markdown
---
description: NYLB 시장 트렌드 스캔 — 수집 후 결정론 의사결정 상황판 자동 생성 (LLM 평결 없음)
---

사용자가 `/trend-scan <키워드/렌즈 힌트>`로 호출했습니다. 인자: $ARGUMENTS

**원칙: 시장의 판단은 사용자(사장님) 고유 영역.** 이 명령은 수치를 *검증·맥락화*해 상황판으로 정리할 뿐, 평결·추천을 작성하지 않습니다.

수행 절차:
1. 인자에서 렌즈를 정한다(기본 `menu`). 필요하면 `config/lenses.yaml` 키워드를 잠시 조정해도 된다.
2. 수집 실행: `python -m nylb scan --lens <lens> --store nylb` → 출력의 `run_id` 확인(부분 실패 허용).
3. 상황판 생성: `python -m nylb report-html --run <run_id>` → `reports/<run_id>.analysis.html` 자동 생성.
   - 보드는 **100% 데이터-주도**(검증 게이트 + 컨텍스트화)로 만들어진다. synthesis JSON을 작성하지 않는다.
   - 미검증 급상승어(예: 없는 브랜드)는 자동으로 "미검증 원시신호" 칸에 격리된다.
4. 생성된 HTML 경로를 사용자에게 알린다. 해석·결정은 사용자가 보드를 보고 직접 내린다.

로컬 상시 사용은 `python -m nylb dashboard`(버튼 클릭) 경로를 안내한다.
```

- [ ] **Step 2: Commit the command change**

```bash
git add .claude/commands/trend-scan.md
git commit -m "docs: repoint /trend-scan to data-driven board (no synthesis/verdicts)"
```

- [ ] **Step 3: Live verification (manual, requires .env keys)**

Run a real scan + render and inspect:

```bash
.\.venv\Scripts\python.exe -m nylb scan --lens menu --store nylb
.\.venv\Scripts\python.exe -m nylb report-html --run <run_id_from_above>
```

Then open `reports/<run_id>.analysis.html` with Playwright MCP and confirm:
- 0 JS console errors (favicon-404 is acceptable).
- Core signals show direction arrow + caption (e.g. "관심도 NN/100 · …").
- Any phantom rising term appears ONLY under "🚧 미검증 원시신호" — never in 레이더/경쟁사.
- No verdict/action sections (no 실행 계획/리스크/추천).

- [ ] **Step 4: Local button smoke test**

```bash
.\.venv\Scripts\python.exe -m nylb dashboard --lens menu --port 8765
```
Open `http://127.0.0.1:8765/`, confirm the "🔄 스캔 실행" button renders; click it; confirm the board populates after the scan. Ctrl-C to stop.

- [ ] **Step 5: Final full-suite run + commit any fixes**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS. Commit any verification-driven fixes:

```bash
git add -A
git commit -m "test: live-verify decision-support board renders + button works"
```

---

## Self-Review

**1. Spec coverage:**
- D1 검증 게이트 → Task 1 (`verify.py`, phantom 비키 베이글 quarantined, never promoted). ✓
- D2 컨텍스트화 → Task 2 (`context.py`, direction/vs_baseline/rank/caption, no prescriptive wording test). ✓
- D3 보드 + synthesis 제거 → Task 3 (`board.py`, no verdict keys) + Task 4 (`html.py`, `build_dashboard(result, chart)` 2-arg, no `syn`). ✓
- D4 로컬 버튼 → Task 5 (`server.py`) + Task 6 (`nylb dashboard`). ✓
- trend-scan.md synthesis 의존 제거 → Task 7. ✓
- 데이터 신뢰도/한계 섹션(dropped_by_source) → board.data_trust (Task 3) + render (Task 4). ✓
- 미래 웹 seam (board.json) → board model is plain JSON (Task 3); not built now (Phase 2, out of scope). ✓

**2. Placeholder scan:** No TBD/TODO. Every code step contains complete code. Test steps contain real assertions. ✓

**3. Type consistency:** `verify_rising` returns `{"verified","unverified"}` (Task 1) → consumed as `verdict["unverified"]` (Task 3). `contextualize` keys `term/value/peak/direction/momentum/vs_baseline/recent_drop/rank/total/caption` (Task 2) → rendered as `c.term/c.direction/c.momentum/c.peak/c.caption` (Task 4). `build_chart_block` → `{dates,series,ymax,source}` (Task 3) → board.chart + `+note` → `DATA.chart.dates/series/ymax/note` (Task 4). `build_dashboard(result, chart)` 2-arg defined Task 4, called Task 5 (`run_scan_and_render`) and Task 6 (`_report_html`). `make_server(port, render_fn)` defined Task 5, used Task 6. Consistent. ✓

**4. Deviations from spec (intentional, DRY):**
- `contextualize` consumes the existing `chart_data._trend_stats` dict (latest/recent_avg/base_avg/momentum) instead of recomputing from `daily`+`now`+`baseline_days` — reuses computation already in the codebase (DRY). `build_board(result, chart)` drops the unused `now` param for the same reason (no unused-arg smell). Behavior identical to spec intent.

## Execution Handoff

Two execution options once approved:
1. **Subagent-Driven (recommended)** — fresh subagent per task + two-stage review between tasks (matches how sub-projects A and the price-positioning slice were built).
2. **Inline Execution** — batch in this session with checkpoints.
