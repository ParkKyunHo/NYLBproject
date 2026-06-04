# 경쟁사 가격 크롤러 (마켓컬리) — 설계문서

- 작성일: 2026-06-04 · 상태: 승인됨(브레인스토밍)
- 선행: `reports/2026-06-04-bakery-pricing-research.md`(경쟁사 가격엔 공식 API 없음 → 2차 소스 크롤링), `docs/.../specs/2026-06-04-nylb-saas-mvp-design.md`(이 크롤러는 그 MVP의 차별화 슬라이스)
- **Due-diligence 검증(2026-06-04):** 마켓컬리 `robots.txt`는 `User-agent: *`에 `/goods/`(상품페이지) **허용**(Disallow는 `/mypage`·`/order`·`/popup`·`/games`·`goods_qna`만). 상품페이지를 일반 httpx GET으로 **200 수신**(안티봇 없음, 브라우저 불필요). 가격은 페이지 내 `__NEXT_DATA__` JSON의 `discountedPrice`(예 8910)·`basePrice`(예 9900), 상품명은 `og:title`("[포비베이글] 크림치즈 200g 8종 (택1) - 마켓컬리").

## 1. 개요 & 목표
경쟁사 제품 **가격을 자동 수집·표시**한다. 공식 API가 없으므로 정형·검증된 **마켓컬리 상품페이지**부터 크롤한다. 기존 `competitor` 렌즈를 사용하고, 결과를 대시보드 "경쟁사 가격" 섹션으로 보여준다. 현 모드(로컬·온디맨드, 유료 API 보류)와 정합.

## 2. 동작 / 아키텍처
```
config(competitor.competitor_products: brand+kurly url)
   → kurly 수집기: 각 URL httpx GET(UA·지연·캐시) → __NEXT_DATA__ 파싱
   → Item(source=kurly, lens=competitor, type=product, metrics={price,base_price})
   → Store(Local/Supabase) → chart_data → html.py "🏷️ 경쟁사 가격" 섹션
```

## 3. 컴포넌트 (기존 패턴 정합)
- **schema:** `Item.source` Literal에 `"kurly"` 추가.
- **`src/nylb/collectors/kurly.py`:** 균일 계약 `collect(query, lens, *, settings, collected_at)` / 순수 `_parse(html, products, lens, collected_at)` / `_fetch(url, settings)`. 다른 수집기와 동일 형태.
  - `_fetch`: httpx GET, 명시 User-Agent, **요청 간 ~1.5s 지연**, **파일 캐시(`data/cache/`)** 로 재요청 최소화(공개 상품페이지만, 로그인·우회 없음).
  - `_parse`: 페이지의 `__NEXT_DATA__` JSON에서 상품명·`discountedPrice`·`basePrice` 추출(og:title은 이름 폴백). 상품당 1 Item.
- **`src/nylb/core/scan.py`:** `competitor_products`를 `query`에 전달. `kurly`를 `DEFAULT_COLLECTORS`에 등록. (`kurly` 소스는 config의 `sources: [kurly]`로 명시 — 다른 렌즈와 동일 방식, 자동추가 불필요.)
- **`config/lenses.yaml`:** `competitor` 렌즈에 `sources: [kurly]` + `competitor_products` 목록.
- **`src/nylb/report/chart_data.py`:** competitor Item을 `competitors: [{brand, product, price, base_price, url}]`로 노출.
- **`src/nylb/report/html.py`:** competitor 데이터가 있을 때만 **"🏷️ 경쟁사 가격" 섹션**(브랜드·상품·가격 표) 렌더.

## 4. 예의바른 크롤링 (법적·ToS)
robots 허용 확인됨. 안전장치: 명시 User-Agent, 요청 간 지연(~1.5s), `data/cache/` 캐시(주 단위 TTL — 가격 변동 주기 대응), 공개 상품페이지만, 접근통제 우회 없음, 출처(url) 표기. (대법원 야놀자 2021도1533: 공개데이터 크롤 우호적이나 약관·접근통제가 변수 — 위 안전장치로 대응.)

## 5. 데이터 모델
```
Item(source="kurly", lens="competitor", type="product",
     title=상품명, url=상품url, author=brand,
     metrics={"price": 할인가(float), "base_price": 정가(float)},
     raw={원 JSON 일부}, collected_at=...)
```

## 6. 캐시 (`data/cache/`)
새 작은 모듈 `src/nylb/collectors/cache.py`: `get_cached(url, ttl_days)` / `put_cache(url, text)` — URL을 해시한 파일명으로 `data/cache/`에 본문 저장, mtime 기반 TTL. `kurly._fetch`가 사용. (재요청 최소화 = 예의 + 속도.)

## 7. 테스트 (TDD)
- `tests/collectors/test_kurly.py`: 저장한 실제 페이지 fixture로 `_parse`(상품명·price 8910·base_price 9900 검증), `_fetch` monkeypatch, `competitor_products` 없으면 빈 결과, collect 예외→CollectError.
- `tests/collectors/test_cache.py`: `put`→`get` 왕복, TTL 만료 시 None.
- `tests/report/test_chart_data.py`: competitor Item → `competitors` 추출.
- `tests/report/test_html.py`: competitor 있을 때 "경쟁사 가격" 섹션 렌더, 없을 때 미렌더.

## 8. 범위
- ✅ IN: kurly 수집기 + competitor 설정/스키마 + 캐시 + 대시보드 경쟁사 섹션.
- ⏭️ OUT(후속): 다이닝코드·네이버 플레이스, NYLB↔경쟁사 자동 가격비교 인사이트, 신메뉴 추적, 스케줄 자동화.

## 9. 수용 기준
- `python -m nylb scan --lens competitor --store nylb`가 포비·LBM 컬리 상품가를 Item으로 수집(포비 price=8910, base_price=9900).
- 대시보드(`report-html`)에 "경쟁사 가격" 섹션 표시. 기존 전체 테스트 무회귀. robots·rate-limit·캐시 준수.

## 10. 결정 로그 / 오픈 이슈
- 시작 소스 = 마켓컬리(사용자). 가격 파싱 = `__NEXT_DATA__`(검증됨); 정확한 JSON 경로는 fixture로 빌드 시 확정.
- 캐시 TTL = 7일(주 단위). competitor 섹션은 데이터 있을 때만 조건부 렌더.
- 오픈: 컬리 미입점 경쟁사(NYLB 자체·코끼리베이글 등) 인스토어 가격은 다음 소스(다이닝코드/네이버)에서 — 후속 슬라이스.
