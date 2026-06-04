# NYLB 트렌드 레이더 + 데이터랩 + HTML 자동화 — 설계문서

- 작성일: 2026-06-04
- 상태: 승인됨 (브레인스토밍 → 설계 승인)
- 선행 설계: `docs/superpowers/specs/2026-06-03-nylb-market-research-design.md` (전체 시스템)
- 범위: 기존 메뉴 스캔에 **인접 음식 트렌드 레이더**를 더하고, **네이버 데이터랩**을 본축으로 연결하며, **종합분석 HTML 대시보드**를 정식 기능으로 승격한다.

---

## 1. 개요 & 목표

현 시스템은 고정 키워드(베이글·소금빵·크로플)만 스캔한다. 사용자 요구: **"베이커리뿐 아니라 최신 관심사도, 베이글을 중심축으로" 파악**. 또한 첫 종합분석이 한국 검색 본축(네이버 데이터랩) 부재와 구글 트렌드 상대 스케일 한계를 지적했고, 일회성으로 만든 HTML 대시보드를 매 스캔마다 자동 생성하길 원한다.

목표:
1. **트렌드 레이더** — 인접 음식·디저트 트렌드를 *떠오르는 순*으로 포착하고, 각 항목을 "베이글 접목 가능성"으로 점수화(두바이 소금빵 패턴의 일반화).
2. **네이버 데이터랩 연동** — 한국 검색 트렌드 본축을 추가해 구글 트렌드와 교차검증.
3. **HTML 대시보드 정식화** — 일회성 스크립트를 테스트되는 재사용 모듈로 만들고 `/trend-scan`이 자동 생성.

설계 선택(사용자 확정):
- 관심사 범위 = **음식·디저트 인접 중심**.
- 탐지 방식 = **하이브리드**(워치리스트 + 자동발견).

## 2. Non-goals (YAGNI)

- 광의 소비·문화 트렌드(Y2K·캐릭터 콜라보 등)는 **이번 범위 밖**(인접 음식만). 나중에 워치리스트 확장으로 흡수 가능.
- 새 "lens" 신설 안 함 — 레이더는 `menu` 렌즈 안에 둔다.
- 베이글 접목 점수를 코드 규칙으로 하드코딩하지 않음 — 분석 단계(Claude)가 판단(엔진 업종 불문 원칙 유지).
- 네이버 데이터랩 쇼핑인사이트(카테고리) API는 이번엔 제외(검색어 트렌드만). 필요 시 후속.

## 3. 트렌드 레이더 (핵심 개념)

### 3.1 하이브리드 탐지
- **워치리스트(curated):** `config/lenses.yaml`의 `menu` 렌즈에 `radar_watchlist: [두바이초콜릿, 탕후루, 약과, 요거트아이스크림, ...]` 추가. 운영자가 통제.
- **자동발견(auto):** 구글 트렌드 `related_queries`(rising)를 **시드 키워드**(베이글·디저트·베이커리)로 조회 → 운영자가 적지 않은 신규 급상승 인접어를 포착.

### 3.2 베이글 접목 점수 (분석 단계)
- 레이더가 수집한 트렌드 항목(워치리스트 + 자동발견)을 Claude가 분석 단계에서 평가: ① 현재 상승 중인가(데이터랩·구글 시계열), ② 베이글/소금빵/베이커리 변주로 접목 가능한가, ③ 어떤 각도인가.
- 코드는 **신호 수집**까지, **해석·점수**는 프롬프트(Claude)가 담당.

## 4. A — 네이버 데이터랩 수집기

신규 수집기 `src/nylb/collectors/naver_datalab.py` — 기존 수집기와 동일한 균일 계약(`collect` / `_fetch` / `_parse`).

- API: `POST https://openapi.naver.com/v1/datalab/search` (통합검색어 트렌드). 헤더는 네이버 검색과 동일한 `X-Naver-Client-Id/Secret` — **신규 키 불필요**.
- 요청 바디: `startDate`, `endDate`, `timeUnit="date"`, `keywordGroups`(그룹당 groupName + keywords). **그룹 최대 5개/요청** → 코어+워치리스트를 5개씩 배치(chunk)해 여러 요청.
- 기간: 최근 **30일**(endDate=오늘, startDate=오늘-30일). (구글 트렌드 7일보다 길게 잡아 추세 안정화)
- `_fetch(query, settings)`:
  - `cid/csec` 없으면 `RuntimeError`(우아한 스킵).
  - 입력 키워드 = `query["keywords"]`(코어) + `query.get("radar_watchlist", [])`.
  - 5개씩 chunk → 각 요청의 `results`를 합쳐 반환.
- `_parse(payload, query, lens, collected_at)`: 각 `results[i]` → `Item(source="naver_datalab", type="search_term", title=groupName, metrics={"interest": 최근값, "peak": 최대값}, raw={"series": data})`.
- 부분 실패 허용: 예외 시 `CollectResult(errors=[CollectError(source="naver_datalab", ...)])`.

### 4.1 구글 트렌드 자동발견 확장
`src/nylb/collectors/google_trends.py` `_fetch` 확장:
- 기존 `interest_over_time`(코어 시계열) 유지.
- 추가: 시드(예: 코어 키워드)로 `pytrends.related_queries()` 호출 → `rising` 상위 N개 추출. **베스트에포트**(예외/빈 응답 시 무시, 코어 수집은 절대 깨지지 않음).
- `_parse`: rising 항목을 `Item(source="google_trends", type="rising_query", title=급상승어, metrics={"value": 상승률}, raw={"seed": 시드})`로 추가.

## 5. B — HTML 대시보드 정식화

### 5.1 재사용 모듈
- `src/nylb/report/chart_data.py` — `extract_chart_data(scan_result) -> dict`. 오늘의 일회성 `_extract.py`를 정식화: 채널 집계, 데이터랩/구글 트렌드 일별 시계열·모멘텀, 키워드×채널 매트릭스, 레이더 항목 목록.
- `src/nylb/report/html.py` — `build_dashboard(scan_result, synthesis: dict, chart: dict) -> str`. **순수 함수**(파일 IO 없음), 자체완결형 HTML 문자열 반환(인라인 CSS/SVG, 외부 의존성 0). 미래 SaaS 웹 대시보드가 이 빌더를 재사용.
- 라이터: 기존 `report/writer.py`로 문자열을 `reports/<run_id>.analysis.html`에 저장(suffix=".analysis.html").

### 5.2 synthesis 계약(스키마)
Claude가 매번 동일 구조로 작성하도록 고정. 키: `headline, executive_summary, trend_verdicts[], top_insights[], menu_opportunities[], pricing_benchmark[], content_ideas[], action_plan[], risks[], data_gaps[], radar[]`. (오늘 워크플로우 산출물 구조 + `radar[]`(접목 점수 매긴 인접 트렌드) 추가.) 빌더는 누락 키를 우아하게 생략.

### 5.3 /trend-scan 통합
`.claude/commands/trend-scan.md` 갱신:
- **기본(경량):** 수집 → digest 읽기 → Claude **단일패스**로 `synthesis` JSON 작성 → `chart_data` + `html.build_dashboard` 호출 → `reports/<run_id>.analysis.html` 자동 생성. 마크다운 리포트도 종전대로.
- **`--deep`(선택·무거움):** 5에이전트 워크플로우로 synthesis 생성 후 동일 빌더로 HTML.
- 산출물 경로(MD + HTML) 사용자에게 안내.

## 6. 데이터모델 변경

- `Item.source` Literal에 `"naver_datalab"` 추가 (현재 `Literal["youtube","naver","google_trends","instagram"]` → 확인됨).
- 신규 `type` 값: `"rising_query"`(구글 트렌드 자동발견). `Item.type`은 자유 `str`이라 **스키마 변경 불필요**(확인됨).
- `scan.py`: `DEFAULT_COLLECTORS`에 `naver_datalab` 등록. `radar_watchlist`가 있거나 sources에 포함되면 데이터랩 소스 추가. `radar_watchlist`를 query에 전달.

## 7. 설정 변경

`config/lenses.yaml` menu 렌즈:
```yaml
menu:
  keywords: [베이글, 소금빵, 크로플]
  radar_watchlist: [두바이초콜릿, 탕후루, 약과, 요거트아이스크림, 마라탕후루, 베이커리]
  radar_seeds: [베이글, 디저트, 베이커리]   # 구글 트렌드 자동발견 시드
  sources: [youtube, naver, google_trends, naver_datalab]
```

## 8. 테스트 (TDD)

- `tests/collectors/test_naver_datalab.py`: `_parse`(픽스처 payload → Items), `_fetch` 그룹 배치(monkeypatch httpx)·무자격 스킵.
- `tests/collectors/test_google_trends.py`: rising `_parse`(픽스처) + related_queries 예외 시 코어 보존(베스트에포트).
- `tests/report/test_chart_data.py`: 일별 집계·모멘텀·매트릭스 정확성.
- `tests/report/test_html.py`: `build_dashboard`가 headline·차트 데이터 포인트·action plan·radar 섹션을 포함하는지(문자열 검증). 누락 키 우아한 생략.
- 전체 기존 테스트 회귀 통과.

## 9. 빌드 순서 & 수용 기준

**순서: A → B.**

A 수용 기준:
- `naver_datalab` 수집기가 코어+워치리스트의 30일 일별 지수를 반환(라이브 키로 검증).
- 구글 트렌드 rising 자동발견이 동작하거나(있으면) 빈 응답에도 코어 수집 무손상.
- `python -m nylb scan --lens menu`가 4채널(youtube/naver/google_trends/naver_datalab) 수집, 부분 실패 허용.

B 수용 기준:
- `/trend-scan`이 기본 모드에서 MD + `reports/<run_id>.analysis.html`을 자동 생성.
- HTML이 브라우저에서 렌더(JS 에러 0) — Playwright로 검증.
- `--deep` 옵션이 워크플로우 synthesis로 동일 빌더 HTML 생성.

## 10. 오픈 이슈 / 결정 로그

- **결정:** 범위=음식 인접, 탐지=하이브리드(사용자 확정).
- **결정:** `--deep`는 옵트인(기본은 경량 단일패스) — 일상 스캔 비용 최소화.
- **확인 필요:** 데이터랩 일일 호출 한도(무료, 1,000회/일) — 워치리스트 과다 시 chunk 수 증가. 초기 워치리스트는 ≤6개로 제한.
- **해소됨:** `Item.type`은 자유 `str` → `rising_query` 스키마 변경 불필요. `Item.source`는 Literal → `naver_datalab` 추가 필요.
- **후속(범위 밖):** 데이터랩 쇼핑인사이트 카테고리, 광의 문화 트렌드, 캐싱(`data/cache/`).
