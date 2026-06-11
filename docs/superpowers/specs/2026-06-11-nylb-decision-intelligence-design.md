# NYLB 의사결정 고도화 v4 Design Spec

**날짜:** 2026-06-11
**오너 요청:** "이 시스템으로 앞으로의 F&B 트렌드·제품개발 의사결정을 해야 한다. 추가 기능·개선점을 자율 판단으로 진행. (버그) 관련 뉴스가 제대로 매칭이 안 된다."

## 유지 원칙

결정론·무LLM·₩0·무평결·산업-불문 엔진(특화는 config). 모든 신규 분석은 순수 함수 + I/O 분리.

## D1. 뉴스 관련성 게이트 (버그 수리, P0)

**문제:** `naver_news.collect`가 `query=용어, sort=date`로 최신 기사를 무조건 가져옴 — 용어가 제목에 없거나(본문 매칭) F&B와 무관한 기사(농산물 시세, 정치)가 카드에 붙는다.

**수리:**
- `display=30, sort=date`로 넉넉히 받은 뒤 **2중 게이트 후 상위 N**:
  1. **용어 게이트** — 정규화(`signal.normalize`)한 용어가 제목 또는 요약(description)에 부분일치.
  2. **맥락 게이트** — 제목+요약에 F&B 맥락어 ≥1. 기본 리스트(디저트·카페·베이커리·빵·메뉴·신메뉴·출시·맛집·음료·케이크·프랜차이즈·외식·편의점·팝업·콜라보·시즌한정 등)는 `naver_news._FNB_CONTEXT`, lens config `news_context_terms`로 교체/확장 가능(`scan.query` 경유).
- 게이트 통과 0건이면 그 용어는 뉴스 없음 — **틀린 뉴스보다 빈 칸이 낫다**(오너 불만의 핵심).
- 출력 형태(title/link/date) 불변 → 렌더러 무변경.

## D2. 콘텐츠 버즈 지표 (P1)

검색 관심도와 독립인 두 번째 축 = **콘텐츠 생산량**. 이미 수집한 youtube/naver 아이템에서 용어별 언급을 집계(₩0):

- `board._buzz(term, content_items)` → `{youtube: n, naver: n, views: v}` (`signal.is_relevant` 재사용, 동의어 포함).
- 모든 cm(core/radar/brand)에 `buzz` 부착. 렌더: 카드에 "▶N · ✍N" 칩(0건이면 숨김).

## D3. 델타 보드 — 이력 비교 (P0)

일회성 스냅샷 → **추세 추적 시스템**. "지난 스캔 대비 무엇이 올라왔나"가 지속 의사결정의 핵심.

- 보드 영속화: `data/boards/<run_id>.board.json` (gitignore). 저장/조회는 `report/history.py`(I/O 전담): `save_board(board)`, `load_previous(lens, before_run_id)` — run_id의 날짜 순 정렬로 직전 보드 선택.
- 순수 비교 `report/history.compare_boards(prev, cur)` → `delta`:
  - `rank_moves`: interest_ranking 텀별 prev_rank-cur_rank (`up n`/`down n`/`new`)
  - `score_moves`: opportunity 텀별 점수 변화
  - `meta`: prev_run_id, prev_date
- `multi.build_lenses_dashboard`가 스캔 후 prev 로드 → `board["delta"]` 부착 → 저장. board.py는 순수 유지.
- 렌더: 랭킹 행에 ↑n/↓n/NEW 칩, 기회 카드에 "점수 ±x vs <전회날짜>".

## D4. 연령별 검색 추세 (P1)

제품개발 타깃팅용. DataLab `ages` 필터로 **버킷별 30일 추세**를 기회 상위 용어에 한해 수집.

- 핵심 제약: DataLab ratio는 요청 내 상대값 → **버킷 간 절대량 비교 불가**. 그러나 버킷 내 *추세(모멘텀·방향)는 척도-불문*으로 유효 — 추세만 표시하고 캐비엇 명시.
- `naver_datalab.collect_age_trends(terms, settings)` — 버킷: 10대[2], 20대[3,4], 30대[5,6], 40대[7,8], 50+[9,10,11]. 버킷당 요청(용어 5개/배치), 30일 일별 → `_trend_stats` 모멘텀/방향. 반환 `{term: {bucket: {direction, momentum}}}`.
- 호출 비용: 기회 상위 8용어 × 5버킷 ≈ 10회/렌즈.
- I/O 와이어: `multi.py`에서 board 생성 후 `board["age_trends"]` 부착 (news_context 패턴).
- 렌더: 기회 카드에 "연령 추세 10대→ 20대▲ ..." 칩 행 + 캐비엇 1줄. data_trust에 한계 명시.

## D5. 조합 탐색 (P2)

기회 용어 × 코어 제품의 **기계적 조합 나열**(아이디어 출발점, 평결 아님).

- config 화이트리스트 `pairing_categories`(예: menu에 `[flavor, seasonal]`)에 속한 기회 용어만, 관심도 상위 2개 코어와 조합: "말차×베이글 · 말차×소금빵".
- board 조립 시 opportunity 엔트리에 `pairings: [..]`. 미설정 렌즈는 기능 꺼짐(산업-불문 유지).

## 데이터 모델 변화

- `scan.query` += `news_context_terms`, `pairing_categories` (config 패스스루).
- board += `delta`, `age_trends`; cm += `buzz`; opportunity 엔트리 += `pairings`.
- 신규 `report/history.py`. `data/boards/` gitignore 추가.

## 테스트 전략

- D1: 용어 미포함 기사 탈락 / 맥락어 없는 기사 탈락 / 통과 기사 형태 유지 / 전부 탈락 → 용어 키 부재.
- D2: 동의어 매칭 포함 buzz 집계 정확성, 0건 숨김 데이터.
- D3: compare_boards 순수 단위(up/down/new/score diff), history 저장→직전 로드 왕복, multi 와이어(첫 스캔 delta 없음 → 2회차 delta 존재).
- D4: 버킷 요청 페이로드(ages)·반환 구조·방향 산출(mock httpx), 절대 비교 캐비엇 문구.
- D5: 화이트리스트 카테고리만 pairing 생성, 미설정 시 부재.

## 범위 외 (다음 후보)

GitHub Actions 주간 자동 스캔 + Supabase 게시(웹 리프트 Phase 2), 인스타그램 재활성화(토큰), 상권·POS 결합, 날씨 연동.
