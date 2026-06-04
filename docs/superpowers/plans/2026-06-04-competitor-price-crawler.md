# Competitor Price Crawler (Marketkurly) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crawl Marketkurly product pages for competitor prices and surface them in the dashboard, via a new `kurly` collector on the existing `competitor` lens, with a polite file cache.

**Architecture:** Follow the uniform collector contract (`collect`/`_fetch`/`_parse`). `kurly._fetch` GETs each configured competitor product URL (User-Agent, ~1.5s delay between live requests, `data/cache/` file cache), `_parse` pulls the product node out of the page's `__NEXT_DATA__` JSON (recursive search, disambiguated by the URL's goods id) and reads `name`/`discountedPrice`/`basePrice`. Results persist via the existing Store seam and render as a "경쟁사 가격" dashboard section.

**Tech Stack:** Python 3.12, httpx, Pydantic v2, pytest. Run with `.\.venv\Scripts\python.exe` (Bash tool mangles the Windows venv path — use the PowerShell tool for python/pytest/git).

**Spec:** `docs/superpowers/specs/2026-06-04-competitor-price-crawler-design.md`

**Verified facts (due-diligence 2026-06-04):** kurly `robots.txt` allows `/goods/` for `*`; product pages return httpx 200 (no anti-bot); price lives in `__NEXT_DATA__` JSON as `discountedPrice` (8910) / `basePrice` (9900); name via `og:title` / JSON `name`.

**Conventions:** fixture-based `_parse` unit tests; live network test tagged `@pytest.mark.live` and excluded by default. Commit per task. Branch: `feat/competitor-crawler`.

---

## File Structure

| File | Responsibility | Create/Modify |
|------|----------------|---------------|
| `src/nylb/core/schema.py` | add `kurly` to `Source` Literal | Modify |
| `src/nylb/collectors/cache.py` | URL→file cache with TTL | Create |
| `src/nylb/collectors/kurly.py` | Kurly product-price collector | Create |
| `src/nylb/core/scan.py` | pass `competitor_products`; register `kurly` | Modify |
| `config/lenses.yaml` | competitor lens: `sources:[kurly]` + products | Modify |
| `src/nylb/report/chart_data.py` | extract `competitors` | Modify |
| `src/nylb/report/html.py` | "경쟁사 가격" section | Modify |
| `pyproject.toml` | exclude `live` tests by default | Modify |
| `tests/collectors/test_cache.py` | cache tests | Create |
| `tests/collectors/test_kurly.py` | parse + live smoke | Create |
| `tests/core/test_scan.py` | competitor_products in query | Modify |
| `tests/report/test_chart_data.py` | competitors extraction | Modify |
| `tests/report/test_html.py` | competitor section | Modify |

---

## Task 1: Add `kurly` to the Source Literal + exclude live tests by default

**Files:**
- Modify: `src/nylb/core/schema.py:8`
- Modify: `pyproject.toml` (`[tool.pytest.ini_options]`)
- Test: `tests/core/test_schema.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_schema.py`:

```python
def test_item_accepts_kurly_source():
    from datetime import datetime, timezone
    from nylb.core.schema import Item
    it = Item(source="kurly", lens="competitor", type="product",
              title="크림치즈", collected_at=datetime(2026, 6, 4, tzinfo=timezone.utc))
    assert it.source == "kurly"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_schema.py::test_item_accepts_kurly_source -v`
Expected: FAIL — Pydantic ValidationError (`kurly` not in Literal).

- [ ] **Step 3: Add the source value + exclude live by default**

In `src/nylb/core/schema.py` line 8:

```python
Source = Literal["youtube", "naver", "google_trends", "naver_datalab", "kurly", "instagram"]
```

In `pyproject.toml`, under `[tool.pytest.ini_options]`, add an `addopts` line so live network tests are skipped unless explicitly selected:

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
markers = ["live: hits real external APIs (needs keys)"]
addopts = "-m 'not live'"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/nylb/core/schema.py pyproject.toml tests/core/test_schema.py
git commit -m "feat: add kurly source; exclude live tests by default"
```

---

## Task 2: File cache (`collectors/cache.py`)

**Files:**
- Create: `src/nylb/collectors/cache.py`
- Test: `tests/collectors/test_cache.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/collectors/test_cache.py`:

```python
import os
import time
from nylb.collectors.cache import get_cached, put_cache


def test_cache_put_get_roundtrip(tmp_path):
    url = "https://www.kurly.com/goods/1"
    assert get_cached(url, ttl_days=7, base_dir=tmp_path) is None
    put_cache(url, "<html>hi</html>", base_dir=tmp_path)
    assert get_cached(url, ttl_days=7, base_dir=tmp_path) == "<html>hi</html>"


def test_cache_ttl_expiry(tmp_path):
    url = "https://www.kurly.com/goods/2"
    put_cache(url, "old", base_dir=tmp_path)
    f = next(tmp_path.glob("*.html"))
    old = time.time() - 10 * 86400
    os.utime(f, (old, old))
    assert get_cached(url, ttl_days=7, base_dir=tmp_path) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/collectors/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: nylb.collectors.cache`.

- [ ] **Step 3: Implement the cache**

Create `src/nylb/collectors/cache.py`:

```python
from __future__ import annotations

import hashlib
import time
from pathlib import Path

_CACHE_DIR = Path("data/cache")


def _name(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + ".html"


def get_cached(url: str, ttl_days: float, base_dir: Path | str = _CACHE_DIR) -> str | None:
    p = Path(base_dir) / _name(url)
    if not p.exists():
        return None
    age_days = (time.time() - p.stat().st_mtime) / 86400
    if age_days > ttl_days:
        return None
    return p.read_text(encoding="utf-8")


def put_cache(url: str, text: str, base_dir: Path | str = _CACHE_DIR) -> None:
    d = Path(base_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / _name(url)).write_text(text, encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/collectors/test_cache.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/nylb/collectors/cache.py tests/collectors/test_cache.py
git commit -m "feat: add file cache for collectors"
```

---

## Task 3: Kurly collector (`collectors/kurly.py`)

**Files:**
- Create: `src/nylb/collectors/kurly.py`
- Test: `tests/collectors/test_kurly.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/collectors/test_kurly.py`:

```python
from datetime import datetime, timezone
import pytest
import nylb.collectors.kurly as k

NOW = datetime(2026, 6, 4, tzinfo=timezone.utc)

# Synthetic page: main product (goods 5043336) + a recommendation node.
# Both carry name/basePrice/discountedPrice; the parser must pick the main one by goods id.
FIXTURE = ('<html><head>'
           '<meta property="og:title" content="[포비베이글] 크림치즈 200g 8종 (택1) - 마켓컬리">'
           '</head><body>'
           '<script id="__NEXT_DATA__" type="application/json">'
           '{"props":{"pageProps":{'
           '"product":{"no":5043336,"name":"[포비베이글] 크림치즈 200g 8종 (택1)",'
           '"basePrice":9900,"discountedPrice":8910},'
           '"recommends":[{"no":111,"name":"다른상품","basePrice":5000,"discountedPrice":4500}]'
           '}}}'
           '</script></body></html>')


def test_parse_picks_product_by_goods_id():
    pages = [{"brand": "포비(FOURB)", "url": "https://www.kurly.com/goods/5043336", "html": FIXTURE}]
    items = k._parse(pages, "competitor", NOW)
    assert len(items) == 1
    it = items[0]
    assert it.source == "kurly" and it.type == "product" and it.lens == "competitor"
    assert it.title == "[포비베이글] 크림치즈 200g 8종 (택1)"
    assert it.metrics["price"] == 8910.0
    assert it.metrics["base_price"] == 9900.0
    assert it.author == "포비(FOURB)"
    assert it.url == "https://www.kurly.com/goods/5043336"


def test_parse_skips_page_without_next_data():
    pages = [{"brand": "x", "url": "https://www.kurly.com/goods/9", "html": "<html>no data</html>"}]
    assert k._parse(pages, "competitor", NOW) == []


def test_collect_handles_error(monkeypatch):
    def boom(query, settings):
        raise RuntimeError("blocked")
    monkeypatch.setattr(k, "_fetch", boom)
    res = k.collect({"competitor_products": [{"url": "x"}]}, "competitor",
                    settings={}, collected_at=NOW)
    assert res.items == []
    assert res.errors[0].source == "kurly"


@pytest.mark.live
def test_kurly_live_smoke():
    q = {"competitor_products": [
        {"brand": "포비(FOURB)", "url": "https://www.kurly.com/goods/5043336"}]}
    res = k.collect(q, "competitor", settings={},
                    collected_at=datetime.now(timezone.utc))
    assert res.items and res.items[0].metrics["price"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/collectors/test_kurly.py -v`
Expected: FAIL — `ModuleNotFoundError: nylb.collectors.kurly`.

- [ ] **Step 3: Implement the collector**

Create `src/nylb/collectors/kurly.py`:

```python
from __future__ import annotations

import json
import re
import time
from datetime import datetime

import httpx

from nylb.collectors.cache import get_cached, put_cache
from nylb.core.schema import CollectError, CollectResult, Item

SOURCE = "kurly"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_NEXT = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL)


def _goods_id(url: str) -> str:
    m = re.search(r"/goods/(\d+)", url)
    return m.group(1) if m else ""


def _find_product(node, goods_id: str):
    """Find a product dict (has name+basePrice+discountedPrice); prefer the
    one whose values include the goods id (disambiguates from recommendations)."""
    found: list[dict] = []

    def walk(n):
        if isinstance(n, dict):
            if {"name", "basePrice", "discountedPrice"} <= n.keys():
                found.append(n)
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(node)
    if not found:
        return None
    for d in found:
        if goods_id and goods_id in {str(v) for v in d.values()}:
            return d
    return found[0]


def _parse(pages: list[dict], lens: str, collected_at: datetime) -> list[Item]:
    items: list[Item] = []
    for pg in pages:
        m = _NEXT.search(pg["html"])
        if not m:
            continue
        prod = _find_product(json.loads(m.group(1)), _goods_id(pg["url"]))
        if not prod:
            continue
        items.append(Item(
            source=SOURCE, lens=lens, type="product",
            title=str(prod["name"]), url=pg["url"], author=pg.get("brand"),
            metrics={"price": float(prod["discountedPrice"]),
                     "base_price": float(prod["basePrice"])},
            collected_at=collected_at, raw={"goods_id": _goods_id(pg["url"])},
        ))
    return items


def _fetch(query: dict, settings: dict) -> list[dict]:
    products = query.get("competitor_products", []) or []
    headers = {"User-Agent": _UA, "Accept-Language": "ko-KR,ko;q=0.9"}
    pages: list[dict] = []
    live_calls = 0
    for p in products:
        url = p["url"]
        html = get_cached(url, ttl_days=7)
        if html is None:
            if live_calls:
                time.sleep(1.5)            # polite rate-limit between live requests
            live_calls += 1
            r = httpx.get(url, headers=headers, timeout=25, follow_redirects=True)
            r.raise_for_status()
            html = r.text
            put_cache(url, html)
        pages.append({"brand": p.get("brand"), "url": url, "html": html})
    return pages


def collect(query: dict, lens: str, *, settings: dict, collected_at: datetime) -> CollectResult:
    try:
        pages = _fetch(query, settings)
        return CollectResult(items=_parse(pages, lens, collected_at))
    except Exception as exc:
        return CollectResult(errors=[CollectError(source=SOURCE, message=str(exc))])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/collectors/test_kurly.py -v`
Expected: PASS for the 3 non-live tests; `test_kurly_live_smoke` is deselected by `addopts = -m 'not live'`.

- [ ] **Step 5: Commit**

```bash
git add src/nylb/collectors/kurly.py tests/collectors/test_kurly.py
git commit -m "feat: add Kurly competitor-price collector"
```

---

## Task 4: Wire into scan + config

**Files:**
- Modify: `src/nylb/core/scan.py:6,12-17,38-43`
- Modify: `config/lenses.yaml` (competitor lens)
- Test: `tests/core/test_scan.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_scan.py`:

```python
def test_run_scan_passes_competitor_products(tmp_path):
    seen = {}
    def fake_kurly(query, lens, *, settings, collected_at):
        seen["products"] = query.get("competitor_products")
        return CollectResult()
    store = LocalJsonStore(base_dir=tmp_path)
    lens_config = {"sources": ["kurly"],
                   "competitor_products": [{"brand": "포비", "url": "u1"}]}
    run_scan("competitor", store_id="nylb", lens_config=lens_config, settings={},
             store=store, run_id="rc", collected_at=NOW,
             collectors={"kurly": fake_kurly})
    assert seen["products"] == [{"brand": "포비", "url": "u1"}]


def test_default_collectors_include_kurly():
    from nylb.core.scan import DEFAULT_COLLECTORS
    assert "kurly" in DEFAULT_COLLECTORS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_scan.py -k "competitor or kurly" -v`
Expected: FAIL — `competitor_products` is `None`; `kurly` not in DEFAULT_COLLECTORS.

- [ ] **Step 3: Update `scan.py`**

In `src/nylb/core/scan.py` line 6, add `kurly` to the collectors import:

```python
from nylb.collectors import google_trends, instagram, kurly, naver, naver_datalab, youtube
```

Add to `DEFAULT_COLLECTORS` (after the `naver_datalab` entry):

```python
    "kurly": kurly.collect,
```

In the `query` dict, add `competitor_products`:

```python
    query = {
        "keywords": lens_config.get("keywords", []),
        "radar_watchlist": lens_config.get("radar_watchlist", []),
        "radar_seeds": lens_config.get("radar_seeds", []),
        "competitor_products": lens_config.get("competitor_products", []),
        "instagram_hashtags": lens_config.get("instagram_hashtags", []),
        "instagram_accounts": lens_config.get("instagram_accounts", []),
    }
```

- [ ] **Step 4: Update `config/lenses.yaml` competitor lens**

Replace the `competitor` lens block with:

```yaml
    competitor:
      keywords: []
      sources: [kurly]
      competitor_products:
        - {brand: "포비(FOURB)", url: "https://www.kurly.com/goods/5043336"}
        - {brand: "런던베이글뮤지엄", url: "https://www.kurly.com/goods/1000773557"}
      instagram_accounts: []
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_scan.py -v`
Expected: PASS (all scan tests).

- [ ] **Step 6: Commit**

```bash
git add src/nylb/core/scan.py config/lenses.yaml tests/core/test_scan.py
git commit -m "feat: wire kurly collector + competitor_products into scan"
```

---

## Task 5: Dashboard — competitors extraction + section

**Files:**
- Modify: `src/nylb/report/chart_data.py:55-62`
- Modify: `src/nylb/report/html.py` (build_dashboard data + template section)
- Test: `tests/report/test_chart_data.py`, `tests/report/test_html.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/report/test_chart_data.py`:

```python
def test_competitors_extracted():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="[포비베이글] 크림치즈", url="https://www.kurly.com/goods/5043336",
                  author="포비(FOURB)", metrics={"price": 8910, "base_price": 9900},
                  collected_at=NOW)]
    result = ScanResult(run_id="rc", store_id="nylb", lens="competitor",
                        query={}, items=items, started_at=NOW, finished_at=NOW)
    data = extract_chart_data(result)
    assert data["competitors"][0]["brand"] == "포비(FOURB)"
    assert data["competitors"][0]["price"] == 8910
    assert data["competitors"][0]["base_price"] == 9900
```

Append to `tests/report/test_html.py`:

```python
def test_competitor_section_renders_when_present():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="[포비베이글] 크림치즈", url="https://www.kurly.com/goods/5043336",
                  author="포비(FOURB)", metrics={"price": 8910, "base_price": 9900},
                  collected_at=NOW)]
    result = ScanResult(run_id="rc", store_id="nylb", lens="competitor",
                        query={"keywords": []}, items=items, started_at=NOW, finished_at=NOW)
    html = build_dashboard(result, SYN, extract_chart_data(result))
    assert "경쟁사 가격" in html
    assert "포비(FOURB)" in html


def test_no_competitor_section_when_absent():
    result = _result()                       # menu result, no kurly items
    html = build_dashboard(result, SYN, extract_chart_data(result))
    assert "경쟁사 가격" not in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/report/test_chart_data.py::test_competitors_extracted tests/report/test_html.py -k competitor -v`
Expected: FAIL — `KeyError: 'competitors'` / "경쟁사 가격" not in html.

- [ ] **Step 3a: Extract competitors in `chart_data.py`**

In `src/nylb/report/chart_data.py`, before the `return {`, add:

```python
    competitors = [
        {"brand": it.author, "product": it.title,
         "price": it.metrics.get("price"), "base_price": it.metrics.get("base_price"),
         "url": it.url}
        for it in result.items if it.source == "kurly"
    ]
```

and add `competitors` to the returned dict:

```python
    return {
        "counts": dict(counts),
        "trends": {s: trends[s] for s in _TREND_SOURCES},
        "matrix": matrix,
        "rising": rising,
        "competitors": competitors,
        "keywords": keywords,
        "radar_watchlist": list(result.query.get("radar_watchlist", [])),
    }
```

- [ ] **Step 3b: Pass competitors into the dashboard data**

In `src/nylb/report/html.py` `build_dashboard`, add `competitors` to the `data` dict (next to `radar_signals`/`interest_ranking`):

```python
        "competitors": chart.get("competitors", []),
```

- [ ] **Step 3c: Add the competitor section to the template**

In `src/nylb/report/html.py`, find the PRICING section that ends with:

```javascript
pc.appendChild(pt);pr.appendChild(pc);app.appendChild(pr);
```

Insert immediately after it:

```javascript

/* COMPETITORS — 경쟁사 가격 (크롤링) */
(function(){
  const comp=DATA.competitors||[];
  if(!comp.length) return;
  const sec=sect("🏷️","경쟁사 가격 (마켓컬리)","경쟁사 리테일 상품가 — 공개 상품페이지 크롤링(robots 허용·rate-limit·캐시 준수)");
  const card=h("div",{class:"card"});const tb=h("table");
  tb.appendChild(h("tr",null,[th("브랜드"),th("상품"),th("판매가"),th("정가")]));
  comp.forEach(c=>tb.appendChild(h("tr",null,[
    h("td",null,h("b",null,c.brand||"-")),
    h("td",null,c.product||"-"),
    h("td",null,h("b",{},c.price!=null?Math.round(c.price).toLocaleString()+"원":"-")),
    h("td",{style:"color:#9b8f80;text-decoration:line-through"},
      c.base_price!=null?Math.round(c.base_price).toLocaleString()+"원":"")])));
  card.appendChild(tb);
  card.appendChild(h("div",{class:"note"},"리테일 SKU 기준이라 매장 인스토어가와 다를 수 있음. 가격은 시점·프로모션에 따라 변동."));
  sec.appendChild(card);app.appendChild(sec);
})();
```

(`sect`, `h`, `th` are module-level helpers already defined and hoisted, so placement after PRICING is fine.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/report -v`
Expected: PASS (chart_data + html, including the two new competitor tests and the existing stale-hardcode test).

- [ ] **Step 5: Commit**

```bash
git add src/nylb/report/chart_data.py src/nylb/report/html.py tests/report/test_chart_data.py tests/report/test_html.py
git commit -m "feat: render competitor price section in dashboard"
```

---

## Task 6: Full-suite + live verification (controller)

**Files:** none (verification only). Run by the controller; the live step hits real kurly.

- [ ] **Step 1: Full suite (live excluded)**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS — all tests green; live smoke deselected by `addopts`.

- [ ] **Step 2: Live collector smoke**

Run: `.\.venv\Scripts\python.exe -m pytest tests/collectors/test_kurly.py -m live -v`
Expected: `test_kurly_live_smoke` PASSES — real kurly fetch parses a price > 0. (First run populates `data/cache/`.)

- [ ] **Step 3: Live competitor scan + dashboard**

Run: `.\.venv\Scripts\python.exe -m nylb scan --lens competitor --store nylb`
Expected: items include the configured competitors (포비 price≈8910, base≈9900); `errors=0`.

Author a minimal synthesis JSON at `data/raw/<run_id>.synthesis.json` (headline/executive_summary + empty list keys), then:

Run: `.\.venv\Scripts\python.exe -m nylb report-html --run <run_id>`
Open `reports/<run_id>.analysis.html` and confirm the "경쟁사 가격" section shows 포비/LBM prices. (Serve via `http.server` + Playwright; favicon 404 is the only acceptable console error.)

- [ ] **Step 4: Finish the branch**

Use `superpowers:finishing-a-development-branch` (merge `feat/competitor-crawler` → `main` + push).

---

## Self-Review (completed during planning)

- **Spec coverage:** schema kurly (§3) → Task 1; cache (§6) → Task 2; kurly collector `_fetch`/`_parse`/polite crawl (§3,§4) → Task 3; scan wiring + config (§3) → Task 4; chart_data competitors + html section (§3) → Task 5; acceptance (§9) → Task 6. All spec items mapped. ✓
- **Placeholder scan:** no TBD/"handle errors"; collector error path is explicit `try/except`→`CollectError`; the `__NEXT_DATA__` extraction is concrete (regex + recursive `_find_product` disambiguated by goods id). ✓
- **Type consistency:** `_parse(pages, lens, collected_at)` (Task 3) matches its test calls; `collect(query, lens, *, settings, collected_at)` matches the scan call site and `fake_kurly` (Task 4); Item shape (`metrics{price,base_price}`, `author=brand`) matches chart_data extraction keys (`brand/product/price/base_price/url`, Task 5) and the html template fields (`c.brand/c.product/c.price/c.base_price`); `get_cached(url, ttl_days, base_dir)` / `put_cache(url, text, base_dir)` (Task 2) match kurly `_fetch` calls (default base_dir) and the cache tests (explicit base_dir). ✓
```
