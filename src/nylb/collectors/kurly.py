from __future__ import annotations

import json
import re
import time
from datetime import datetime

import httpx

from nylb.collectors.cache import get_cached, put_cache
from nylb.core.schema import CollectError, CollectResult, Item

SOURCE = "kurly"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_NEXT = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL)


def _goods_id(url: str) -> str:
    m = re.search(r"/goods/(\d+)", url)
    return m.group(1) if m else ""


def _find_product(node, goods_id: str):
    """Find a product dict (has name+basePrice+discountedPrice); prefer the
    one whose values include the goods id (disambiguates from recommendations)."""
    found: list[dict] = []

    def walk(n):
        if isinstance(n, dict):
            if {"name", "basePrice", "discountedPrice"} <= n.keys():
                found.append(n)
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(node)
    if not found:
        return None
    for d in found:
        if goods_id and goods_id in {str(v) for v in d.values()}:
            return d
    return found[0]


def _parse(pages: list[dict], lens: str, collected_at: datetime) -> list[Item]:
    items: list[Item] = []
    for pg in pages:
        m = _NEXT.search(pg["html"])
        if not m:
            continue
        prod = _find_product(json.loads(m.group(1)), _goods_id(pg["url"]))
        if not prod:
            continue
        base = prod.get("basePrice")
        disc = prod.get("discountedPrice")
        price = disc if disc is not None else base       # fall back to list price
        if price is None:                                # no usable price → skip, don't crash others
            continue
        items.append(Item(
            source=SOURCE, lens=lens, type="product",
            title=str(prod["name"]), url=pg["url"], author=pg.get("brand"),
            metrics={"price": float(price),
                     "base_price": float(base) if base is not None else float(price)},
            collected_at=collected_at, raw={"goods_id": _goods_id(pg["url"])},
        ))
    return items


def _fetch(query: dict, settings: dict) -> list[dict]:
    products = query.get("competitor_products", []) or []
    headers = {"User-Agent": _UA, "Accept-Language": "ko-KR,ko;q=0.9"}
    pages: list[dict] = []
    live_calls = 0
    for p in products:
        url = p["url"]
        try:
            html = get_cached(url, ttl_days=7)
            if html is None:
                if live_calls:
                    time.sleep(1.5)        # polite rate-limit between live requests
                live_calls += 1
                r = httpx.get(url, headers=headers, timeout=25, follow_redirects=True)
                r.raise_for_status()
                html = r.text
                put_cache(url, html)
            pages.append({"brand": p.get("brand"), "url": url, "html": html})
        except Exception:
            continue                       # one bad URL must not drop the others
    return pages


def collect(query: dict, lens: str, *, settings: dict, collected_at: datetime) -> CollectResult:
    try:
        pages = _fetch(query, settings)
        return CollectResult(items=_parse(pages, lens, collected_at))
    except Exception as exc:
        return CollectResult(errors=[CollectError(source=SOURCE, message=str(exc))])
