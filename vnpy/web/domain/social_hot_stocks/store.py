from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from typing import Any

from psycopg.types.json import Jsonb

from vnpy.web.base_store import PgStore, _jsonb
from vnpy.web.db import DbSettings
from vnpy.web.contracts.social_hot_stocks import SocialHotStockItem, SocialHotStocksResponse


def _now_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


@dataclass(frozen=True)
class StoredSocialHotSnapshot:
    id: int
    source: str
    source_label: str
    source_url: str
    source_filter: str
    window_hours: int
    refresh_seconds: int
    generated_at: str
    fetched_at_epoch: float
    count: int
    provider_pages: int
    provider_pages_fetched: int
    item_count: int
    items: list[SocialHotStockItem]

    @property
    def persisted_at(self) -> str:
        return datetime.fromtimestamp(self.fetched_at_epoch, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


class SocialHotStocksStore(PgStore):
    """PostgreSQL-backed ApeWisdom snapshot store."""

    def __init__(self, settings: DbSettings) -> None:
        super().__init__(settings)

    def insert_snapshot(
        self,
        response: SocialHotStocksResponse,
        *,
        provider_pages: int,
        provider_pages_fetched: int,
        fetched_at_epoch: float | None = None,
    ) -> int:
        fetched_at = fetched_at_epoch or time.time()
        items_jsonb = _jsonb([item.model_dump(mode="json") for item in response.items])
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO oltp.social_hot_stock_snapshot (
                    source, source_label, source_filter, source_url,
                    window_hours, refresh_seconds, generated_at, fetched_at_epoch,
                    count, provider_pages, provider_pages_fetched, item_count, items_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    response.source,
                    response.source_label,
                    response.source_filter,
                    response.source_url,
                    response.window_hours,
                    response.refresh_seconds,
                    response.generated_at,
                    fetched_at,
                    response.count,
                    provider_pages,
                    provider_pages_fetched,
                    len(response.items),
                    items_jsonb,
                ),
            )
            row = cursor.fetchone()
            return int(row["id"])

    def load_latest_snapshot(
        self,
        *,
        source: str,
        source_filter: str,
        min_item_count: int = 1,
        max_age_seconds: int | None = None,
    ) -> StoredSocialHotSnapshot | None:
        cutoff = time.time() - max_age_seconds if max_age_seconds is not None else None
        query = (
            "SELECT * FROM oltp.social_hot_stock_snapshot "
            "WHERE source = %s AND source_filter = %s AND item_count >= %s "
        )
        params: list[Any] = [source, source_filter, min_item_count]
        if cutoff is not None:
            query += "AND fetched_at_epoch >= %s "
            params.append(cutoff)
        query += "ORDER BY fetched_at_epoch DESC, id DESC LIMIT 1"

        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return self._row_to_snapshot(row) if row is not None else None

    def prune_snapshots(self, *, source: str, source_filter: str, keep: int) -> None:
        if keep <= 0:
            return
        with self._connect() as conn:
            conn.execute(
                """
                DELETE FROM oltp.social_hot_stock_snapshot
                WHERE source = %s
                  AND source_filter = %s
                  AND id NOT IN (
                      SELECT id
                      FROM oltp.social_hot_stock_snapshot
                      WHERE source = %s AND source_filter = %s
                      ORDER BY fetched_at_epoch DESC, id DESC
                      LIMIT %s
                  )
                """,
                (source, source_filter, source, source_filter, keep),
            )

    @staticmethod
    def _row_to_snapshot(row: dict[str, Any]) -> StoredSocialHotSnapshot:
        raw_items = row["items_json"]
        if isinstance(raw_items, str):
            raw_items = json.loads(raw_items)
        items = [
            SocialHotStockItem.model_validate(item)
            for item in raw_items
            if isinstance(item, dict)
        ]
        return StoredSocialHotSnapshot(
            id=int(row["id"]),
            source=str(row["source"]),
            source_label=str(row["source_label"]),
            source_url=str(row["source_url"]),
            source_filter=str(row["source_filter"]),
            window_hours=int(row["window_hours"]),
            refresh_seconds=int(row["refresh_seconds"]),
            generated_at=str(row["generated_at"] or _now_label()),
            fetched_at_epoch=float(row["fetched_at_epoch"]),
            count=int(row["count"]),
            provider_pages=int(row["provider_pages"]),
            provider_pages_fetched=int(row["provider_pages_fetched"]),
            item_count=int(row["item_count"]),
            items=items,
        )
