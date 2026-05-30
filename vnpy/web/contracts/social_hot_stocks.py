from __future__ import annotations

from pydantic import BaseModel, Field


class SocialHotStockItem(BaseModel):
    source: str = "apewisdom"
    source_filter: str
    source_url: str
    rank: int
    symbol: str
    name: str
    mentions: int
    upvotes: int
    rank_24h_ago: int | None = None
    mentions_24h_ago: int | None = None
    mention_change: int | None = None
    mention_change_pct: float | None = None
    rank_change: int | None = None


class SocialHotStocksResponse(BaseModel):
    source: str = "apewisdom"
    source_label: str = "ApeWisdom"
    source_url: str
    source_filter: str = Field(description="ApeWisdom filter, for example all-stocks or wallstreetbets.")
    window_hours: int = 24
    refresh_seconds: int
    generated_at: str
    count: int
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
    returned_count: int = 0
    cache_status: str = Field(
        default="live",
        description="Data path used for this response: live, memory, persisted-cache, or persisted-fallback.",
    )
    snapshot_id: int | None = None
    persisted_at: str | None = None
    items: list[SocialHotStockItem]
