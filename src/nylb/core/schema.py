from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Source = Literal["youtube", "naver", "google_trends", "naver_datalab", "kurly", "instagram"]


class Item(BaseModel):
    store_id: str = "nylb"            # 🏢 tenancy seam
    source: Source
    lens: str  # config-driven lens name (industry-agnostic), not a fixed enum
    type: str                        # e.g. video, blog, search_term, hashtag_media
    title: str
    url: str | None = None
    text: str | None = None
    author: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    published_at: datetime | None = None
    collected_at: datetime
    raw: dict = Field(default_factory=dict)


class CollectError(BaseModel):
    source: str
    message: str


class CollectResult(BaseModel):
    items: list[Item] = Field(default_factory=list)
    errors: list[CollectError] = Field(default_factory=list)


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
