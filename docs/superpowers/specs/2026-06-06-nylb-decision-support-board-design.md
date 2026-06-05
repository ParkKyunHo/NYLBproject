# NYLB 의사결정 상황판(Decision-Support Board) Design Spec

**날짜:** 2026-06-06
**하위 프로젝트:** 시장분석 overhaul의 **표현·신뢰 토대**. A(신호 품질)·B(키워드 유니버스) 위에 얹혀, 모은 신호를 *사람이 판단할 수 있는 형태*로 바꾼다. 우선순위상 B보다 먼저 한다(오너 확정).

## 문제 (Why)

오너 피드백: "시스템이 돌아도 시장 파악이 안 되고, 나무 수치 나열이라 관리자가 판단하기 어렵다. 비키 베이글은 잘못된 건데 여전히 HTML에 있다. 향후 내 도움 없이 버튼 클릭으로 쓰고 싶다." 세 가지가 한 뿌리다.

1. **수치 나열 = 도움 없이 못 씀, 같은 문제.** 현재 시스템은 (a) 결정론 파이썬 엔진(수집·집계, `chart_data.py`)과 (b) 분석 두뇌 = Claude(`/trend-scan`에서 `synthesis` JSON을 수동 작성)의 하이브리드다. `build_dashboard(result, synthesis, chart)`에서 **모든 해석·판단은 `synthesis`(=Claude)에 있다**: `headline·executive_summary·trend_verdicts·top_insights·menu_opportunities·action_plan·risks·radar(bagel_fit/angle)`. Claude가 빠지면 남는 건 결정론 `chart`(숫자표)뿐 → 버튼만 눌러 돌리면 정확히 "수치 나열".
2. **유령어 검증 없음.** Google Trends `rising_query` 자동발굴이 미검증 문자열(없는 브랜드·오타)을 그대로 끌어온다. `chart.rising`은 "미검증" 라벨이라도 붙지만, **Claude가 그 유령어를 `synthesis.radar`의 "경쟁 모니터링" 카드로 승격**시킨다(`reports/2026-06-04-menu-ef50e4.analysis.html`의 "비키 베이글 / 포비 베이글 … 경쟁 모니터링"이 실증). 검증 게이트가 없다.
3. **판단의 주체가 잘못됨.** ef50e4 리포트가 "마음에 안 들었던" 진짜 이유 — 그건 Claude가 "베이글이 캐시카우, 소금빵 줄여라" 같은 **평결**을 써넣은 것. 오너가 원한 건 AI의 결론이 아니라, *본인이 2분 만에 판단할 수 있는 깔끔한 상황판*이다.

## 결정 (오너 확정)

대화를 통해 확정한 설계 원칙:

- **시장의 판단은 사용자 고유 영역. AI/Claude는 판단하지 않는다.** 시스템은 수치를 *검증하고 맥락을 붙여* 판단 가능하게 만들 뿐, 결정은 사람이 한다. (선택지 A — 결정론 컨텍스트화만, LLM 없음)
- 만들 물건 = **AI 평결기 ❌ → 의사결정 지원 상황판 ⭕.** 보드는 "여기 신호가 있습니다 / 여길 보세요"에서 멈춘다. **"그러니 이렇게 하세요"(추천·평결·실행계획)는 절대 생성하지 않는다.**
- **₩0 유지.** 파이프라인에 LLM 없음 → 런타임에 Claude·유료 API 불필요. (비용은 변수가 아님이 확인됐으나, 오너 원칙상 판단을 AI에 위임하지 않으므로 LLM을 두지 않는다.)
- **로컬 우선, 서버리스 웹으로 확장 가능하게.** 지금은 내 PC에서 버튼 한 번(한국 IP → 크롤 차단 회피). 나중에 GitHub Actions + Supabase + Next.js/Vercel로 리프트.
- **스택:** Convex 기각(엔진이 파이썬이라 Convex가 못 돌림 + 이미 Supabase 라이브 투자분). Supabase 유지. **대시보드를 로컬 웹앱으로** 지어 미래 웹 리프트의 seam으로 삼는다.
- **"보드 계산"과 "보드 렌더"를 분리** — 같은 `board` 모델(JSON)을 로컬 HTML도, 미래 웹앱도 렌더한다.

## 목표 (What)

`build_dashboard`의 **`synthesis`(Claude) 의존을 제거**하고, 보드를 **100% 데이터-주도**로 생성한다. 각 수치에 검증 마커·맥락·교차검증 캐비엇·신뢰도를 붙이되 평결은 일절 없다. 엔진은 산업-불문 유지(베이글 특화 판단은 config의 keywords/synonyms로만 주입).

## 설계 (How)

네 조각. 각 조각은 독립적으로 이해·테스트 가능하다. 1·2는 순수 함수(₩0, LLM 없음), 3은 데이터-주도 렌더, 4는 로컬 버튼.

### D1. 검증 게이트 (`core/verify.py`, 신규·순수)

비키 베이글 같은 유령어를 *코드로* 떨군다.

- `verify_rising(rising, content_items, datalab_terms, keywords, synonyms, min_corroboration=2) -> {"verified": [...], "unverified": [...]}`.
- 각 rising 용어 `t`를 분류:
  - **verified** = (a) `t`가 알려진 키워드/동의어/레이더 용어와 일치(이미 실재), **또는** (b) DataLab에 `t`의 관심도 신호 존재(>0), **또는** (c) 콘텐츠 채널(youtube/naver) 아이템 중 `t`를 포함하는 게 `min_corroboration`건 이상. 매칭은 `core/signal.is_relevant`의 정규화 부분일치(소문자·공백압축) 재사용 → 필터와 일관.
  - **unverified** = 위 어디에도 안 걸림 → "미검증 원시신호"로 격리.
- 출력 각 항목은 근거(corroboration 건수·소스·DataLab 유무)를 동봉 → 투명성.
- **불변식:** unverified 용어는 레이더·경쟁사 카드에 **영원히 승격되지 않는다.** 미검증 칸에만, "실존 미확인 — 참고만" 라벨로 표시. (Claude의 `synthesis.radar` 승격 경로가 사라지므로 비키 베이글은 구조적으로 차단됨.)
- 비키 베이글: 미지의 용어 + DataLab 신호 없음 + 콘텐츠 뒷받침 0 → unverified → 격리.

### D2. 컨텍스트화 레이어 (`core/context.py`, 신규·순수)

"수치 나열"을 "판단 가능한 수치"로. 평결이 아니라 *수치가 말하는 바*만 기계적으로 기술한다.

- `contextualize(term, daily, peers, now, baseline_days=30) -> ContextualizedMetric`:
  - `value`(=latest), `direction`(▲/▼/→), `vs_baseline`(최근값 vs `baseline_days` 평균 %), `momentum`(기존 series `momentum` 재사용), `rank`(peers 내 순위), `recent_drop`(최근 N일 하락 여부), `freshness`(최신 날짜).
- `cross_source_caveat(datalab_info, gtrends_info) -> str|None`: DataLab(일단위)·Google(시간단위) 발산 시 "시간단위 차이 — 데이터랩 우선" 같은 규칙기반 캐비엇.
- `caption(cm) -> str`: 위 필드를 조합한 **템플릿 한 줄**(규칙기반 NLG, LLM 아님). 예) `"관심도 87/100 · 30일 평균 +12% · 단 최근 3일 하락"`. 문장은 *관찰 기술*에 한정 — "줄여라/늘려라" 등 처방 어휘는 절대 넣지 않는다.

### D3. 상황판 정보구조 + 렌더 (`report/board.py` 신규 + `report/html.py` 개편)

- `board.build_board(result, chart, now) -> dict`(순수): `chart`(기존 결정론 집계) + D1 + D2를 조립한 **board 모델**. `synthesis` 입력 없음.
- `html.build_dashboard(result, chart)` 개편: 내부에서 `build_board` 호출 → board 렌더. **`synthesis` 파라미터 제거.** 템플릿에서 `S.*`(Claude 평결) 사용 섹션 전부 제거/대체.

**board 모델 (board.json) — 미래 웹 리프트의 계약:**
```
board = {
  meta:    {brand, run_id, collected, lens, items, errors, counts, sources_status, trend_label},
  headline:{strongest_signal, biggest_mover(±), freshness, n_collected, n_dropped},  # 데이터 산출, 평결 아님
  core_signals:  [ContextualizedMetric...],   # 베이글/소금빵/크로플 + caption
  radar:         [ContextualizedMetric...],   # verified 인접 트렌드만 (관심도·방향·검증·노출위치)
  unverified_raw:[{term, why, corroboration}],# 비키 베이글이 여기로 격리
  interest_ranking, chart, matrix,            # 기존 결정론 뷰 유지(판단 가능한 수치)
  competitors, comparisons,                   # 기존 가격/포지셔닝 유지 + 결정론 캐비엇
  data_trust:    [{note, severity}],          # 표본 크기·출처 한계(=dropped_by_source + 정적 캐비엇)
}
```

**섹션 IA(관리자가 2분에 판단):** ①한눈에(헤드라인) ②핵심 메뉴 신호 ③레이더(verified) ④미검증 원시신호 ⑤경쟁사 가격/포지셔닝 ⑥데이터 신뢰도/한계. 모든 수치는 ①맥락 ②검증마커 ③교차검증 캐비엇을 단다.

**제거되는 섹션(=Claude 평결):** `trend_verdicts`의 stage/summary, `top_insights`, `menu_opportunities`, `action_plan`, `risks`, `radar`의 `bagel_fit`/`angle`. → 대신 D2 caption(관찰)·검증마커로 대체하거나 삭제(처방성 섹션은 삭제). `momentum`은 결정론(series.mom)이라 ▲▼로 유지. 렌더는 자체완결 HTML(인라인 SVG, 외부 의존 없음) 유지.

### D4. 로컬 원클릭 러너 (버튼) — `report/server.py` 신규 + `nylb dashboard` CLI

- 작은 로컬 웹서버(표준 라이브러리 `http.server` 또는 경량 의존). 라우트 `/`(현재 board HTML 서빙) + `/run`(POST → `run_scan` + `build_board` + `build_dashboard` 재생성 → 갱신). 페이지의 `스캔 실행` 버튼이 `/run`을 호출.
- **네이티브 데스크톱 아님, 로컬 웹앱** — 같은 `/run` 의미·board 모델·렌더가 미래 Vercel/Next.js로 그대로 이식된다.
- `nylb dashboard [--lens menu] [--port 8765]`로 기동. 이게 "내 도움 없이 버튼클릭"의 정식 경로.

## 데이터 모델 변화

- 신규 순수 모듈: `core/verify.py`, `core/context.py`. 신규: `report/board.py`(board 조립), `report/server.py`(로컬 러너).
- `report/html.py`: `build_dashboard(result, chart)`로 시그니처 변경(**`synthesis` 제거**), board 렌더로 템플릿 개편.
- `cli.py`: `nylb dashboard` 서브커맨드 추가.
- `.claude/commands/trend-scan.md`: 합성 스키마 의존 제거. `/trend-scan`은 "스캔 실행 + 보드 열기" 얇은 편의 명령으로 축소(또는 폐기). **보드는 더 이상 Claude 합성을 필요로 하지 않는다.**
- config: 검증 임계값(`min_corroboration` 기본 2)·baseline 윈도우(30일)는 상수(필요 시 config 승격). 신규 베이글 특화 키 없음.

## 테스트 전략

- **D1:** `verify_rising` 순수 단위 — 유령어(뒷받침 0) → unverified; DataLab 신호 있는 용어 → verified; 콘텐츠 ≥2 매칭 → verified; 알려진 키워드 → verified. **비키 베이글 fixture → 격리, radar/competitor에 부재** 단언.
- **D2:** `contextualize`·`caption` 순수 단위 — direction/vs_baseline/rank/recent_drop 정확성, 교차검증 캐비엇 발화, caption에 처방 어휘 부재 단언.
- **D3:** `build_board` — sample chart→board 구조, `synthesis` 미사용, unverified가 radar/competitor와 격리, data_trust에 dropped_by_source 반영, **평결 필드 부재**(action_plan/risks 키 없음). HTML 렌더 Playwright(0 JS 오류).
- **D4:** 로컬 러너 — `GET /` board 서빙, `POST /run`이 스캔 코드패스 호출(수집기 mock)→board 재생성. 라이브 검증: 로컬 버튼→스캔→비키 베이글이 미검증 칸에만·코어 신호에 맥락·캡션·검증마커·처방문구 0건, Playwright 렌더(favicon-404만).

## 범위 경계 (YAGNI)

- **포함:** 검증 게이트(D1), 컨텍스트화(D2), 데이터-주도 보드 재설계 + synthesis 제거(D3), 로컬 웹 러너/버튼(D4).
- **제외(→ Phase 2/나중):** GitHub Actions 크론·`workflow_dispatch`, Next.js/Vercel 웹 리프트, Supabase 읽기전용 공개, **LLM 애널리스트 노트(선택지 B/C)** — 오너가 A를 택했으므로 보류. B 키워드 대량확장.
- **B(키워드 유니버스)와의 관계:** 검증 게이트는 B의 rising 미검증 처리를 흡수한다. B의 키워드 확장은 이 보드 위에 *더 많은 신호*로 쌓이며 충돌하지 않는다. 순서: **이 보드 먼저**(표현·신뢰가 오너 불만의 핵심) → 그다음 B.
- **기존 자산 재사용(버리는 것 없음):** `chart_data.py`(집계), `html.py` 템플릿/SVG, Store seam(Supabase, `--store-backend`), 모든 수집기.

## 미래 확장 seam (Phase 2 — 서버리스 웹)

board 모델이 깨끗한 JSON이고 렌더가 분리돼 있으므로 리프트는 *추가*다: ① GitHub Actions(무료)가 `nylb scan`을 크론+`workflow_dispatch`("버튼")로 실행 → `build_board` → Store seam으로 **Supabase**에 board JSON 저장. ② **Next.js on Vercel**(무료)이 board를 읽어 같은 IA로 렌더. ③ Slice 1의 `SupabaseStore`가 이미 있어 저장 경로는 검증됨. 전 구간 무료티어 = ₩0 SaaS, 포트폴리오 강함, AI 평결 없음 유지.

## 인터페이스/단위 요약

- `verify.verify_rising(rising, content_items, datalab_terms, keywords, synonyms, min_corroboration=2) -> {verified, unverified}` — 무엇: 유령어 격리. 의존: `signal.is_relevant`(순수).
- `context.contextualize(term, daily, peers, now, baseline_days=30) -> ContextualizedMetric` — 무엇: 수치에 방향·기준대비·순위·캡션. 의존: 없음(순수).
- `board.build_board(result, chart, now) -> dict` — 무엇: 데이터-주도 의사결정 보드 조립(평결 없음). 의존: verify·context·chart.
- `html.build_dashboard(result, chart) -> str` — 무엇: board를 자체완결 HTML로 렌더(synthesis 없음). 의존: `build_board`.
- `nylb dashboard` / `report/server.py` — 무엇: 로컬 버튼으로 스캔→보드 갱신. 의존: `run_scan`·`build_board`·`build_dashboard`.

## Self-Review

- Placeholder 없음(모든 조각 구체 함수·파일 지정). 임계값(min_corroboration=2)·baseline(30일)·검증 규칙(키워드/DataLab/콘텐츠≥N) 명시값 확정(튜닝 가능).
- 일관성: 검증·컨텍스트화 매칭이 `signal.is_relevant`와 동일 규칙. board가 build_board·html·테스트에서 동일 의미. synthesis 제거가 데이터모델·CLI·trend-scan.md 전반에 반영됨.
- 범위: 단일 플랜 구현 가능(신규 순수 모듈 2 + board 조립 1 + html 개편 + 로컬 러너 + CLI). 웹 리프트·LLM 노트·B 확장은 분리.
- 모호성: "평결 없음"을 처방 어휘 부재 단언으로 테스트에 고정. unverified 격리를 불변식+테스트로 고정. 보드 계산/렌더 분리를 board 모델(JSON)로 명시.
- 핵심 위험: 일부 실재 신흥어가 뒷받침 부족으로 unverified될 수 있음 → 삭제가 아닌 *격리*(투명 노출)로 완화, 오너가 미검증 칸에서 직접 판단.
