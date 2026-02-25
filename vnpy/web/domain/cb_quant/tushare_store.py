from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Any


@dataclass
class TushareStoreSummary:
    cb_trade_days: int
    cb_date_start: str | None
    cb_date_end: str | None
    factor_trade_days: int
    factor_date_start: str | None
    factor_date_end: str | None
    event_rows: int
    db_path: str


@dataclass
class TushareSyncLog:
    sync_at: str
    mode: str
    source: str
    start_date: str
    end_date: str
    trade_days: int
    cb_daily_rows: int
    stock_daily_rows: int
    event_rows: int
    factor_rows: int
    snapshot_rows: int
    status: str
    message: str


class CbTushareStore:
    """SQLite store for tushare raw/derived data and sync logs."""

    def __init__(self, db_path: Path) -> None:
        self._db_path: Path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock: Lock = Lock()
        self._ensure_schema()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def upsert_trade_calendar(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values: list[tuple[str, int, str, str]] = []
        for row in rows:
            cal_date = str(row.get("cal_date") or "").strip()
            if not cal_date:
                continue
            is_open = 1 if str(row.get("is_open", "0")) in {"1", "Y", "y", "true", "True"} else 0
            values.append(
                (
                    cal_date,
                    is_open,
                    now,
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                )
            )
        if not values:
            return 0
        with self._lock, self._connect() as conn:
            conn.executemany(
                "INSERT INTO ts_trade_calendar (cal_date, is_open, updated_at, row_json) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(cal_date) DO UPDATE SET "
                "is_open=excluded.is_open, updated_at=excluded.updated_at, row_json=excluded.row_json",
                values,
            )
            conn.commit()
        return len(values)

    def list_open_trade_dates(self, *, start_date: str, end_date: str) -> list[str]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT cal_date FROM ts_trade_calendar "
                "WHERE cal_date >= ? AND cal_date <= ? AND is_open = 1 "
                "ORDER BY cal_date",
                (start_date.replace("-", ""), end_date.replace("-", "")),
            )
            raw = [str(item[0]) for item in cursor.fetchall()]
        return [f"{item[0:4]}-{item[4:6]}-{item[6:8]}" for item in raw if len(item) == 8]

    def upsert_cb_basic(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values: list[tuple[str, str, str, str, str, str, str]] = []
        for row in rows:
            ts_code = str(row.get("ts_code") or "").strip()
            if not ts_code:
                continue
            values.append(
                (
                    ts_code,
                    str(row.get("bond_short_name") or row.get("name") or ""),
                    str(row.get("stk_code") or ""),
                    str(row.get("maturity_date") or row.get("maturity_dt") or ""),
                    str(row.get("issue_size") or row.get("actual_issue_scale") or ""),
                    now,
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                )
            )
        if not values:
            return 0
        with self._lock, self._connect() as conn:
            conn.executemany(
                "INSERT INTO ts_cb_basic ("
                "ts_code, bond_short_name, stk_code, maturity_date, issue_size, updated_at, row_json"
                ") VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(ts_code) DO UPDATE SET "
                "bond_short_name=excluded.bond_short_name, stk_code=excluded.stk_code, "
                "maturity_date=excluded.maturity_date, issue_size=excluded.issue_size, "
                "updated_at=excluded.updated_at, row_json=excluded.row_json",
                values,
            )
            conn.commit()
        return len(values)

    def load_cb_basic_map(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        with self._connect() as conn:
            cursor = conn.execute("SELECT ts_code, row_json FROM ts_cb_basic")
            for row in cursor.fetchall():
                code = str(row[0] or "")
                try:
                    payload = json.loads(str(row[1]))
                except Exception:
                    payload = {}
                if code:
                    result[code] = payload
        return result

    def upsert_cb_daily_ods(self, *, trade_date: str, rows: list[dict[str, Any]]) -> int:
        return self._upsert_trade_rows(
            table="ts_cb_daily_ods",
            trade_date=trade_date,
            rows=rows,
            code_key_candidates=("ts_code", "bond_code", "code"),
        )

    def upsert_stock_daily_ods(self, *, trade_date: str, rows: list[dict[str, Any]]) -> int:
        return self._upsert_trade_rows(
            table="ts_stock_daily_ods",
            trade_date=trade_date,
            rows=rows,
            code_key_candidates=("ts_code", "stock_code", "code"),
        )

    def upsert_stock_daily_basic_ods(self, *, trade_date: str, rows: list[dict[str, Any]]) -> int:
        return self._upsert_trade_rows(
            table="ts_stock_daily_basic_ods",
            trade_date=trade_date,
            rows=rows,
            code_key_candidates=("ts_code", "stock_code", "code"),
        )

    def upsert_factor_rows(self, *, trade_date: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        td = trade_date.replace("-", "")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values: list[tuple[str, str, str, str]] = []
        for row in rows:
            bond_id = str(row.get("cb_code") or row.get("bond_id") or "").strip()
            if not bond_id:
                continue
            values.append(
                (
                    td,
                    bond_id,
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                    now,
                )
            )
        if not values:
            return 0
        with self._lock, self._connect() as conn:
            conn.executemany(
                "INSERT INTO ts_cb_factor_daily (trade_date, bond_id, row_json, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(trade_date, bond_id) DO UPDATE SET "
                "row_json=excluded.row_json, updated_at=excluded.updated_at",
                values,
            )
            conn.commit()
        return len(values)

    def get_summary(self) -> TushareStoreSummary:
        with self._connect() as conn:
            cb_row = conn.execute(
                "SELECT COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) FROM ts_cb_daily_ods"
            ).fetchone()
            factor_row = conn.execute(
                "SELECT COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) FROM ts_cb_factor_daily"
            ).fetchone()
            event_row = conn.execute("SELECT COUNT(1) FROM ts_cb_event_ods").fetchone()

        cb_days = int(cb_row[0] or 0) if cb_row else 0
        cb_start = self._format_trade_date(cb_row[1]) if cb_row and cb_row[1] else None
        cb_end = self._format_trade_date(cb_row[2]) if cb_row and cb_row[2] else None
        factor_days = int(factor_row[0] or 0) if factor_row else 0
        factor_start = self._format_trade_date(factor_row[1]) if factor_row and factor_row[1] else None
        factor_end = self._format_trade_date(factor_row[2]) if factor_row and factor_row[2] else None
        event_rows = int(event_row[0] or 0) if event_row else 0

        return TushareStoreSummary(
            cb_trade_days=cb_days,
            cb_date_start=cb_start,
            cb_date_end=cb_end,
            factor_trade_days=factor_days,
            factor_date_start=factor_start,
            factor_date_end=factor_end,
            event_rows=event_rows,
            db_path=str(self._db_path),
        )

    def append_sync_log(
        self,
        *,
        mode: str,
        source: str,
        start_date: str,
        end_date: str,
        trade_days: int,
        cb_daily_rows: int,
        stock_daily_rows: int,
        event_rows: int,
        factor_rows: int,
        snapshot_rows: int,
        status: str,
        message: str,
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO ts_sync_log ("
                "sync_at, mode, source, start_date, end_date, trade_days, "
                "cb_daily_rows, stock_daily_rows, event_rows, factor_rows, snapshot_rows, status, message"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    now,
                    mode,
                    source,
                    start_date,
                    end_date,
                    int(trade_days),
                    int(cb_daily_rows),
                    int(stock_daily_rows),
                    int(event_rows),
                    int(factor_rows),
                    int(snapshot_rows),
                    status,
                    message[:800],
                ),
            )
            conn.commit()

    def latest_sync_log(self) -> TushareSyncLog | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT sync_at, mode, source, start_date, end_date, trade_days, "
                "cb_daily_rows, stock_daily_rows, event_rows, factor_rows, snapshot_rows, status, message "
                "FROM ts_sync_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return TushareSyncLog(
            sync_at=str(row[0]),
            mode=str(row[1]),
            source=str(row[2]),
            start_date=str(row[3]),
            end_date=str(row[4]),
            trade_days=int(row[5] or 0),
            cb_daily_rows=int(row[6] or 0),
            stock_daily_rows=int(row[7] or 0),
            event_rows=int(row[8] or 0),
            factor_rows=int(row[9] or 0),
            snapshot_rows=int(row[10] or 0),
            status=str(row[11]),
            message=str(row[12] or ""),
        )

    def upsert_cb_event_rows(
        self,
        *,
        event_type: str,
        rows: list[dict[str, Any]],
    ) -> int:
        if not rows:
            return 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values: list[tuple[str, str, str, str, str, str]] = []
        for row in rows:
            ts_code = str(row.get("ts_code") or row.get("bond_code") or row.get("code") or "").strip()
            biz_date = self._extract_event_date(row)
            if not ts_code:
                continue
            payload = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            row_hash = self._row_hash(payload)
            values.append((event_type, biz_date, ts_code, row_hash, payload, now))
        if not values:
            return 0
        with self._lock, self._connect() as conn:
            conn.executemany(
                "INSERT INTO ts_cb_event_ods (event_type, biz_date, ts_code, row_hash, row_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(event_type, biz_date, ts_code, row_hash) DO UPDATE SET "
                "row_json=excluded.row_json, updated_at=excluded.updated_at",
                values,
            )
            conn.commit()
        return len(values)

    def _upsert_trade_rows(
        self,
        *,
        table: str,
        trade_date: str,
        rows: list[dict[str, Any]],
        code_key_candidates: tuple[str, ...],
    ) -> int:
        if not rows:
            return 0
        td = trade_date.replace("-", "")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values: list[tuple[str, str, str, str]] = []
        for row in rows:
            code = ""
            for key in code_key_candidates:
                raw = row.get(key)
                if raw is None:
                    continue
                text = str(raw).strip()
                if text:
                    code = text
                    break
            if not code:
                continue
            values.append(
                (
                    td,
                    code,
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                    now,
                )
            )

        if not values:
            return 0
        sql = (
            f"INSERT INTO {table} (trade_date, ts_code, row_json, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(trade_date, ts_code) DO UPDATE SET "
            "row_json=excluded.row_json, updated_at=excluded.updated_at"
        )
        with self._lock, self._connect() as conn:
            conn.executemany(sql, values)
            conn.commit()
        return len(values)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False)

    @staticmethod
    def _format_trade_date(value: Any) -> str | None:
        text = str(value or "").strip()
        if len(text) == 8 and text.isdigit():
            return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
        if len(text) >= 10 and text[4] == "-":
            return text[:10]
        return None

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ts_trade_calendar ("
                "cal_date TEXT PRIMARY KEY, "
                "is_open INTEGER NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "row_json TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ts_trade_calendar_open "
                "ON ts_trade_calendar (is_open, cal_date)"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS ts_cb_basic ("
                "ts_code TEXT PRIMARY KEY, "
                "bond_short_name TEXT, "
                "stk_code TEXT, "
                "maturity_date TEXT, "
                "issue_size TEXT, "
                "updated_at TEXT NOT NULL, "
                "row_json TEXT NOT NULL"
                ")"
            )

            for table in ("ts_cb_daily_ods", "ts_stock_daily_ods", "ts_stock_daily_basic_ods"):
                conn.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} ("
                    "trade_date TEXT NOT NULL, "
                    "ts_code TEXT NOT NULL, "
                    "row_json TEXT NOT NULL, "
                    "updated_at TEXT NOT NULL, "
                    "PRIMARY KEY (trade_date, ts_code)"
                    ")"
                )
                conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_date "
                    f"ON {table} (trade_date)"
                )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS ts_cb_factor_daily ("
                "trade_date TEXT NOT NULL, "
                "bond_id TEXT NOT NULL, "
                "row_json TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "PRIMARY KEY (trade_date, bond_id)"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ts_cb_factor_daily_date "
                "ON ts_cb_factor_daily (trade_date)"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS ts_sync_log ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "sync_at TEXT NOT NULL, "
                "mode TEXT NOT NULL, "
                "source TEXT NOT NULL, "
                "start_date TEXT NOT NULL, "
                "end_date TEXT NOT NULL, "
                "trade_days INTEGER NOT NULL, "
                "cb_daily_rows INTEGER NOT NULL, "
                "stock_daily_rows INTEGER NOT NULL, "
                "event_rows INTEGER NOT NULL DEFAULT 0, "
                "factor_rows INTEGER NOT NULL, "
                "snapshot_rows INTEGER NOT NULL, "
                "status TEXT NOT NULL, "
                "message TEXT NOT NULL"
                ")"
            )
            # Backward-compatible migration for existing databases.
            columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(ts_sync_log)").fetchall()
            }
            if "event_rows" not in columns:
                conn.execute("ALTER TABLE ts_sync_log ADD COLUMN event_rows INTEGER NOT NULL DEFAULT 0")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS ts_cb_event_ods ("
                "event_type TEXT NOT NULL, "
                "biz_date TEXT NOT NULL, "
                "ts_code TEXT NOT NULL, "
                "row_hash TEXT NOT NULL, "
                "row_json TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "PRIMARY KEY (event_type, biz_date, ts_code, row_hash)"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ts_cb_event_ods_type_date "
                "ON ts_cb_event_ods (event_type, biz_date)"
            )
            conn.commit()

    @staticmethod
    def _extract_event_date(row: dict[str, Any]) -> str:
        candidates = (
            "trade_date",
            "ann_date",
            "change_date",
            "end_date",
            "list_date",
            "issue_date",
        )
        for key in candidates:
            value = row.get(key)
            text = str(value or "").strip()
            if len(text) == 8 and text.isdigit():
                return text
            if len(text) >= 10 and text[4] == "-":
                return f"{text[0:4]}{text[5:7]}{text[8:10]}"
        return "00000000"

    @staticmethod
    def _row_hash(payload: str) -> str:
        import hashlib

        return hashlib.md5(payload.encode("utf-8")).hexdigest()
