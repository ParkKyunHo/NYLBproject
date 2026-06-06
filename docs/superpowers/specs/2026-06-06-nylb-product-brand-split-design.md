# NYLB 제품/브랜드 분리 + 제품 유니버스 확장 Design Spec

**날짜:** 2026-06-06
**하위 프로젝트:** 의사결정 상황판 정밀화 — 검색 관심도를 **제품(일반명사)과 브랜드(고유명사)로 분리**해 각자끼리 비교하고, **제품 유니버스를 확장**한다. 음료·베이커리 두 렌즈 동일.

## 문제 (Why)

오너: "제품과 브랜드를 나누자. 음료 카테고리에서 음료와 브랜드명 분리. 개별 제품은 더 넓고 많은 분석. (베이커리도 마찬가지)." 반복 지적된 한계 — **브랜드(고유명사) 검색량이 제품(일반명사)을 압도**(메가커피 = 아메리카노의 93배). 한 랭킹에 섞이면 브랜드가 차트를 먹고 제품 신호가 안 보인다. 그리고 제품 카테고리가 아직 얕다.

## 결정 (오너 확정)

- **분리 UX = 한 보드 안 두 섹션**(스플릿/별도탭 대비 선택). 각 렌즈 보드에 `📊 제품 관심도`(제품 앵커 기준) + `🏪 브랜드 관심도`(1등 브랜드=100). 한눈에 둘 다.
- **브랜드 재스케일은 추가 수집 없이.** DataLab은 이미 전 용어를 *제품 앵커*에 정규화하므로, 브랜드 부분만 그들의 최댓값으로 다시 나누면 "1등 브랜드 대비 %"가 된다(제품 앵커가 비율에서 약분). 수집기·앵커 불변.
- **제품 유니버스 확장**(음료·베이커리 둘 다, 리서치 키워드). 비용: DataLab 호출 증가(렌즈당 ~12콜) → 스캔이 느려짐(쿼터 내, 수용).
- 산업-불문·LLM 없음·평결 없음 유지. `brands`는 config 카테고리(어떤 업종이든 자기 브랜드).

## 현재 코드와의 정합

`report/board.build_board`는 `interest_ranking`(전 용어 혼합)·`radar`(non-core, category 포함, 브랜드도 섞임)을 만든다. `core/context.contextualize(term, stats, rank, total)`는 stats(series 통계)로 value/direction/caption 생성. 분리는 build_board 후처리 + html 렌더만 바꾼다(수집기/앵커/discover/news 불변).

## 설계 (How) — 3 조각

### P1. 제품 유니버스 확장 (`config/lenses.yaml`)

`brands`는 분리 대상으로 유지하고, 제품 카테고리를 넓힌다(2026 리서치 확정값; 트렌드 항목은 기존 리서치 재사용 — 에어로카노·우베라떼·버터떡 실재 확인). 카테고리 라벨은 임의(엔진 opaque).

음료(anchor 아메리카노):
```yaml
keywords: [아메리카노, 카페라떼, 콜드브루, 바닐라라떼, 말차라떼]
radar:
  coffee:  [에스프레소, 카푸치노, 플랫화이트, 아인슈페너, 카페모카, 카라멜마끼아또, 연유라떼, 디카페인, 에어로카노]
  tea:     [밀크티, 흑당밀크티, 자몽에이드, 레몬에이드, 청귤에이드, 얼그레이, 캐모마일, 유자차, 히비스커스]
  blended: [딸기스무디, 망고스무디, 요거트스무디, 프라푸치노, 빙수]
  trend:   [우베라떼, 흑임자라떼, 쑥라떼, 콤부차, 제로음료, 단백질음료]
  brands:  [스타벅스, 메가커피, 컴포즈커피, 빽다방, 투썸플레이스, 이디야, 더벤티, 폴바셋, 블루보틀, 할리스]
```
베이커리(anchor 베이글) — flavor/pastry/bread로 제품 심화:
```yaml
keywords: [베이글, 소금빵, 크로플, 휘낭시에, 프레첼]
radar:
  flavor:   [말차, 흑임자, 피스타치오, 두바이초콜릿, 솔티드캐러멜, 비스코프, 얼그레이]
  pastry:   [크루아상, 뺑오쇼콜라, 까눌레, 마들렌, 스콘, 에그타르트, 마카롱, 도넛, 파운드케이크]
  bread:    [식빵, 바게트, 치아바타, 깜빠뉴, 브리오슈, 베이글샌드위치]
  adjacent: [탕후루, 약과, 요거트아이스크림, 크룽지, 버터떡, 두쫀쿠]
  brands:   [성심당, 런던베이글뮤지엄, 노티드, 아우어베이커리, 포비, 뚜레쥬르, 파리바게뜨, 이성당]
```
빌드 때 키워드 재확인.

### P2. 제품/브랜드 분리 (`report/board.py`)

build_board에 `brand_category="brands"`(상수) 기준 분리:
- `is_brand(term)` = `cats.get(term) == "brands"`.
- **`radar`**: non-core **AND non-brand** 용어만 contextualize(제품 트렌드 카드).
- **`brand_signals`**(신규): brand 용어를 **재스케일된 stats**로 contextualize. 재스케일 factor = `100 / max(brand latest)`; 각 brand의 series를 factor배 → contextualize가 value=「1등 대비 %」, direction/vs_baseline(비율, 척도불변) 보존, rank는 brand들 사이. (브랜드 0개면 빈 리스트.)
- **`interest_ranking`**: **제품만**(core + non-brand) `[{term, interest, core}]`(제품 앵커 값 그대로).
- **`brand_ranking`**(신규): brand 용어 `[{term, interest=round(latest/max_brand*100,1)}]`, 내림차순.
- core_signals·verify·candidates·news_context·chart·competitors·data_trust 등 나머지 불변. (news_context는 라이저 — 제품/브랜드 모두 첨부 가능; brand_signals 카드에도 뉴스 렌더.)

### P3. 두 섹션 렌더 (`report/html.py`, renderBoard)

- "검색 관심도 랭킹" 섹션 라벨 → **`📊 제품 관심도`**(interest_ranking, 제품만).
- 신규 **`🏪 브랜드 관심도 (1등=100)`** 섹션(brand_ranking 막대) — 바로 아래.
- 레이더 섹션 = 제품 트렌드 카드(radar, 브랜드 빠짐).
- 신규 **`🏪 브랜드 신호`** 카드 그룹(brand_signals — 방향·캡션·뉴스), 레이더와 동일 카드 스타일.
- `renderBoard(DATA, app)` 안에서만 변경(탭 구조 불변). 두 렌즈 자동 동일.

## 데이터 모델 변화

- `config/lenses.yaml`: menu·beverage 제품 카테고리 확장, brands 유지.
- `board` 모델: `interest_ranking`(제품만), 신규 `brand_ranking`·`brand_signals`; `radar`는 브랜드 제외.
- `report/html.py`: 두 랭킹 섹션 + 브랜드 신호 카드.

## 테스트 전략

- **P1:** 확장 config 로드(카테고리 키·brands·anchor).
- **P2:** build_board — interest_ranking에 브랜드 부재, brand_ranking 존재+1등=100 재스케일(예: brand latest [800,400] → [100,50]), radar에 브랜드 부재, brand_signals 존재(direction/caption). 브랜드 0개 렌즈 → brand_ranking/brand_signals 빈 리스트(섹션 자가 숨김). 재스케일이 momentum 부호 보존.
- **P3:** build_multi/build_dashboard HTML에 `📊 제품 관심도`·`🏪 브랜드 관심도`·`brand_ranking`·`brand_signals` 포함; 브랜드 없으면 브랜드 섹션 부재.
- **라이브:** menu+beverage 스캔 → 제품 섹션(아메리카노 앵커: 콜드브루·라떼…)과 브랜드 섹션(메가커피=100·스타벅스…) 분리 렌더, Playwright 0 JS오류.

## 범위 경계 (YAGNI)

- **포함:** 제품/브랜드 분리(2 랭킹 + 브랜드 신호 카드), 브랜드 재스케일(추가 수집 없음), 제품 유니버스 확장.
- **제외:** 브랜드 전용 앵커 2차 DataLab 쿼리(재스케일로 충분), 브랜드 인스토어 가격·신메뉴 심층(=C), 별도 브랜드 탭/렌즈(이번엔 섹션 분리), discover/news 로직 변경.

## 산업-불문 체크리스트

- `brands`는 config 카테고리 — 엔진은 "brands"라는 라벨만 알고 브랜드명은 모름. `brand_category="brands"` 상수 1개가 유일한 결합점(문서화). 다른 업종은 자기 brands 리스트만 config에.

## 인터페이스/단위 요약

- `board.build_board` — +brand_ranking·brand_signals, interest_ranking/radar는 제품만. 의존: contextualize, cats.
- `renderBoard` (JS) — 제품 랭킹 + 브랜드 랭킹 + 브랜드 신호 카드. 의존: DATA.brand_ranking/brand_signals.

## Self-Review

- **Placeholder:** 키워드는 리서치 확정값(빌드 때 재확인). brand_category 상수·재스케일 공식(100/max) 명시.
- **일관성:** `brand_ranking`/`brand_signals` 키가 board·html·테스트 동일. interest_ranking/radar가 "제품만"으로 일관(브랜드는 별 경로). 재스케일은 제품-앵커 약분 논리로 정당.
- **범위:** 단일 플랜(≈4-5 태스크: config + board 분리/재스케일 + html 두 섹션 + 테스트 + 라이브). 수집기 불변.
- **모호성:** 브랜드 value=「1등 대비 %」로 명시(0~100, 제품 0~∞와 다른 척도 — 라벨로 구분). 브랜드 0개 fallback 명시.
