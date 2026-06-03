from __future__ import annotations

from datetime import datetime

import httpx

from nylb.collectors.base import parse_iso
from nylb.core.schema import CollectError, CollectResult, Item

SOURCE = "youtube"
_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def _fetch(query: dict, settings: dict) -> dict:
    api_key = settings.get("youtube_api_key")
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY missing")
    keywords = " ".join(query.get("keywords", [])) or "베이글"
    params = {
        "key": api_key, "q": keywords, "part": "snippet", "type": "video",
        "order": "viewCount", "maxResults": 15, "regionCode": "KR",
        "relevanceLanguage": "ko",
    }
    r = httpx.get(_SEARCH_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def _parse(payload: dict, query: dict, lens: str, collected_at: datetime) -> list[Item]:
    items: list[Item] = []
    for raw in payload.get("items", []):
        video_id = raw.get("id", {}).get("videoId")
        if not video_id:
            continue
        sn = raw.get("snippet", {})
        items.append(Item(
            source=SOURCE, lens=lens, type="video",
            title=sn.get("title", ""), url=f"https://youtu.be/{video_id}",
            text=sn.get("description"), author=sn.get("channelTitle"),
            published_at=parse_iso(sn.get("publishedAt")),
            collected_at=collected_at, raw=raw,
        ))
    return items


def collect(query: dict, lens: str, *, settings: dict, collected_at: datetime) -> CollectResult:
    try:
        payload = _fetch(query, settings)
        return CollectResult(items=_parse(payload, query, lens, collected_at))
    except Exception as exc:  # partial-failure tolerant
        return CollectResult(errors=[CollectError(source=SOURCE, message=str(exc))])
