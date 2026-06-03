from __future__ import annotations

import re
from datetime import datetime


def strip_html(text: str | None) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
