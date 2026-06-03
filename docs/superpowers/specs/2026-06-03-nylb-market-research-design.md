# NYLB 시장조사 시스템 — 설계 문서 (Design Spec)

- **작성일:** 2026-06-03
- **저장소:** https://github.com/ParkKyunHo/NYLBproject.git
- **상태:** Phase 1 설계 확정, 구현 계획 대기

---

## 1. 개요

**한 줄 정의:** 무료 공식 API로 SNS·검색 데이터를 수집하고, Claude Code가 그것을 해석해
*"지금 무엇이 왜 핫한지 + 우리 매장이 무엇을 하면 좋은지"*를 리포트로 내주는,
온디맨드 베이커리/F&B 시장조사 도구.

**배경:** NYLB는 운영 중인 베이글/베이커리 매장이며, 성장·개선을 위해 인스타그램·네이버·구글·유튜브에서
"지금 시장에서 뜨는 것"을 빠르게 파악하고 실행으로 연결하고자 한다. 기존 도구(네이버 데이터랩, 썸트렌드,
블랙키위, 아이템스카우트 등)는 대부분 *날것의 데이터·차트*를 제공해 사장이 직접 해석해야 한다.
본 시스템은 **해석과 실행 제안까지** 자동화한다.

**포지셔닝:** "바쁜 자영업자를 위한, 데이터가 아니라 **결정**을 주는 AI 시장조사 비서."

---

## 2. 목표 & 비목표

### 목표 (Phase 1)
- 무료(월 ≈ 0원) 범위에서 동작.
- 온디맨드 실행: 사장이 원할 때 돌리면 결과가 나오고, 필요하면 리포트로 출력.
- 다채널 수집(유튜브·네이버·구글, 인스타그램은 조건부) → 공통 스키마로 정규화.
- Claude Code가 분석·요약·**실행 제안(메뉴/콘텐츠)** 까지 수행.
- 향후 SaaS(멀티테넌트, 웹 대시보드, 구독)로 **재작성 없이** 확장 가능한 경계(이음새)를 코드에 미리 심는다.

### 비목표 (Phase 1에서 안 함)
- 상시 가동 웹 대시보드(Phase 4).
- 데이터베이스(Supabase) 연결(Phase 3).
- 서버사이드 유료 LLM 분석(Phase 3 — Phase 1은 Claude Code가 무료로 분석).
- 리뷰 렌즈의 본격 구현(Phase 3 — 무료 제약상 가장 약함).
- 결제·구독·멀티테넌트 운영(Phase 4).
- 자동 스케줄 발송(Phase 2의 cron).

---

## 3. 사용자 & 사용 시나리오

- **주 사용자:** NYLB 매장주(바쁨, 비개발자~준개발자, Windows + Claude Code 사용).
- **시나리오 A (온디맨드):** Claude Code에서 `/trend-scan 베이글 신메뉴` → 수집 → 분석 → 마크다운 리포트.
- **시나리오 B (리포트 출력):** 위 결과를 `reports/`에 저장, 필요 시 PDF/HTML로 내보내기.
- **시나리오 C (독립 실행, Phase 2~):** `python -m nylb scan --lens menu`로 Claude 없이도 수집(자동화 기반).

---

## 4. 범위: 4개 렌즈 & 단계별 로드맵

같은 "수집→분석→리포트" 엔진을 공유하고, **렌즈(관점)** 만 바꾼다 → "엔진 1개 + 렌즈 4개".

| 렌즈 | 무엇을 보나 | 무료 가용성 | 단계 |
|------|------------|------------|------|
| **menu** 신메뉴·상품 | 뜨는 베이커리 품목·플레이버·플레이팅 | ✅ 유튜브·네이버 데이터랩·구글 트렌드·IG 해시태그 | **Phase 1** |
| **content** SNS 콘텐츠 포맷 | 터지는 릴스/숏폼·후킹·해시태그·업로드 패턴 | ✅ 유튜브·IG 인게이지먼트 | **Phase 1** |
| **competitor** 경쟁·벤치마크 | 경쟁사 신메뉴·가격·이벤트·반응 | ✅ IG 경쟁사 조회·유튜브·네이버 | **Phase 2** |
| **review** 고객·리뷰 반응 | 네이버 플레이스·구글·배달앱 리뷰 감성·키워드 | ⚠️ 네이버 플레이스 리뷰 공식 API 없음, 구글 Places 유료 | **Phase 3** |

### 로드맵 (개인 도구 → SaaS 진화)

| 단계 | 범위 | 저장 | 분석 | 인터페이스 | 비용 |
|------|------|------|------|-----------|------|
| **Phase 1 (지금)** | NYLB 전용 · menu+content | 로컬 JSON | Claude Code | 슬래시 커맨드 | 월 0원 |
| **Phase 2** | + competitor · 주간 리포트 자동화(cron) | 로컬 JSON(+DB 준비) | Claude Code | CLI/Claude | 0원 |
| **Phase 3** | + review · 멀티테넌트 데이터 모델 | **Supabase(Postgres)** | 서버사이드 Claude API | REST API | 구독 수익 |
| **Phase 4 (SaaS)** | 다른 F&B 자영업자 온보딩 · 업종 확장 | Supabase(Auth+RLS) | 서버사이드 | **웹 대시보드(Next.js)** + 구독결제 | 유료 |

---

## 5. 아키텍처 (4 레이어)

```
 사용자 → Claude Code:  "/trend-scan 베이글 신메뉴"
                │  (오케스트레이션)
                ▼
   ┌───────────────────────────┐      무료 공식 API 호출
   │  Collection Engine        │  ── YouTube / Naver / Google / IG
   │  (독립 Python 모듈)        │
   └───────────┬───────────────┘
               ▼
       data/raw/<run_id>.json   ← 소스 달라도 "공통 스키마"로 정규화
               │
               ▼
   ┌───────────────────────────┐
   │  Claude Code = 분석 두뇌   │  ← 추가 비용 0원
   │  • 트렌드 패턴 해석         │
   │  • "왜 핫한지" 인사이트     │
   │  • 실행 제안(메뉴/콘텐츠)   │
   └───────────┬───────────────┘
               ▼
     reports/2026-06-03-bagel-menu.md  (+ 선택: PDF/HTML)
```

**레이어**
1. **Collection Engine (독립 Python):** 소스별 collector. 입력=키워드/해시태그/경쟁사계정 + 렌즈,
   출력=정규화 JSON. *Claude 없이도 단독 실행 가능 → cron 자동화/REST 노출 길이 열림.*
2. **Normalizer (공통 스키마):** 소스가 달라도 하나의 `Item` 형태로 통일.
3. **Claude Code 스킬 (운전석+두뇌):** 슬래시 커맨드가 collector 실행 → 정규화 데이터 읽고 → 해석·제안.
4. **Report Writer:** 마크다운 리포트 저장(+선택적 PDF/HTML).

---

## 6. 모듈 구조 & 경계 (인터페이스 계약)

각 모듈은 "하나의 명확한 역할 + 정의된 인터페이스"로 분리한다(테스트·교체 용이).

| 모듈 | 역할 | 인터페이스(계약) |
|------|------|-----------------|
| `collectors/{youtube,naver,google_trends,instagram}.py` | 소스별 수집 | `collect(query: dict, lens: str) -> CollectResult` |
| `core/schema.py` | 공통 데이터 모델 | `Item`, `ScanResult`, `CollectResult`, `CollectError` |
| `core/store.py` | 결과 저장/로드 (이음새 🗄️) | `Store.save(result)`, `Store.load(run_id)`; 구현체 `LocalJsonStore` |
| `core/analyzer.py` | 분석 추상화 (이음새 🧠) | `Analyzer.analyze(result) -> Analysis`; Phase1 구현 `ClaudeCodeAnalyzer` |
| `config.py` | 설정/키 로딩 | `load_config()`, `load_lenses()` |
| `cli.py` | 독립 실행 진입점 (이음새 🔌) | `python -m nylb scan --lens <lens> [--store nylb]` |
| `report/writer.py` | 리포트 생성 | `write(analysis, run_id) -> path` |
| `.claude/commands/trend-scan.md` | Claude 오케스트레이션 | 슬래시 커맨드 프롬프트 |

**데이터 흐름:** 커맨드 → collector 실행 → `CollectResult` → `Store.save` → `data/raw/<run_id>.json`
→ Claude가 읽고 분석 → `report/writer` → `reports/`.

---

## 7. 데이터 모델 (Pydantic v2, DB 친화)

DB(Supabase Postgres)와 1:1로 매핑되도록 평탄하고 명시적으로 설계. 모든 레코드에 `store_id`(테넌시 이음새 🏢).

```python
class Item(BaseModel):
    store_id: str                 # 기본 "nylb" — 멀티테넌트 이음새
    source: Literal["youtube","naver","google_trends","instagram"]
    lens: Literal["menu","content","competitor","review"]
    type: str                     # 예: video, blog, search_term, hashtag_media
    title: str
    url: str | None = None
    text: str | None = None       # 캡션/스니펫
    author: str | None = None
    metrics: dict[str, float] = {} # views, likes, comments, search_ratio 등 유연
    published_at: datetime | None = None
    collected_at: datetime
    raw: dict = {}                # 원본 페이로드(디버깅·재처리용)

class CollectError(BaseModel):
    source: str
    message: str

class CollectResult(BaseModel):   # collector 1회 호출 결과(부분 실패 허용)
    items: list[Item] = []
    errors: list[CollectError] = []

class ScanResult(BaseModel):      # 1회 스캔 전체
    run_id: str
    store_id: str
    lens: str
    query: dict                   # 사용된 키워드/해시태그/계정
    items: list[Item] = []
    errors: list[CollectError] = []
    started_at: datetime
    finished_at: datetime
```

> `run_id`/`collected_at` 등 시간값은 호출 시점에 주입(테스트 결정성 확보).

---

## 8. 데이터 출처별 가용성 & 수집 전략

| 출처 | 공식 수집 수단 | 현실 / 제약 |
|------|---------------|------------|
| **유튜브** | Data API v3 (무료 할당량 ~10,000 units/day) | ✅ 가장 깔끔. 검색·조회수·댓글까지 합법·안정 |
| **네이버** | 검색 API + 데이터랩(검색어 트렌드) | ✅ 무료 앱등록. 단 **플레이스 리뷰는 공식 API 없음** |
| **구글** | 트렌드(pytrends, 비공식) · Places API(유료) | ⚠️ 검색 트렌드는 쓸만, 리뷰/지도는 유료 |
| **인스타그램** | Graph API (사장님 Meta dev 계정) | ⚠️ **해시태그 검색**(7일당 30개 한도, 게시자명 제약) + **경쟁사 계정 조회**(아는 아이디만). 일반 검색 불가. 초기 dev 모드 가능, 본격 운영 시 앱 검수 필요 가능 |

**Phase 1 수집 전략 (월 0원, 공식 API 우선):**
- 기본 소스 = 유튜브 + 네이버(검색/데이터랩) + 구글 트렌드.
- 인스타그램 = **조건부(best-effort)**: `.env`에 Graph 토큰이 있으면 해시태그/경쟁사 수집, 없으면 스킵하고 리포트에 표기.
- 모든 한도/필드는 **구현 착수 시 최신 공식 문서로 재확인**(정책 변동 가능). → 구현 1순위 작업 = 각 API 가용성 PoC.

---

## 9. SaaS 진화 경로 & 이음새 4개

**원칙:** Phase 1은 가볍고 무료로, 단 SaaS로 자라날 경계선은 지금 긋는다.
NYLB 매장 자체가 **첫 고객(디자인 파트너)** — 내 매장에서 검증 후 다른 F&B 자영업자에게 확장.

**지금 코드에 심는 이음새 4개** (나중에 "재작성"이 아니라 "어댑터 추가"로 확장):
1. **🗄️ 저장소 추상화** — `Store` 인터페이스. Phase1 `LocalJsonStore` → SaaS `SupabaseStore`. collector는 저장 위치를 모름.
2. **🧠 분석기 추상화** — `Analyzer` 인터페이스. Phase1 `ClaudeCodeAnalyzer`(파일 읽기·세션 분석, 무료) → SaaS `ApiAnalyzer`(서버에서 Claude API).
3. **🏢 테넌시** — 모든 데이터에 `store_id`(기본 `"nylb"`). 멀티테넌트 전환 = 데이터 키 추가.
4. **🔌 인터페이스 분리** — 수집 엔진은 순수 서비스 함수. Phase1 CLI/Claude 호출 → SaaS FastAPI REST가 같은 함수 재사용.

**SaaS 핵심 설계 결정 (Phase 3~4, 방향 확정):**
- **타겟:** F&B 전체(식당·카페·베이커리). 검증은 NYLB(베이커리)부터.
- **차별화:** "데이터가 아니라 결정을 판다" — 멀티채널 통합 + AI 액션 제안 + F&B 특화 + 자연어 온디맨드.
- **데이터 아키텍처(핵심):** 트렌드는 공유 자산. **업종/키워드별 중앙 1회 스캔 → 캐시 → 모든 테넌트 공유.**
  테넌트 *전용* 수집은 그 가게의 **경쟁사·리뷰**뿐. → API 한도/비용 문제 최소화, 가입자 증가 시 단위비용 하락.
- **요금제:** **프리미엄(Freemium)** — 무료=공유 트렌드 주간 리포트(서빙비용≈0), Pro=온디맨드 무제한 + 내 경쟁사·리뷰·액션 제안.
- **업종 확장:** 엔진은 업종 무관. 베이커리 지식은 코드가 아니라 **config + Claude 분석 프롬프트**에 위치 → 카페·식당 확장 = 설정 추가.

---

## 10. 기술 스택 & 프로젝트 구조

| 영역 | 선택 | 이유 |
|------|------|------|
| 언어 | Python 3.11+ | 수집·분석 표준, FastAPI 백엔드로 자연 확장 |
| 패키지 관리 | uv (또는 venv+pip) | 빠르고 현대적, Windows OK |
| 데이터 모델 | Pydantic v2 | 검증 + JSON↔DB 매핑, Postgres 스키마와 1:1 |
| HTTP | httpx | 깔끔, 비동기 가능 |
| 설정 | python-dotenv + PyYAML | `.env`(키) + `lenses.yaml`(렌즈) |
| 구글 트렌드 | pytrends | 무료(비공식) |
| 리포트 | Jinja2 → 마크다운 | (PDF는 Phase 2 선택) |
| 테스트 | pytest | 표준 |
| Claude 연동 | `.claude/commands/` | 슬래시 커맨드 |

```
NYLBproject/
├─ .claude/commands/trend-scan.md   # Claude 오케스트레이션(운전석+두뇌)
├─ src/nylb/
│  ├─ core/
│  │  ├─ schema.py        # Item, ScanResult 등 (store_id 포함, DB 친화)
│  │  ├─ store.py         # 🗄️ Store 인터페이스 + LocalJsonStore
│  │  └─ analyzer.py      # 🧠 Analyzer 인터페이스 + ClaudeCodeAnalyzer
│  ├─ collectors/
│  │  ├─ base.py          # collect(query, lens) 계약
│  │  ├─ youtube.py  naver.py  google_trends.py  instagram.py
│  ├─ report/
│  │  ├─ writer.py
│  │  └─ templates/weekly.md.j2
│  ├─ config.py
│  └─ cli.py              # 🔌 `python -m nylb scan ...` 독립 실행
├─ config/
│  ├─ lenses.yaml         # 렌즈별 키워드·해시태그·경쟁사
│  └─ industries.yaml     # F&B 하위 업종 템플릿(확장용)
├─ data/raw/   data/cache/   reports/      # (gitignore)
├─ tests/
├─ .env.example   .gitignore   pyproject.toml   README.md
```

---

## 11. 설정 · 키관리 · 레이트리밋 · 에러처리

- **🔑 키 관리:** 모든 키는 `.env`(커밋 금지), `.env.example`만 커밋.
  필요 키: `YOUTUBE_API_KEY`, `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET`, `INSTAGRAM_GRAPH_TOKEN`(조건부).
- **⚙️ 설정 예시** (`config/lenses.yaml`):
  ```yaml
  nylb:                    # store_id (테넌시 이음새)
    industry: bakery
    lenses:
      menu:
        keywords: [베이글, 소금빵, 크로플]
        sources: [youtube, naver_datalab, google_trends]
        instagram_hashtags: [베이글맛집, 베이글]
      content:
        keywords: [베이글, 베이커리]
        sources: [youtube]
        instagram_hashtags: [베이글맛집]
      competitor:
        instagram_accounts: [경쟁사아이디]
        youtube_channels: []
  ```
- **🚦 레이트리밋 가드:** IG 7일당 30해시태그 한도 추적; YouTube 일일 쿼터 추정;
  **동일 쿼리 캐싱**(N시간 내 재호출 방지, `data/cache/`)으로 무료 한도 보호.
- **🛡️ 에러 처리 (부분 실패 허용):** 한 소스가 죽어도 나머지는 진행.
  각 collector는 `CollectResult{items, errors}` 반환 → 리포트에 "IG 수집 실패" 표기, 나머지는 정상 산출.
  명확한 로그(어떤 소스가 왜 실패했는지).

---

## 12. 테스트 전략

- **collector 단위테스트:** 모킹된 API 응답(JSON 픽스처)으로 파싱·정규화 검증(실 호출 없음).
- **schema 테스트:** Pydantic 직렬화/역직렬화 라운드트립.
- **store 테스트:** `LocalJsonStore` 저장→로드 왕복 일치.
- **통합 테스트:** 1개 렌즈 end-to-end(모킹 소스 → 정규화 → 저장 → 리포트 생성).
- **라이브 스모크:** 실제 API 호출은 `@pytest.mark.live`로 분리(키 있을 때만 실행).

---

## 13. Phase 1 수용 기준 (Acceptance Criteria)

Phase 1이 "완료"되려면:
1. `python -m nylb scan --lens menu` 실행 시, 설정된 소스(유튜브·네이버·구글, IG는 토큰 있으면)에서 수집해
   정규화 JSON을 `data/raw/<run_id>.json`에 저장하고, **단일 소스 실패에도 중단되지 않는다.**
2. `/trend-scan` 슬래시 커맨드가 collector를 실행하고, Claude가 데이터를 읽어
   `reports/`에 마크다운 리포트를 생성한다. 리포트는 최소: **(a) 핫 키워드/항목 TOP, (b) 채널별 근거,
   (c) "그래서 무엇을 하라" 액션 제안(메뉴/콘텐츠).**
3. 테스트(모킹 collector·schema·store·1개 렌즈 e2e) 통과.
4. 비밀키는 `.env`에만 있고 커밋되지 않는다(`.env.example`만 커밋).

---

## 14. 오픈 이슈 / 향후 결정

- **GTM(#6):** 자영업자 도달 경로·초기 고객 확보 — Phase 4에서 구체화.
- **운영 리스크(상세):** IG 데이터 *재배포* 약관(유료 고객 대상), 개인정보보호법(리뷰 익명화·집계) — Phase 3~4.
- **PDF/HTML 내보내기:** Phase 2 선택.
- **각 API 실제 한도/필드:** 구현 1순위 PoC로 재확인(정책 변동 가능).
- **로컬 폴더명 불일치:** 작업 폴더 `C:\NYLB_market_research` ↔ 원격 `NYLBproject` — origin 연결로 해소(푸시 시 NYLBproject 채움).

---

## 15. 결정 요약 (Decision Log)

| 주제 | 결정 |
|------|------|
| 매장 단계 | 운영 중(성장·개선) |
| 스캔 초점 | 4개 렌즈(menu·content·competitor·review) 모두, 단 1단계는 menu·content |
| 결과물 형태 | 온디맨드 우선 + 필요 시 리포트 출력 |
| 수집 전략 | 공식 API 우선(무료), IG는 사장님 Meta dev 계정으로 조건부 |
| 월 예산 | ≈ 0원 (AI 분석은 Claude Code가 무료 수행) |
| 아키텍처 | 하이브리드(독립 Python 엔진 + Claude Code 분석) |
| 확장성 | SaaS(멀티테넌트·웹 대시보드·Supabase·구독) 대비 이음새 4개 선설계 |
| SaaS 타겟 | F&B 전체(베이커리부터 검증) |
| SaaS 요금제 | 프리미엄(무료 공유트렌드 / Pro 테넌트 전용) |
| 기술 스택 | Python 3.11+ · Pydantic v2 · httpx · pytest · Jinja2 |
