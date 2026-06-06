from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from vnpy.web.base_store import PgStore, _jsonb
from vnpy.web.db import DbSettings
from vnpy.web.domain.cb_quant.snapshot_schema import normalize_snapshot_row

@dataclass
class HistoryStoreSummary:
    snapshot_count: int
    date_start: str | None
    date_end: str | None
    latest_trade_date: str | None
    latest_bond_count: int
    db_path: str


@dataclass
class HistorySyncLog:
    sync_at: str
    mode: str
    source: str
    trade_date: str
    upserted: int
    status: str
    message: str


class CbHistoryStore(PgStore):
    """PostgreSQL-backed store for daily CB cross-section snapshots."""

    def __init__(self, settings: DbSettings) -> None:
        super().__init__(settings)

    @property
    def db_path(self) -> str:
        return self._settings.pg_dsn

    def upsert_snapshot_rows(
        self,
        *,
        trade_date: str,
        source: str,
        rows: list[dict[str, Any]],
    ) -> int:
        if not rows:
            return 0

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values: list[tuple[str, str, str, Any, str]] = []
        for row in rows:
            normalized_row = normalize_snapshot_row(dict(row))
            bond_id = str(normalized_row.get("bond_code") or "").strip()
            if not bond_id:
                continue
            values.append((trade_date, bond_id, source, _jsonb(normalized_row), now))

        if not values:
            return 0

        sql = (
            "INSERT INTO olap.cb_daily_snapshot (trade_date, bond_id, source, payload, updated_at) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (trade_date, bond_id) DO UPDATE SET "
            "source = EXCLUDED.source, payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at"
        )
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, values)
        return len(values)

    def list_trade_dates(self) -> list[str]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT trade_date FROM olap.cb_daily_snapshot ORDER BY trade_date")
                return [str(row["trade_date"]) for row in cur.fetchall()]

    def load_market_dataset(self) -> list[tuple[str, pd.DataFrame]]:
        dates = self.list_trade_dates()
        if not dates:
            return []

        dataset: list[tuple[str, pd.DataFrame]] = []
        with self._connect() as conn:
            for trade_date in dates:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT payload FROM olap.cb_daily_snapshot WHERE trade_date = %s ORDER BY bond_id",
                        (trade_date,),
                    )
                    raw_rows = [normalize_snapshot_row(dict(row["payload"])) for row in cur.fetchall()]
                if not raw_rows:
                    continue
                frame = pd.DataFrame(raw_rows)
                if "bond_code" not in frame.columns:
                    continue
                frame["bond_code"] = frame["bond_code"].astype(str)
                frame = frame.set_index("bond_code", drop=False)
                dataset.append((trade_date, frame))
        return dataset

    def get_summary(self) -> HistoryStoreSummary:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT MIN(trade_date) AS date_start, MAX(trade_date) AS date_end, "
                    "COUNT(DISTINCT trade_date) AS snapshot_count FROM olap.cb_daily_snapshot"
                )
                date_row = cur.fetchone()
                date_start = str(date_row["date_start"]) if date_row and date_row["date_start"] else None
                date_end = str(date_row["date_end"]) if date_row and date_row["date_end"] else None
                snapshot_count = int(date_row["snapshot_count"] or 0) if date_row else 0

                latest_bond_count = 0
                if date_end:
                    cur.execute(
                        "SELECT COUNT(1) AS cnt FROM olap.cb_daily_snapshot WHERE trade_date = %s",
                        (date_end,),
                    )
                    latest_row = cur.fetchone()
                    latest_bond_count = int(latest_row["cnt"] or 0) if latest_row else 0

        return HistoryStoreSummary(
            snapshot_count=snapshot_count,
            date_start=date_start,
            date_end=date_end,
            latest_trade_date=date_end,
            latest_bond_count=latest_bond_count,
            db_path=self._settings.pg_dsn,
        )

    def append_sync_log(
        self,
        *,
        mode: str,
        source: str,
        trade_date: str,
        upserted: int,
        status: str,
        message: str,
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO olap.cb_sync_log (sync_at, mode, source, trade_date, upserted, status, message) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (now, mode, source, trade_date, upserted, status, message[:600]),
                )

    def latest_sync_log(self) -> HistorySyncLog | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sync_at, mode, source, trade_date, upserted, status, message "
                    "FROM olap.cb_sync_log ORDER BY id DESC LIMIT 1"
                )
                row = cur.fetchone()
        if not row:
            return None
        return HistorySyncLog(
            sync_at=str(row["sync_at"]),
            mode=str(row["mode"]),
            source=str(row["source"]),
            trade_date=str(row["trade_date"]),
            upserted=int(row["upserted"] or 0),
            status=str(row["status"]),
            message=str(row["message"] or ""),
        )
