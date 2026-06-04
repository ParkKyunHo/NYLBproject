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
    """Per-keyword search.list → {video_id: snippet}, deduped (IDs only here).

    One keyword's failure (quota/403) doesn't lose the others' results; but if
    EVERY search fails we re-raise so the outer handler surfaces a real error
    instead of silently returning empty.
    """
    snippets: dict[str, dict] = {}
    kws = keywords[:_MAX_SEARCHES] or ["베이글"]
    last_exc: Exception | None = None
    failures = 0
    for kw in kws:
        params = {"key": api_key, "q": kw, "part": "snippet", "type": "video",
                  "order": "relevance", "maxResults": 20, "regionCode": "KR",
                  "relevanceLanguage": "ko"}
        try:
            r = httpx.get(_SEARCH_URL, params=params, timeout=20)
            r.raise_for_status()
        except Exception as exc:          # tolerate a single keyword failing
            last_exc, failures = exc, failures + 1
            continue
        for raw in r.json().get("items", []):
            vid = raw.get("id", {}).get("videoId")
            if vid and vid not in snippets:
                snippets[vid] = raw.get("snippet", {})
    if failures == len(kws) and last_exc is not None:
        raise last_exc                    # total failure → don't hide it
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
            collected_at=collected_at, raw=v if v else {"snippet": search_sn},
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
