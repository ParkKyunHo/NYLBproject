# NYLB ↔ 경쟁사 가격 포지셔닝 (Slice B) — 설계

- 작성일: 2026-06-04
- 브랜치: `feat/price-comparison`
- 목표: 경쟁사 크롤러가 모은 가격을 NYLB 자체 매장가와 나란히 비교해 "어느 품목이 경쟁사 대비
  비싼지/싼지(차이 %)"와 가격 조정 액션까지 대시보드에서 보여준다. 크롤러를 '가격 리스트'에서
  '의사결정 도구'로 승격시키는 슬라이스.

## 배경 / 현재 상태

- `competitor` 렌즈가 Marketkurly 상품페이지를 크롤해 가격을 수집한다(`collectors/kurly.py`).
  현재 데이터: 포비(FOURB) 크림치즈 8,910원(정가 9,900) · 런던베이글뮤지엄(LBM) 냉동세트 40,200원.
- `chart_data.extract_chart_data`가 `competitors: [{brand, product, price, base_price, url}]`를 만든다.
- `html.py`가 🏷️ 경쟁사 가격 섹션을 **데이터 있을 때만** 조건부 렌더한다(IIFE 패턴).
- synthesis(종합분석 JSON)는 **Claude Code가 수동 작성**한다(유료 LLM API 보류 유지).
- `result.query`는 이미 `competitor_products`(brand/url)를 collector로 전달하며 `chart_data`에서도 접근 가능.

## 핵심 정직성 리스크 (설계의 출발점)

현재 경쟁사 데이터는 **리테일 SKU가**(컬리 — 포비 크림치즈 8,910원=200g 통, LBM 40,200원=냉동 여러 개
세트)인 반면, NYLB 자체가는 **매장 단품가**(예: 크림치즈 베이글 4,500원 1개)다. 4,500 vs 8,910을 그대로
"−49% 싸다"로 보여주면 사과-오렌지 비교라 오해를 부른다.

→ 대응: 표의 각 행에 **비교 기준(리테일/매장) 라벨 + 캐비엇**을 같이 노출하고, 실제 해석은
synthesis의 `price_positioning`(수동 작성)에 담는다. 엔진은 단순 계산만, 판단은 owner + Claude가 한다.

## 확정된 설계 결정 (브레인스토밍)

1. **매칭 방식 = `match_key` 명시 매칭.** 경쟁사·NYLB 양쪽 config에 같은 `match_key` 문자열을 owner가
   직접 지정해 결합(1:N 카테시안 가능). 예측 가능하고 의도치 않은 오매칭이 없다. `category`는 own 쪽
   표시용 라벨로만 쓴다(자동 매칭 키 아님).
2. **표 형태 = 표 + 차이% + 기준 라벨.** 한 행에 카테고리·NYLB가·경쟁사(브랜드+상품, basis 배지)·
   경쟁가·차이%를 나열. 색상: 우리가 더 비싸면 빨강 / 더 싸면 초록. 하단 캐비엇 + 인사이트 박스.

## 아키텍처 / 데이터 흐름

새 collector 없음. 매칭은 **전부 `chart_data`에서** 일어난다.

```
config/lenses.yaml ──> run_scan.query(+own_products) ──> chart_data(매칭→comparisons) ──> html(📊 섹션)
                                                              synthesis.price_positioning(수동) ──┘
```

## 1. config 변경 (`config/lenses.yaml` competitor 렌즈)

```yaml
competitor:
  keywords: []
  sources: [kurly]
  own_products:                       # 신규 — NYLB 매장가(owner 입력)
    - {product: 플레인 크림치즈 베이글, category: 크림치즈, price: 4500, match_key: 크림치즈}
  competitor_products:
    - {brand: 포비(FOURB), url: https://www.kurly.com/goods/5043336, match_key: 크림치즈, basis: "리테일 200g"}
    - {brand: 런던베이글뮤지엄, url: https://www.kurly.com/goods/1000773557, basis: "냉동 세트"}
  instagram_accounts: []
```

- `match_key` = 조인 키(양쪽). `category` = 표시 라벨(own). `basis` = 경쟁가 기준 배지(competitor, **선택**).
- LBM 세트는 `match_key`를 비워 비교에서 제외(원시 🏷️ 목록엔 남음) — 냉동 멀티팩이라 단품 비교 대상이 없음.
- ⚠️ **실제 NYLB 가격은 owner 확정 필요.** 위 4,500은 spec 예시값 → 빌드 시 placeholder로 넣고
  라이브 검증 전 실제 메뉴가를 받는다.

## 2. `run_scan` query 확장 (`src/nylb/core/scan.py`)

`query` dict에 한 줄 추가(가산적·기존 동작 불변):

```python
"own_products": lens_config.get("own_products", []),
```

## 3. `comparisons` 생성 (`src/nylb/report/chart_data.py`)

`extract_chart_data` 반환 dict에 `comparisons` 키 추가.

행 스키마:

```python
comparisons: [{
  "match_key", "category",
  "nylb_product", "nylb_price",
  "competitor_brand", "competitor_product", "competitor_price", "competitor_basis",
  "diff",       # nylb_price - competitor_price (원)
  "diff_pct",   # round((nylb - comp) / comp * 100, 1)
  "position",   # "above"(우리가 비쌈·빨강) | "below"(싸다·초록) | "equal"
}]
```

매칭 규칙:

1. `result.query["competitor_products"]`에서 `url → {match_key, basis}` 맵 구성.
2. kurly item(`source == "kurly"`)마다 `url`로 match_key/basis 조회.
3. `result.query["own_products"]` 중 같은 `match_key`인 항목과 결합(1:N 카테시안).
4. **양쪽 다 존재할 때만** 행 생성. 한쪽만 있으면 비교 제외(경쟁사는 기존 `competitors`에 잔존).
5. 가드: `competitor_price`가 0/None이면 행 스킵(0나눗셈 방지).
6. `position`: `nylb_price > competitor_price` → "above", `<` → "below", `==` → "equal".

엔진은 계산만 한다. 기준 비교 가능성 판단은 owner(매칭 선택)와 Claude(synthesis)가 맡는다.

## 4. html 렌더 — 📊 가격 포지셔닝 섹션 (`src/nylb/report/html.py`)

- **위치:** 🏷️ 가격 벤치마크 → **📊 가격 포지셔닝(신규)** → 🏷️ 경쟁사 가격(원시 목록) 순.
  결정 뷰를 먼저, 원시 백업을 뒤에.
- **조건부 렌더:** `DATA.comparisons.length`가 있을 때만(기존 competitor IIFE 패턴 그대로).
- **표:** 카테고리 | NYLB | 경쟁사(브랜드 + 상품, `competitor_basis` 배지) | 경쟁가 | 차이(▲/▼ % 색상).
- **색상 매핑:** `position==="above"`(우리가 비쌈) → 빨강 `var(--down)`,
  `"below"`(싸다) → 초록 `var(--up)`, `"equal"` → 중립. 화살표: above ▲, below ▼.
- **캐비엇 note:** 리테일 vs 매장 기준 차이 주의(기존 competitor note와 동일 톤).
- **인사이트 박스:** `synthesis.price_positioning`이 있으면 표 위에 강조 박스로 렌더(해석 + 가격조정 액션).
  없으면 미표시.
- `build_dashboard`의 data dict에 `"comparisons": chart.get("comparisons", [])` 추가.

## 5. synthesis 스키마 확장

- `price_positioning` 키 추가. **v1 = 문자열**(2~4문장, 해석 + 권장 가격조정 액션 포함).
  없으면 대시보드에서 미표시. 후속에 구조화(`{summary, actions[]}`) 여지 남김.
- `.claude/commands/trend-scan.md`의 synthesis 스키마 설명에도 `price_positioning(선택)` 추가.

## 6. 테스트 (TDD)

검증은 **렌더 문자열이 아니라 임베드된 `const DATA`(JSON)** 로 한다(섹션 제목은 템플릿에 항상 존재).

chart_data (`tests/report/test_chart_data.py`):
- match_key 일치 시 comparison 행 생성 + diff/diff_pct/position 정확.
- match_key 불일치 → `comparisons == []`, 경쟁사는 `competitors`에 잔존.
- 우리가 싸면 `position=="below"`, 비싸면 `"above"`.
- `competitor_basis`가 config에서 행에 실린다.
- `competitor_price == 0` → 행 스킵.

html (`tests/report/test_html.py`):
- comparisons가 있을 때 `_embedded_data(html)["comparisons"]`에 임베드.
- 비어 있으면 self-hide(`comparisons == []`).
- `price_positioning` passthrough(`_embedded_data(html)["syn"]["price_positioning"]`).

scan (`tests/core/test_scan.py`):
- `test_run_scan_passes_own_products` — query에 `own_products`가 collector로 전달된다
  (기존 `test_run_scan_passes_competitor_products` 패턴 그대로). 기존 테스트는 `query.get(...)`만
  쓰므로 키 추가로 깨지지 않음(확인 완료).

## 7. 라이브 검증

- owner의 실제 메뉴가로 `own_products` 확정 후 `python -m nylb scan --lens competitor` 실행
  (`.\.venv\Scripts\python.exe` 경유).
- `python -m nylb report-html --run <id>` → `reports/<id>.analysis.html` 생성.
- http.server + Playwright로 📊 가격 포지셔닝 섹션 렌더 확인(0 JS 에러, favicon 404만 무해).
- 예상 결과: 현재 Kurly 데이터로는 **'크림치즈' 1행**(NYLB 4,500 vs 포비 8,910 [리테일 200g] −49% 초록)
  + 캐비엇. LBM은 비교 제외(원시 목록만). 이는 기준 차이를 드러내는 정직한 결과.

## 8. 범위 밖 / 한계

- 매장 인스토어 경쟁가(다이닝코드 / 네이버 플레이스 메뉴탭) — 별도 슬라이스(이게 들어와야 like-for-like
  비교가 풍부해짐).
- ApiAnalyzer / 유료 LLM, Next.js 웹앱, 결제.
- `price_positioning` 구조화, 가격 밴드(±편차) 표현은 후속.

## 9. 제약 (이 레포 고유)

- 파이썬/pytest는 `.\.venv\Scripts\python.exe`로만. git/python은 PowerShell 도구 사용.
- 한국어 콘텐츠 UTF-8. live 테스트는 `@pytest.mark.live` + `addopts="-m 'not live'"`로 기본 제외.
- 대시보드 HTML 검증은 http.server + Playwright(file 프로토콜 차단).
- html.py 테스트는 임베드 `const DATA`(JSON)로 검증.
- 작업은 `feat/price-comparison`에서, 끝나면 main 병합 + 푸시.
