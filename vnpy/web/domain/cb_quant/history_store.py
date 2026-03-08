from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Any

import pandas as pd

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


class CbHistoryStore:
    """SQLite-backed store for daily CB cross-section snapshots."""

    def __init__(self, db_path: Path) -> None:
        self._db_path: Path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock: Lock = Lock()
        self._ensure_schema()

    @property
    def db_path(self) -> Path:
        return self._db_path

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
        values: list[tuple[str, str, str, str, str]] = []
        for row in rows:
            normalized_row = normalize_snapshot_row(dict(row))
            bond_id = str(normalized_row.get("cb_code") or "").strip()
            if not bond_id:
                continue
            payload = json.dumps(normalized_row, ensure_ascii=False, separators=(",", ":"))
            values.append((trade_date, bond_id, source, payload, now))

        if not values:
            return 0

        sql = (
            "INSERT INTO cb_daily_snapshot (trade_date, bond_id, source, payload_json, updated_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(trade_date, bond_id) DO UPDATE SET "
            "source=excluded.source, payload_json=excluded.payload_json, updated_at=excluded.updated_at"
        )
        with self._lock, self._connect() as conn:
            conn.executemany(sql, values)
            conn.commit()
        return len(values)

    def list_trade_dates(self) -> list[str]:
        with self._connect() as conn:
            cursor = conn.execute("SELECT DISTINCT trade_date FROM cb_daily_snapshot ORDER BY trade_date")
            return [str(row[0]) for row in cursor.fetchall()]

    def load_market_dataset(self) -> list[tuple[str, pd.DataFrame]]:
        dates = self.list_trade_dates()
        if not dates:
            return []

        dataset: list[tuple[str, pd.DataFrame]] = []
        with self._connect() as conn:
            for trade_date in dates:
                cursor = conn.execute(
                    "SELECT payload_json FROM cb_daily_snapshot WHERE trade_date = ? ORDER BY bond_id",
                    (trade_date,),
                )
                raw_rows = [json.loads(str(item[0])) for item in cursor.fetchall()]
                if not raw_rows:
                    continue
                frame = pd.DataFrame(raw_rows)
                if "cb_code" not in frame.columns:
                    continue
                frame["cb_code"] = frame["cb_code"].astype(str)
                frame = frame.set_index("cb_code", drop=False)
                dataset.append((trade_date, frame))
        return dataset

    def get_summary(self) -> HistoryStoreSummary:
        with self._connect() as conn:
            date_row = conn.execute(
                "SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM cb_daily_snapshot"
            ).fetchone()
            date_start = str(date_row[0]) if date_row and date_row[0] else None
            date_end = str(date_row[1]) if date_row and date_row[1] else None
            snapshot_count = int(date_row[2] or 0) if date_row else 0

            latest_bond_count = 0
            if date_end:
                latest_row = conn.execute(
                    "SELECT COUNT(1) FROM cb_daily_snapshot WHERE trade_date = ?",
                    (date_end,),
                ).fetchone()
                latest_bond_count = int(latest_row[0] or 0) if latest_row else 0

        return HistoryStoreSummary(
            snapshot_count=snapshot_count,
            date_start=date_start,
            date_end=date_end,
            latest_trade_date=date_end,
            latest_bond_count=latest_bond_count,
            db_path=str(self._db_path),
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
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO cb_sync_log (sync_at, mode, source, trade_date, upserted, status, message) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now, mode, source, trade_date, upserted, status, message[:600]),
            )
            conn.commit()

    def latest_sync_log(self) -> HistorySyncLog | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT sync_at, mode, source, trade_date, upserted, status, message "
                "FROM cb_sync_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return HistorySyncLog(
            sync_at=str(row[0]),
            mode=str(row[1]),
            source=str(row[2]),
            trade_date=str(row[3]),
            upserted=int(row[4] or 0),
            status=str(row[5]),
            message=str(row[6] or ""),
        )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False)

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_daily_snapshot ("
                "trade_date TEXT NOT NULL, "
                "bond_id TEXT NOT NULL, "
                "source TEXT NOT NULL, "
                "payload_json TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "PRIMARY KEY (trade_date, bond_id)"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_daily_snapshot_date ON cb_daily_snapshot (trade_date)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_sync_log ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "sync_at TEXT NOT NULL, "
                "mode TEXT NOT NULL, "
                "source TEXT NOT NULL, "
                "trade_date TEXT NOT NULL, "
                "upserted INTEGER NOT NULL, "
                "status TEXT NOT NULL, "
                "message TEXT NOT NULL"
                ")"
            )
            conn.commit()
