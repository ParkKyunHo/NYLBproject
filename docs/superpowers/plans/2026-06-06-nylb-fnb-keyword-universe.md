# F&B Keyword Universe v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the decision-support board's monitoring universe (categorized keywords incl. brands), rank it accurately (anchored DataLab), auto-discover new terms, and annotate risers with news — all deterministic (no LLM), and **industry-agnostic** so any F&B vertical works by config swap.

**Architecture:** Config gains a categorized `radar` map + an `anchor` keyword (opaque labels; engine has zero bakery literals). `run_scan` flattens the map. `naver_datalab` injects the anchor into every 5-batch and rescales to anchor-relative interest (cross-batch comparable). A pure `core/discover.py` mines candidate terms; a `collectors/naver_news.py` fetches riser headlines. `build_board` gains `candidates`, `news_context`, and per-term `category`; `html.py` renders category badges + 발굴 후보 + 뉴스 links. News I/O stays OUT of pure `build_board` — a thin `report/news.py` helper gathers it and the caller passes it in.

**Tech Stack:** Python 3.11+, Pydantic v2, httpx, stdlib, pytest. No new deps. No LLM.

**Setup note:** Run via venv: `.\.venv\Scripts\python.exe -m pytest ...`. Config `pythonpath=["src"]`, `addopts = -m 'not live'`. Branch: `feat/fnb-keyword-universe`.

**Spec:** `docs/superpowers/specs/2026-06-06-nylb-fnb-keyword-universe-design.md`

---

## File Structure

| File | Responsibility | New/Modify |
|---|---|---|
| `config/lenses.yaml` | menu lens: `radar` category map + `anchor` (+ researched keyword lists) | Modify |
| `src/nylb/core/scan.py` | flatten `radar` dict → `radar_watchlist` + `radar_categories` + `anchor` in query | Modify |
| `src/nylb/collectors/naver_datalab.py` | anchor-injected batches + anchor-relative rescale (legacy fallback) | Modify |
| `src/nylb/core/discover.py` | pure auto-discovery (n-gram + rising), base+config stopwords | Create |
| `src/nylb/collectors/naver_news.py` | Naver news headlines per term (cached) | Create |
| `src/nylb/collectors/naver.py` | per-keyword search (dedupe, resilience) | Modify |
| `src/nylb/report/board.py` | `build_board(..., news_context=None)` + candidates + category | Modify |
| `src/nylb/report/news.py` | gather riser headlines (I/O), keep build_board pure | Create |
| `src/nylb/report/html.py` | category badges + 발굴 후보 + 뉴스 links | Modify |
| `src/nylb/cli.py`, `src/nylb/report/server.py` | wire `report/news` into report-html / dashboard | Modify |
| tests: `test_scan_radar.py`, `test_datalab_anchor.py`, `test_discover.py`, `test_naver_news.py`, `test_naver_perkw.py`, `test_board_universe.py` | unit tests | Create |

**Interface contracts (keep identical across tasks):**
- `query["radar_categories"]: dict[str,str]` (term→category), `query["anchor"]: str|None`
- `naver_datalab` items keep `metrics={"interest": <anchor-relative>, "peak": ...}` + `raw={"series":[{date,value}]}` (rescaled)
- `discover.discover_candidates(result, top_n=10) -> list[dict]` keys: `term, freq, signal, sources, sample_title, from_rising`
- `naver_news.collect(terms: list[str], *, settings: dict, max_per_term=3) -> dict[str, list[dict]]` headline keys: `title, link, date`
- `news.gather_riser_news(result, chart, settings, top_n=5) -> dict[str, list[dict]]`
- `board.build_board(result, chart, news_context=None) -> dict` adds keys `candidates`, `news_context`; each core_signals/radar item gains `category`
- `html.build_dashboard(result, chart, news_context=None) -> str`

---

### Task 1: Categorized radar + anchor flattening (`core/scan.py`)

**Files:** Modify `src/nylb/core/scan.py`; Test `tests/test_scan_radar.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scan_radar.py
from datetime import datetime, timezone

from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _run(lens_config, tmp_path):
    import os
    os.chdir(tmp_path)
    return run_scan("menu", store_id="nylb", lens_config=lens_config, settings={},
                    store=LocalJsonStore(), run_id="r1", collected_at=NOW, collectors={})


def test_categorized_radar_flattens_with_categories_and_anchor(tmp_path):
    cfg = {"keywords": ["베이글"], "anchor": "베이글", "sources": [],
           "radar": {"flavor": ["말차", "흑임자"], "brands": ["성심당"]}}
    r = _run(cfg, tmp_path)
    assert set(r.query["radar_watchlist"]) == {"말차", "흑임자", "성심당"}
    assert r.query["radar_categories"] == {"말차": "flavor", "흑임자": "flavor", "성심당": "brands"}
    assert r.query["anchor"] == "베이글"


def test_legacy_flat_radar_still_works_and_anchor_defaults_to_first_keyword(tmp_path):
    cfg = {"keywords": ["베이글", "소금빵"], "sources": [],
           "radar_watchlist": ["탕후루"]}
    r = _run(cfg, tmp_path)
    assert r.query["radar_watchlist"] == ["탕후루"]
    assert r.query["radar_categories"] == {}
    assert r.query["anchor"] == "베이글"  # defaults to keywords[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_scan_radar.py -v`
Expected: FAIL (`KeyError: 'radar_categories'`).

- [ ] **Step 3: Edit `run_scan` in `src/nylb/core/scan.py`**

In the `query = {...}` dict, the existing key `"radar_watchlist": lens_config.get("radar_watchlist", [])` stays. After the `query = {...}` block (before the collectors loop), insert:

```python
    # Industry-agnostic: a categorized `radar` map (opaque category labels) is
    # flattened to the collector-compatible flat watchlist + a term→category map.
    radar_cfg = lens_config.get("radar")
    radar_categories: dict[str, str] = {}
    if isinstance(radar_cfg, dict):
        flat: list[str] = []
        for category, terms in radar_cfg.items():
            for term in terms:
                radar_categories[term] = category
                flat.append(term)
        query["radar_watchlist"] = flat
    query["radar_categories"] = radar_categories
    query["anchor"] = lens_config.get("anchor") or (
        (lens_config.get("keywords") or [None])[0])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_scan_radar.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/nylb/core/scan.py tests/test_scan_radar.py
git commit -m "feat: flatten categorized radar map + anchor into scan query"
```

---

### Task 2: Anchored DataLab (`collectors/naver_datalab.py`)

**Files:** Modify `src/nylb/collectors/naver_datalab.py`; Test `tests/test_datalab_anchor.py`

Anchoring: include the anchor keyword in every batch; rescale each term's daily series by `100 / mean(anchor_series)` for that batch. The anchor's mean becomes 100 in every batch, so terms across batches share one scale. No anchor → legacy per-batch behavior.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_datalab_anchor.py
from datetime import datetime, timezone

from nylb.collectors import naver_datalab

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


class _FakeResp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def _series(vals):
    return [{"period": f"2026-05-{i+1:02d}", "ratio": v} for i, v in enumerate(vals)]


def test_anchor_rescales_terms_to_common_scale(monkeypatch):
    # Two batches; anchor "베이글" present in both with DIFFERENT raw scales
    # (DataLab normalizes each request independently). After rescale, a term equal
    # in true volume to the anchor must read ~100 in BOTH batches.
    calls = []

    def fake_post(url, json, headers, timeout):
        groups = [g["groupName"] for g in json["keywordGroups"]]
        calls.append(groups)
        # batch1 raw: anchor peaks at 50; batch2 raw: anchor peaks at 10
        if "성심당" in groups:  # batch with brand
            data = {"베이글": _series([10, 10, 10]), "성심당": _series([80, 80, 80])}
        else:
            data = {"베이글": _series([50, 50, 50]), "말차": _series([25, 25, 25])}
        return _FakeResp({"results": [{"title": t, "data": data[t]} for t in groups]})

    monkeypatch.setattr(naver_datalab.httpx, "post", fake_post)
    query = {"keywords": ["베이글"], "radar_watchlist": ["말차", "성심당"], "anchor": "베이글"}
    res = naver_datalab.collect(query, "menu",
                                settings={"naver_client_id": "x", "naver_client_secret": "y"},
                                collected_at=NOW)
    by = {it.title: it.metrics["interest"] for it in res.items}
    # 베이글 rescaled mean == 100 in both batches → emitted once at ~100
    assert abs(by["베이글"] - 100) < 1
    # 말차 = half of anchor (25 vs 50) → ~50 ; 성심당 = 8x anchor (80 vs 10) → ~800
    assert abs(by["말차"] - 50) < 1
    assert abs(by["성심당"] - 800) < 1


def test_no_anchor_falls_back_to_legacy(monkeypatch):
    def fake_post(url, json, headers, timeout):
        groups = [g["groupName"] for g in json["keywordGroups"]]
        return _FakeResp({"results": [{"title": t, "data": _series([10, 20, 30])} for t in groups]})
    monkeypatch.setattr(naver_datalab.httpx, "post", fake_post)
    query = {"keywords": ["베이글"], "radar_watchlist": ["말차"]}  # no anchor
    res = naver_datalab.collect(query, "menu",
                                settings={"naver_client_id": "x", "naver_client_secret": "y"},
                                collected_at=NOW)
    by = {it.title: it.metrics["interest"] for it in res.items}
    assert by["베이글"] == 30.0 and by["말차"] == 30.0  # raw latest, unrescaled
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_datalab_anchor.py -v`
Expected: FAIL (anchor rescale not implemented; values are raw).

- [ ] **Step 3: Rewrite `_fetch` and `_parse` in `naver_datalab.py`**

Replace `_fetch` and `_parse` with:

```python
def _rescale(series: list[dict], factor: float) -> list[dict]:
    return [{"date": p["date"], "value": round(p["value"] * factor, 2)} for p in series]


def _fetch(query: dict, settings: dict) -> dict:
    cid = settings.get("naver_client_id")
    csec = settings.get("naver_client_secret")
    if not (cid and csec):
        raise RuntimeError("NAVER credentials missing")
    terms = list(query.get("keywords", [])) + list(query.get("radar_watchlist", []))
    terms = [t for t in dict.fromkeys(terms) if t]
    if not terms:
        return {"results": []}
    anchor = query.get("anchor")
    if anchor not in terms:
        anchor = None  # anchor must be queryable to rescale; else legacy
    others = [t for t in terms if t != anchor]
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=30)
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec,
               "Content-Type": "application/json"}
    out: list[dict] = []
    seen: set[str] = set()
    batch_size = 4 if anchor else 5
    for group in _chunks(others, batch_size):
        names = ([anchor] + list(group)) if anchor else list(group)
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(),
                "timeUnit": "date",
                "keywordGroups": [{"groupName": t, "keywords": [t]} for t in names]}
        r = httpx.post(_URL, json=body, headers=headers, timeout=20)
        r.raise_for_status()
        raw = {res.get("title", ""): [{"date": d["period"], "value": float(d["ratio"])}
                                      for d in res.get("data", [])]
               for res in r.json().get("results", [])}
        factor = 1.0
        if anchor:
            avals = [p["value"] for p in raw.get(anchor, [])]
            amean = sum(avals) / len(avals) if avals else 0.0
            factor = (100.0 / amean) if amean > 0 else 1.0
        for name, series in raw.items():
            if name in seen:
                continue
            seen.add(name)
            out.append({"title": name,
                        "series": _rescale(series, factor) if anchor else
                                  [{"date": p["date"], "value": p["value"]} for p in series]})
    return {"results": out}


def _parse(payload: dict, query: dict, lens: str, collected_at: datetime) -> list[Item]:
    items: list[Item] = []
    for res in payload.get("results", []):
        series = res["series"]
        latest = series[-1]["value"] if series else 0.0
        peak = max((p["value"] for p in series), default=0.0)
        items.append(Item(
            source=SOURCE, lens=lens, type="search_term", title=res["title"],
            metrics={"interest": latest, "peak": peak},
            collected_at=collected_at, raw={"series": series},
        ))
    return items
```

(Note: `_fetch` now returns pre-extracted `series` per result, so `_parse` reads `res["series"]` directly — no more `res["data"]`/`ratio`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_datalab_anchor.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run full suite to catch chart_data/board consumers**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS. `chart_data._trend_stats` consumes `raw["series"]` `{date,value}` which is unchanged in shape, so board/context keep working.

- [ ] **Step 6: Commit**

```bash
git add src/nylb/collectors/naver_datalab.py tests/test_datalab_anchor.py
git commit -m "feat: anchor-relative DataLab rescale (cross-batch comparable ranking)"
```

---

### Task 3: Auto-discovery (`core/discover.py`)

**Files:** Create `src/nylb/core/discover.py`; Test `tests/test_discover.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_discover.py
from datetime import datetime, timezone

from nylb.core.schema import Item, ScanResult
from nylb.core.discover import discover_candidates

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _yt(title):
    return Item(source="youtube", lens="menu", type="video", title=title, collected_at=NOW)


def _result(items, query):
    return ScanResult(run_id="r", store_id="nylb", lens="menu", query=query,
                      items=items, started_at=NOW, finished_at=NOW)


def test_discovers_repeated_unknown_term_excludes_known_and_stopwords():
    items = [_yt("두바이 쫀득 쿠키 리뷰"), _yt("두바이 쫀득 쿠키 후기"),
             _yt("베이글 맛집 추천")]  # 베이글=known, 맛집/추천/후기=stopword
    q = {"keywords": ["베이글"], "radar_categories": {}, "synonyms": {}}
    out = discover_candidates(_result(items, q), top_n=10)
    terms = [c["term"] for c in out]
    assert "두바이" in terms or "쫀득" in terms or "두바이 쫀득" in terms
    assert "베이글" not in terms
    assert "맛집" not in terms and "추천" not in terms


def test_single_occurrence_dropped_and_rising_merged():
    items = [_yt("말차 라떼")]  # appears once → below >=2 threshold
    rising = Item(source="google_trends", lens="menu", type="rising_query",
                  title="버터떡", collected_at=NOW, metrics={"value": 9000.0},
                  raw={"seed": "디저트"})
    q = {"keywords": [], "radar_categories": {}, "synonyms": {}}
    out = discover_candidates(_result([items[0], rising], q), top_n=10)
    terms = {c["term"]: c for c in out}
    assert "말차" not in terms                 # single occurrence dropped
    assert "버터떡" in terms and terms["버터떡"]["from_rising"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_discover.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `src/nylb/core/discover.py`**

```python
from __future__ import annotations

import re

from nylb.core.schema import ScanResult
from nylb.core.signal import score_items

_CONTENT_SOURCES = {"youtube", "naver"}
_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")

# F&B-generic stopwords (no specific food/brand literals — works across verticals).
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
    from nylb.core.signal import item_key

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
        tokens = [t for t in _TOKEN.findall(it.title)]
        for g in _ngrams(tokens):
            k = g.lower()
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_discover.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/nylb/core/discover.py tests/test_discover.py
git commit -m "feat: deterministic auto-discovery of candidate terms (n-gram + rising)"
```

---

### Task 4: Naver news collector (`collectors/naver_news.py`)

**Files:** Create `src/nylb/collectors/naver_news.py`; Test `tests/test_naver_news.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_naver_news.py
from nylb.collectors import naver_news


class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def test_collect_returns_headlines_per_term(monkeypatch):
    def fake_get(url, params, headers, timeout):
        return _Resp({"items": [
            {"title": "<b>아우어</b> 신메뉴 출시", "link": "http://n/1",
             "pubDate": "Mon, 02 Jun 2026 09:00:00 +0900"},
            {"title": "두 번째 기사", "link": "http://n/2", "pubDate": ""},
        ]})
    monkeypatch.setattr(naver_news.httpx, "get", fake_get)
    out = naver_news.collect(["아우어베이커리"],
                             settings={"naver_client_id": "x", "naver_client_secret": "y"},
                             max_per_term=3)
    assert "아우어베이커리" in out
    first = out["아우어베이커리"][0]
    assert first["title"] == "아우어 신메뉴 출시"  # html stripped
    assert first["link"] == "http://n/1"


def test_missing_credentials_returns_empty(monkeypatch):
    out = naver_news.collect(["x"], settings={}, max_per_term=3)
    assert out == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_naver_news.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `src/nylb/collectors/naver_news.py`**

```python
from __future__ import annotations

import httpx

from nylb.collectors.base import strip_html

_URL = "https://openapi.naver.com/v1/search/news.json"


def collect(terms: list[str], *, settings: dict, max_per_term: int = 3) -> dict[str, list[dict]]:
    """Recent Naver news headlines per term (title/link/date). Deterministic context
    for risers — NO summarization, NO verdict. Returns {} if creds/scope unavailable
    or on error (best-effort; never raises)."""
    cid = settings.get("naver_client_id")
    csec = settings.get("naver_client_secret")
    if not (cid and csec):
        return {}
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
    out: dict[str, list[dict]] = {}
    for term in terms:
        try:
            r = httpx.get(_URL, params={"query": term, "display": max_per_term, "sort": "date"},
                          headers=headers, timeout=15)
            r.raise_for_status()
            heads = [{"title": strip_html(it.get("title", "")),
                      "link": it.get("link", ""),
                      "date": it.get("pubDate", "")}
                     for it in r.json().get("items", [])[:max_per_term]]
            if heads:
                out[term] = heads
        except Exception:
            continue  # best-effort per term (scope disabled / rate / network)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_naver_news.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/nylb/collectors/naver_news.py tests/test_naver_news.py
git commit -m "feat: Naver news collector for riser headlines (best-effort, no LLM)"
```

---

### Task 5: Naver per-keyword search (`collectors/naver.py`)

**Files:** Modify `src/nylb/collectors/naver.py`; Test `tests/test_naver_perkw.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_naver_perkw.py
from datetime import datetime, timezone

from nylb.collectors import naver

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def test_searches_each_keyword_and_dedupes(monkeypatch):
    seen = []

    def fake_get(url, params, headers, timeout):
        seen.append(params["query"])
        # both keywords return one shared link + one unique
        return _Resp({"items": [
            {"title": params["query"], "link": "http://shared", "description": "", "postdate": ""},
            {"title": params["query"] + " uniq", "link": "http://" + params["query"],
             "description": "", "postdate": ""},
        ]})
    monkeypatch.setattr(naver.httpx, "get", fake_get)
    res = naver.collect({"keywords": ["베이글", "소금빵"]}, "menu",
                        settings={"naver_client_id": "x", "naver_client_secret": "y"},
                        collected_at=NOW)
    assert seen == ["베이글", "소금빵"]            # one call per keyword
    links = [it.url for it in res.items]
    assert links.count("http://shared") == 1       # deduped across keywords


def test_one_keyword_failure_tolerated(monkeypatch):
    def fake_get(url, params, headers, timeout):
        if params["query"] == "소금빵":
            raise RuntimeError("boom")
        return _Resp({"items": [{"title": "t", "link": "http://ok",
                                 "description": "", "postdate": ""}]})
    monkeypatch.setattr(naver.httpx, "get", fake_get)
    res = naver.collect({"keywords": ["베이글", "소금빵"]}, "menu",
                        settings={"naver_client_id": "x", "naver_client_secret": "y"},
                        collected_at=NOW)
    assert [it.url for it in res.items] == ["http://ok"]  # 베이글 survived
    assert res.errors == []                               # partial failure tolerated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_naver_perkw.py -v`
Expected: FAIL (current `_fetch` joins keywords into one query → `seen` would be `["베이글 소금빵"]`).

- [ ] **Step 3: Replace `_fetch` and `collect` in `naver.py`** (keep `_parse`, `_parse_postdate` unchanged)

```python
def _fetch_one(keyword: str, settings: dict) -> dict:
    cid = settings.get("naver_client_id")
    csec = settings.get("naver_client_secret")
    if not (cid and csec):
        raise RuntimeError("NAVER credentials missing")
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
    params = {"query": keyword, "display": 20, "sort": "sim"}
    r = httpx.get(_SEARCH_URL, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


def collect(query: dict, lens: str, *, settings: dict, collected_at: datetime) -> CollectResult:
    keywords = list(query.get("keywords", [])) or ["베이글"]
    items: list[Item] = []
    errors: list[CollectError] = []
    seen: set[str] = set()
    for kw in keywords:
        try:
            payload = _fetch_one(kw, settings)
        except Exception as exc:
            errors.append(CollectError(source=SOURCE, message=f"{kw}: {exc}"))
            continue
        for it in _parse(payload, query, lens, collected_at):
            key = it.url or it.title
            if key in seen:
                continue
            seen.add(key)
            items.append(it)
    # total failure (every keyword errored) surfaces; partial is tolerated
    if errors and not items and len(errors) == len(keywords):
        return CollectResult(errors=errors)
    return CollectResult(items=items)
```

(The `["베이글"]` default is a harmless empty-keywords guard mirroring the old code; it is not a domain assumption used by any non-bakery lens, which always supplies its own keywords.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_naver_perkw.py -v` then full suite `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nylb/collectors/naver.py tests/test_naver_perkw.py
git commit -m "refactor: per-keyword Naver search with dedupe + resilience"
```

---

### Task 6: Board integration — categories + candidates + news (`report/board.py`, `report/news.py`)

**Files:** Modify `src/nylb/report/board.py`; Create `src/nylb/report/news.py`; Test add to `tests/test_board_universe.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_board_universe.py
from datetime import datetime, timezone

from nylb.core.schema import Item, ScanResult
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _series(vals):
    return [{"date": f"2026-05-{i+1:02d}", "value": v} for i, v in enumerate(vals)]


def _dl(term, vals):
    return Item(source="naver_datalab", lens="menu", type="search_term", title=term,
                collected_at=NOW, raw={"series": _series(vals)})


def _yt(title):
    return Item(source="youtube", lens="menu", type="video", title=title, collected_at=NOW)


def _result():
    items = [_dl("베이글", [80, 85, 90]), _dl("성심당", [200, 400, 800]),
             _yt("두바이 쫀득 쿠키 후기"), _yt("두바이 쫀득 쿠키 리뷰")]
    q = {"keywords": ["베이글"], "synonyms": {},
         "radar_categories": {"성심당": "brands"}, "anchor": "베이글"}
    return ScanResult(run_id="r", store_id="nylb", lens="menu", query=q,
                      items=items, started_at=NOW, finished_at=NOW)


def test_board_has_category_candidates_and_news_context():
    r = _result()
    chart = extract_chart_data(r)
    news = {"성심당": [{"title": "성심당 신메뉴", "link": "http://n", "date": "x"}]}
    board = build_board(r, chart, news_context=news)
    # radar item carries its config category
    sansim = next(c for c in board["radar"] if c["term"] == "성심당")
    assert sansim["category"] == "brands"
    # discovered candidate present (두바이 쫀득 쿠키 appears twice)
    assert any("두바이" in c["term"] or "쫀득" in c["term"] for c in board["candidates"])
    # news context passed through
    assert board["news_context"]["성심당"][0]["title"] == "성심당 신메뉴"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_board_universe.py -v`
Expected: FAIL (`build_board` takes 2 args; no `category`/`candidates`/`news_context`).

- [ ] **Step 3a: Edit `build_board` in `report/board.py`**

Change the signature and add the three pieces. Replace `def build_board(result, chart):` with:

```python
def build_board(result, chart, news_context=None):
```

Add this import at the top of `board.py`:

```python
from nylb.core.discover import discover_candidates
```

Where `core_signals` and `radar` lists are built via `contextualize(...)`, stamp each item with its category. Replace the two list comprehensions with:

```python
    cats = chart.get("radar_categories", {}) or result.query.get("radar_categories", {})

    def _ctx(term, st):
        cm = contextualize(term, st, rank_of.get(term), total)
        cm["category"] = cats.get(term, "core" if term in core_set else "radar")
        return cm

    core_signals = [_ctx(t, tstats[t]) for t in core if t in tstats]
    radar = [_ctx(t, st) for t, st in ranked if t not in core_set]
```

In the returned dict, add three keys (anywhere in the dict literal):

```python
        "candidates": discover_candidates(result, top_n=10),
        "news_context": news_context or {},
```

- [ ] **Step 3b: Make `chart_data` expose `radar_categories`**

In `src/nylb/report/chart_data.py`, the returned dict currently ends with `"radar_watchlist": ...`. Add one key:

```python
        "radar_categories": dict(result.query.get("radar_categories", {})),
```

- [ ] **Step 3c: Create `src/nylb/report/news.py`** (riser selection + fetch; keeps build_board pure)

```python
from __future__ import annotations

from nylb.collectors import naver_news
from nylb.report.board import build_chart_block  # noqa: F401  (kept: shared trend source)


def gather_riser_news(result, chart, settings: dict, top_n: int = 5) -> dict:
    """Pick the top risers (by momentum) across the tracked trend universe and
    fetch recent Naver news headlines for them. I/O lives here so build_board stays
    pure. Returns {} on no creds (best-effort)."""
    source = "naver_datalab" if chart["trends"].get("naver_datalab") else "google_trends"
    tstats = chart["trends"].get(source, {})
    risers = sorted(tstats.items(), key=lambda kv: kv[1].get("momentum", 0.0), reverse=True)
    terms = [t for t, st in risers if st.get("momentum", 0.0) > 0][:top_n]
    if not terms:
        return {}
    return naver_news.collect(terms, settings=settings, max_per_term=3)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_board_universe.py -v` then full suite `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS. (Earlier board tests call `build_board(result, chart)` — `news_context` defaults to None, so they still pass.)

- [ ] **Step 5: Commit**

```bash
git add src/nylb/report/board.py src/nylb/report/news.py src/nylb/report/chart_data.py tests/test_board_universe.py
git commit -m "feat: board categories + auto-discovery candidates + riser news context"
```

---

### Task 7: Render universe (`report/html.py`, wire news in cli/server)

**Files:** Modify `src/nylb/report/html.py`, `src/nylb/cli.py`, `src/nylb/report/server.py`

- [ ] **Step 1: Write the failing test (extend `tests/test_board_universe.py`)**

```python
def test_dashboard_renders_candidates_and_news():
    from nylb.report.html import build_dashboard
    r = _result()
    chart = extract_chart_data(r)
    news = {"성심당": [{"title": "성심당 신메뉴", "link": "http://n", "date": "x"}]}
    html = build_dashboard(r, chart, news_context=news)
    assert '"candidates"' in html and '"news_context"' in html
    assert "발굴 후보" in html          # discovery section header
    assert "관련 뉴스" in html           # news header
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_board_universe.py::test_dashboard_renders_candidates_and_news -v`
Expected: FAIL (`build_dashboard` is 2-arg; sections absent).

- [ ] **Step 3a: Update `build_dashboard` in `html.py`**

```python
def build_dashboard(result: ScanResult, chart: dict, news_context=None) -> str:
    board = build_board(result, chart, news_context=news_context)
    return _TEMPLATE.replace("__DATA__", json.dumps(board, ensure_ascii=False))
```

- [ ] **Step 3b: Add two render blocks to the `<script>` in `_TEMPLATE`**

Immediately BEFORE the `/* DATA TRUST */` block, insert a 발굴 후보 section and a category-aware note. Add:

```html
/* DISCOVERY CANDIDATES */
(function(){const cs=DATA.candidates||[]; if(!cs.length)return;
  const sec=sect("🔎","발굴 후보 (미편입)","콘텐츠·급상승어에서 자동 발굴된 후보 — 검증·편입 판단은 사장님 몫");
  const card=h("div",{class:"card"});const ul=h("ul",{class:"gaps"});
  cs.forEach(c=>ul.appendChild(h("li",null,
    c.term+"  ·  빈도 "+c.freq+(c.from_rising?"  ·  🔥급상승":"")+
    (c.sample_title?("  ·  예: "+c.sample_title.slice(0,30)):"")))); 
  card.appendChild(ul); sec.appendChild(card); app.appendChild(sec);})();
```

In the CORE SIGNALS and RADAR render blocks, append the category badge + news links. In the RADAR block, change the card body push to also show category and any news. Replace the RADAR IIFE body's `rd.forEach(...)` with:

```html
  rd.forEach(c=>{const card=h("div",{class:"vc"});card.style.borderTopColor=DCOL[c.direction];
    card.appendChild(h("h3",null,[document.createTextNode(c.term),
      h("span",{class:"mom "+c.direction},ARROW[c.direction]+" "+(c.momentum>=0?"+":"")+c.momentum)]));
    card.appendChild(h("div",{class:"stage"},"검증됨 ✓ · "+(c.category||"radar")));
    card.appendChild(h("p",null,c.caption));
    const nx=(DATA.news_context||{})[c.term]||[];
    if(nx.length){const nd=h("div",{style:"margin-top:7px;font-size:11.5px"});
      nd.appendChild(h("div",{style:"color:var(--muted);font-weight:700"},"📰 관련 뉴스"));
      nx.slice(0,3).forEach(n=>{const a=h("a",{href:n.link,target:"_blank",
        style:"display:block;color:var(--bagel);text-decoration:none;margin-top:2px"},
        "· "+n.title); nd.appendChild(a);});
      card.appendChild(nd);}
    g.appendChild(card);});
```

Also add the news block to CORE SIGNALS the same way (so a rising core keyword shows news): in the CORE SIGNALS IIFE, before `g.appendChild(card);`, insert the same `const nx=...` news block.

- [ ] **Step 3c: Wire news fetching in `cli._report_html` and `server.run_scan_and_render`**

In `src/nylb/cli.py` `_report_html`:

```python
def _report_html(args) -> int:
    from nylb.config import load_settings
    from nylb.report.news import gather_riser_news
    result = LocalJsonStore().load(args.run)
    chart = extract_chart_data(result)
    news = gather_riser_news(result, chart, load_settings())
    html = build_dashboard(result, chart, news_context=news)
    path = write_text_report(html, args.run, out_dir="reports", suffix=".analysis.html")
    print(f"html={path}")
    return 0
```

In `src/nylb/report/server.py` `run_scan_and_render`, after `result = run_scan(...)`:

```python
    chart = extract_chart_data(result)
    from nylb.report.news import gather_riser_news
    news = gather_riser_news(result, chart, settings)
    return build_dashboard(result, chart, news_context=news)
```

(Replace its existing `return build_dashboard(result, extract_chart_data(result))` line. `settings` is already loaded in that function.)

- [ ] **Step 4: Run tests + full suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (the new render test + all prior). Update any existing test that asserted exact `build_dashboard` arity if needed (it has a default, so 2-arg calls still work).

- [ ] **Step 5: Commit**

```bash
git add src/nylb/report/html.py src/nylb/cli.py src/nylb/report/server.py tests/test_board_universe.py
git commit -m "feat: render category badges, discovery candidates, riser news links"
```

---

### Task 8: Researched config + industry-agnostic test + live verify

**Files:** Modify `config/lenses.yaml`; Test `tests/test_industry_agnostic.py`

- [ ] **Step 1: Industry-agnostic test (non-bakery lens)**

```python
# tests/test_industry_agnostic.py
from datetime import datetime, timezone

from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore
from nylb.core.discover import discover_candidates
from nylb.core.schema import Item, ScanResult

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def test_scan_flatten_works_for_a_chicken_shop(tmp_path):
    import os
    os.chdir(tmp_path)
    cfg = {"keywords": ["치킨", "교촌"], "anchor": "치킨", "sources": [],
           "radar": {"flavor": ["양념", "마라"], "brands": ["bbq", "굽네"]}}
    r = run_scan("menu", store_id="s", lens_config=cfg, settings={},
                 store=LocalJsonStore(), run_id="r", collected_at=NOW, collectors={})
    assert r.query["anchor"] == "치킨"
    assert r.query["radar_categories"]["bbq"] == "brands"
    # discovery has no bakery literals — a chicken title yields chicken candidates
    items = [Item(source="youtube", lens="menu", type="video", title="마라 치킨 먹방", collected_at=NOW),
             Item(source="youtube", lens="menu", type="video", title="마라 치킨 후기", collected_at=NOW)]
    res = ScanResult(run_id="r", store_id="s", lens="menu",
                     query={"keywords": ["치킨"], "radar_categories": {}, "synonyms": {}},
                     items=items, started_at=NOW, finished_at=NOW)
    cands = [c["term"] for c in discover_candidates(res)]
    assert "치킨" not in cands  # known excluded; engine carries no bakery/chicken bias
```

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_industry_agnostic.py -v` → expect PASS (the engine is already generic after Tasks 1 & 3).

- [ ] **Step 2: Research + write the bakery config**

Replace the menu lens in `config/lenses.yaml` with a researched categorized universe. Use WebSearch + `reports/2026-06-04-bakery-pricing-research.md` to confirm 2026-current terms; AVOID false positives (e.g. 마라탕후루 = a song). Set `anchor: 베이글`. Categories: `flavor`, `format`, `adjacent`, `brands`. Keep `keywords` at 5–7. Example skeleton to fill from research:

```yaml
    menu:
      keywords: [베이글, 소금빵, 크로플, 휘낭시에, 프레첼]
      anchor: 베이글
      radar:
        flavor:   [말차, 흑임자, 피스타치오, 두바이초콜릿, 솔티드캐러멜, 비스코프, 얼그레이]
        format:   [베이글샌드위치, 오픈샌드위치, 구움과자, 디저트박스, 스콘]
        adjacent: [탕후루, 약과, 요거트아이스크림, 크룽지, 버터떡, 두쫀쿠, 까눌레]
        brands:   [성심당, 런던베이글뮤지엄, 노티드, 아우어베이커리, 포비, 뚜레쥬르, 파리바게뜨]
      radar_seeds: [베이글, 디저트, 베이커리]
      sources: [youtube, naver, google_trends, naver_datalab]
      synonyms:
        베이글: [bagel]
        소금빵: ["소금 빵", "salt bread"]
        크로플: [croffle]
      discover_stopwords: [맛집, 카페, 후기, 추천, 먹방, 신상]
```

- [ ] **Step 3: Commit the config**

```bash
git add config/lenses.yaml tests/test_industry_agnostic.py
git commit -m "feat: researched categorized bakery universe + industry-agnostic test"
```

- [ ] **Step 4: Live verification (needs .env keys)**

```bash
.\.venv\Scripts\python.exe -m nylb scan --lens menu --store nylb
.\.venv\Scripts\python.exe -m nylb report-html --run <run_id>
```

Open `reports/<run_id>.analysis.html` (serve via `python -m http.server` under `reports/`, Playwright can't open file://). Confirm:
- DataLab covers the expanded radar; interest ranking is anchor-relative and spans categories.
- Category badges show on radar cards (flavor/format/adjacent/brands).
- 🔎 발굴 후보 section appears.
- 📰 관련 뉴스 links appear on at least one riser.
- No verdict sections; 0 JS console errors (favicon-404 ok).

- [ ] **Step 5: Final full suite + commit any fixes**

Run: `.\.venv\Scripts\python.exe -m pytest -q` → PASS. Commit verification-driven fixes if any.

---

## Self-Review

**1. Spec coverage:** B1 categorized universe + anchor → Task 1 & config Task 8. B2 anchored DataLab → Task 2. B3 auto-discovery → Task 3. B4 news context → Task 4 (+wiring Task 6/7). B5 per-keyword Naver → Task 5. Board category grouping + candidates + news render → Tasks 6 & 7. Industry-agnostic constraint → Task 8 test + the config-only domain vocab throughout. LLM-free preserved (discover/news are deterministic; no synthesis). ✓

**2. Placeholder scan:** No TBD/TODO. Every code step has complete code. The config keyword *lists* in Task 8 are explicitly a research step (the engine is generic; lists are config data the implementer researches — mirrors the spec's intended owner/research step), with a complete fill-in skeleton given. ✓

**3. Type consistency:** `radar_categories` (term→category) defined Task 1, consumed Task 6/8. `anchor` defined Task 1, consumed Task 2. DataLab `raw["series"]` `{date,value}` shape preserved (Task 2) → `chart_data._trend_stats` unaffected. `discover_candidates(result, top_n)` keys `term/freq/signal/sources/sample_title/from_rising` defined Task 3, rendered Task 7. `naver_news.collect(terms, *, settings, max_per_term)` → `{term:[{title,link,date}]}` defined Task 4, consumed Task 6 (`news.py`) and rendered Task 7. `build_board(result, chart, news_context=None)` defined Task 6, called Task 7 (`build_dashboard`) + cli/server. `gather_riser_news(result, chart, settings, top_n)` defined Task 6, called Task 7. ✓

## Execution Handoff

Two options:
1. **Subagent-Driven (recommended)** — fresh subagent per task + two-stage review (same flow as the board build).
2. **Inline Execution** — batch with checkpoints.
