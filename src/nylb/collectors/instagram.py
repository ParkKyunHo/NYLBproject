from __future__ import annotations

from datetime import datetime

import httpx

from nylb.collectors.base import parse_iso
from nylb.core.schema import CollectError, CollectResult, Item

SOURCE = "instagram"
_BASE = "https://graph.facebook.com/v19.0"


def _fetch(query: dict, settings: dict) -> dict:
    token = settings["instagram_graph_token"]
    user_id = settings.get("instagram_user_id")
    if not user_id:
        raise RuntimeError("INSTAGRAM_USER_ID missing")
    tags = query.get("instagram_hashtags", [])
    if not tags:
        return {"data": []}
    search = httpx.get(
        f"{_BASE}/ig_hashtag_search",
        params={"user_id": user_id, "q": tags[0], "access_token": token}, timeout=20,
    )
    search.raise_for_status()
    found = search.json().get("data", [])
    if not found:
        return {"data": []}
    hashtag_id = found[0]["id"]
    media = httpx.get(
        f"{_BASE}/{hashtag_id}/recent_media",
        params={
            "user_id": user_id,
            "fields": "id,caption,like_count,comments_count,media_type,permalink,timestamp",
            "access_token": token,
        }, timeout=20,
    )
    media.raise_for_status()
    return media.json()


def _parse(payload: dict, query: dict, lens: str, collected_at: datetime) -> list[Item]:
    items: list[Item] = []
    for raw in payload.get("data", []):
        caption = raw.get("caption") or ""
        items.append(Item(
            source=SOURCE, lens=lens, type="hashtag_media",
            title=caption[:80], url=raw.get("permalink"), text=caption or None,
            metrics={
                "likes": float(raw.get("like_count") or 0),
                "comments": float(raw.get("comments_count") or 0),
            },
            published_at=parse_iso(raw.get("timestamp")),
            collected_at=collected_at, raw=raw,
        ))
    return items


def collect(query: dict, lens: str, *, settings: dict, collected_at: datetime) -> CollectResult:
    if not settings.get("instagram_graph_token"):
        return CollectResult(errors=[CollectError(
            source=SOURCE, message="no INSTAGRAM_GRAPH_TOKEN; skipped")])
    try:
        payload = _fetch(query, settings)
        return CollectResult(items=_parse(payload, query, lens, collected_at))
    except Exception as exc:
        return CollectResult(errors=[CollectError(source=SOURCE, message=str(exc))])
