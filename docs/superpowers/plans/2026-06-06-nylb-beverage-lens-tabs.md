# Beverage Lens + Lens-Tabs Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a beverage analysis domain (config-only lens, own anchor 아메리카노) and a multi-lens **tabbed** board so 메뉴/음료 (and later 경쟁사) live on one page — all deterministic, industry-agnostic (lens labels/icons/list config-driven).

**Architecture:** `beverage` is a new config lens (the industry-agnostic engine renders it with zero new data code). The new code is the renderer: extract the board-render JS into `renderBoard(board, app)`, add a tab bar driven by a `LENSES=[{key,label,icon,board}]` array, add `build_multi_dashboard(lenses)`. A `report/multi.py` orchestrator scans/builds each lens's board and assembles the tabbed HTML; `nylb dashboard --lenses menu,beverage` drives it.

**Tech Stack:** Python 3.11+, Pydantic v2, stdlib, pytest. No new deps. No LLM.

**Setup note:** venv `.\.venv\Scripts\python.exe -m pytest ...`; `pythonpath=["src"]`, `addopts=-m 'not live'`. Branch `feat/beverage-tabs`.

**Spec:** `docs/superpowers/specs/2026-06-06-nylb-beverage-lens-tabs-design.md`

**Key file facts (current `report/html.py`):** `<script>` at line 107; `const DATA = __DATA__;` line 108; helpers `h/esc/sect` lines 109-116; render body starts at line 117 (`const app=document.getElementById("app");`) and runs through the FOOTER (just before `</script>`); `build_dashboard(result, chart, news_context=None)` at line 301. `tests/report/test_html.py` extracts the board via `html.split("const DATA = ", 1)[1].split(";\n", 1)[0]` at 3 sites (lines 83, 94, 100) plus `assert "const DATA" in html` (line 24).

---

## File Structure
| File | Responsibility | New/Modify |
|---|---|---|
| `config/lenses.yaml` | `beverage` lens (+ `label`/`icon` on menu+beverage) | Modify |
| `src/nylb/report/html.py` | `renderBoard()` extraction, tab bar, `build_multi_dashboard`, `.tabs` CSS | Modify |
| `tests/report/test_html.py` | update board-extraction for `LENSES[0].board` | Modify |
| `src/nylb/report/multi.py` | `build_lenses_dashboard(lens_keys, ...)` orchestration | Create |
| `src/nylb/cli.py`, `src/nylb/report/server.py` | `nylb dashboard --lenses` multi-lens | Modify |
| tests: `test_multi_dashboard.py`, `test_report_multi.py` | unit tests | Create |

**Interfaces (keep identical):**
- `html.build_multi_dashboard(lenses: list[dict]) -> str` ; each lens `{key, label, icon, board}`. JS global `LENSES`.
- `html.build_dashboard(result, chart, news_context=None) -> str` (single — delegates to build_multi).
- `multi.build_lenses_dashboard(lens_keys: list[str], *, lenses_file="config/lenses.yaml", store_id="nylb", settings, collectors=None) -> str`

---

### Task 1: Beverage lens config (+ lens label/icon)

**Files:** Modify `config/lenses.yaml`; Test `tests/test_beverage_config.py`

- [ ] **Step 1: Failing test**
```python
# tests/test_beverage_config.py
from nylb.config import get_lens_config, load_lenses


def test_beverage_lens_loads_with_anchor_and_categories():
    lenses = load_lenses("config/lenses.yaml")
    c = get_lens_config(lenses, "nylb", "beverage")
    assert c["anchor"] == "아메리카노"
    assert set(c["radar"].keys()) == {"coffee", "noncoffee", "blended", "trend", "brands"}
    assert "스타벅스" in c["radar"]["brands"]


def test_menu_and_beverage_have_label_icon():
    lenses = load_lenses("config/lenses.yaml")
    m = get_lens_config(lenses, "nylb", "menu")
    b = get_lens_config(lenses, "nylb", "beverage")
    assert m["label"] == "메뉴" and m["icon"] == "🥯"
    assert b["label"] == "음료" and b["icon"] == "🥤"
```

- [ ] **Step 2: Run → FAIL** `.\.venv\Scripts\python.exe -m pytest tests/test_beverage_config.py -v` (no beverage lens).

- [ ] **Step 3: Edit `config/lenses.yaml`** — add `label`/`icon` to the existing `menu` lens (right after its `keywords:` line add `label: 메뉴` and `icon: "🥯"`), and add a new `beverage` lens as a sibling of `menu` (same indentation, inside `lenses:`):
```yaml
    beverage:
      label: 음료
      icon: "🥤"
      keywords: [아메리카노, 카페라떼, 바닐라라떼, 콜드브루, 말차라떼]
      anchor: 아메리카노
      radar:
        coffee:    [아인슈페너, 플랫화이트, 디카페인, 카푸치노, 에어로카노]
        noncoffee: [밀크티, 흑당밀크티, 자몽에이드, 레몬에이드, 청귤에이드, 얼그레이]
        blended:   [딸기스무디, 망고스무디, 요거트스무디, 프라푸치노]
        trend:     [우베라떼, 흑임자라떼, 쑥라떼, 콤부차, 제로음료]
        brands:    [스타벅스, 메가커피, 컴포즈커피, 빽다방, 투썸플레이스, 이디야, 더벤티]
      radar_seeds: [커피, 음료, 카페]
      sources: [youtube, naver, google_trends, naver_datalab]
      synonyms:
        아메리카노: [아아, americano]
        카페라떼: [라떼, latte]
      discover_stopwords: [맛집, 카페, 후기, 추천, 먹방, 신상, 레시피, 만드는]
```
(Add `label: 메뉴` and `icon: "🥯"` to the `menu` lens too. Leave `content`/`competitor` unchanged. `get_lens_config` returns the lens dict as-is, so `label`/`icon` flow through.)

- [ ] **Step 4: Run → PASS** both config tests; then full suite green.

- [ ] **Step 5: Commit**
```bash
git add config/lenses.yaml tests/test_beverage_config.py
git commit -m "feat: beverage lens (anchor 아메리카노, researched categories) + lens label/icon"
```

---

### Task 2: Multi-lens tabbed renderer (`report/html.py`)

**Files:** Modify `src/nylb/report/html.py`, `tests/report/test_html.py`; Test `tests/test_multi_dashboard.py`

- [ ] **Step 1: Failing test**
```python
# tests/test_multi_dashboard.py
from datetime import datetime, timezone
from nylb.core.schema import Item, ScanResult
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data
from nylb.report.html import build_multi_dashboard, build_dashboard

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _board(term):
    it = Item(source="naver_datalab", lens="menu", type="search_term", title=term,
              collected_at=NOW, raw={"series": [{"date": "2026-05-01", "value": 80.0},
                                                  {"date": "2026-05-02", "value": 85.0}]})
    r = ScanResult(run_id="r", store_id="nylb", lens="menu", query={"keywords": [term]},
                   items=[it], started_at=NOW, finished_at=NOW)
    return build_board(r, extract_chart_data(r))


def test_multi_dashboard_has_tabs_and_both_boards():
    lenses = [{"key": "menu", "label": "메뉴", "icon": "🥯", "board": _board("베이글")},
              {"key": "beverage", "label": "음료", "icon": "🥤", "board": _board("아메리카노")}]
    html = build_multi_dashboard(lenses)
    assert "const LENSES" in html
    assert "메뉴" in html and "음료" in html          # tab labels
    assert "renderBoard" in html                       # render fn present
    assert "베이글" in html and "아메리카노" in html    # both boards embedded


def test_single_build_dashboard_backward_compatible():
    it = Item(source="naver_datalab", lens="menu", type="search_term", title="베이글",
              collected_at=NOW, raw={"series": [{"date": "2026-05-01", "value": 80.0}]})
    r = ScanResult(run_id="r", store_id="nylb", lens="menu", query={"keywords": ["베이글"]},
                   items=[it], started_at=NOW, finished_at=NOW)
    html = build_dashboard(r, extract_chart_data(r))
    assert "const LENSES" in html and "베이글" in html
```

- [ ] **Step 2: Run → FAIL** (`build_multi_dashboard` undefined).

- [ ] **Step 3a: Refactor the `<script>` in `_TEMPLATE`** (lines 108-end of script):
  - Change line 108 `const DATA = __DATA__;` → `const LENSES = __DATA__;`
  - Delete line 117 `const app=document.getElementById("app");`
  - Insert a function header `function renderBoard(DATA, app){` immediately AFTER the `sect(...)` helper (after line 116) and BEFORE line 118 (`const M=DATA.meta...`).
  - Insert the closing `}` for `renderBoard` immediately AFTER the FOOTER block (after `app.appendChild(ft);`, before `</script>`).
  - (Everything from `const M=DATA.meta` through the footer — including the nested `kpi`/`buildChart` functions and all IIFEs — is now the body of `renderBoard(DATA, app)`, with `DATA` = one board and `app` = the container. No other edits to those blocks.)
  - After the `renderBoard` closing `}`, add the tab-bar entry:
```javascript
const _root=document.getElementById("app");
let _active=0;
function _renderTabs(){
  _root.innerHTML="";
  if(LENSES.length>1){
    const tabs=h("div",{class:"tabs"});
    LENSES.forEach((L,i)=>{const b=h("button",{class:"tab"+(i===_active?" on":"")},(L.icon||"")+" "+L.label);
      b.onclick=()=>{_active=i;_renderTabs();}; tabs.appendChild(b);});
    _root.appendChild(tabs);
  }
  const board=h("div"); _root.appendChild(board);
  renderBoard(LENSES[_active].board, board);
}
_renderTabs();
```

- [ ] **Step 3b: Add tab CSS** to the `<style>` block (insert near the other component rules):
```css
  .tabs{display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap}
  .tab{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:9px 18px;
    font-size:14px;font-weight:700;color:var(--muted);cursor:pointer;font-family:inherit}
  .tab.on{background:var(--accent);color:#fff;border-color:var(--accent)}
```

- [ ] **Step 3c: Replace `build_dashboard` (line 301) + add `build_multi_dashboard`:**
```python
def build_multi_dashboard(lenses: list[dict]) -> str:
    """Render multiple lens boards into one tabbed HTML. Each lens = {key,label,icon,board}."""
    return _TEMPLATE.replace("__DATA__", json.dumps(lenses, ensure_ascii=False))


def build_dashboard(result: ScanResult, chart: dict, news_context=None) -> str:
    """Single-lens convenience — wraps one board as a 1-tab dashboard (tab bar hidden)."""
    board = build_board(result, chart, news_context=news_context)
    label = result.lens
    return build_multi_dashboard([{"key": result.lens, "label": label, "icon": "🍽", "board": board}])
```

- [ ] **Step 3d: Update `tests/report/test_html.py`** — the board is now at `LENSES[0].board`. Replace the 3 extraction sites and the assertion:
  - Line 24 `assert "const DATA" in html` → `assert "const LENSES" in html`
  - Lines 83/94/100 pattern `json.loads(html.split("const DATA = ", 1)[1].split(";\n", 1)[0])` → extract `[0]["board"]`. Simplest: change `_embedded_data` (line 99-100) to:
```python
def _embedded_data(html):
    lenses = json.loads(html.split("const LENSES = ", 1)[1].split(";\n", 1)[0])
    return lenses[0]["board"]
```
  and change lines 83 & 94 to use `_embedded_data(html)["chart"]["series"]` and `_embedded_data(html)` respectively (route both through the helper).

- [ ] **Step 4: Run → PASS** `tests/test_multi_dashboard.py` + `tests/report/test_html.py` + full suite. (If any other test parsed `const DATA`, update it the same way and report.)

- [ ] **Step 5: Commit**
```bash
git add src/nylb/report/html.py tests/report/test_html.py tests/test_multi_dashboard.py
git commit -m "feat: multi-lens tabbed renderer (renderBoard + tab bar + build_multi_dashboard)"
```

---

### Task 3: Orchestration (`report/multi.py`)

**Files:** Create `src/nylb/report/multi.py`; Test `tests/test_report_multi.py`

- [ ] **Step 1: Failing test**
```python
# tests/test_report_multi.py
from nylb.report.multi import build_lenses_dashboard


def test_build_lenses_dashboard_two_lenses(monkeypatch):
    html = build_lenses_dashboard(["menu", "beverage"], settings={}, collectors={})
    # collectors={} → empty scans, but each lens still builds a board + tab
    assert "const LENSES" in html
    assert "메뉴" in html and "음료" in html        # labels from config
    assert "🥯" in html and "🥤" in html           # icons from config
```

- [ ] **Step 2: Run → FAIL** (module missing).

- [ ] **Step 3: Implement `src/nylb/report/multi.py`:**
```python
from __future__ import annotations

from datetime import datetime, timezone

from nylb.config import get_lens_config, load_lenses
from nylb.core.scan import run_scan
from nylb.core.store import LocalJsonStore
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data
from nylb.report.html import build_multi_dashboard
from nylb.report.news import gather_riser_news


def build_lenses_dashboard(lens_keys: list[str], *, lenses_file: str = "config/lenses.yaml",
                           store_id: str = "nylb", settings: dict, collectors=None) -> str:
    """Scan each lens, build its board (+ riser news), assemble a tabbed dashboard.
    Lens label/icon come from config (industry-agnostic)."""
    from nylb.cli import build_run_id
    lenses_cfg = load_lenses(lenses_file)
    now = datetime.now(timezone.utc)
    out: list[dict] = []
    for key in lens_keys:
        lc = get_lens_config(lenses_cfg, store_id, key)
        result = run_scan(key, store_id=store_id, lens_config=lc, settings=settings,
                          store=LocalJsonStore(), run_id=build_run_id(key, now),
                          collected_at=now, collectors=collectors)
        chart = extract_chart_data(result)
        news = gather_riser_news(result, chart, settings)
        out.append({"key": key, "label": lc.get("label", key), "icon": lc.get("icon", "🍽"),
                    "board": build_board(result, chart, news_context=news)})
    return build_multi_dashboard(out)
```

- [ ] **Step 4: Run → PASS** the test + full suite. (`collectors={}` makes `run_scan` add "unknown source" errors but still build a board with 0 items — fine for the orchestration test.)

- [ ] **Step 5: Commit**
```bash
git add src/nylb/report/multi.py tests/test_report_multi.py
git commit -m "feat: report/multi build_lenses_dashboard (scan+board per lens -> tabs)"
```

---

### Task 4: CLI/server wiring (`nylb dashboard --lenses`)

**Files:** Modify `src/nylb/cli.py`, `src/nylb/report/server.py`; Test `tests/test_cli_dashboard_lenses.py`

- [ ] **Step 1: Failing test**
```python
# tests/test_cli_dashboard_lenses.py
from nylb.cli import _build_parser


def test_dashboard_lenses_flag_parses():
    ns = _build_parser().parse_args(["dashboard", "--lenses", "menu,beverage", "--port", "0"])
    assert ns.cmd == "dashboard" and ns.lenses == "menu,beverage"
```

- [ ] **Step 2: Run → FAIL** (`--lenses` not defined).

- [ ] **Step 3a: `cli.py` `_build_parser`** — on the `dashboard` subparser, add:
```python
    dash_p.add_argument("--lenses", default="menu,beverage",
                        help="comma-separated lenses to show as tabs")
```

- [ ] **Step 3b: `cli.py` `_dashboard`** — pass the lens list to the server:
```python
def _dashboard(args) -> int:
    from nylb.report.server import make_server
    lens_keys = [s.strip() for s in args.lenses.split(",") if s.strip()]
    server = make_server(port=args.port, lens_keys=lens_keys, lenses_file=args.lenses_file)
    host, port = server.server_address
    print(f"dashboard http://127.0.0.1:{port}  ('스캔 실행' 버튼으로 수집 · 탭: {', '.join(lens_keys)})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0
```

- [ ] **Step 3c: `server.py` `make_server` + `run_scan_and_render`** — accept `lens_keys` and render multi-lens. Change `make_server` signature to add `lens_keys=None`, and its default render to call a multi-lens render. Replace `run_scan_and_render` to delegate when multiple lenses:
```python
def run_lenses_and_render(lens_keys: list[str], *, lenses_file: str = "config/lenses.yaml",
                          store_id: str = "nylb", collectors=None) -> str:
    from nylb.config import load_settings
    from nylb.report.multi import build_lenses_dashboard
    return build_lenses_dashboard(lens_keys, lenses_file=lenses_file, store_id=store_id,
                                  settings=load_settings(), collectors=collectors)
```
and in `make_server`, change the default render to:
```python
def make_server(host: str = "127.0.0.1", port: int = 8765, *,
                lens: str = "menu", lens_keys=None, lenses_file: str = "config/lenses.yaml",
                render_fn=None, **_) -> ThreadingHTTPServer:
    keys = lens_keys or [lens]
    render = render_fn or (lambda: run_lenses_and_render(keys, lenses_file=lenses_file))
    ...
```
(Keep the existing single-lens `run_scan_and_render` for any caller still using it; the `render_fn`-injected server tests are unaffected. The button still POSTs `/run` → `render()` → tabbed HTML.)

- [ ] **Step 4: Run → PASS** the new test + full suite (existing `tests/test_server.py` inject `render_fn`, so they bypass the new path — confirm green).

- [ ] **Step 5: Commit**
```bash
git add src/nylb/cli.py src/nylb/report/server.py tests/test_cli_dashboard_lenses.py
git commit -m "feat: nylb dashboard --lenses (multi-lens tabbed board server)"
```

---

### Task 5: Live verification

**Files:** none (manual). Requires `.env` keys + Playwright.

- [ ] **Step 1: Run the multi-lens dashboard once** (or render via a short script): start `.\.venv\Scripts\python.exe -m nylb dashboard --lenses menu,beverage --port 8780`, open `http://127.0.0.1:8780/`, click **스캔 실행** (runs BOTH lenses; may take a couple minutes). Alternatively script `build_lenses_dashboard(["menu","beverage"], settings=load_settings())` to a file and serve it.
- [ ] **Step 2: Playwright verify** (serve the HTML over http; file:// is blocked): confirm
  - Two tabs render: 🥯 메뉴 / 🥤 음료.
  - Clicking 음료 switches to the beverage board (아메리카노-anchored ranking; coffee/noncoffee/blended/trend/brands categories; 발굴 후보; news).
  - Clicking 메뉴 switches back.
  - 0 JS console errors (favicon-404 ok).
- [ ] **Step 3: Final full suite + commit any fixes**
```bash
.\.venv\Scripts\python.exe -m pytest -q   # expect green
git add -A && git commit -m "test: live-verify beverage tab + menu tab switching"
```

---

## Self-Review

**1. Spec coverage:** C1 beverage lens + label/icon → Task 1. C2 renderBoard + tab bar + build_multi_dashboard → Task 2 (+ test_html update). C3 orchestration → Task 3. C4 dashboard --lenses → Task 4. Live tab switching → Task 5. Industry-agnostic (label/icon/lens-list config-driven) → Tasks 1,3,4. No-LLM preserved (same board). ✓

**2. Placeholder scan:** No TBD. Beverage keyword lists are explicit (research-confirmed in spec); every code step has complete code. ✓

**3. Type consistency:** `LENSES=[{key,label,icon,board}]` defined Task 2, produced by `build_multi_dashboard` (Task 2) and `build_lenses_dashboard` (Task 3), consumed by the JS tab bar (Task 2). `build_dashboard` single delegates to `build_multi_dashboard` (Task 2). `make_server(lens_keys=...)` defined Task 4, called by `_dashboard` (Task 4). `_embedded_data` updated to `LENSES[0].board` (Task 2). ✓

## Execution Handoff
1. **Subagent-Driven (recommended)** — fresh subagent per task + two-stage review.
2. **Inline Execution** — batch with checkpoints.
