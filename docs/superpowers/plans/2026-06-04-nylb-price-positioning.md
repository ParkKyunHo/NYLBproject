# NYLB ↔ 경쟁사 가격 포지셔닝 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 경쟁사 크롤 가격을 NYLB 매장가와 나란히 비교해 차이(%)·포지셔닝·가격조정 액션을 대시보드 📊 가격 포지셔닝 섹션으로 보여준다.

**Architecture:** 새 collector 없음. owner가 `config/lenses.yaml`에 `own_products`(NYLB 매장가)와 경쟁사 `match_key`/`basis`를 입력 → `run_scan`이 `own_products`를 query로 전달 → `chart_data`가 `match_key`로 결합해 `comparisons` 행 생성 → `html.py`가 조건부 섹션 렌더. 해석/액션(`price_positioning`)은 synthesis에 Claude가 수동 작성.

**Tech Stack:** Python 3.12 (`.\.venv\Scripts\python.exe`), Pydantic v2, pytest, Jinja-free f-string 템플릿(`html.py`), YAML config. git/python은 PowerShell 도구로.

---

## File Structure

- `src/nylb/core/scan.py` — `run_scan` query dict에 `own_products` 한 줄 추가.
- `src/nylb/report/chart_data.py` — `extract_chart_data`에 `comparisons` 매칭/계산 로직 추가.
- `src/nylb/report/html.py` — 📊 가격 포지셔닝 IIFE 섹션 + `build_dashboard` data dict에 `comparisons`.
- `config/lenses.yaml` — competitor 렌즈에 `own_products` + `competitor_products`의 `match_key`/`basis`.
- `.claude/commands/trend-scan.md` — synthesis 스키마 설명에 `price_positioning(선택)`.
- 테스트: `tests/core/test_scan.py`, `tests/report/test_chart_data.py`, `tests/report/test_html.py`.

**테스트 규약(이 레포):** html.py 테스트는 렌더 문자열이 아니라 임베드된 `const DATA`(JSON)로 검증한다(섹션 제목은 템플릿에 항상 존재하므로 무의미). `tests/report/test_html.py`에 이미 헬퍼 `_embedded_data(html)`가 있다.

---

## Task 1: scan이 own_products를 query로 전달

**Files:**
- Modify: `src/nylb/core/scan.py:40-47` (query dict)
- Test: `tests/core/test_scan.py`

- [ ] **Step 1: Write the failing test**

`tests/core/test_scan.py` 끝에 추가:

```python
def test_run_scan_passes_own_products(tmp_path):
    seen = {}
    def fake_kurly(query, lens, *, settings, collected_at):
        seen["own"] = query.get("own_products")
        return CollectResult()
    store = LocalJsonStore(base_dir=tmp_path)
    lens_config = {"sources": ["kurly"],
                   "own_products": [{"product": "베이글", "category": "베이글",
                                     "price": 3500, "match_key": "베이글"}]}
    run_scan("competitor", store_id="nylb", lens_config=lens_config, settings={},
             store=store, run_id="ro", collected_at=NOW,
             collectors={"kurly": fake_kurly})
    assert seen["own"] == [{"product": "베이글", "category": "베이글",
                            "price": 3500, "match_key": "베이글"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_scan.py::test_run_scan_passes_own_products -v`
Expected: FAIL — `seen["own"]` is `None` (key not in query).

- [ ] **Step 3: Write minimal implementation**

`src/nylb/core/scan.py`의 query dict에 한 줄 추가(`competitor_products` 다음):

```python
    query = {
        "keywords": lens_config.get("keywords", []),
        "radar_watchlist": lens_config.get("radar_watchlist", []),
        "radar_seeds": lens_config.get("radar_seeds", []),
        "competitor_products": lens_config.get("competitor_products", []),
        "own_products": lens_config.get("own_products", []),
        "instagram_hashtags": lens_config.get("instagram_hashtags", []),
        "instagram_accounts": lens_config.get("instagram_accounts", []),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_scan.py -v`
Expected: PASS (all scan tests green).

- [ ] **Step 5: Commit**

```powershell
git add src/nylb/core/scan.py tests/core/test_scan.py
git commit -m "feat: pass own_products through scan query"
```

---

## Task 2: chart_data가 comparisons 행을 생성

**Files:**
- Modify: `src/nylb/report/chart_data.py` (`extract_chart_data`, return 직전 + return dict)
- Test: `tests/report/test_chart_data.py`

매칭 규칙: competitor config에서 `url → cfg` 맵 → kurly item을 url로 조회해 `match_key`/`basis` 획득 → 같은 `match_key`의 own_product와 1:N 결합. 양쪽 다 있고 `competitor_price`가 truthy(0/None 아님)일 때만 행 생성. `position`: nylb>comp→above, nylb<comp→below, ==→equal.

- [ ] **Step 1: Write the failing tests**

`tests/report/test_chart_data.py` 끝에 추가:

```python
def _competitor_result(own_products, competitor_products, items):
    return ScanResult(run_id="rc", store_id="nylb", lens="competitor",
                      query={"own_products": own_products,
                             "competitor_products": competitor_products},
                      items=items, started_at=NOW, finished_at=NOW)


def test_comparison_row_built_on_match_key():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="[포비베이글] 크림치즈", url="https://www.kurly.com/goods/5043336",
                  author="포비(FOURB)", metrics={"price": 8910, "base_price": 9900},
                  collected_at=NOW)]
    data = extract_chart_data(_competitor_result(
        own_products=[{"product": "플레인 크림치즈 베이글", "category": "크림치즈",
                       "price": 4500, "match_key": "크림치즈"}],
        competitor_products=[{"brand": "포비(FOURB)",
                              "url": "https://www.kurly.com/goods/5043336",
                              "match_key": "크림치즈", "basis": "리테일 200g"}],
        items=items))
    rows = data["comparisons"]
    assert len(rows) == 1
    r = rows[0]
    assert r["category"] == "크림치즈"
    assert r["nylb_product"] == "플레인 크림치즈 베이글"
    assert r["nylb_price"] == 4500
    assert r["competitor_brand"] == "포비(FOURB)"
    assert r["competitor_price"] == 8910
    assert r["competitor_basis"] == "리테일 200g"
    assert r["diff"] == 4500 - 8910
    assert r["diff_pct"] == -49.5
    assert r["position"] == "below"


def test_no_comparison_when_match_key_absent():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="LBM 세트", url="https://www.kurly.com/goods/1000773557",
                  author="런던베이글뮤지엄", metrics={"price": 40200, "base_price": 40200},
                  collected_at=NOW)]
    data = extract_chart_data(_competitor_result(
        own_products=[{"product": "플레인 크림치즈 베이글", "category": "크림치즈",
                       "price": 4500, "match_key": "크림치즈"}],
        competitor_products=[{"brand": "런던베이글뮤지엄",
                              "url": "https://www.kurly.com/goods/1000773557",
                              "basis": "냉동 세트"}],          # match_key 없음
        items=items))
    assert data["comparisons"] == []
    assert len(data["competitors"]) == 1          # 경쟁사는 원시 목록에 잔존


def test_position_above_when_nylb_more_expensive():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="경쟁 베이글", url="u1", author="경쟁사",
                  metrics={"price": 3000}, collected_at=NOW)]
    data = extract_chart_data(_competitor_result(
        own_products=[{"product": "NYLB 베이글", "category": "베이글",
                       "price": 3500, "match_key": "베이글"}],
        competitor_products=[{"brand": "경쟁사", "url": "u1", "match_key": "베이글"}],
        items=items))
    r = data["comparisons"][0]
    assert r["position"] == "above"
    assert r["diff_pct"] > 0
    assert r["competitor_basis"] is None          # basis는 선택


def test_zero_competitor_price_skipped():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="이상치", url="u1", author="X",
                  metrics={"price": 0}, collected_at=NOW)]
    data = extract_chart_data(_competitor_result(
        own_products=[{"product": "P", "category": "C", "price": 4500, "match_key": "C"}],
        competitor_products=[{"brand": "X", "url": "u1", "match_key": "C"}],
        items=items))
    assert data["comparisons"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/report/test_chart_data.py -v -k comparison or position or zero`

(또는 단순히 `... tests/report/test_chart_data.py -v`)
Expected: FAIL — `KeyError: 'comparisons'` (키 미존재).

- [ ] **Step 3: Write minimal implementation**

`src/nylb/report/chart_data.py`의 `extract_chart_data`에서 `competitors = [...]` 다음, `return {` 직전에 추가:

```python
    own_by_key: dict[str, list[dict]] = defaultdict(list)
    for op in result.query.get("own_products", []):
        own_by_key[op.get("match_key")].append(op)
    comp_cfg = {c.get("url"): c for c in result.query.get("competitor_products", [])}

    comparisons: list[dict] = []
    for it in result.items:
        if it.source != "kurly":
            continue
        cfg = comp_cfg.get(it.url, {})
        mk = cfg.get("match_key")
        comp_price = it.metrics.get("price")
        if not mk or mk not in own_by_key or not comp_price:
            continue
        for op in own_by_key[mk]:
            nylb_price = op.get("price")
            if nylb_price is None:
                continue
            diff = nylb_price - comp_price
            comparisons.append({
                "match_key": mk,
                "category": op.get("category", mk),
                "nylb_product": op.get("product"),
                "nylb_price": nylb_price,
                "competitor_brand": it.author,
                "competitor_product": it.title,
                "competitor_price": comp_price,
                "competitor_basis": cfg.get("basis"),
                "diff": diff,
                "diff_pct": round(diff / comp_price * 100, 1),
                "position": "above" if diff > 0 else "below" if diff < 0 else "equal",
            })
```

그리고 return dict에 `competitors` 다음 한 줄 추가:

```python
        "competitors": competitors,
        "comparisons": comparisons,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/report/test_chart_data.py -v`
Expected: PASS (기존 + 신규 모두 green).

- [ ] **Step 5: Commit**

```powershell
git add src/nylb/report/chart_data.py tests/report/test_chart_data.py
git commit -m "feat: build NYLB vs competitor comparisons in chart_data"
```

---

## Task 3: html.py 📊 가격 포지셔닝 섹션

**Files:**
- Modify: `src/nylb/report/html.py` (`_TEMPLATE` PRICING 다음·COMPETITORS 앞에 IIFE 삽입; `build_dashboard` data dict에 `comparisons`)
- Test: `tests/report/test_html.py`

- [ ] **Step 1: Write the failing tests**

`tests/report/test_html.py` 끝에 추가(파일에 이미 `_embedded_data`, `SYN`, `NOW`, `Item`, `ScanResult` 존재):

```python
def test_price_positioning_comparison_embedded_when_present():
    items = [Item(source="kurly", lens="competitor", type="product",
                  title="[포비베이글] 크림치즈", url="https://www.kurly.com/goods/5043336",
                  author="포비(FOURB)", metrics={"price": 8910, "base_price": 9900},
                  collected_at=NOW)]
    result = ScanResult(run_id="rc", store_id="nylb", lens="competitor",
        query={"own_products": [{"product": "플레인 크림치즈 베이글", "category": "크림치즈",
                                 "price": 4500, "match_key": "크림치즈"}],
               "competitor_products": [{"brand": "포비(FOURB)",
                   "url": "https://www.kurly.com/goods/5043336",
                   "match_key": "크림치즈", "basis": "리테일 200g"}]},
        items=items, started_at=NOW, finished_at=NOW)
    syn = dict(SYN, price_positioning="크림치즈 베이글은 포비 리테일가보다 저렴해 가격 여력 있음.")
    html = build_dashboard(result, syn, extract_chart_data(result))
    comp = _embedded_data(html)["comparisons"]
    assert len(comp) == 1
    assert comp[0]["position"] == "below"
    assert comp[0]["competitor_basis"] == "리테일 200g"
    assert _embedded_data(html)["syn"]["price_positioning"].startswith("크림치즈")


def test_no_comparison_data_when_absent():
    result = _result()                       # menu result, no own/competitor
    html = build_dashboard(result, SYN, extract_chart_data(result))
    assert _embedded_data(html)["comparisons"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/report/test_html.py -v -k comparison`
Expected: FAIL — `KeyError: 'comparisons'` in embedded DATA (build_dashboard data dict에 키 없음).

- [ ] **Step 3a: Add comparisons to build_dashboard data dict**

`src/nylb/report/html.py`의 `build_dashboard` data dict에서 `"competitors": chart.get("competitors", []),` 다음 줄에 추가:

```python
        "competitors": chart.get("competitors", []),
        "comparisons": chart.get("comparisons", []),
```

- [ ] **Step 3b: Insert the 📊 가격 포지셔닝 section in the template**

`src/nylb/report/html.py`의 `_TEMPLATE` 안, `/* PRICING */` 블록의 마지막 줄
`pc.appendChild(pt);pr.appendChild(pc);app.appendChild(pr);` **다음**, `/* COMPETITORS — 경쟁사 가격 (크롤링) */` **앞**에 아래 IIFE를 삽입:

```javascript
/* PRICE POSITIONING — 📊 가격 포지셔닝 (NYLB vs 경쟁사) */
(function(){
  const cmp=DATA.comparisons||[];
  if(!cmp.length) return;
  const sec=sect("📊","가격 포지셔닝","NYLB 매장가 vs 경쟁사 — 차이(%)로 본 포지셔닝 (위=비쌈·빨강, 아래=쌈·초록)");
  if(S.price_positioning)
    sec.appendChild(h("div",{class:"insight"},[h("h3",null,"포지셔닝 인사이트"),h("p",null,S.price_positioning)]));
  const card=h("div",{class:"card"});const tb=h("table");
  tb.appendChild(h("tr",null,[th("카테고리"),th("NYLB"),th("경쟁사"),th("경쟁가"),th("차이")]));
  cmp.forEach(c=>{
    const color=c.position==="above"?"var(--down)":c.position==="below"?"var(--up)":"var(--muted)";
    const arrow=c.position==="above"?"▲":c.position==="below"?"▼":"▬";
    const compCell=h("td",null,[h("b",null,c.competitor_brand||"-"),
      document.createTextNode(" "+(c.competitor_product||"")),
      c.competitor_basis?h("span",{class:"tag",style:"margin-left:6px"},c.competitor_basis):null]);
    const diffCell=h("td",null,h("b",{style:"color:"+color},
      arrow+" "+(c.diff_pct>0?"+":"")+c.diff_pct+"%"));
    tb.appendChild(h("tr",null,[
      h("td",null,h("b",null,c.category||"-")),
      h("td",null,(c.nylb_price!=null?Math.round(c.nylb_price).toLocaleString()+"원":"-")),
      compCell,
      h("td",null,(c.competitor_price!=null?Math.round(c.competitor_price).toLocaleString()+"원":"-")),
      diffCell]));
  });
  card.appendChild(tb);
  card.appendChild(h("div",{class:"note"},"※ 컬리 리테일가는 매장 단품가와 기준이 달라 직접 비교에 주의(기준 라벨 참고). 가격은 시점·프로모션에 따라 변동."));
  sec.appendChild(card);app.appendChild(sec);
})();
```

(참고: `sect`, `th`, `h`, `S`, `DATA` 헬퍼는 템플릿에 이미 정의되어 있고 `.insight`/`.card`/`.note`/`.tag` CSS도 이미 존재한다.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/report/test_html.py -v`
Expected: PASS (기존 + 신규 모두 green).

- [ ] **Step 5: Commit**

```powershell
git add src/nylb/report/html.py tests/report/test_html.py
git commit -m "feat: render 가격 포지셔닝 dashboard section"
```

---

## Task 4: config — own_products + match_key/basis

**Files:**
- Modify: `config/lenses.yaml` (competitor 렌즈)

자동 테스트 없음(데이터 설정). ⚠️ `own_products`의 가격은 **owner 확정 전 placeholder**다. Step 2에서 owner에게 실제 매장가를 확인한다.

- [ ] **Step 1: Edit competitor lens**

`config/lenses.yaml`의 `competitor:` 블록을 아래로 교체:

```yaml
    competitor:
      keywords: []
      sources: [kurly]
      own_products:
        # ⚠️ 아래 가격은 예시(placeholder) — owner가 실제 매장가로 확정할 것.
        - {product: "플레인 크림치즈 베이글", category: "크림치즈", price: 4500, match_key: "크림치즈"}
      competitor_products:
        - {brand: "포비(FOURB)", url: "https://www.kurly.com/goods/5043336", match_key: "크림치즈", basis: "리테일 200g"}
        - {brand: "런던베이글뮤지엄", url: "https://www.kurly.com/goods/1000773557", basis: "냉동 세트"}
      instagram_accounts: []
```

- [ ] **Step 2: Confirm real prices with owner, then run config-load test**

owner에게 NYLB 실제 매장 단품가를 확인해 `price`를 갱신한다(필요시 own_products 항목 추가).
Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: PASS (YAML 파싱 정상).

- [ ] **Step 3: Commit**

```powershell
git add config/lenses.yaml
git commit -m "feat: add NYLB own_products + match_key/basis to competitor lens"
```

---

## Task 5: trend-scan 커맨드 synthesis 스키마에 price_positioning

**Files:**
- Modify: `.claude/commands/trend-scan.md` (synthesis 스키마 설명 줄)

- [ ] **Step 1: Add price_positioning to the schema description**

`.claude/commands/trend-scan.md`의 synthesis 스키마(키) 줄 끝, `chart_note(선택).` 앞에 추가:

```
... risks[{risk,mitigation}], data_gaps[], radar[{trend,rising_signal,bagel_fit,angle}], price_positioning(선택; competitor 렌즈일 때 NYLB vs 경쟁사 해석 + 권장 가격조정 액션, 2~4문장 문자열), chart_note(선택).
```

- [ ] **Step 2: Commit**

```powershell
git add .claude/commands/trend-scan.md
git commit -m "docs: add price_positioning to trend-scan synthesis schema"
```

---

## Task 6: 라이브 검증

**Files:** 없음(실행/검증). `@pytest.mark.live` 대상 아님 — 수동 실행.

- [ ] **Step 1: 전체 테스트 green 확인**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: 기존 74 + 신규(scan 1 + chart_data 4 + html 2 = 7) ≈ 81 passed, live 제외.

- [ ] **Step 2: competitor 스캔 실행**

Run: `.\.venv\Scripts\python.exe -m nylb scan --lens competitor --store nylb`
Expected: 0 errors, 포비/LBM 가격 수집. 출력의 `run_id` 기록.

- [ ] **Step 3: synthesis 작성(수동) + HTML 생성**

`data/raw/<run_id>.synthesis.json`에 `price_positioning` 포함한 종합 JSON 작성(competitor 렌즈라 최소 키 + price_positioning).
Run: `.\.venv\Scripts\python.exe -m nylb report-html --run <run_id>`
Expected: `reports/<run_id>.analysis.html` 생성.

- [ ] **Step 4: Playwright 렌더 검증**

http.server 띄우고 Playwright로 `reports/<run_id>.analysis.html` 로드 → 📊 가격 포지셔닝 섹션에 크림치즈 행(NYLB 4,500 vs 포비 8,910 [리테일 200g] ▼-49.5% 초록) 노출, 0 JS 에러(favicon 404만 무해) 확인.

- [ ] **Step 5: 메모리 업데이트 + 마무리**

`nylb-project.md`에 이 슬라이스 요약 추가. `superpowers:finishing-a-development-branch`로 main 병합 + 푸시 결정.

---

## Self-Review (작성자 체크)

**Spec coverage:** §1 config→Task4 · §2 scan→Task1 · §3 comparisons→Task2 · §4 html 섹션→Task3 · §5 synthesis 스키마→Task5 · §6 테스트→Task1~3 · §7 라이브→Task6. 모든 spec 섹션에 대응 태스크 존재.

**Placeholder scan:** own_products 가격은 의도된 owner-확정 placeholder(Task4 Step2에서 처리). 코드 스텝은 전부 실제 코드 포함. TBD/TODO 없음.

**Type consistency:** `comparisons` 행 키(match_key/category/nylb_product/nylb_price/competitor_brand/competitor_product/competitor_price/competitor_basis/diff/diff_pct/position)가 chart_data 구현(Task2)·html 렌더(Task3)·테스트 전반에서 동일. `position` 값(above/below/equal)·색상 매핑(above→--down 빨강, below→--up 초록) 일관.
