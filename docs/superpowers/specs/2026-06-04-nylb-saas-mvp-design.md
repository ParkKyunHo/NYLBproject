# F&B 시장조사 SaaS MVP — 설계문서

- 작성일: 2026-06-04 · 상태: 승인됨(브레인스토밍)
- 선행: 전체 시스템 스펙 `2026-06-03-nylb-market-research-design.md`, 트렌드레이더 `2026-06-04-nylb-trend-radar-design.md`
- 입력 리서치: `reports/2026-06-04-bakery-pricing-research.md` — 경쟁사 가격/메뉴는 공식 API 부재 → 2차 소스 크롤링이 유일 경로(법적으로 우호적이나 약관 준수 필요)임을 확인.

## 1. 개요 & 목표
NYLB용 트렌드 스캐너를 **F&B 자영업자 전체용 시장조사 SaaS**로 확장한다. 현 자산: 4채널 트렌드 스캔 엔진 + 종합분석 + HTML 대시보드 빌더(`report/html.py`) + SaaS 이음새 4개(Store/Analyzer 추상화, `store_id` 멀티테넌시, CLI/REST 분리).

**확정 설계(사용자):**
- MVP 형태 = **셀프서브 씬 웹앱(트렌드 우선)**
- 데이터 운영 = **테넌트별 맞춤 스캔**(현재 1인 테스트, 비용은 수익화 시점에)
- 스택 = **Next.js + Supabase + Python 워커**
- **현 단계 제약:** 로컬·온디맨드(사용자 명령 시 수집), **유료 LLM API(ApiAnalyzer/Claude API) 보류** → 분석은 현행(결정적 digest + 필요 시 수동 종합) 유지.

## 2. 목표 아키텍처 (North Star)
```
 [사장님] ── Next.js 웹앱(Vercel) ──┐ scan_jobs(큐)
              │ Supabase Auth        ▼
        Supabase Postgres ─────► [Python 워커]
         (RLS 멀티테넌트) ◄─────  · 4채널 스캔 엔진(기존)
              │ scan_results        · 분석(현행 digest, API는 보류)
              ▼                     · html.py 대시보드 빌더
        Next.js 대시보드 표시
```

## 3. 분해(슬라이스) — 멀티서브시스템이라 단계 빌드
- **슬라이스 1 (이번 구현): Supabase 영속화** — 멀티테넌트 스키마 + `SupabaseStore`(Store 이음새 구현) + CLI가 결과를 Supabase에 저장. 로컬·온디맨드에서 동작, **API 불필요**. 방금 만든 프로젝트(`Market_research_FnB` / `tvkhyqgpfiytrzlpkszp`) 사용.
- 슬라이스 2: Python 워커 + 잡 큐(`scan_jobs`) — 큐 폴링→스캔→현행 분석→결과 적재.
- 슬라이스 3: Next.js 웹앱 — Supabase Auth, 온보딩(매장+키워드), 대시보드(HTML 임베드), 스캔 트리거.
- 슬라이스 4(후속): Freemium 게이팅, `ApiAnalyzer`(유료, 보류 해제 시), 경쟁사 가격 크롤러, 결제.

## 4. Non-goals (현 범위 밖)
ApiAnalyzer/유료 LLM, 경쟁사 가격 크롤러, 결제연동, 네이티브 React 대시보드(처음엔 html.py 임베드), 스케줄 자동화, 업종별 공유 캐시 최적화. (모두 후속 슬라이스)

---

## 5. 슬라이스 1 상세 (이번 구현 대상)

### 5.1 Supabase 프로젝트
`Market_research_FnB` (ref `tvkhyqgpfiytrzlpkszp`, region ap-south-1, 현재 테이블 0). 마이그레이션은 **Supabase MCP `apply_migration`**로 적용.

### 5.2 스키마 (`public`, RLS-ready)
- **stores**: `id uuid pk default gen_random_uuid()`, `owner_id uuid null`(후속 auth.users fk), `store_key text unique`(예 `'nylb'`), `name text`, `industry text`, `plan text default 'free'`, `created_at timestamptz default now()`
- **scan_results**: `id uuid pk default gen_random_uuid()`, `store_id uuid references stores(id)`, `run_id text not null`, `lens text`, `payload jsonb not null`(전체 `ScanResult` 직렬화), `created_at timestamptz default now()`, `unique(store_id, run_id)`
- RLS: 두 테이블 `enable row level security`. 슬라이스 1은 단일 사용자/서버라 **service_role 키로 접근**(RLS 우회). `owner_id` 기준 사용자별 정책은 슬라이스 3(Auth)에서 활성화.

### 5.3 `SupabaseStore` (Store Protocol 구현)
`src/nylb/core/store.py`에 `SupabaseStore` 추가 — 기존 `Store` Protocol(`save(ScanResult)->...`, `load(run_id)->ScanResult`)을 그대로 만족.
- `supabase`(파이썬 클라이언트) 사용. 생성자: `SupabaseStore(url, service_key, store_key="nylb")`.
- `save(result)`: `store_key`→`stores.id` 매핑(없으면 upsert 생성) 후 `scan_results`에 upsert(`store_id, run_id, lens, payload=result.model_dump(mode="json")`).
- `load(run_id)`: `scan_results`에서 `(store_id, run_id)` 조회 → `payload`로 `ScanResult.model_validate`.
- 무자격(url/key 없음) 시 명확한 에러.
- **Protocol 정합:** `Store.save` 반환 타입을 `Path` → `str`(locator)로 넓힌다. `LocalJsonStore.save`는 `str(path)`, `SupabaseStore.save`는 `f"supabase://{store_key}/{run_id}"` 반환. (현재 `run_scan`은 `save()` 반환값을 소비하지 않으므로 호출부 무영향 — 회귀 없음.)

### 5.4 설정/연결 배선
- `config.load_settings()`에 `supabase_url`, `supabase_service_key` 추가(.env에서).
- `cli.py`에 `--store-backend [local|supabase]` 플래그(기본 `local`) → `supabase`면 `SupabaseStore` 사용. **기존 로컬 흐름은 기본값으로 보존**, supabase는 옵트인.
- ⚠️ **.env 정비 필요(빌드 전):** 현재 `SUPABASE_connect:` 1개 → `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` 2개로. URL은 MCP `get_project_url`, service_role 키는 사용자가 대시보드(Settings→API)에서 복사.

### 5.5 테스트 (TDD)
- `tests/core/test_supabase_store.py`: 가짜 supabase 클라이언트(monkeypatch)로 ① `save`가 `stores` upsert + `scan_results` upsert를 올바른 payload로 호출, ② `load`가 조회 결과를 `ScanResult`로 복원, ③ 무자격 시 에러. (네트워크 없이 단위 검증)
- (옵션·게이트) 실제 프로젝트 통합 스모크 1회: `save`→`load` 왕복.
- 기존 전체 스위트 무회귀.

### 5.6 의존성
`pyproject.toml`에 `supabase`(파이썬) 추가.

## 6. 슬라이스 1 수용 기준
- `python -m nylb scan --lens menu --store nylb --store-backend supabase`가 `Market_research_FnB`의 `scan_results`에 행 1개 적재.
- `SupabaseStore.load(run_id)`가 동일 `ScanResult` 복원.
- 기존 로컬 흐름(`--store-backend local` 기본)·전체 테스트 무회귀.

## 7. 결정 로그
- 스택 = Next.js + Supabase + Python 워커(사용자).
- 데이터 = 테넌트별 맞춤(사용자).
- 유료 LLM API = **보류**(사용자) → 현행 분석 유지.
- 슬라이스 1 = Supabase 영속화 먼저(로컬·API불필요, 방금 만든 프로젝트 활용).

## 8. 오픈 이슈
- **.env Supabase 연결 변수 정비**(`SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`) — 슬라이스 1 라이브 검증 전 필수.
- `supabase-py`(PostgREST) vs 직접 psycopg — 스펙은 `supabase-py`(JSON 적재 단순).
- RLS 사용자별 정책 전면 활성화는 슬라이스 3(Auth) 시점.
- 리전 ap-south-1(뭄바이)은 한국에서 다소 멀지만 MVP엔 무방 — 변경 안 함.
