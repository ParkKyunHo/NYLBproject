from __future__ import annotations

from datetime import datetime, timezone

import httpx

from nylb.collectors.base import strip_html
from nylb.core.schema import CollectError, CollectResult, Item

SOURCE = "naver"
_SEARCH_URL = "https://openapi.naver.com/v1/search/blog.json"


def _fetch_one(keyword: str, settings: dict) -> dict:
    cid = settings.get("naver_client_id")
    csec = settings.get("naver_client_secret")
    if not (cid and csec):
        raise RuntimeError("NAVER credentials missing")
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec}
    params = {"query": keyword, "display": 20, "sort": "sim"}
    r = httpx.get(_SEARCH_URL, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()


def _parse_postdate(value: str | None) -> datetime | None:
    if value and len(value) == 8 and value.isdigit():
        try:
            return datetime(int(value[:4]), int(value[4:6]), int(value[6:8]), tzinfo=timezone.utc)
        except ValueError:
            return None  # 8 digits but invalid date (e.g. month 13) → skip, don't crash batch
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


def collect(query: dict, lens: str, *, settings: dict, collected_at: datetime) -> CollectResult:
    keywords = list(query.get("keywords", [])) or ["베이글"]
    items: list[Item] = []
    errors: list[CollectError] = []
    seen: set[str] = set()
    for kw in keywords:
        try:
            payload = _fetch_one(kw, settings)
        except Exception as exc:
            errors.append(CollectError(source=SOURCE, message=f"{kw}: {exc}"))
            continue
        for it in _parse(payload, query, lens, collected_at):
            key = it.url or it.title
            if key in seen:
                continue
            seen.add(key)
            items.append(it)
    # total failure (every keyword errored) surfaces; partial is tolerated
    if errors and not items and len(errors) == len(keywords):
        return CollectResult(errors=errors)
    return CollectResult(items=items)
