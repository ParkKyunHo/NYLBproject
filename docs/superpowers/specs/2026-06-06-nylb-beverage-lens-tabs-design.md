# NYLB 음료 렌즈 + 렌즈 탭 보드 Design Spec

**날짜:** 2026-06-06
**하위 프로젝트:** 의사결정 상황판 위에 **두 번째 도메인(음료)** 추가 + **다중 렌즈 탭 UX**. 산업-불문 엔진(B+ shipped)의 실전 확장 — 음료는 config만, 새 코드는 탭 렌더러뿐.

## 문제 (Why)

오너: "어떤 음료가 인기있는지도 지금처럼 방대하게 분석 + 그에 맞는 카테고리 + 메뉴와 같이 볼 UX 설계." 두 가지:
1. **음료 분석** — 베이커리만큼 풍부한 음료 유니버스(커피/논커피/스무디/트렌드/브랜드).
2. **다중 렌즈 UX** — 메뉴(베이커리) + 음료를 한 화면에서. 오너가 옵션 비교 후 **렌즈 탭 전환** 선택(스플릿/통합/인덱스 대비).

엔진은 이미 산업-불문(B+)이라 음료 *데이터*는 config로 끝. 새 일은 **여러 렌즈 보드를 한 HTML에 탭으로** 합치는 렌더러.

## 결정 (오너 확정)

- **음료 = 새 `beverage` 렌즈.** 자체 앵커 `아메리카노`(베이글 앵커링 금지 — 음료 vs 빵 사과-오렌지), 2026 리서치 카테고리. **엔진 코드 0줄**(수집·앵커·발굴·뉴스가 그대로 동작).
- **UX = 렌즈 탭 전환.** 상단 탭([🥯 메뉴][🥤 음료]), 클릭 시 해당 렌즈 풀 보드 렌더, 한 페이지. 확장(경쟁사 탭)·포트폴리오에 유리.
- **산업-불문·LLM 없음·평결 없음 유지.** 탭 라벨/아이콘·렌즈 조합은 config 주도(어떤 F&B 업종·렌즈 조합이든). 보드 내용은 기존과 동일(데이터-주도).

## 현재 코드와의 정합

- 엔진(scan/collectors/board/chart_data)은 렌즈-불문. `report/html.py`의 `<script>`가 **단일 board를 `app`에 직접 렌더**(`build_dashboard(result, chart, news_context)`). 탭을 위해 이 렌더 로직을 **`renderBoard(board)` 함수로 추출**하고 상단에 탭 바를 둔다.
- `core/discover`·`core/context`·`report/news`·`report/board.build_board`·`collectors/*` 전부 재사용(렌즈만 바뀜).

## 설계 (How) — 4 조각

### C1. 음료 렌즈 (config) — 리서치 확정

`config/lenses.yaml`에 `beverage` 렌즈 추가(2026 트렌드 그라운딩; 에어로카노·우베라떼 등 실재 확인):

```yaml
    beverage:
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

빌드 때 키워드 재확인(리서치). 기존 `menu`/`content`/`competitor` 렌즈는 불변.

### C2. 렌즈 탭 렌더러 (`report/html.py` 리팩터)

- **`renderBoard(board, app)` 추출:** 현재 top-level `<script>`의 모든 렌더 블록(HERO/KPI/랭킹/차트/코어신호/레이더/미검증/경쟁사/발굴후보/뉴스/신뢰도/푸터)을 `function renderBoard(DATA, app)`로 감싼다. 헬퍼(`h`/`esc`/`sect`/`buildChart`)는 top-level 유지.
- **탭 바 + 진입 데이터 변경:** 템플릿이 `const LENSES = __DATA__;`(배열 `[{key,label,icon,board}]`)을 읽는다. `LENSES.length>1`이면 탭 바 렌더(라벨·아이콘), 활성 탭 클릭 시 `app` 비우고 `renderBoard(LENSES[active].board, app)`. 기본 활성=0.
- **`build_multi_dashboard(lenses: list[dict]) -> str`** (신규 진입점): 각 lens = `{key, label, icon, board}`. JSON으로 `__DATA__` 치환.
- **`build_dashboard(result, chart, news_context=None)`** (단일, 하위호환 유지): 내부에서 `build_board` → `build_multi_dashboard([{key:lens, label:..., icon:..., board}])` 위임. 단일이면 탭 바 숨김.
- **테스트 영향:** `tests/report/test_html.py`의 `_embedded_data`가 `const DATA = (...)`를 파싱하므로, `const LENSES = [...]`로 바뀌면 그 헬퍼를 `LENSES[0].board`를 꺼내도록 갱신해야 한다(이 리팩터의 알려진 ripple — 플랜에서 처리).

### C3. 오케스트레이션 (`report/multi.py` 신규)

`build_lenses_dashboard(lens_keys, *, lenses_file, store_id, settings, collectors=None) -> str`:
- 각 lens_key에 대해: `get_lens_config` → `run_scan`(또는 최신 run 로드) → `extract_chart_data` → `gather_riser_news` → `build_board` → `{key, label, icon, board}`.
- 라벨/아이콘은 lens_config의 선택 필드 `label`/`icon`(없으면 key 그대로, 아이콘 기본 🍽). **도메인 라벨도 config 주도(산업-불문).**
- `build_multi_dashboard(lenses)` 반환.

### C4. 배선 (`cli.py`, `report/server.py`)

- `nylb dashboard --lenses menu,beverage`(기본 `menu,beverage`): 서버 `/run`이 그 렌즈들을 `build_lenses_dashboard`로 스캔→탭 보드 렌더. 버튼 한 번에 전 렌즈 갱신.
- (선택) `nylb report-multi --lenses menu,beverage`: 라이브 키 없이 최신 저장 run들로 탭 HTML 생성(검증·CI용). YAGNI면 dashboard 경로만.

## 데이터 모델 변화

- `config/lenses.yaml`: `beverage` 렌즈 추가(+선택 `label`/`icon` 필드를 menu/beverage에). menu/competitor/content 불변.
- `report/html.py`: `_TEMPLATE` `<script>`가 `LENSES` 배열 소비 + `renderBoard` 함수 + 탭 바. `build_multi_dashboard` 신규, `build_dashboard` 위임.
- 신규 `report/multi.py`: `build_lenses_dashboard`.
- `cli.py`/`report/server.py`: dashboard 다중 렌즈.

## 테스트 전략

- **C1:** `beverage` 렌즈 로드(`get_lens_config`), `radar` 카테고리·anchor 파싱.
- **C2:** `build_multi_dashboard([menu_board, bev_board])` → HTML에 두 탭 라벨 + 두 board 데이터(`core_signals` 등) + 탭 스위처 JS 포함; `LENSES.length==1`이면 탭 바 없음. `build_dashboard` 단일 하위호환(기존 board 테스트 통과 — `_embedded_data` 갱신).
- **C3:** `build_lenses_dashboard(['menu','beverage'])` — collectors mock으로 각 렌즈 보드 빌드, lenses 2개·라벨/아이콘 적용 검증.
- **C4:** dashboard `--lenses` 파싱; server `/run`이 다중 렌즈 렌더(render_fn 주입).
- **산업-불문:** 임의 렌즈 리스트(예: `['menu']`만, 또는 가짜 비-음료 렌즈)로 build_lenses_dashboard 동작.
- **라이브:** `nylb dashboard --lenses menu,beverage` → 두 탭, 클릭 전환, 각 탭 풀 보드(음료=아메리카노 앵커 랭킹·카테고리·발굴·뉴스), Playwright 탭클릭 동작 + 0 JS 오류.

## 범위 경계 (YAGNI)

- **포함:** beverage 렌즈 config, renderBoard 추출 + 탭 바 + build_multi_dashboard, multi.py 오케스트레이션, dashboard 다중 렌즈, 라이브.
- **제외:** 크로스-렌즈 통합 랭킹(렌즈별 앵커 다름 — 합치면 무의미), 탭별 독립 갱신(버튼=전체 갱신), URL 딥링크/라우팅(JS 탭 상태로 충분), content/competitor 자동 탭 편입(전달된 렌즈 리스트만), 음료 인스토어 가격(=C). LLM 요약 없음.

## 산업-불문 체크리스트

- 탭 라벨·아이콘·렌즈 조합 = config(`label`/`icon`/`--lenses`). 엔진·렌더에 음료/커피/브랜드 리터럴 0.
- 다른 업종은 자기 렌즈들을 config에 넣고 `--lenses`로 조합 — 코드 변경 0.

## 인터페이스/단위 요약

- `html.build_multi_dashboard(lenses) -> str` — 무엇: 여러 렌즈 board를 탭 HTML로. 의존: `_TEMPLATE`.
- `html.renderBoard(DATA, app)` (JS) — 무엇: 단일 board 렌더. 의존: 헬퍼.
- `multi.build_lenses_dashboard(lens_keys, ...)` — 무엇: 렌즈별 스캔→board→탭 조립. 의존: scan/board/news/build_multi_dashboard.
- `nylb dashboard --lenses` — 무엇: 다중 렌즈 로컬 탭 보드.

## Self-Review

- **Placeholder:** 음료 키워드는 대표 리서치값(빌드 때 재확인). 그 외 TBD 없음. renderBoard 추출·LENSES 배열·탭 바 조건 명시.
- **일관성:** `LENSES=[{key,label,icon,board}]` 형태가 build_multi·build_dashboard·multi.py·테스트에서 동일. build_dashboard 단일 위임으로 하위호환.
- **범위:** 단일 플랜(≈5-6 태스크: config, html 리팩터, build_multi, multi.py, dashboard 배선, 라이브). C(경쟁사)·통합랭킹 분리.
- **모호성:** 앵커는 렌즈별(음료=아메리카노) 명시. 탭=JS 상태(라우팅 없음). `_embedded_data` 갱신을 ripple로 명시.
