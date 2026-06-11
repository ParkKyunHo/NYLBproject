# NYLB 시장조사 도구

무료 공식 API로 SNS·검색 트렌드를 수집해 **결정론 의사결정 상황판**(LLM 평결 없음)을 자동 생성하는 도구.

상황판 구성: 신메뉴 기회 보드(공식 공개 점수 = 관심도 30%·30일 성장 30%·시즌 25%·방향 15%)
· 시즌 캘린더(네이버 3년 월별 시즌 지수) · 지금 뜨는 제품(모멘텀+스파크라인) · 제품/브랜드
관심도 · 추이 차트 · 미검증 신호 격리 · 가격 포지셔닝 · 데이터 신뢰도.

의사결정 보조 레이어: **전회 스캔 대비 변화**(랭킹 ↑↓/NEW·기회점수 Δ, `data/boards/` 이력)
· **연령별 검색 추세**(기회 상위 용어, 방향만 — 연령 간 절대량 비교 불가) · **콘텐츠 버즈**
(유튜브·블로그 언급량) · **조합 탐색**(기회 용어 × 코어 제품 기계 조합) · **뉴스 게이트**
(제목에 용어 + F&B 맥락어 필수 — 무관 기사 차단).

## 설치
```
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -e ".[dev]"
```

## 설정
1. `.env.example`를 `.env`로 복사하고 키를 채운다(YouTube/Naver 필수, Instagram 선택).
2. `config/lenses.yaml`에서 키워드·해시태그를 매장에 맞게 수정.

## 사용
```
python -m nylb dashboard                       # 로컬 상황판 서버 — '스캔 실행' 버튼 한 번이면 끝
python -m nylb validate --term "복숭아 크림치즈"  # 후보 아이디어 1개 집중 검증 (수요·시즌·연령·버즈·뉴스)
python -m nylb scan --lens menu                # 수집만 → data/raw/<run_id>.json + .digest.md
python -m nylb report-html --run <id>          # 저장된 런으로 상황판 HTML 생성
python -m nylb report-pdf --run <id>           # 상황판을 PDF로 추출 (Edge/Chrome 헤드리스, 의존성 0)
```
대시보드 우하단 **🔬 후보 검증** 입력창에 아이디어를 치면 새 탭에 검증 보드가 열린다.
브랜드 동향 섹션에는 **경쟁 브랜드 신제품 뉴스**(출시·신메뉴·콜라보 게이트 통과분)가 함께 표시된다.
menu 렌즈는 NYLB의 실제 결정 공간(베이글 종류·스프레드·샌드위치 카테고리)을 직접 추적한다.
대시보드 우하단 버튼: **◉ 스캔 실행** · **⬇ PDF** (현재 보드를 PDF 다운로드) · **⬇ HTML**
(자체완결 HTML 다운로드 — 오프라인/공유용). PDF는 설치된 Edge/Chrome을 헤드리스로 사용하며
다른 브라우저를 쓰려면 `NYLB_BROWSER` 환경변수에 실행파일 경로를 지정한다.
Claude Code에서: `/trend-scan 베이글 신메뉴`  → 수집 후 분석 리포트(`reports/`) 생성.

## 테스트
```
pytest            # 단위·통합
pytest -m live    # 실제 API 호출(키 필요)
```
