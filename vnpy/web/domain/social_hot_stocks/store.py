from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import Lock
import time
from typing import Any

from vnpy.web.contracts.social_hot_stocks import SocialHotStockItem, SocialHotStocksResponse


def _now_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _loads(payload: str) -> Any:
    return json.loads(payload)


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


class SocialHotStocksStore:
    """SQLite-backed ApeWisdom snapshot store."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._ensure_schema()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def insert_snapshot(
        self,
        response: SocialHotStocksResponse,
        *,
        provider_pages: int,
        provider_pages_fetched: int,
        fetched_at_epoch: float | None = None,
    ) -> int:
        fetched_at = fetched_at_epoch or time.time()
        items_json = _dumps([item.model_dump(mode="json") for item in response.items])
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO social_hot_stock_snapshot (
                    source,
                    source_label,
                    source_filter,
                    source_url,
                    window_hours,
                    refresh_seconds,
                    generated_at,
                    fetched_at_epoch,
                    count,
                    provider_pages,
                    provider_pages_fetched,
                    item_count,
                    items_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    items_json,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

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
            "SELECT * FROM social_hot_stock_snapshot "
            "WHERE source = ? AND source_filter = ? AND item_count >= ? "
        )
        params: list[Any] = [source, source_filter, min_item_count]
        if cutoff is not None:
            query += "AND fetched_at_epoch >= ? "
            params.append(cutoff)
        query += "ORDER BY fetched_at_epoch DESC, id DESC LIMIT 1"

        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return self._row_to_snapshot(row) if row is not None else None

    def prune_snapshots(self, *, source: str, source_filter: str, keep: int) -> None:
        if keep <= 0:
            return
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                DELETE FROM social_hot_stock_snapshot
                WHERE source = ?
                  AND source_filter = ?
                  AND id NOT IN (
                      SELECT id
                      FROM social_hot_stock_snapshot
                      WHERE source = ? AND source_filter = ?
                      ORDER BY fetched_at_epoch DESC, id DESC
                      LIMIT ?
                  )
                """,
                (source, source_filter, source, source_filter, keep),
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS social_hot_stock_snapshot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_label TEXT NOT NULL,
                    source_filter TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    window_hours INTEGER NOT NULL,
                    refresh_seconds INTEGER NOT NULL,
                    generated_at TEXT NOT NULL,
                    fetched_at_epoch REAL NOT NULL,
                    count INTEGER NOT NULL,
                    provider_pages INTEGER NOT NULL,
                    provider_pages_fetched INTEGER NOT NULL,
                    item_count INTEGER NOT NULL,
                    items_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_social_hot_snapshot_lookup
                ON social_hot_stock_snapshot (source, source_filter, item_count, fetched_at_epoch DESC, id DESC)
                """
            )
            conn.commit()

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> StoredSocialHotSnapshot:
        raw_items = _loads(str(row["items_json"]))
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
