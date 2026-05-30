from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
import math
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Final

import requests

from vnpy.web.contracts.social_hot_stocks import SocialHotStockItem, SocialHotStocksResponse
from vnpy.web.domain.social_hot_stocks import SocialHotStocksStore, StoredSocialHotSnapshot


SUPPORTED_APEWISDOM_FILTERS = {
    "all",
    "all-stocks",
    "all-crypto",
    "4chan",
    "CryptoCurrency",
    "CryptoCurrencies",
    "Bitcoin",
    "SatoshiStreetBets",
    "CryptoMoonShots",
    "CryptoMarkets",
    "stocks",
    "wallstreetbets",
    "options",
    "WallStreetbetsELITE",
    "Wallstreetbetsnew",
    "SPACs",
    "investing",
    "Daytrading",
}


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


_AUTO_STORE: Final = object()


class SocialHotStocksService:
    """Adapter for social-media stock mention providers."""

    def __init__(self, session: requests.Session | None = None, store: SocialHotStocksStore | None | object = _AUTO_STORE) -> None:
        self._session = session or requests.Session()
        self._base_url = os.getenv("APEWISDOM_API_BASE_URL", "https://apewisdom.io/api/v1.0").rstrip("/")
        self._timeout = float(os.getenv("APEWISDOM_TIMEOUT_SECONDS", "15"))
        self._cache_seconds = int(os.getenv("SOCIAL_HOT_CACHE_SECONDS", "300"))
        self._refresh_seconds = int(os.getenv("SOCIAL_HOT_REFRESH_SECONDS", "300"))
        self._max_page_size = int(os.getenv("SOCIAL_HOT_MAX_PAGE_SIZE", "500"))
        self._max_fetch_items = int(os.getenv("SOCIAL_HOT_MAX_FETCH_ITEMS", "5000"))
        self._snapshot_retention = int(os.getenv("SOCIAL_HOT_SNAPSHOT_RETENTION", "200"))
        self._cache: dict[tuple[str, int], tuple[float, dict[str, Any]]] = {}
        if store is _AUTO_STORE:
            self._store = SocialHotStocksStore(self._default_db_path()) if _env_bool("SOCIAL_HOT_PERSIST_ENABLED", default=True) else None
        else:
            self._store = store

    @staticmethod
    def _default_db_path() -> Path:
        configured = os.getenv("SOCIAL_HOT_DB_PATH", "").strip()
        if configured:
            return Path(configured).expanduser()
        return Path.home() / ".vntrader" / "social_hot_stocks" / "social_hot_stocks.db"

    @staticmethod
    def _generated_at() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _fetch_page(self, source_filter: str, page: int) -> dict[str, Any]:
        key = (source_filter, page)
        now = time.time()
        cached = self._cache.get(key)
        if cached and now - cached[0] < self._cache_seconds:
            return cached[1]

        url = f"{self._base_url}/filter/{source_filter}/page/{page}"
        response = self._session.get(
            url,
            headers={"User-Agent": os.getenv("APEWISDOM_USER_AGENT", "vnpy-social-hot-stocks/0.1")},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("ApeWisdom returned an invalid response.")
        self._cache[key] = (now, payload)
        return payload

    @staticmethod
    def _map_item(raw: dict[str, Any], source_filter: str, base_url: str) -> SocialHotStockItem:
        rank = _safe_int(raw.get("rank")) or 0
        mentions = _safe_int(raw.get("mentions")) or 0
        upvotes = _safe_int(raw.get("upvotes")) or 0
        rank_24h_ago = _safe_int(raw.get("rank_24h_ago"))
        mentions_24h_ago = _safe_int(raw.get("mentions_24h_ago"))
        mention_change = None if mentions_24h_ago is None else mentions - mentions_24h_ago
        mention_change_pct = None
        if mentions_24h_ago and mentions_24h_ago > 0:
            mention_change_pct = round((mentions - mentions_24h_ago) / mentions_24h_ago * 100, 1)
        rank_change = None if rank_24h_ago is None else rank_24h_ago - rank

        symbol = str(raw.get("ticker") or "").strip().upper()
        source_url = f"{base_url}/filter/{source_filter}/page/1"
        return SocialHotStockItem(
            source_filter=source_filter,
            source_url=source_url,
            rank=rank,
            symbol=symbol,
            name=unescape(str(raw.get("name") or symbol).strip()),
            mentions=mentions,
            upvotes=upvotes,
            rank_24h_ago=rank_24h_ago,
            mentions_24h_ago=mentions_24h_ago,
            mention_change=mention_change,
            mention_change_pct=mention_change_pct,
            rank_change=rank_change,
        )

    def _fetch_items(self, source_filter: str, requested_count: int) -> tuple[list[SocialHotStockItem], int, int, int]:
        items: list[SocialHotStockItem] = []
        page = 1
        pages = 1
        count = 0
        fetched_pages = 0

        while len(items) < requested_count and page <= pages:
            payload = self._fetch_page(source_filter, page)
            fetched_pages += 1
            pages = _safe_int(payload.get("pages")) or pages
            count = _safe_int(payload.get("count")) or count
            raw_results = payload.get("results")
            if not isinstance(raw_results, list):
                break
            for raw in raw_results:
                if not isinstance(raw, dict):
                    continue
                row = self._map_item(raw, source_filter, self._base_url)
                if row.symbol:
                    items.append(row)
                if len(items) >= requested_count:
                    break
            page += 1

        return items, count or len(items), pages, fetched_pages

    def _build_response(
        self,
        *,
        source: str,
        source_filter: str,
        items: list[SocialHotStockItem],
        count: int,
        page: int,
        page_size: int,
        generated_at: str,
        cache_status: str,
        snapshot_id: int | None = None,
        persisted_at: str | None = None,
    ) -> SocialHotStocksResponse:
        effective_count = max(count, len(items))
        offset = (page - 1) * page_size
        paged_items = items[offset : offset + page_size]
        return SocialHotStocksResponse(
            source=source,
            source_url=f"{self._base_url}/filter/{source_filter}/page/1",
            source_filter=source_filter,
            refresh_seconds=self._refresh_seconds,
            generated_at=generated_at,
            count=effective_count,
            page=page,
            page_size=page_size,
            total_pages=max(1, math.ceil(effective_count / page_size)),
            returned_count=len(paged_items),
            cache_status=cache_status,
            snapshot_id=snapshot_id,
            persisted_at=persisted_at,
            items=paged_items,
        )

    def _build_snapshot_response(
        self,
        *,
        source: str,
        source_filter: str,
        items: list[SocialHotStockItem],
        count: int,
        generated_at: str,
    ) -> SocialHotStocksResponse:
        page_size = max(1, len(items))
        return SocialHotStocksResponse(
            source=source,
            source_url=f"{self._base_url}/filter/{source_filter}/page/1",
            source_filter=source_filter,
            refresh_seconds=self._refresh_seconds,
            generated_at=generated_at,
            count=max(count, len(items)),
            page=1,
            page_size=page_size,
            total_pages=max(1, math.ceil(max(count, len(items)) / page_size)),
            returned_count=len(items),
            cache_status="live",
            items=items,
        )

    def _from_snapshot(
        self,
        snapshot: StoredSocialHotSnapshot,
        *,
        page: int,
        page_size: int,
        cache_status: str,
    ) -> SocialHotStocksResponse:
        offset = (page - 1) * page_size
        paged_items = snapshot.items[offset : offset + page_size]
        effective_count = max(snapshot.count, len(snapshot.items))
        return SocialHotStocksResponse(
            source=snapshot.source,
            source_label=snapshot.source_label,
            source_url=snapshot.source_url,
            source_filter=snapshot.source_filter,
            window_hours=snapshot.window_hours,
            refresh_seconds=snapshot.refresh_seconds,
            generated_at=snapshot.generated_at,
            count=effective_count,
            page=page,
            page_size=page_size,
            total_pages=max(1, math.ceil(effective_count / page_size)),
            returned_count=len(paged_items),
            cache_status=cache_status,
            snapshot_id=snapshot.id,
            persisted_at=snapshot.persisted_at,
            items=paged_items,
        )

    def _load_snapshot(
        self,
        *,
        source: str,
        source_filter: str,
        min_item_count: int,
        max_age_seconds: int | None,
    ) -> StoredSocialHotSnapshot | None:
        if self._store is None:
            return None
        return self._store.load_latest_snapshot(
            source=source,
            source_filter=source_filter,
            min_item_count=min_item_count,
            max_age_seconds=max_age_seconds,
        )

    def get_hot_stocks(
        self,
        *,
        source: str = "apewisdom",
        source_filter: str = "all-stocks",
        limit: int | None = None,
        page: int = 1,
        page_size: int | None = None,
        refresh: bool = False,
    ) -> SocialHotStocksResponse:
        normalized_source = source.lower()
        if normalized_source != "apewisdom":
            raise ValueError(f"unsupported social hot stocks source: {source}")
        if source_filter not in SUPPORTED_APEWISDOM_FILTERS:
            raise ValueError(f"unsupported ApeWisdom filter: {source_filter}")

        bounded_page = max(1, page)
        requested_page_size = page_size if page_size is not None else (limit if limit is not None else 50)
        bounded_page_size = max(1, min(requested_page_size, self._max_page_size))
        requested_count = bounded_page * bounded_page_size
        if requested_count > self._max_fetch_items:
            raise ValueError(
                f"requested social-hot-stocks page requires {requested_count} rows; "
                f"max fetch window is {self._max_fetch_items}. Reduce page or page_size."
            )

        if not refresh:
            snapshot = self._load_snapshot(
                source=normalized_source,
                source_filter=source_filter,
                min_item_count=requested_count,
                max_age_seconds=self._cache_seconds,
            )
            if snapshot is not None:
                return self._from_snapshot(
                    snapshot,
                    page=bounded_page,
                    page_size=bounded_page_size,
                    cache_status="persisted-cache",
                )

        try:
            items, count, provider_pages, provider_pages_fetched = self._fetch_items(source_filter, requested_count)
        except requests.RequestException:
            fallback = self._load_snapshot(
                source=normalized_source,
                source_filter=source_filter,
                min_item_count=max(1, (bounded_page - 1) * bounded_page_size + 1),
                max_age_seconds=None,
            )
            if fallback is not None:
                return self._from_snapshot(
                    fallback,
                    page=bounded_page,
                    page_size=bounded_page_size,
                    cache_status="persisted-fallback",
                )
            raise

        generated_at = self._generated_at()
        snapshot_id: int | None = None
        persisted_at: str | None = None
        if self._store is not None:
            snapshot_response = self._build_snapshot_response(
                source=normalized_source,
                source_filter=source_filter,
                items=items,
                count=count,
                generated_at=generated_at,
            )
            try:
                fetched_at_epoch = time.time()
                snapshot_id = self._store.insert_snapshot(
                    snapshot_response,
                    provider_pages=provider_pages,
                    provider_pages_fetched=provider_pages_fetched,
                    fetched_at_epoch=fetched_at_epoch,
                )
                persisted_at = datetime.fromtimestamp(fetched_at_epoch, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                self._store.prune_snapshots(
                    source=normalized_source,
                    source_filter=source_filter,
                    keep=self._snapshot_retention,
                )
            except sqlite3.Error:
                snapshot_id = None
                persisted_at = None

        return self._build_response(
            source=normalized_source,
            source_filter=source_filter,
            items=items,
            count=count,
            page=bounded_page,
            page_size=bounded_page_size,
            generated_at=generated_at,
            cache_status="live",
            snapshot_id=snapshot_id,
            persisted_at=persisted_at,
        )
