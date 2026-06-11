# NYLB 시즌·기회 분석 + 디자인 전면 개편 Design Spec

**날짜:** 2026-06-11
**오너 요청:** "신메뉴개발 / 검색관심도 / 어떤 제품이 뜨고 있고 / 시즌 메뉴 / 신메뉴는 어떤걸 준비하면 좋을지 — 포트폴리오급 전문 디자인, 깔끔하고 파워풀하게. 질문 없이 자율 진행."

## 유지하는 원칙 (기존 오너 확정사항)

- **결정론·무LLM·₩0** — 파이프라인에 LLM 없음. 모든 신규 분석은 순수 함수.
- **평결 없음** — "하세요/줄여라" 처방 어휘 금지. 신규 "기회 점수"는 **공식이 공개된 결정론 합산**이며, 점수와 근거를 보여주고 판단은 오너가 한다. (기존 `interest_ranking`이 이미 같은 성격의 결정론 랭킹)
- **자체완결 HTML** — 외부 CDN/폰트/JS 의존 없음.
- **산업-불문 엔진** — 베이글 특화는 config에만.

## 신규 기능 (What)

### S1. 시즌 엔진 — `core/season.py` (신규·순수) + DataLab 다년 수집

오너 질문 "시즌 메뉴는?"에 답하는 토대. 30일 창으로는 계절성을 볼 수 없으므로 **3년 월별** 데이터를 추가 수집한다.

- `naver_datalab.py`: 기존 30일 일별 fetch에 더해 **timeUnit=month, 36개월** fetch를 1회 추가 실행. 같은 앵커-배치·리스케일 로직 재사용. 아이템 type = `search_term_monthly`. API 호출 ~2배(렌즈당 ~20회, 일일 무료쿼터 1,000회 대비 여유).
- `season.monthly_profile(series) -> dict[month, index]`: 달력월별 평균을 전체 평균=100으로 정규화한 **시즌 지수**.
- `season.season_summary(profile, month_now) -> dict`: `peak_months`(지수≥115), `status`(`in_season`/`entering`(다음 1~2달이 피크)/`off`/`no_data`), `now_index`, `next_index`, `coverage_months`(12 미만이면 저신뢰 라벨).
- 보드 `season_calendar`: 전 제품 용어의 12칸 시즌 스트립 + 상태 배지. "지금 시즌 → 진입 임박 → 비수기" 순 정렬.

### S2. 신메뉴 기회 점수 — `core/opportunity.py` (신규·순수)

오너 질문 "신메뉴는 어떤 걸 준비하면?"에 답하는 **투명 공식 점수**. 평결이 아니라 신호의 가중합이며 공식·부분점수를 전부 노출한다.

```
score = 관심도(latest, 0~100) × 0.30
      + 성장(vs_baseline -50%~+100% → 0~100) × 0.30
      + 시즌(다가오는 1~2달 시즌지수 50~200 → 0~100, 무데이터=중립 50) × 0.25
      + 방향(up=100 / steady=60 / down=20) × 0.15
```

- `opportunity.score(cm, season) -> {score, parts, formula}` — parts에 4개 요소의 점수·가중치 동봉.
- 보드 `opportunities`: 레이더 제품 용어(코어·브랜드 제외) 상위 8개. 카드 = 점수 도넛 + 요소 분해 바 + 시즌 스트립 + 관찰 캡션 + 관련 뉴스. 라벨: "공식 공개 결정론 점수 — 판단은 사장님 몫".

### S3. 뜨는 제품 (급상승) — board 조립 확장

- 모든 ContextualizedMetric에 `spark`(최근 30일 일별 값 배열) 추가 → 카드 스파크라인.
- `movers`: 모멘텀 > 0 제품 용어 상위 6 — "지금 뜨는 제품" 섹션.

### S4. 키워드 유니버스 — 시즌 카테고리 확장 (config만)

- menu.radar.seasonal: `[딸기, 복숭아, 무화과, 밤, 고구마, 단호박, 옥수수, 유자]`
- beverage.radar.seasonal: `[아이스티, 뱅쇼, 핫초코, 미숫가루]`

### S5. 디자인 전면 개편 — `report/html.py`

포트폴리오급 에디토리얼 대시보드. 데이터 계약(`renderBoard(DATA, app)`·렌즈 탭)은 유지, 표현만 전면 교체.

- 정제된 타이포·여백 체계, 고급 베이커리 에디토리얼 팔레트(크림 캔버스 + 에스프레소 잉크 + 골드 액센트).
- 히어로 = 브랜드 마스트헤드 + KPI 스탯 밴드. 섹션 앵커 내비(스티키).
- 신규 섹션: ①기회 보드(점수 도넛+분해) ②시즌 캘린더(12칸 히트 스트립) ③지금 뜨는 제품(스파크라인).
- 기존 섹션 전부 유지·재스타일: 관심도 랭킹, 추이 차트(그라데이션 영역+호버), 핵심 신호, 레이더, 브랜드, 미검증 격리, 가격 포지셔닝, 발굴 후보, 데이터 신뢰도.
- 인쇄 친화(@media print) + 반응형. 외부 의존 0.

## 데이터 모델 변화

- 신규 순수 모듈: `core/season.py`, `core/opportunity.py`.
- `naver_datalab.py`: `_fetch(terms, time_unit, days)` 파라미터화, 월별 패스 추가.
- `chart_data.py`: `monthly[source][term] = series` 추출 추가.
- `board.py`: `movers`, `opportunities`, `season_calendar` 키 추가, cm에 `spark`·`season` 부착. 기존 키 전부 유지(웹 리프트 계약 호환).
- `html.py`: `_TEMPLATE` 전면 교체(데이터 계약 동일).

## 테스트 전략

- **S1:** `monthly_profile` 정규화(평균=100)·`season_summary` 상태판정(피크월/진입/비수기/무데이터·저커버리지) 순수 단위. DataLab 월별 fetch는 httpx mock으로 timeUnit=month·36개월 범위·type 단언.
- **S2:** 공식 경계값(클램프)·parts 합=score·처방 어휘 부재 단언. 시즌 무데이터 → 중립 50.
- **S3:** board에 movers/opportunities/season_calendar 존재, 브랜드 제외, spark 길이≤31, 기존 금지 키(`action_plan` 등) 여전히 부재.
- **S5:** 렌더 HTML에 신규 섹션 마커 존재, Playwright 0 JS 오류 + 스크린샷 라이브 검증.

## 범위 경계 (YAGNI)

- 제외: 날씨·이벤트 데이터 결합, 웹 리프트(Phase 2), LLM 노트, 인스타 재활성화.
- 기존 자산 전부 재사용 — 버리는 것 없음.
