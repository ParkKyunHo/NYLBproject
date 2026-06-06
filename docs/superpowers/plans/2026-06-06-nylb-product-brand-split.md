# Product/Brand Split + Product Universe Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split each lens board's search-interest ranking into 📊 제품(products, product-anchored) and 🏪 브랜드(brands, rescaled to top-brand=100) so each is compared apples-to-apples, and expand the product keyword universe — no collector/anchor change.

**Architecture:** `build_board` post-processes the already-anchored DataLab values: brands (config category `brands`) are rescaled by `100/max(brand)` (the product anchor cancels in brand-vs-brand ratios, so no second query). Products fill `interest_ranking`/`radar`; brands fill new `brand_ranking`/`brand_signals`. `html.renderBoard` gains a 브랜드 관심도 section + 브랜드 신호 cards. Config adds product breadth.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest. No new deps. No LLM. No collector change.

**Setup:** venv `.\.venv\Scripts\python.exe -m pytest ...`; `pythonpath=["src"]`, `addopts=-m 'not live'`. Branch `feat/product-brand-split`.

**Spec:** `docs/superpowers/specs/2026-06-06-nylb-product-brand-split-design.md`

**Current `build_board` facts:** in `src/nylb/report/board.py`, `cats = chart.get("radar_categories", {}) or result.query.get("radar_categories", {})` (line 52); `_ctx(term, st)` adds `category` (line 54-57); `radar = [_ctx(t, st) for t, st in ranked if t not in core_set]` (line 60); `interest_ranking` is all `ranked` terms (line 113-116). `context.contextualize(term, stats, rank, total)` reads `stats.{latest,base_avg,momentum,recent_avg,peak}` → `value=round(latest,1)`, `vs_baseline=momentum/base_avg*100`, sign-based `direction`, caption.

**Current `html.py` facts:** the INTEREST RANKING IIFE (`/* INTEREST RANKING */`) renders `DATA.interest_ranking` (header "🍞 검색 관심도 랭킹"); the RADAR IIFE (`/* RADAR (verified only) */`) renders `DATA.radar` cards with category + news. All inside `renderBoard(DATA, app)`.

---

## File Structure
| File | Responsibility | New/Modify |
|---|---|---|
| `config/lenses.yaml` | expand menu + beverage product categories (brands kept) | Modify |
| `src/nylb/report/board.py` | split products/brands; rescale brands; new `brand_ranking`/`brand_signals` | Modify |
| `src/nylb/report/html.py` | 📊 제품 관심도 + 🏪 브랜드 관심도 sections + 🏪 브랜드 신호 cards | Modify |
| tests: `test_board_split.py` | unit tests | Create |

**Interfaces (keep identical):** board gains `brand_ranking: [{term, interest}]` and `brand_signals: [contextualized + category]`; `interest_ranking` and `radar` become products-only. `_BRAND_CAT = "brands"` is the single config coupling constant.

---

### Task 1: Expand product universe (`config/lenses.yaml`)

**Files:** Modify `config/lenses.yaml`; Test `tests/test_split_config.py`

- [ ] **Step 1: Failing test**
```python
# tests/test_split_config.py
from nylb.config import get_lens_config, load_lenses


def test_expanded_product_categories():
    L = load_lenses("config/lenses.yaml")
    b = get_lens_config(L, "nylb", "beverage")
    assert {"coffee", "tea", "blended", "trend", "brands"} <= set(b["radar"].keys())
    assert "카푸치노" in b["radar"]["coffee"] and "할리스" in b["radar"]["brands"]
    m = get_lens_config(L, "nylb", "menu")
    assert {"flavor", "pastry", "bread", "adjacent", "brands"} <= set(m["radar"].keys())
    assert "크루아상" in m["radar"]["pastry"] and "이성당" in m["radar"]["brands"]
```

- [ ] **Step 2: Run → FAIL** `.\.venv\Scripts\python.exe -m pytest tests/test_split_config.py -v`.

- [ ] **Step 3: Edit `config/lenses.yaml`** — replace the `menu` lens `radar:` map and the `beverage` lens `radar:` map with the expanded versions (keep each lens's `keywords`/`anchor`/`label`/`icon`/`sources`/`synonyms`/`discover_stopwords`/`radar_seeds` unchanged; only the `radar:` block changes). `menu` radar:
```yaml
      radar:
        flavor:   [말차, 흑임자, 피스타치오, 두바이초콜릿, 솔티드캐러멜, 비스코프, 얼그레이]
        pastry:   [크루아상, 뺑오쇼콜라, 까눌레, 마들렌, 스콘, 에그타르트, 마카롱, 도넛, 파운드케이크]
        bread:    [식빵, 바게트, 치아바타, 깜빠뉴, 브리오슈, 베이글샌드위치]
        adjacent: [탕후루, 약과, 요거트아이스크림, 크룽지, 버터떡, 두쫀쿠]
        brands:   [성심당, 런던베이글뮤지엄, 노티드, 아우어베이커리, 포비, 뚜레쥬르, 파리바게뜨, 이성당]
```
`beverage` radar (also rename the old `noncoffee` key to `tea`):
```yaml
      radar:
        coffee:  [에스프레소, 카푸치노, 플랫화이트, 아인슈페너, 카페모카, 카라멜마끼아또, 연유라떼, 디카페인, 에어로카노]
        tea:     [밀크티, 흑당밀크티, 자몽에이드, 레몬에이드, 청귤에이드, 얼그레이, 캐모마일, 유자차, 히비스커스]
        blended: [딸기스무디, 망고스무디, 요거트스무디, 프라푸치노, 빙수]
        trend:   [우베라떼, 흑임자라떼, 쑥라떼, 콤부차, 제로음료, 단백질음료]
        brands:  [스타벅스, 메가커피, 컴포즈커피, 빽다방, 투썸플레이스, 이디야, 더벤티, 폴바셋, 블루보틀, 할리스]
```

- [ ] **Step 4: Run → PASS** the config test; verify load: `.\.venv\Scripts\python.exe -c "from nylb.config import load_lenses,get_lens_config; c=get_lens_config(load_lenses('config/lenses.yaml'),'nylb','beverage'); print(list(c['radar'].keys()))"` prints the 5 keys; full suite green. (The `test_beverage_config.py` from earlier asserts `set(...keys()) == {coffee,noncoffee,blended,trend,brands}` — that will now FAIL because `noncoffee`→`tea`. Update that test's expected set to `{coffee, tea, blended, trend, brands}` and report.)

- [ ] **Step 5: Commit**
```bash
git add config/lenses.yaml tests/test_split_config.py tests/test_beverage_config.py
git commit -m "feat: expand product universe (menu pastry/bread, beverage coffee/tea)"
```

---

### Task 2: Split products/brands in `build_board` (`report/board.py`)

**Files:** Modify `src/nylb/report/board.py`; Test `tests/test_board_split.py`

- [ ] **Step 1: Failing test**
```python
# tests/test_board_split.py
from datetime import datetime, timezone
from nylb.core.schema import Item, ScanResult
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _dl(term, vals):
    return Item(source="naver_datalab", lens="beverage", type="search_term", title=term,
                collected_at=NOW, raw={"series": [{"date": f"2026-05-{i+1:02d}", "value": v}
                                                    for i, v in enumerate(vals)]})


def _result():
    items = [_dl("아메리카노", [90, 95, 100]),   # core (product)
             _dl("콜드브루", [70, 72, 78]),       # radar product
             _dl("메가커피", [700, 750, 800]),    # brand
             _dl("스타벅스", [380, 390, 400])]    # brand
    q = {"keywords": ["아메리카노"], "synonyms": {}, "anchor": "아메리카노",
         "radar_categories": {"콜드브루": "coffee", "메가커피": "brands", "스타벅스": "brands"}}
    return ScanResult(run_id="r", store_id="nylb", lens="beverage", query=q,
                      items=items, started_at=NOW, finished_at=NOW)


def test_products_and_brands_are_split_and_brands_rescaled():
    b = build_board(_result(), extract_chart_data(_result()))
    # interest_ranking + radar = products only (no brand names)
    assert "메가커피" not in {x["term"] for x in b["interest_ranking"]}
    assert "메가커피" not in {c["term"] for c in b["radar"]}
    assert "콜드브루" in {x["term"] for x in b["interest_ranking"]}
    # brand_ranking present, rescaled so top brand (메가커피, latest 800) == 100
    br = {x["term"]: x["interest"] for x in b["brand_ranking"]}
    assert abs(br["메가커피"] - 100) < 0.5
    assert abs(br["스타벅스"] - 50) < 0.5          # 400/800*100
    # brand_signals are contextualized cards (have caption/direction)
    bs = {c["term"]: c for c in b["brand_signals"]}
    assert "메가커피" in bs and bs["메가커피"]["caption"]
    assert abs(bs["메가커피"]["value"] - 100) < 0.5


def test_no_brands_yields_empty_brand_lists():
    items = [_dl("아메리카노", [100, 100, 100]), _dl("콜드브루", [50, 50, 50])]
    q = {"keywords": ["아메리카노"], "synonyms": {}, "anchor": "아메리카노",
         "radar_categories": {"콜드브루": "coffee"}}
    r = ScanResult(run_id="r", store_id="nylb", lens="beverage", query=q,
                   items=items, started_at=NOW, finished_at=NOW)
    b = build_board(r, extract_chart_data(r))
    assert b["brand_ranking"] == [] and b["brand_signals"] == []
```

- [ ] **Step 2: Run → FAIL** `.\.venv\Scripts\python.exe -m pytest tests/test_board_split.py -v`.

- [ ] **Step 3: Edit `src/nylb/report/board.py`**

3a. Add a module constant near the top (after the imports / `_PALETTE`):
```python
_BRAND_CAT = "brands"  # the single config↔engine coupling: the radar category treated as brands
```

3b. In `build_board`, REPLACE the `radar = [...]` line (current line 60) with the product/brand split. Insert after the `_ctx` def (after line 57):
```python
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
        cm["category"] = _BRAND_CAT
        return cm

    brand_signals = [_brand_ctx(t, st) for t, st in brand_terms]
    brand_signals.sort(key=lambda c: c["value"], reverse=True)
    for i, c in enumerate(brand_signals, 1):
        c["rank"] = i
    brand_ranking = [{"term": t, "interest": round(st.get("latest", 0.0) * _bf, 1)}
                     for t, st in brand_terms]
    brand_ranking.sort(key=lambda x: x["interest"], reverse=True)
```

3c. Change `interest_ranking` (current line 113-116) to PRODUCTS ONLY, and add the two new keys to the returned dict:
```python
        "interest_ranking": [
            {"term": t, "interest": round(st.get("latest", 0.0), 1), "core": t in core_set}
            for t, st in ranked if not _is_brand(t)
        ],
```
And add (anywhere in the dict literal, e.g. after `radar`):
```python
        "brand_ranking": brand_ranking,
        "brand_signals": brand_signals,
```

(Note: `vs_baseline = momentum/base_avg` is scale-invariant, so scaling the brand series by `_bf` preserves direction/vs_baseline/recent_drop and only rescales the displayed `value`/`momentum` into the top-brand=100 frame. The `movers`/headline computation at line 70 still uses `core_signals + radar` (products) — leave it; brands are not "biggest mover" candidates.)

- [ ] **Step 4: Run → PASS** `.\.venv\Scripts\python.exe -m pytest tests/test_board_split.py -v` + full suite. (Existing board tests assert `interest_ranking`/`radar` contents — if any asserted a brand term was present, update it; the test fixtures mostly use core/non-brand terms so should pass. Report any updated test.)

- [ ] **Step 5: Commit**
```bash
git add src/nylb/report/board.py tests/test_board_split.py
git commit -m "feat: split products vs brands in board (brands rescaled to top=100)"
```

---

### Task 3: Render two sections + brand cards (`report/html.py`)

**Files:** Modify `src/nylb/report/html.py`; Test add to `tests/test_board_split.py`

- [ ] **Step 1: Failing test (append)**
```python
def test_dashboard_renders_product_and_brand_sections():
    from nylb.report.html import build_dashboard
    html = build_dashboard(_result(), extract_chart_data(_result()))
    assert "제품 관심도" in html and "브랜드 관심도" in html
    assert "브랜드 신호" in html
    assert '"brand_ranking"' in html and '"brand_signals"' in html
```

- [ ] **Step 2: Run → FAIL** `.\.venv\Scripts\python.exe -m pytest tests/test_board_split.py::test_dashboard_renders_product_and_brand_sections -v`.

- [ ] **Step 3: Edit the `<script>` inside `_TEMPLATE`** (all inside `renderBoard`).

3a. In the INTEREST RANKING IIFE (`/* INTEREST RANKING */`), change the `sect(...)` header line from `sect("🍞","검색 관심도 랭킹","사람들이 지금 어떤 베이커리·디저트를 검색하나 (0~100)")` to:
```javascript
  const sec=sect("📊","제품 관심도","제품 검색 관심도 (제품 앵커=100 기준). 브랜드는 아래 별도 섹션.");
```

3b. IMMEDIATELY AFTER the INTEREST RANKING IIFE's closing `})();`, insert a BRAND RANKING IIFE:
```javascript
/* BRAND RANKING */
(function(){const br=DATA.brand_ranking||[]; if(!br.length)return;
  const sec=sect("🏪","브랜드 관심도","경쟁 브랜드 검색 관심도 (1등 브랜드=100 기준 — 브랜드끼리만 비교)");
  const card=h("div",{class:"card"});
  const maxv=Math.max.apply(null, br.map(x=>x.interest).concat([1]));
  br.forEach(x=>{const row=h("div",{style:"display:grid;grid-template-columns:130px 1fr 40px;align-items:center;gap:10px;margin:7px 0"});
    row.appendChild(h("div",{style:"font-weight:700;font-size:13px"}, x.term));
    const bar=h("div",{class:"bar",style:"height:15px;background:#f0e7da"});
    bar.appendChild(h("i",{style:"width:"+(x.interest/maxv*100)+"%;background:var(--steady)"}));
    row.appendChild(bar);
    row.appendChild(h("div",{style:"font-weight:800;font-size:13px;text-align:right"},String(Math.round(x.interest))));
    card.appendChild(row);});
  card.appendChild(h("div",{class:"note"},"※ 브랜드(고유명사)는 제품(일반명사)과 검색 척도가 달라 분리. 1등 브랜드 대비 상대값."));
  sec.appendChild(card); app.appendChild(sec);})();
```

3c. IMMEDIATELY AFTER the RADAR IIFE's closing `})();` (`/* RADAR (verified only) */`), insert a BRAND SIGNALS IIFE (same card style as radar, reads `brand_signals`, includes news):
```javascript
/* BRAND SIGNALS */
(function(){const bs=DATA.brand_signals||[]; if(!bs.length)return;
  const sec=sect("🏪","브랜드 신호","브랜드별 검색 모멘텀 (1등=100 기준) · 뉴스");
  const g=h("div",{class:"grid verdicts"});
  bs.forEach(c=>{const card=h("div",{class:"vc"});card.style.borderTopColor=DCOL[c.direction];
    card.appendChild(h("h3",null,[document.createTextNode(c.term),
      h("span",{class:"mom "+c.direction},ARROW[c.direction]+" "+(c.momentum>=0?"+":"")+c.momentum)]));
    card.appendChild(h("div",{class:"stage"},"브랜드 · "+(c.rank||"-")+"위"));
    card.appendChild(h("p",null,c.caption));
    const nx=(DATA.news_context||{})[c.term]||[];
    if(nx.length){const nd=h("div",{style:"margin-top:7px;font-size:11.5px"});
      nd.appendChild(h("div",{style:"color:var(--muted);font-weight:700"},"📰 관련 뉴스"));
      nx.slice(0,3).forEach(nw=>{const a=h("a",{href:nw.link,target:"_blank",rel:"noopener noreferrer",
        style:"display:block;color:var(--bagel);text-decoration:none;margin-top:2px"},
        "· "+nw.title); nd.appendChild(a);});
      card.appendChild(nd);}
    g.appendChild(card);});
  sec.appendChild(g); app.appendChild(sec);})();
```

(The RADAR IIFE itself needs NO change — it reads `DATA.radar`, which is now products-only from Task 2.)

- [ ] **Step 4: Run → PASS** the render test + full suite. (The `test_board_universe.py` render test asserts the discovery/news sections still render — unaffected. If a test asserted the old "검색 관심도 랭킹" header string, update it to "제품 관심도" and report.)

- [ ] **Step 5: Commit**
```bash
git add src/nylb/report/html.py tests/test_board_split.py
git commit -m "feat: render 제품 관심도 + 브랜드 관심도 sections + 브랜드 신호 cards"
```

---

### Task 4: Live verification

**Files:** none (manual). Requires `.env` keys + Playwright.

- [ ] **Step 1: Build the two-lens board** (script): `build_lenses_dashboard(["menu","beverage"], settings=load_settings())` → write to `reports/split-verify.html`. Both lenses now have expanded products (more DataLab calls — slower).
- [ ] **Step 2: Playwright verify** (serve over http): confirm
  - Each tab's board has **📊 제품 관심도** (products only — no brand names) AND **🏪 브랜드 관심도** (메가커피=100, 스타벅스, … for beverage; 성심당-led for menu) AND **🏪 브랜드 신호** cards.
  - Products no longer dominated by brands (the product ranking shows 아메리카노/콜드브루/라떼…, not 메가커피).
  - 0 JS console errors (favicon-404 ok).
- [ ] **Step 3: Final full suite + commit fixes**
```bash
.\.venv\Scripts\python.exe -m pytest -q   # green
git add -A && git commit -m "test: live-verify product/brand split renders in both lenses"
```

---

## Self-Review

**1. Spec coverage:** P1 product expansion → Task 1. P2 board split + brand rescale → Task 2. P3 two sections + brand cards → Task 3. Live → Task 4. Brand rescale = `100/max(brand)` (no extra query), products keep product-anchor values. ✓

**2. Placeholder scan:** No TBD. Config keyword lists explicit (research-confirmed in spec). Every code step complete. ✓

**3. Type consistency:** `_BRAND_CAT="brands"` (Task 2) matches config category (Task 1). `brand_ranking: [{term, interest}]` + `brand_signals: [contextualized + rank + category]` defined Task 2, rendered Task 3 (`DATA.brand_ranking`/`DATA.brand_signals`). `interest_ranking`/`radar` products-only (Task 2) consumed by existing/relabeled IIFEs (Task 3). Brand-rescale preserves `direction`/`vs_baseline` (scale-invariant), rescales `value`/`momentum`. ✓

## Execution Handoff
1. **Subagent-Driven (recommended)** — fresh subagent per task + two-stage review.
2. **Inline Execution** — batch with checkpoints.
