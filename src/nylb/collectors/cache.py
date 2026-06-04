from __future__ import annotations

import hashlib
import time
from pathlib import Path

_CACHE_DIR = Path("data/cache")


def _name(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + ".html"


def get_cached(url: str, ttl_days: float, base_dir: Path | str = _CACHE_DIR) -> str | None:
    p = Path(base_dir) / _name(url)
    if not p.exists():
        return None
    age_days = (time.time() - p.stat().st_mtime) / 86400
    if age_days > ttl_days:
        return None
    return p.read_text(encoding="utf-8")


def put_cache(url: str, text: str, base_dir: Path | str = _CACHE_DIR) -> None:
    d = Path(base_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / _name(url)).write_text(text, encoding="utf-8")
