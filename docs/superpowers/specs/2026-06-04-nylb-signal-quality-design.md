# NYLB 신호 품질(Signal Quality) Design Spec

**날짜:** 2026-06-04
**하위 프로젝트:** 시장분석 overhaul의 **A — 신호 품질(토대)**. 이후 B(키워드·관심사 유니버스) → C(경쟁사 인텔리전스)가 이 위에 쌓인다.

## 문제 (Why)

현재 시스템은 데이터를 모으지만 "분석"이 얇다. 두 가지 결손:

1. **인기 지표 결손** — `youtube.py`가 `search.list`만 호출해 조회수/좋아요가 응답에 없다. 그래서 `Item.metrics`가 비고(digest에 `[—]`), "인기순"이 사실상 수집순이다.
2. **노이즈** — `naver.py`가 키워드를 `"베이글 소금빵 크로플"`로 합쳐 `sort=date`(최신순)로 검색 → 관련성을 무시하고 최근 글만 긁어 베이글과 무관한 카페 후기(파주 마장호수, 망월동 젤라또)가 상위에 온다. YouTube도 `order=viewCount`라 "20만 만칼로리 챌린지" 같은 고조회수 무관 영상이 뜬다.

키워드만 늘리면(하위 프로젝트 B) 노이즈만 늘어난다. 그래서 신호 품질이 토대다.

## 결정 (오너 확정)

- **랭킹 기준 = "지금 진짜 뜨는 것" = 최신성 × 인기.** 오래된 바이럴보다 최근 화제 우선. 단 관련성 필터를 전제로 둔다(고조회수라도 무관하면 컷).
- **Naver 블로그 = 유지하되 관련성 필터.** `sort=sim`(관련성) + 키워드 매칭으로 정제해 "최근 관련 글" 증거·채널폭 신호로만 쓴다. 인기 랭킹은 YouTube·트렌드·DataLab이 담당.

## 목표 (What)

수집 데이터를 *최신성×인기*로 정렬·필터해서 (1) 인기순이 진짜 인기순이 되고, (2) 무관한 노이즈가 빠지게 한다. 엔진은 산업-불문(industry-agnostic) 유지 — 베이글 특화 판단은 키워드/동의어 config로만 들어온다.

## 설계 (How)

세 조각. 각 조각은 독립적으로 이해·테스트 가능하다.

### A1. YouTube 인기 지표 보강 (`collectors/youtube.py`)

- `search.list`는 **후보 영상 ID 수집**용으로만 쓴다: `order=relevance`, `maxResults≈20`, `regionCode=KR`, `relevanceLanguage=ko`. **핵심 키워드별로 1회씩** 검색해 커버리지를 넓힌다(현재는 합친 1회). 키워드가 늘어날 B를 대비해 **스캔당 검색 횟수 상한**(기본 20)을 둔다.
- 수집한 video ID를 dedupe → **`videos.list?part=statistics,snippet`** 를 50개씩 배치 호출(각 1유닛)해 `viewCount/likeCount/commentCount`와 정확한 `publishedAt`을 얻는다.
- `Item.metrics`에 `views`, `likes`, `comments`(int)를 채운다. `published_at`을 videos.list 기준으로 세팅.
- **쿼터:** search=100유닛/회, videos=1유닛/회, 무료 10,000/일. 핵심 3키워드 → 약 300유닛/스캔. B에서 키워드가 늘어도 상한으로 보호.
- 부분 실패 허용 규약 유지: videos.list가 실패하면 통계 없이 search 결과만(메트릭 0) 반환, 전체 collect는 죽지 않는다.

### A2. 관련성 필터 (노이즈 게이트) — `core/signal.py`(신규), 전 소스 공통

- 순수 함수 `is_relevant(item, keywords, synonyms) -> bool`: `title + " " + (text or "")`를 정규화(소문자·공백 압축)한 뒤, 렌즈 키워드 또는 동의어 중 **1개 이상**이 부분일치하면 True. 시작은 느슨하게(1개 매칭)해 recall 손해를 줄인다.
- **동의어 맵**은 `config/lenses.yaml`의 렌즈에 선택 필드 `synonyms`(예: `{베이글: [bagel], 소금빵: ["소금 빵", salt bread]}`)로 주입. 기본 빈 맵. 엔진은 베이글을 모른다.
- 적용 위치: 수집 직후 **scan 파이프라인의 중앙 필터 단계**(소스-불문, 테스트 용이). DataLab/google_trends처럼 키워드 자체가 아이템인 소스는 필터 면제(이미 키워드).
- **침묵 절단 금지:** 필터로 떨어진 개수를 소스별로 집계해 digest와 `synthesis` data_gaps 참고용으로 노출(`dropped_by_source`). 몇 개를 왜 버렸는지 보이게.
- Naver 수집기: `sort=date` → **`sort=sim`**. (필터는 중앙 단계가 담당하므로 수집기는 정렬만 바꾼다.)

### A3. 최신성×인기 랭킹 (`core/signal.py`)

- 순수 함수들:
  - `popularity(item) -> float`: 소스별 원시 인기. youtube=`views + likes*5 + comments*10`; google_trends/naver_datalab=`interest`(0–100, rising은 기존 `_rising_value` 유지); naver=관련성 베이스(매칭 키워드 수 등 낮은 상수). 인기 지표 없는 소스는 낮게.
  - `recency_weight(item, now) -> float`: `published_at` 나이 기반 감쇠. 최근일수록 1에 가깝고 오래될수록 급감(반감기 ≈ 30일 지수감쇠, 하한 ≈ 0.1). `published_at` 없으면(트렌드/데이터랩=현재 신호) 1.0(중립), Naver 블로그는 `postdate` 사용.
  - `score_items(result, now) -> dict[item_key, float]`: **소스 내 정규화** 후 결합. 각 소스의 `popularity`를 그 소스 최대값(또는 랭크)으로 0–1 스케일 → `signal = norm_popularity * recency_weight`. 이렇게 해야 YouTube 원시 조회수(수십만)가 trends 관심도(0–100)를 압도하지 않는다.
- **소비처 교체:**
  - `analyzer.py`: `_engagement` 대신 `signal_score`로 per-source top-N 정렬 및 cross-channel 타이브레이크. `cross_channel_terms`는 **채널 수 우선**(견고) 유지하되 동점 시 정규화 signal 합으로 정렬.
  - `report/chart_data.py` / `report/html.py`: 랭킹/정렬에 engagement를 쓰던 곳을 signal로 교체(검색 관심도 막대·라인차트는 interest 그대로).
- signal은 분석 시점 계산값이며 수집물에 저장하지 않는다(collector는 원시 메트릭만).

## 데이터 모델 변화

- `Item.metrics`: youtube 아이템에 `views`/`likes`/`comments` 추가(기존 free dict라 스키마 변경 없음).
- `config/lenses.yaml`: 각 렌즈 선택 필드 `synonyms`(기본 없음).
- 새 모듈 `src/nylb/core/signal.py`(순수 함수: is_relevant, popularity, recency_weight, score_items).
- scan 파이프라인: 수집→**중앙 관련성 필터**→저장 사이 단계 추가, `dropped_by_source` 집계를 결과/ digest에 전달.

## 테스트 전략

- **A1:** httpx mock으로 search.list→videos.list 2단계 호출 검증(통계 metrics 채워짐, ID 배치/ dedupe, videos.list 실패 시 graceful). 라이브 테스트는 `@pytest.mark.live`.
- **A2:** `is_relevant` 순수 단위테스트(매칭/비매칭/동의어/대소문자/공백). scan 필터 단계가 무관 아이템을 떨구고 DataLab은 면제, `dropped_by_source` 집계 검증.
- **A3:** `popularity`·`recency_weight`·`score_items` 순수 단위테스트(소스 내 정규화로 YouTube가 trends를 압도하지 않음, 최신 항목이 동일 인기에서 상위). analyzer/ chart_data가 새 점수로 정렬하는지 검증.
- **라이브 검증:** menu 스캔 1회 → digest에 실제 조회수 + 무관 카페 후기 사라짐 + 최신 화제 상위 확인, HTML 렌더(Playwright, favicon 404만).

## 범위 경계 (YAGNI)

- **A에 포함:** YouTube 조회수 보강, 전 소스 관련성 필터, 최신성×인기 랭킹.
- **A에서 제외(→ B/C 또는 별도):** Naver 뉴스/카페 엔드포인트 추가, YouTube 댓글/감성 분석, Instagram(보류 중), 키워드·관심사 확장(=B), 경쟁사 브랜드 모니터링(=C). 동의어 맵은 A에서 최소만(핵심 키워드), 대량 확장은 B.

## 인터페이스/단위 요약

- `signal.is_relevant(item, keywords, synonyms) -> bool` — 무엇: 아이템이 렌즈와 관련 있는지. 의존: 없음(순수).
- `signal.score_items(result, now) -> dict[str, float]` — 무엇: 아이템별 최신성×인기 점수(소스내 정규화). 의존: `popularity`, `recency_weight`.
- `youtube.collect` — 무엇: 검색→통계 보강된 영상 아이템. 의존: YouTube Data API(search.list+videos.list).
- scan 중앙 필터 — 무엇: 무관 아이템 제거 + `dropped_by_source` 집계. 의존: `signal.is_relevant`, 렌즈 config.

## Self-Review

- Placeholder 없음(모든 조각 구체적 함수·파일 지정). recency 반감기·popularity 가중치는 명시값(30일/likes*5/comments*10) — 구현 시 튜닝 가능하나 기본값 확정.
- 일관성: `signal_score`가 analyzer·chart_data·테스트에서 동일 의미. Naver는 인기 베이스 낮음 + 관련성 필터로 일관.
- 범위: 단일 플랜으로 구현 가능(수집기 1개 수정 + 신규 모듈 1개 + 소비처 2곳 + config). 경쟁사/키워드 확장은 분리됨.
- 모호성: "관련성 1개 매칭"으로 필터 강도 명시. 정규화는 "소스 내 max 스케일"로 명시.
