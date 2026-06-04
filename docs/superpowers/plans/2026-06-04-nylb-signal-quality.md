# NYLB 신호 품질(Signal Quality) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 수집 데이터를 *최신성×인기*로 정렬·필터해 "인기순이 진짜 인기순"이 되고 무관한 노이즈가 빠지게 한다(시장분석 overhaul의 토대 A).

**Architecture:** 새 순수모듈 `core/signal.py`(관련성 필터 + 최신성×인기 점수)를 만들고, ① YouTube 수집기를 `search.list`+`videos.list` 2단계로 바꿔 조회수/좋아요를 채우고, ② Naver를 `sort=sim`+postdate로 바꾸고, ③ `run_scan`에 중앙 관련성 필터를 끼우고, ④ `analyzer`의 랭킹을 engagement→signal로 교체한다. 베이글 특화 지식은 전부 config(키워드·동의어)로만 주입 — 엔진은 산업 불문.

**Tech Stack:** Python 3.12 (`.\.venv\Scripts\python.exe`), Pydantic v2, httpx, pytest. git/python은 PowerShell 도구로.

---

## File Structure

- `src/nylb/core/signal.py` — **신규**. 순수 함수: `is_relevant`, `filter_relevant`(관련성 게이트) / `popularity`, `recency_weight`, `score_items`, `_item_key`(최신성×인기 점수).
- `src/nylb/collectors/youtube.py` — `search.list`→`videos.list` 2단계, metrics(views/likes/comments) + published_at 채움.
- `src/nylb/collectors/naver.py` — `sort=date`→`sort=sim`, postdate→published_at 파싱.
- `src/nylb/core/scan.py` — 수집 직후 중앙 관련성 필터 적용, `dropped_by_source` 집계.
- `src/nylb/core/schema.py` — `ScanResult`에 `dropped_by_source: dict[str,int]` 추가.
- `src/nylb/core/analyzer.py` — 랭킹/교차키워드를 `signal` 점수로 교체 + 필터 제외 섹션.
- `config/lenses.yaml` — menu 렌즈에 `synonyms`(선택, 기본 없음).
- 테스트: `tests/core/test_signal.py`(신규), `tests/collectors/test_youtube.py`(재작성), `tests/collectors/test_naver.py`, `tests/core/test_scan.py`, `tests/core/test_analyzer.py`, `tests/test_config.py`.

**테스트 규약(이 레포):** 수집기 테스트는 `monkeypatch.setattr(<mod>.httpx, "get", fake)`로 HTTP를 가짜화한다. 순수 함수는 직접 단위테스트. 라이브는 `@pytest.mark.live`(기본 제외). digest 테스트는 문자열 포함으로 검증.

**범위 메모:** 대시보드(`report/chart_data.py`·`report/html.py`)는 아이템을 engagement로 정렬하는 코드가 없다(검색 관심도 막대·라인차트는 interest를 직접 사용). 따라서 A에서 chart_data/html은 **변경 없음** — 신호 품질 개선은 digest를 통해 synthesis 품질로 전달된다.

---

## Task 1: signal.py — 관련성 필터 (is_relevant / filter_relevant)

**Files:**
- Create: `src/nylb/core/signal.py`
- Test: `tests/core/test_signal.py`

- [ ] **Step 1: Write the failing tests**

`tests/core/test_signal.py` 생성:

```python
from datetime import datetime, timezone

from nylb.core.schema import Item
from nylb.core.signal import is_relevant, filter_relevant

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)


def _yt(title, text=None):
    return Item(source="youtube", lens="menu", type="video", title=title,
                text=text, collected_at=NOW)


def test_is_relevant_matches_keyword_in_title():
    assert is_relevant(_yt("베이글 신메뉴 리뷰"), ["베이글", "소금빵"]) is True


def test_is_relevant_matches_in_text():
    assert is_relevant(_yt("디저트 브이로그", "오늘은 소금빵 먹방"), ["소금빵"]) is True


def test_is_relevant_false_when_unrelated():
    assert is_relevant(_yt("20만 기념 만칼로리 챌린지"), ["베이글", "소금빵"]) is False


def test_is_relevant_synonym_match():
    syn = {"베이글": ["bagel"]}
    assert is_relevant(_yt("Best BAGEL in Seoul"), ["베이글"], syn) is True


def test_filter_relevant_drops_off_topic_and_counts():
    items = [_yt("베이글 리뷰"), _yt("먹방 챌린지"), _yt("소금빵 만들기")]
    kept, dropped = filter_relevant(items, ["베이글", "소금빵"])
    assert [it.title for it in kept] == ["베이글 리뷰", "소금빵 만들기"]
    assert dropped == {"youtube": 1}


def test_filter_relevant_exempts_trend_and_kurly_sources():
    items = [
        Item(source="google_trends", lens="menu", type="search_term", title="탕후루", collected_at=NOW),
        Item(source="kurly", lens="competitor", type="product", title="포비 크림치즈", collected_at=NOW),
    ]
    kept, dropped = filter_relevant(items, ["베이글"])
    assert len(kept) == 2          # trend/kurly are exempt from the gate
    assert dropped == {}


def test_filter_relevant_noop_without_keywords():
    items = [_yt("아무 제목")]
    kept, dropped = filter_relevant(items, [])
    assert len(kept) == 1 and dropped == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_signal.py -v`
Expected: FAIL — `ModuleNotFoundError: nylb.core.signal`.

- [ ] **Step 3: Write minimal implementation**

`src/nylb/core/signal.py` 생성:

```python
from __future__ import annotations

import re

from nylb.core.schema import Item

_WS = re.compile(r"\s+")

# Trend sources (google_trends, naver_datalab) ARE the keyword, and kurly is
# competitor products matched by URL — all exempt from the relevance gate.
FILTERABLE_SOURCES = {"youtube", "naver", "instagram"}


def _norm(text: str | None) -> str:
    return _WS.sub(" ", (text or "").lower()).strip()


def is_relevant(item: Item, keywords: list[str],
                synonyms: dict[str, list[str]] | None = None) -> bool:
    """True if any lens keyword (or a configured synonym) appears in title+text."""
    synonyms = synonyms or {}
    hay = _norm(f"{item.title} {item.text or ''}")
    terms: list[str] = []
    for kw in keywords:
        terms.append(kw)
        terms.extend(synonyms.get(kw, []))
    return any(_norm(t) in hay for t in terms if t)


def filter_relevant(items: list[Item], keywords: list[str],
                    synonyms: dict[str, list[str]] | None = None
                    ) -> tuple[list[Item], dict[str, int]]:
    """Drop off-topic items from FILTERABLE_SOURCES; return (kept, dropped_by_source).
    No-op when keywords is empty (e.g. competitor lens)."""
    if not keywords:
        return list(items), {}
    kept: list[Item] = []
    dropped: dict[str, int] = {}
    for it in items:
        if it.source in FILTERABLE_SOURCES and not is_relevant(it, keywords, synonyms):
            dropped[it.source] = dropped.get(it.source, 0) + 1
            continue
        kept.append(it)
    return kept, dropped
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_signal.py -v`
Expected: PASS (7 tests green).

- [ ] **Step 5: Commit**

```powershell
git add src/nylb/core/signal.py tests/core/test_signal.py
git commit -m "feat: add relevance filter (signal.is_relevant/filter_relevant)"
```

---

## Task 2: signal.py — 최신성×인기 점수 (popularity / recency_weight / score_items)

**Files:**
- Modify: `src/nylb/core/signal.py` (append)
- Test: `tests/core/test_signal.py` (append)

매칭 규칙: 소스별 원시 인기를 그 소스 최대값으로 0–1 정규화 → `recency_weight`(반감기 30일 지수감쇠) 곱. trends/datalab은 published_at 없으니 recency=1.0(현재 신호). naver는 인기지표 없어 베이스 1.0 → 정규화 후 모두 동률 → recency가 순서 결정.

- [ ] **Step 1: Write the failing tests**

`tests/core/test_signal.py` 끝에 추가:

```python
from nylb.core.schema import ScanResult
from nylb.core.signal import popularity, recency_weight, score_items, _item_key


def test_popularity_by_source():
    yt = Item(source="youtube", lens="menu", type="video", title="t",
              metrics={"views": 1000, "likes": 10, "comments": 2}, collected_at=NOW)
    assert popularity(yt) == 1000 + 10 * 5 + 2 * 10
    gt = Item(source="google_trends", lens="menu", type="search_term", title="베이글",
              metrics={"interest": 80}, collected_at=NOW)
    assert popularity(gt) == 80
    nv = Item(source="naver", lens="menu", type="blog", title="t", collected_at=NOW)
    assert popularity(nv) == 1.0


def test_recency_weight_decays_with_age():
    fresh = Item(source="youtube", lens="menu", type="video", title="t",
                 published_at=NOW, collected_at=NOW)
    old = Item(source="youtube", lens="menu", type="video", title="t",
               published_at=datetime(2026, 4, 4, tzinfo=timezone.utc), collected_at=NOW)
    undated = Item(source="google_trends", lens="menu", type="search_term", title="t",
                   collected_at=NOW)
    assert recency_weight(fresh, NOW) == 1.0
    assert recency_weight(old, NOW) < recency_weight(fresh, NOW)   # ~60 days → decayed
    assert recency_weight(undated, NOW) == 1.0                     # undated = neutral


def test_score_items_normalizes_within_source():
    # YouTube raw views are huge vs trends interest 0-100; normalization must
    # keep them comparable (each source's max → 1.0).
    yt_big = Item(source="youtube", lens="menu", type="video", title="big",
                  url="y1", metrics={"views": 500000}, collected_at=NOW)
    gt = Item(source="google_trends", lens="menu", type="search_term", title="베이글",
              url="g1", metrics={"interest": 100}, collected_at=NOW)
    res = ScanResult(run_id="r", store_id="nylb", lens="menu", query={},
                     items=[yt_big, gt], started_at=NOW, finished_at=NOW)
    scores = score_items(res, NOW)
    assert scores[_item_key(yt_big)] == 1.0    # source-max → 1.0, not swamping
    assert scores[_item_key(gt)] == 1.0


def test_score_items_recency_breaks_ties():
    fresh = Item(source="youtube", lens="menu", type="video", title="fresh", url="f",
                 metrics={"views": 1000}, published_at=NOW, collected_at=NOW)
    old = Item(source="youtube", lens="menu", type="video", title="old", url="o",
               metrics={"views": 1000}, published_at=datetime(2026, 4, 4, tzinfo=timezone.utc),
               collected_at=NOW)
    res = ScanResult(run_id="r", store_id="nylb", lens="menu", query={},
                     items=[fresh, old], started_at=NOW, finished_at=NOW)
    scores = score_items(res, NOW)
    assert scores[_item_key(fresh)] > scores[_item_key(old)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_signal.py -k "popularity or recency or score" -v`
Expected: FAIL — `ImportError: cannot import name 'popularity'`.

- [ ] **Step 3: Write minimal implementation**

`src/nylb/core/signal.py` 끝에 추가(상단 import에 `from datetime import datetime`, `from nylb.core.schema import Item, ScanResult` 보강):

```python
from datetime import datetime          # add to existing imports at top of file
from nylb.core.schema import ScanResult  # extend existing schema import

_HALF_LIFE_DAYS = 30.0


def _item_key(item: Item) -> str:
    return item.url or f"{item.source}:{item.title}"


def popularity(item: Item) -> float:
    """Raw (un-normalized) popularity by source."""
    m = item.metrics
    if item.source == "youtube":
        return m.get("views", 0.0) + m.get("likes", 0.0) * 5 + m.get("comments", 0.0) * 10
    if item.source in ("google_trends", "naver_datalab"):
        return m.get("interest", m.get("value", 0.0))
    if item.source == "naver":
        return 1.0  # no popularity metric; low base so recency/relevance decide order
    return m.get("interest", 0.0)


def recency_weight(item: Item, now: datetime) -> float:
    """Exponential time-decay (≈30-day half-life). Undated items (trend signals) = 1.0."""
    pub = item.published_at
    if pub is None:
        return 1.0
    if pub.tzinfo is None and now.tzinfo is not None:
        pub = pub.replace(tzinfo=now.tzinfo)
    elif pub.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=pub.tzinfo)
    age_days = max(0.0, (now - pub).total_seconds() / 86400.0)
    return max(0.1, 0.5 ** (age_days / _HALF_LIFE_DAYS))


def score_items(result: ScanResult, now: datetime) -> dict[str, float]:
    """Per-item recency×popularity, normalized WITHIN each source so raw YouTube
    view counts don't swamp 0–100 trend interest."""
    max_pop: dict[str, float] = {}
    for it in result.items:
        p = popularity(it)
        if p > max_pop.get(it.source, 0.0):
            max_pop[it.source] = p
    scores: dict[str, float] = {}
    for it in result.items:
        mp = max_pop.get(it.source, 0.0)
        norm = (popularity(it) / mp) if mp > 0 else 0.0
        scores[_item_key(it)] = norm * recency_weight(it, now)
    return scores
```

(참고: 파일 상단 import 블록을 `from __future__ import annotations` / `import re` / `from datetime import datetime` / `from nylb.core.schema import Item, ScanResult`로 정리. `ScanResult`는 score_items용.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_signal.py -v`
Expected: PASS (11 tests green).

- [ ] **Step 5: Commit**

```powershell
git add src/nylb/core/signal.py tests/core/test_signal.py
git commit -m "feat: add recency×popularity scoring (signal.score_items)"
```

---

## Task 3: YouTube 인기 지표 보강 (search.list → videos.list)

**Files:**
- Modify: `src/nylb/collectors/youtube.py` (전면 교체)
- Test: `tests/collectors/test_youtube.py` (재작성)

- [ ] **Step 1: Rewrite the test**

`tests/collectors/test_youtube.py` 전체를 아래로 교체:

```python
from datetime import datetime, timezone
import httpx
import nylb.collectors.youtube as yt

NOW = datetime(2026, 6, 3, tzinfo=timezone.utc)

_SEARCH_RESP = {"items": [
    {"id": {"videoId": "abc123"}, "snippet": {"title": "베이글 신메뉴 리뷰",
        "description": "요즘 핫한 베이글", "channelTitle": "빵튜브",
        "publishedAt": "2026-05-30T10:00:00Z"}},
    {"id": {"kind": "channel"}, "snippet": {"title": "skip me"}},  # no videoId
]}
_VIDEOS_RESP = {"items": [
    {"id": "abc123", "snippet": {"title": "베이글 신메뉴 리뷰",
        "description": "요즘 핫한 베이글", "channelTitle": "빵튜브",
        "publishedAt": "2026-05-30T10:00:00Z"},
     "statistics": {"viewCount": "12345", "likeCount": "678", "commentCount": "90"}},
]}


class _Resp:
    def __init__(self, data): self._data = data
    def raise_for_status(self): pass
    def json(self): return self._data


def _fake_get(search=_SEARCH_RESP, videos=_VIDEOS_RESP, fail_videos=False):
    def get(url, params=None, timeout=None, headers=None):
        if url == yt._SEARCH_URL:
            return _Resp(search)
        if url == yt._VIDEOS_URL:
            if fail_videos:
                raise httpx.HTTPError("videos boom")
            return _Resp(videos)
        raise AssertionError(f"unexpected url {url}")
    return get


def test_collect_enriches_with_statistics(monkeypatch):
    monkeypatch.setattr(yt.httpx, "get", _fake_get())
    res = yt.collect({"keywords": ["베이글"]}, "menu",
                     settings={"youtube_api_key": "k"}, collected_at=NOW)
    assert len(res.items) == 1 and res.errors == []
    it = res.items[0]
    assert it.source == "youtube" and it.type == "video"
    assert it.url == "https://youtu.be/abc123"
    assert it.author == "빵튜브"
    assert it.metrics["views"] == 12345
    assert it.metrics["likes"] == 678
    assert it.metrics["comments"] == 90
    assert it.published_at == datetime(2026, 5, 30, 10, 0, tzinfo=timezone.utc)


def test_collect_graceful_when_videos_list_fails(monkeypatch):
    monkeypatch.setattr(yt.httpx, "get", _fake_get(fail_videos=True))
    res = yt.collect({"keywords": ["베이글"]}, "menu",
                     settings={"youtube_api_key": "k"}, collected_at=NOW)
    assert len(res.items) == 1                 # search results survive
    assert res.items[0].metrics["views"] == 0  # no stats → zero
    assert res.errors == []


def test_collect_missing_key_errors(monkeypatch):
    res = yt.collect({"keywords": ["베이글"]}, "menu", settings={}, collected_at=NOW)
    assert res.items == []
    assert res.errors[0].source == "youtube"
    assert "YOUTUBE_API_KEY" in res.errors[0].message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/collectors/test_youtube.py -v`
Expected: FAIL — `AttributeError: module 'nylb.collectors.youtube' has no attribute '_VIDEOS_URL'` (and `_fetch` 기반 옛 함수 부재).

- [ ] **Step 3: Rewrite the collector**

`src/nylb/collectors/youtube.py` 전체를 아래로 교체:

```python
from __future__ import annotations

from datetime import datetime

import httpx

from nylb.collectors.base import parse_iso
from nylb.core.schema import CollectError, CollectResult, Item

SOURCE = "youtube"
_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_MAX_SEARCHES = 20  # cap search.list calls/scan (quota guard for the bigger keyword set in B)


def _search(keywords: list[str], api_key: str) -> dict[str, dict]:
    """Per-keyword search.list → {video_id: snippet}, deduped (IDs only here)."""
    snippets: dict[str, dict] = {}
    for kw in (keywords[:_MAX_SEARCHES] or ["베이글"]):
        params = {"key": api_key, "q": kw, "part": "snippet", "type": "video",
                  "order": "relevance", "maxResults": 20, "regionCode": "KR",
                  "relevanceLanguage": "ko"}
        r = httpx.get(_SEARCH_URL, params=params, timeout=20)
        r.raise_for_status()
        for raw in r.json().get("items", []):
            vid = raw.get("id", {}).get("videoId")
            if vid and vid not in snippets:
                snippets[vid] = raw.get("snippet", {})
    return snippets


def _fetch_stats(ids: list[str], api_key: str) -> dict[str, dict]:
    """videos.list → {video_id: full video object (snippet+statistics)} in batches of 50."""
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        params = {"key": api_key, "part": "snippet,statistics", "id": ",".join(chunk)}
        r = httpx.get(_VIDEOS_URL, params=params, timeout=20)
        r.raise_for_status()
        for raw in r.json().get("items", []):
            out[raw["id"]] = raw
    return out


def _parse(snippets: dict[str, dict], videos: dict[str, dict],
           lens: str, collected_at: datetime) -> list[Item]:
    items: list[Item] = []
    for vid, search_sn in snippets.items():
        v = videos.get(vid, {})
        sn = v.get("snippet", search_sn)          # videos.list snippet is richer
        st = v.get("statistics", {})
        items.append(Item(
            source=SOURCE, lens=lens, type="video",
            title=sn.get("title", ""), url=f"https://youtu.be/{vid}",
            text=sn.get("description"), author=sn.get("channelTitle"),
            published_at=parse_iso(sn.get("publishedAt")),
            metrics={
                "views": float(st.get("viewCount", 0) or 0),
                "likes": float(st.get("likeCount", 0) or 0),
                "comments": float(st.get("commentCount", 0) or 0),
            },
            collected_at=collected_at, raw=v or {"snippet": search_sn},
        ))
    return items


def collect(query: dict, lens: str, *, settings: dict, collected_at: datetime) -> CollectResult:
    try:
        api_key = settings.get("youtube_api_key")
        if not api_key:
            raise RuntimeError("YOUTUBE_API_KEY missing")
        keywords = list(query.get("keywords", []))
        snippets = _search(keywords, api_key)
        if not snippets:
            return CollectResult()
        try:
            videos = _fetch_stats(list(snippets), api_key)
        except Exception:
            videos = {}  # graceful: keep search results with zero metrics
        return CollectResult(items=_parse(snippets, videos, lens, collected_at))
    except Exception as exc:  # partial-failure tolerant
        return CollectResult(errors=[CollectError(source=SOURCE, message=str(exc))])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/collectors/test_youtube.py -v`
Expected: PASS (3 tests green).

- [ ] **Step 5: Commit**

```powershell
git add src/nylb/collectors/youtube.py tests/collectors/test_youtube.py
git commit -m "feat: enrich YouTube items with view/like/comment statistics"
```

---

## Task 4: Naver — sort=sim + postdate→published_at

**Files:**
- Modify: `src/nylb/collectors/naver.py`
- Test: `tests/collectors/test_naver.py`

- [ ] **Step 1: Write/append the failing tests**

`tests/collectors/test_naver.py`의 `test_parse_strips_html`에 published_at 단언 추가하고, 파일 끝에 sort 테스트 추가. 우선 import에 `from datetime import datetime, timezone` 확인(이미 있음). `test_parse_strips_html` 끝에 추가:

```python
    assert it.published_at == datetime(2026, 5, 30, tzinfo=timezone.utc)
```

파일 끝에 추가:

```python
def test_fetch_uses_relevance_sort(monkeypatch):
    captured = {}

    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"items": []}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update(params or {})
        return _Resp()

    monkeypatch.setattr(nv.httpx, "get", fake_get)
    nv._fetch({"keywords": ["베이글"]},
              {"naver_client_id": "a", "naver_client_secret": "b"})
    assert captured.get("sort") == "sim"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/collectors/test_naver.py -v`
Expected: FAIL — `test_parse_strips_html`에서 `published_at`가 `None`, `test_fetch_uses_relevance_sort`에서 `sort == "date"`.

- [ ] **Step 3: Write minimal implementation**

`src/nylb/collectors/naver.py` 상단 import에 datetime 추가하고, `_fetch`의 sort 변경, `_parse`에 postdate 파싱 추가:

상단 import 블록을 아래로:

```python
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from nylb.collectors.base import strip_html
from nylb.core.schema import CollectError, CollectResult, Item
```

`_fetch`의 params 한 줄 교체:

```python
    params = {"query": keywords, "display": 20, "sort": "sim"}
```

`_parse` 위에 헬퍼 추가하고 `_parse`에서 published_at 세팅:

```python
def _parse_postdate(value: str | None) -> datetime | None:
    if value and len(value) == 8 and value.isdigit():
        return datetime(int(value[:4]), int(value[4:6]), int(value[6:8]), tzinfo=timezone.utc)
    return None


def _parse(payload: dict, query: dict, lens: str, collected_at: datetime) -> list[Item]:
    items: list[Item] = []
    for raw in payload.get("items", []):
        items.append(Item(
            source=SOURCE, lens=lens, type="blog",
            title=strip_html(raw.get("title", "")), url=raw.get("link"),
            text=strip_html(raw.get("description")), author=raw.get("bloggername"),
            published_at=_parse_postdate(raw.get("postdate")),
            collected_at=collected_at, raw=raw,
        ))
    return items
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/collectors/test_naver.py -v`
Expected: PASS (기존 + 신규 green).

- [ ] **Step 5: Commit**

```powershell
git add src/nylb/collectors/naver.py tests/collectors/test_naver.py
git commit -m "feat: Naver sort=sim + parse postdate to published_at"
```

---

## Task 5: 중앙 관련성 필터 + ScanResult.dropped_by_source

**Files:**
- Modify: `src/nylb/core/schema.py` (`ScanResult`)
- Modify: `src/nylb/core/scan.py` (`run_scan`)
- Test: `tests/core/test_scan.py`

- [ ] **Step 1: Write the failing tests**

먼저 기존 `test_run_scan_aggregates_and_tolerates_failure`의 `fake_youtube`가 새 필터에 걸리지 않도록 제목을 키워드 포함으로 바꾼다. `tests/core/test_scan.py`의 `fake_youtube`를 교체:

```python
def fake_youtube(query, lens, *, settings, collected_at):
    return CollectResult(items=[Item(source="youtube", lens=lens, type="video",
                                     title="베이글 vid", collected_at=collected_at)])
```

파일 끝에 신규 테스트 추가:

```python
def test_run_scan_filters_off_topic(tmp_path):
    def fy(query, lens, *, settings, collected_at):
        return CollectResult(items=[
            Item(source="youtube", lens=lens, type="video", title="베이글 리뷰",
                 collected_at=collected_at),
            Item(source="youtube", lens=lens, type="video", title="먹방 챌린지",
                 collected_at=collected_at),
        ])
    store = LocalJsonStore(base_dir=tmp_path)
    lens_config = {"keywords": ["베이글"], "sources": ["youtube"]}
    result = run_scan("menu", store_id="nylb", lens_config=lens_config, settings={},
                      store=store, run_id="rf", collected_at=NOW,
                      collectors={"youtube": fy})
    assert [it.title for it in result.items] == ["베이글 리뷰"]
    assert result.dropped_by_source == {"youtube": 1}


def test_run_scan_synonyms_keep_english_title(tmp_path):
    def fy(query, lens, *, settings, collected_at):
        return CollectResult(items=[Item(source="youtube", lens=lens, type="video",
                                         title="Best BAGEL in Seoul", collected_at=collected_at)])
    store = LocalJsonStore(base_dir=tmp_path)
    lens_config = {"keywords": ["베이글"], "sources": ["youtube"],
                   "synonyms": {"베이글": ["bagel"]}}
    result = run_scan("menu", store_id="nylb", lens_config=lens_config, settings={},
                      store=store, run_id="rs", collected_at=NOW,
                      collectors={"youtube": fy})
    assert len(result.items) == 1                  # synonym let it through
    assert result.dropped_by_source == {}


def test_run_scan_no_filter_without_keywords(tmp_path):
    def fk(query, lens, *, settings, collected_at):
        return CollectResult(items=[Item(source="kurly", lens=lens, type="product",
                                         title="포비 크림치즈", collected_at=collected_at)])
    store = LocalJsonStore(base_dir=tmp_path)
    lens_config = {"sources": ["kurly"]}           # competitor lens, no keywords
    result = run_scan("competitor", store_id="nylb", lens_config=lens_config, settings={},
                      store=store, run_id="rk", collected_at=NOW,
                      collectors={"kurly": fk})
    assert len(result.items) == 1
    assert result.dropped_by_source == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_scan.py -v`
Expected: FAIL — `AttributeError: 'ScanResult' object has no attribute 'dropped_by_source'`.

- [ ] **Step 3a: Add the field to ScanResult**

`src/nylb/core/schema.py`의 `ScanResult`에 한 줄 추가(`errors` 다음):

```python
class ScanResult(BaseModel):
    run_id: str
    store_id: str
    lens: str
    query: dict
    items: list[Item] = Field(default_factory=list)
    errors: list[CollectError] = Field(default_factory=list)
    dropped_by_source: dict[str, int] = Field(default_factory=dict)
    started_at: datetime
    finished_at: datetime
```

- [ ] **Step 3b: Apply the filter in run_scan**

`src/nylb/core/scan.py` 상단 import에 추가:

```python
from nylb.core.signal import filter_relevant
```

`run_scan`에서 수집 루프 직후(`result = ScanResult(...)` 직전)에 추가하고, ScanResult 생성에 `dropped_by_source` 전달:

```python
    items, dropped = filter_relevant(
        items, query.get("keywords", []), lens_config.get("synonyms"))

    result = ScanResult(
        run_id=run_id, store_id=store_id, lens=lens, query=query,
        items=items, errors=errors, dropped_by_source=dropped,
        started_at=collected_at, finished_at=collected_at,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_scan.py tests/core/test_schema.py -v`
Expected: PASS (기존 + 신규 green).

- [ ] **Step 5: Commit**

```powershell
git add src/nylb/core/schema.py src/nylb/core/scan.py tests/core/test_scan.py
git commit -m "feat: apply central relevance filter in run_scan (+ dropped_by_source)"
```

---

## Task 6: analyzer — signal 점수 랭킹 + 필터 제외 섹션

**Files:**
- Modify: `src/nylb/core/analyzer.py` (전면 교체)
- Test: `tests/core/test_analyzer.py` (신규 테스트 추가; 기존은 그대로 통과)

- [ ] **Step 1: Write the failing test**

`tests/core/test_analyzer.py` 끝에 추가:

```python
def test_prepare_shows_dropped_section():
    res = ScanResult(
        run_id="rd", store_id="nylb", lens="menu", query={"keywords": ["베이글"]},
        items=[Item(source="youtube", lens="menu", type="video", title="베이글 영상",
                    collected_at=NOW)],
        dropped_by_source={"youtube": 2, "naver": 3},
        started_at=NOW, finished_at=NOW,
    )
    digest = ClaudeCodeAnalyzer().prepare(res)
    assert "관련성 필터" in digest
    assert "youtube: 2" in digest and "naver: 3" in digest


def test_prepare_ranks_recent_over_old_same_views():
    items = [
        Item(source="youtube", lens="menu", type="video", title="옛날 베이글", url="o",
             metrics={"views": 1000},
             published_at=datetime(2026, 4, 4, tzinfo=timezone.utc), collected_at=NOW),
        Item(source="youtube", lens="menu", type="video", title="최신 베이글", url="f",
             metrics={"views": 1000}, published_at=NOW, collected_at=NOW),
    ]
    res = ScanResult(run_id="rr", store_id="nylb", lens="menu", query={"keywords": ["베이글"]},
                     items=items, started_at=NOW, finished_at=NOW)
    digest = ClaudeCodeAnalyzer().prepare(res)
    assert digest.index("최신 베이글") < digest.index("옛날 베이글")   # recency wins the tie
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_analyzer.py -k "dropped or recent" -v`
Expected: FAIL — digest에 "관련성 필터" 섹션 없음 / 정렬이 최신성 미반영.

- [ ] **Step 3: Rewrite the analyzer**

`src/nylb/core/analyzer.py` 전체를 아래로 교체:

```python
from __future__ import annotations

from typing import Protocol

from nylb.core.schema import ScanResult
from nylb.core.signal import _item_key, score_items


def cross_channel_terms(result: ScanResult, top_n: int = 10,
                        scores: dict[str, float] | None = None) -> list[dict]:
    """Rank candidate terms by how many distinct channels mention them, then by
    summed recency×popularity signal. Channel breadth is the strongest trend
    signal, so it stays primary; signal is the tiebreak."""
    if scores is None:
        scores = score_items(result, result.finished_at)

    candidates: set[str] = set(result.query.get("keywords", []) or [])
    candidates |= set(result.query.get("instagram_hashtags", []) or [])
    for item in result.items:
        if item.source == "google_trends":
            candidates.add(item.title)

    rows: list[dict] = []
    for term in candidates:
        needle = term.lower()
        channels: set[str] = set()
        signal = 0.0
        for item in result.items:
            haystack = f"{item.title} {item.text or ''}".lower()
            if needle in haystack:
                channels.add(item.source)
                signal += scores.get(_item_key(item), 0.0)
        if channels:
            rows.append({
                "term": term,
                "channels": sorted(channels),
                "channel_count": len(channels),
                "signal": round(signal, 3),
            })
    rows.sort(key=lambda r: (r["channel_count"], r["signal"]), reverse=True)
    return rows[:top_n]


class Analyzer(Protocol):
    def prepare(self, result: ScanResult, top_n: int = 10) -> str: ...


class ClaudeCodeAnalyzer:
    """Phase 1 analyzer: builds a deterministic digest (no LLM call).
    The Claude Code session reads this digest and adds insight/actions.
    SaaS swaps in an ApiAnalyzer behind the same Protocol."""

    def prepare(self, result: ScanResult, top_n: int = 10) -> str:
        scores = score_items(result, result.finished_at)
        lines = [
            f"# Scan digest — {result.lens} ({result.run_id})",
            "",
            f"- store: {result.store_id}",
            f"- items: {len(result.items)}  errors: {len(result.errors)}",
        ]
        if result.errors:
            lines += ["", "## Collection errors"]
            lines += [f"- {e.source}: {e.message}" for e in result.errors]

        if result.dropped_by_source:
            lines += ["", "## 🧹 관련성 필터로 제외"]
            lines += [f"- {s}: {n}건 (키워드 무관)"
                      for s, n in sorted(result.dropped_by_source.items())]

        cross = cross_channel_terms(result, top_n=top_n, scores=scores)
        if cross:
            multi = [r for r in cross if r["channel_count"] >= 2]
            lines += ["", "## 🔥 채널 교차 핫 키워드"]
            if multi:
                for r in multi:
                    lines.append(
                        f"- **{r['term']}** — {r['channel_count']}개 채널 "
                        f"({', '.join(r['channels'])}), 신호 {r['signal']}"
                    )
            else:
                lines.append("- (2개 이상 채널에서 동시 등장한 키워드 없음)")

        by_source: dict[str, list] = {}
        for item in result.items:
            by_source.setdefault(item.source, []).append(item)

        for source, items in by_source.items():
            ranked = sorted(items, key=lambda it: scores.get(_item_key(it), 0.0),
                            reverse=True)[:top_n]
            lines += ["", f"## {source} (top {len(ranked)})"]
            for it in ranked:
                metric_str = ", ".join(f"{k}={int(v)}" for k, v in it.metrics.items()) or "—"
                lines.append(f"- **{it.title}** [{metric_str}] {it.url or ''}".rstrip())
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/core/test_analyzer.py -v`
Expected: PASS (기존 5 + 신규 2 = 7 green; 기존 테스트는 signal 정렬에서도 동일 순서 유지).

- [ ] **Step 5: Commit**

```powershell
git add src/nylb/core/analyzer.py tests/core/test_analyzer.py
git commit -m "feat: rank digest by recency×popularity signal + filter-drop section"
```

---

## Task 7: config — menu 렌즈 synonyms

**Files:**
- Modify: `config/lenses.yaml` (menu 렌즈)
- Test: `tests/test_config.py`

자동 효과는 Task 5의 필터가 소비. 여기선 핵심 키워드 동의어만 최소로(대량 확장은 하위 프로젝트 B).

- [ ] **Step 1: Write the failing test**

`tests/test_config.py` 끝에 추가(파일 상단 import·헬퍼 패턴은 기존 테스트 따라):

```python
def test_menu_lens_has_synonyms():
    from nylb.config import load_lenses, get_lens_config
    lenses = load_lenses("config/lenses.yaml")
    menu = get_lens_config(lenses, "nylb", "menu")
    syn = menu.get("synonyms", {})
    assert "bagel" in syn.get("베이글", [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config.py::test_menu_lens_has_synonyms -v`
Expected: FAIL — `synonyms` 키 없음.

- [ ] **Step 3: Edit the menu lens**

`config/lenses.yaml`의 `menu:` 블록에 `synonyms` 추가(`sources:` 아래, 들여쓰기 맞춰):

```yaml
    menu:
      keywords: [베이글, 소금빵, 크로플]
      radar_watchlist: [두바이초콜릿, 탕후루, 약과, 요거트아이스크림, 마라탕후루, 베이커리]
      radar_seeds: [베이글, 디저트, 베이커리]
      sources: [youtube, naver, google_trends, naver_datalab]
      synonyms:
        베이글: [bagel]
        소금빵: ["소금 빵", "salt bread"]
        크로플: [croffle]
      # instagram_hashtags: [베이글맛집, 베이글]  # 인스타 보류 — Meta 토큰 발급 후 주석 해제
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add config/lenses.yaml tests/test_config.py
git commit -m "feat: add menu lens synonyms for relevance filter"
```

---

## Task 8: 라이브 검증 + 마무리

**Files:** 없음(실행/검증). `@pytest.mark.live` 대상 아님 — 수동.

- [ ] **Step 1: 전체 테스트 green 확인**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: 기존 81 + 신규(signal 11 + youtube 재작성 net + naver 1 + scan 3 + analyzer 2 + config 1) ≈ 95+ passed, live 제외, 0 fail.

- [ ] **Step 2: menu 스캔 실행**

Run: `.\.venv\Scripts\python.exe -m nylb scan --lens menu --store nylb`
Expected: 0 errors(또는 부분 실패만), `run_id` 기록. 출력 digest 경로 확인.

- [ ] **Step 3: digest 육안 검증**

`data/raw/<run_id>.digest.md`를 읽어 확인:
- youtube 항목에 `views=…, likes=…` 실제 수치(더 이상 `[—]` 아님).
- `## 🧹 관련성 필터로 제외` 섹션에 떨어진 개수 노출(노이즈 제거 증거).
- 무관 카페 후기(파주 마장호수·망월동 젤라또류)가 naver 상위에서 사라짐.
- 최신 화제가 상위(오래된 바이럴이 밀려남).

- [ ] **Step 4: synthesis 작성 + HTML 렌더 검증**

기존 흐름대로 `data/raw/<run_id>.synthesis.json` 작성 → `.\.venv\Scripts\python.exe -m nylb report-html --run <run_id>` → http.server + Playwright로 `reports/<run_id>.analysis.html` 로드, 0 JS 에러(favicon 404만) 확인.

- [ ] **Step 5: 메모리 업데이트 + 마무리**

`nylb-project.md`에 신호 품질(A) 슬라이스 요약 추가(YouTube 조회수 보강·중앙 관련성 필터·최신성×인기 랭킹·Naver sim/postdate). `superpowers:finishing-a-development-branch`로 main 병합 + 푸시 결정. B(키워드·관심사) 착수는 사용자 확인 후.

---

## Self-Review (작성자 체크)

**Spec coverage:** spec §A1(YouTube 보강)→Task3 · §A2(관련성 필터·Naver sim)→Task1·4·5·7 · §A3(최신성×인기 랭킹)→Task2·6 · 데이터모델(metrics·dropped_by_source·synonyms)→Task3·5·7 · 테스트전략→각 Task · 라이브→Task8. 모든 spec 섹션에 대응 태스크 존재. spec이 언급한 chart_data/html 변경은 **불필요**(아이템 engagement 정렬 코드 없음)로 확인 — 범위에서 명시 제외.

**Placeholder scan:** TBD/TODO 없음. 모든 코드 스텝에 실제 코드. 가중치(likes*5/comments*10)·반감기(30일)·maxResults(20)·_MAX_SEARCHES(20) 전부 명시값.

**Type consistency:** `_item_key`·`score_items`·`popularity`·`recency_weight`가 signal.py(Task2) 정의와 analyzer(Task6)·테스트에서 동일 시그니처. `dropped_by_source: dict[str,int]`가 schema(Task5)·scan(Task5)·analyzer(Task6)·테스트에서 일관. `filter_relevant` 반환 `(list, dict)` 튜플이 scan 사용처와 일치. cross_channel row 키 `engagement`→`signal` 전환을 analyzer·테스트에서 일관 반영(기존 테스트는 해당 키 미검증이라 안전).

**기존 테스트 회귀:** test_scan `fake_youtube` 제목을 "베이글 vid"로 수정(필터 통과). test_analyzer 기존 5개는 published_at 없는 동일시점 항목이라 signal=정규화 인기로 기존 순서 유지(high view>low view, 베이글 channel_count 우선) → green.
