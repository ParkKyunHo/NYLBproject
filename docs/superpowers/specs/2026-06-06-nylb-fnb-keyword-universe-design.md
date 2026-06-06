# NYLB 키워드·관심사 유니버스 v2 (F&B-generic) Design Spec

**날짜:** 2026-06-06
**하위 프로젝트:** 시장분석 overhaul의 **B(키워드·관심사 유니버스)** 재빌드. A(신호 품질)·의사결정 상황판(데이터-주도 보드, shipped) 위에 쌓는다. 옛 spec `2026-06-04-nylb-keyword-universe-design.md`(브랜치 `feat/keyword-universe`)를 **대체**한다 — 그건 보드가 Claude `synthesis`를 쓰던 시절 작성됐고 지금은 보드가 LLM-free이기 때문.

## 문제 (Why)

의사결정 상황판은 깨끗·정직해졌지만 **보는 범위가 좁다** — 핵심 3(베이글·소금빵·크로플) + 평면 radar 몇 개뿐. 오너 피드백: "카테고리가 간소하다. 어떤 베이커리 브랜드가 검색 많이 되나, 어떤 디저트가 새로 뜨나, 베이글·소금빵 말고도 다양한 종류 파악 안 되나?" 네 가지 결손:

1. **유니버스가 좁고 평면적** — 카테고리화·확장 필요(품목/플레이버/포맷/브랜드…).
2. **DataLab 랭킹이 cross-batch 비교 불가** — `naver_datalab`은 5개씩 배치로 호출하고 **각 배치가 독립적으로 0~100 정규화**된다. 그래서 "베이커리 56 vs 베이글 79"는 다른 배치라 직접 비교 불가(현재 랭킹의 숨은 결함). 큰 유니버스를 정확히 줄세우려면 **공통 앵커**로 재정규화해야 한다.
3. **라이저의 "왜"가 안 보임** — 예: 아우어베이커리 검색 +103% 급등(실측). 동력은 시그니처 '더티초코' + 콜라보·리테일 바이럴이나, 정확한 트리거는 일반 검색으론 미확정 → **급상승어에 최신 뉴스 헤드라인을 붙여줘야** "왜"가 보인다.
4. **새로 뜨는 미지의 것을 자동 발굴 못 함** — 알려진 세트의 랭킹만 됨. 진짜 신규는 자동발굴 필요.

## 결정 (오너 확정 — 이번 대화)

- **전체 스코프(B1~B5)를 한 번에.**
- **⭐ 모든 F&B로 확장 가능한 산업-불문 설계.** 카테고리 라벨·키워드·앵커·stopword 확장은 **전부 config 주도**. 엔진 코드엔 베이커리/디저트 리터럴 0 → 치킨·카페·피자 등 다른 업종은 **config만 교체하면 동작**. (기존 "엔진은 산업-불문" 원칙의 강화·확장)
- **LLM 없음·평결 없음 유지.** 발굴 후보·뉴스컨텍스트는 *데이터*로 보드에 표시하고, **판단·승격은 사장님 몫**. (옛 B의 "Claude가 synthesis로 편입 추천(keyword_candidates)" 부분은 **폐기** — 보드엔 Claude가 없다.)
- **브랜드 추적은 B의 한 카테고리**(DataLab 관심도-only, 다른 카테고리와 동일 메커니즘)로 포함. 심층 C(per-brand 신메뉴·SNS·인스토어 가격 모니터링)는 별도.
- 마라탕후루(=노래 제목, 오너 지적) 같은 오탐은 빌드 때 리서치로 거른다.

## 현재 코드와의 정합 (이미 있는 뼈대)

- **티어 라우팅 존재:** `youtube`/`naver`는 `query["keywords"]`만 검색(Tier A=콘텐츠+관심도). `naver_datalab`은 `keywords + radar_watchlist` 전부를 5개씩 배치로 관심도 추적(Tier B 백본). `google_trends`는 `keywords[:5]`만(pytrends 5-cap).
- **보드는 `report/board.build_board(result, chart)` → 데이터-주도(LLM 없음).** 발굴 후보·카테고리 그룹·뉴스컨텍스트는 board 모델 + `html.py` 렌더에 *데이터 섹션*으로 추가(평결 섹션 아님).
- `core/verify`·`core/context`·`core/signal`·`report/chart_data` 재사용.

## 설계 (How) — 5 조각

### B1. 카테고리 유니버스 (config + scan 평탄화) — 산업-불문

- `config/lenses.yaml`의 평면 `radar_watchlist`를 **카테고리 맵 `radar`**로 교체. **카테고리 키는 임의 라벨**(엔진엔 opaque) — bakery 인스턴스 예:
  ```yaml
  menu:
    keywords: [베이글, 소금빵, 크로플, 프레첼, 휘낭시에]   # Tier A (소수 유지)
    anchor: 베이글                                          # 🆕 DataLab 앵커(없으면 keywords[0])
    radar:                                                  # Tier B (interest-only), 카테고리별
      flavor:   [말차, 흑임자, 피스타치오, 두바이초콜릿, 솔티드캐러멜, 비스코프]
      format:   [베이글샌드위치, 오픈샌드위치, 구움과자, 디저트박스]
      adjacent: [탕후루, 약과, 요거트아이스크림, 크룽지, 버터떡, 두쫀쿠]
      brands:   [성심당, 런던베이글뮤지엄, 노티드, 아우어베이커리, 포비, 뚜레쥬르]   # 🆕
    discover_stopwords: [맛집, 카페, 후기, 추천, 먹방, 브이로그, 신상]   # 🆕 선택(F&B 기본셋에 추가)
  ```
- **풀 리스트는 빌드 때 웹+`reports/2026-06-04-bakery-pricing-research.md`로 리서치 확정**(2026 기준). 위는 구조+대표 시드.
- **scan 평탄화(`run_scan`):** `lens_config.get("radar")`가 dict면 → 전 카테고리 term 평탄화해 `query["radar_watchlist"]`(콜렉터 호환, 무변경) + `query["radar_categories"]`(={term:category}). `query["anchor"]`도 전달. dict 아니면 레거시 평면 `radar_watchlist` 폴백. **콜렉터 계약 유지.**
- Tier A `keywords`는 5~7개 유지(YouTube 쿼터·trends 5-cap 보호).

### B2. 앵커링된 DataLab (`collectors/naver_datalab.py`) — cross-batch 비교 가능하게

- 각 5개 배치에 **공통 앵커 키워드(`query["anchor"]`)를 포함**시키고, 응답을 앵커로 **재정규화**: 배치 내 term의 일별 series를 그 배치 앵커 series로 나눠 **"앵커 기준 상대 관심도"**(앵커≈100)로 변환. 이렇게 하면 모든 배치 term이 같은 척도(앵커 대비) → 큰 유니버스 정확히 줄세움.
- `anchor`가 없으면 **레거시(배치 독립 0~100) 폴백** — 무해.
- 산업-불문: 앵커는 config(`anchor`), 코드 하드코딩 없음.
- **표현 변화:** 앵커링 후 값은 0~100을 넘을 수 있다(예: 성심당 ≈ 베이글의 8배). 그래서 **interest_ranking·radar는 "앵커 대비 상대 관심도"**로 라벨(예: "베이글=100 기준"). 코어 키워드 라인차트는 앵커와 같은 배치라 기존 표시 유지 가능. 캡션은 절대 "관심도 N/100"이 아니라 앵커-상대로 정직하게.

### B3. 자동발굴 (`core/discover.py` 신규, 순수, LLM 없음)

- `discover_candidates(result, top_n=10) -> list[dict]`:
  - **known** = `keywords` ∪ 전 radar term ∪ synonyms 값.
  - **stopwords** = 모듈 내 **F&B-generic 기본셋**(맛집·카페·후기·추천·먹방·브이로그·asmr·신상·메뉴 …) **+ config `discover_stopwords` 병합**(산업별 확장).
  - Tier A 콘텐츠(source ∈ {youtube, naver}) title 토큰화 → 1·2gram, 아이템 빈도 + `signal.score_items` 합 + 등장 소스. known·stopword·len<2·숫자 제외, ≥2아이템.
  - **Google rising 병합**(`type=="rising_query"`, known 아닌 것; `value` 부스트; rising은 미검증 리드 라벨).
  - 랭킹 freq→signal. 반환 `[{term, freq, signal, sources, sample_title, from_rising}]`.
- 휴리스틱 명시(형태소분석 아님). **보드 "🔎 발굴 후보" 데이터 섹션** → 사장님이 보고 config에 추가(승인제·비영속). **Claude 추천 없음.**

### B4. 급상승 뉴스컨텍스트 (`collectors/naver_news.py` 신규 + board)

- 두드러진 라이저(board의 core_signals+radar 중 모멘텀/상대변화 상위 N)에 대해 **Naver 뉴스 검색 API**(`/v1/search/news.json`, 기존 Naver 키 재사용)로 최근 헤드라인 K개(제목+링크+날짜) 수집.
- board 모델에 `news_context: {term: [{title, link, date}]}` 추가 → html이 라이저 카드에 "📰 관련 뉴스" 링크로 렌더. **LLM 없음·평결 없음** — 헤드라인+링크만, 사장님이 읽고 "왜 떴나" 판단.
- 산업-불문(아무 term이나 뉴스 검색). 폴라이트: User-Agent·rate·`collectors/cache.py` 캐시 재사용. 뉴스 스코프가 키에 비활성이면 graceful(빈 결과, 전체 죽지 않음).

### B5. Naver 키워드별 검색 + 보드 카테고리 그룹핑

- `collectors/naver.py`: 현재 keywords 합쳐 1쿼리(`sort=sim`) → **키워드별 검색**(youtube 패턴), url dedupe, 1개 실패 tolerate·전부 실패 표면화.
- `chart_data`/`board`/`html`: 검색 관심도 랭킹을 **`radar_categories` 배지로 그룹핑**(flavor/format/adjacent/brands…). 카테고리는 config에서 온 라벨 그대로.

## 데이터 모델 변화

- `config/lenses.yaml`: `radar_watchlist`(평면) → `radar`(카테고리 dict) + `anchor` + 선택 `discover_stopwords`. keywords·synonyms 확장.
- `ScanResult.query`: `radar_categories: dict[str,str]`, `anchor: str` 추가(평탄화 시).
- `collectors/naver_datalab.py`: 앵커 포함 배치 + 앵커-상대 재정규화(폴백 보존).
- 신규: `core/discover.py`(순수), `collectors/naver_news.py`.
- `report/board.py`: board 모델에 `candidates`, `news_context`, term별 `category` 추가.
- `report/html.py`: 카테고리 배지 그룹 + 🔎 발굴 후보 카드 + 📰 라이저 뉴스 링크.
- `collectors/naver.py`: 키워드별 검색.

## 테스트 전략

- **B1:** config `radar` 카테고리 파싱, scan 평탄화(dict→평면+categories, anchor 전달, 레거시 폴백) 순수/통합.
- **B2:** 앵커 정규화 단위 — 배치마다 앵커 포함, 앵커-상대 값 산출(앵커=기준), 두 배치의 term이 동일 척도로 비교됨, anchor 없으면 레거시. httpx mock.
- **B3:** `discover_candidates` 순수 — known·stopword(기본+config)·len·숫자 제외, ≥2아이템, rising 병합, 랭킹, 한/영 토큰, 빈 입력.
- **B4:** `naver_news.collect` httpx mock — 헤드라인 파싱, 스코프 비활성 graceful, 캐시; board가 라이저에만 뉴스 첨부.
- **B5:** naver 키워드별(호출 수·dedupe·복원력) mock; board 카테고리 그룹핑·발굴/뉴스 키 board 모델 존재.
- **산업-불문 테스트:** 가짜 비-베이커리 렌즈(예: keywords=[치킨…], radar={…})로 scan 평탄화·discover·anchor가 도메인 리터럴 없이 동작.
- **라이브 검증:** menu 스캔 1회 → DataLab 확장 radar 전부 커버(앵커-상대 랭킹), 보드에 카테고리 그룹·발굴 후보·라이저 뉴스 렌더(Playwright, favicon-404만), 평결 섹션 0 유지.

## 범위 경계 (YAGNI)

- **포함:** 카테고리 radar(+brands) config + 평탄화, 앵커링 DataLab, 자동발굴(n-gram+rising, 비영속·LLM 없음), 급상승 뉴스컨텍스트, Naver 키워드별, 보드 카테고리 그룹핑.
- **제외(→ 별도/C):** 발굴 후보 영속 원장·자동편입, 형태소분석기(휴리스틱 충분), 라인차트 카테고리 재색칠, Instagram(보류), **심층 C(per-brand 신메뉴·SNS·인스토어 가격 모니터링)**, google_trends를 radar까지 확장(DataLab가 Tier B 백본), **LLM 기반 뉴스 요약/평결**(헤드라인 링크만).

## 산업-불문 체크리스트 (이번 핵심 제약)

- 엔진 코드(`core/*`, `collectors/*`, `report/*`)에 베이커리/디저트/특정 브랜드 리터럴 **0**.
- 카테고리 라벨·키워드·`anchor`·`discover_stopwords` 확장은 **config에만**.
- 다른 F&B 업종은 `config/lenses.yaml`에 자기 keywords/radar/anchor만 넣으면 전 파이프라인(수집·앵커·발굴·뉴스·보드)이 동작 — 코드 변경 0. (SaaS 멀티-업종 seam과 정합)

## 인터페이스/단위 요약

- scan 평탄화 — radar(dict)→radar_watchlist(평면)+radar_categories+anchor. 의존: lens_config.
- `naver_datalab.collect` — 앵커 포함 배치 + 앵커-상대 관심도(폴백). 의존: Naver DataLab API, `query["anchor"]`.
- `discover.discover_candidates(result, top_n)` — 미편입 후보 랭킹(LLM 없음). 의존: result.items·query, `signal.score_items`.
- `naver_news.collect(terms, settings)` — 라이저 최근 헤드라인. 의존: Naver 뉴스 API, cache.
- `board.build_board` — +candidates·news_context·category. `html` — 카테고리 그룹·발굴·뉴스 렌더.

## Self-Review

- **Placeholder:** 카테고리 시드는 대표 예시 — 빌드 때 리서치 확정(의도된 리서치 단계). 그 외 TBD 없음. 앵커 정규화·n-gram(1·2)·stopword 병합·top_n 명시.
- **일관성:** `radar_categories`·`anchor`가 scan·datalab·chart_data·board·html·테스트에서 동일 의미. 콜렉터 radar_watchlist(평면) 계약 유지. 발굴/뉴스는 데이터 섹션(평결 아님) — LLM-free 보드와 정합.
- **범위:** 단일 플랜 가능하나 큼(≈8~10 태스크: config+평탄화, 앵커 datalab, discover, naver_news, naver 키워드별, board+html 출력 3종, 산업-불문 테스트). 2단계 분할도 가능(1차 B1+B2, 2차 B3+B4+B5)이나 오너가 전체 택함.
- **모ho성:** 앵커링 후 값이 0~100 초과 → "앵커-상대"로 표기 명시. 발굴=비영속·승인제·Claude 없음 명시. 카테고리 라벨 opaque·산업-불문 명시.
