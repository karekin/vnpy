from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any

from psycopg.types.json import Jsonb

from vnpy.web.base_store import PgStore, _jsonb
from vnpy.web.db import DbSettings


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


class CbTushareStore(PgStore):
    """PostgreSQL store for tushare raw/derived data and sync logs."""

    def __init__(self, settings: DbSettings) -> None:
        super().__init__(settings)

    def upsert_trade_calendar(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values: list[tuple[str, bool, str, Jsonb]] = []
        for row in rows:
            cal_date = str(row.get("cal_date") or "").strip()
            if not cal_date:
                continue
            is_open = str(row.get("is_open", "0")) in {"1", "Y", "y", "true", "True"}
            values.append(
                (
                    cal_date,
                    is_open,
                    now,
                    _jsonb(row),
                )
            )
        if not values:
            return 0
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO olap.ts_trade_calendar (cal_date, is_open, updated_at, payload) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT(cal_date) DO UPDATE SET "
                "is_open=excluded.is_open, updated_at=excluded.updated_at, payload=excluded.payload",
                values,
            )
        return len(values)

    def list_open_trade_dates(self, *, start_date: str, end_date: str) -> list[str]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT cal_date FROM olap.ts_trade_calendar "
                "WHERE cal_date >= %s AND cal_date <= %s AND is_open = TRUE "
                "ORDER BY cal_date",
                (start_date.replace("-", ""), end_date.replace("-", "")),
            )
            raw = [str(item["cal_date"]) for item in cursor.fetchall()]
        return [f"{item[0:4]}-{item[4:6]}-{item[6:8]}" for item in raw if len(item) == 8]

    def upsert_cb_basic(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values: list[tuple[str, str, str, str, str, str, Jsonb]] = []
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
                    _jsonb(row),
                )
            )
        if not values:
            return 0
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO olap.ts_cb_basic ("
                "ts_code, bond_short_name, stk_code, maturity_date, issue_size, updated_at, payload"
                ") VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT(ts_code) DO UPDATE SET "
                "bond_short_name=excluded.bond_short_name, stk_code=excluded.stk_code, "
                "maturity_date=excluded.maturity_date, issue_size=excluded.issue_size, "
                "updated_at=excluded.updated_at, payload=excluded.payload",
                values,
            )
        return len(values)

    def load_cb_basic_map(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        with self._connect() as conn:
            cursor = conn.execute("SELECT ts_code, payload FROM olap.ts_cb_basic")
            for row in cursor.fetchall():
                code = str(row["ts_code"] or "")
                payload = row["payload"]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        payload = {}
                if code:
                    result[code] = payload
        return result

    def upsert_cb_daily_ods(self, *, trade_date: str, rows: list[dict[str, Any]]) -> int:
        return self._upsert_trade_rows(
            table="olap.ts_cb_daily_ods",
            trade_date=trade_date,
            rows=rows,
            code_key_candidates=("ts_code", "bond_code", "code"),
        )

    def upsert_stock_daily_ods(self, *, trade_date: str, rows: list[dict[str, Any]]) -> int:
        return self._upsert_trade_rows(
            table="olap.ts_stock_daily_ods",
            trade_date=trade_date,
            rows=rows,
            code_key_candidates=("ts_code", "stock_code", "code"),
        )

    def upsert_stock_daily_basic_ods(self, *, trade_date: str, rows: list[dict[str, Any]]) -> int:
        return self._upsert_trade_rows(
            table="olap.ts_stock_daily_basic_ods",
            trade_date=trade_date,
            rows=rows,
            code_key_candidates=("ts_code", "stock_code", "code"),
        )

    def upsert_factor_rows(self, *, trade_date: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        td = trade_date.replace("-", "")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values: list[tuple[str, str, Jsonb, str]] = []
        for row in rows:
            bond_id = str(row.get("bond_code") or row.get("bond_id") or "").strip()
            if not bond_id:
                continue
            values.append(
                (
                    td,
                    bond_id,
                    _jsonb(row),
                    now,
                )
            )
        if not values:
            return 0
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO olap.ts_cb_factor_daily (trade_date, bond_id, payload, updated_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT(trade_date, bond_id) DO UPDATE SET "
                "payload=excluded.payload, updated_at=excluded.updated_at",
                values,
            )
        return len(values)

    def load_latest_valid_prices(
        self,
        *,
        before_trade_date: str,
        bond_ids: list[str],
    ) -> dict[str, float]:
        if not bond_ids:
            return {}
        td = before_trade_date.replace("-", "")
        seen: set[str] = set()
        normalized: list[str] = []
        for raw in bond_ids:
            code = str(raw or "").strip()
            if not code or code in seen:
                continue
            seen.add(code)
            normalized.append(code)
        if not normalized:
            return {}

        placeholders = ",".join("%s" for _ in normalized)
        sql = (
            "SELECT src.bond_id, CAST(src.payload->>'close_price' AS FLOAT) AS price "
            "FROM olap.ts_cb_factor_daily AS src "
            "JOIN ("
            "  SELECT bond_id, MAX(trade_date) AS max_trade_date "
            "  FROM olap.ts_cb_factor_daily "
            f"  WHERE trade_date < %s AND bond_id IN ({placeholders}) "
            "    AND CAST(payload->>'close_price' AS FLOAT) > 0 "
            "  GROUP BY bond_id"
            ") AS latest "
            "ON src.bond_id = latest.bond_id AND src.trade_date = latest.max_trade_date"
        )
        params: list[Any] = [td, *normalized]
        result: dict[str, float] = {}
        with self._connect() as conn:
            cursor = conn.execute(sql, params)
            for row in cursor.fetchall():
                code = str(row["bond_id"] or "").strip()
                price = float(row["price"] or 0.0)
                if code and price > 0:
                    result[code] = price
        return result

    def load_trade_row_map(self, *, table: str, trade_date: str) -> dict[str, dict[str, Any]]:
        allowed = {"olap.ts_cb_daily_ods", "olap.ts_stock_daily_ods", "olap.ts_stock_daily_basic_ods"}
        if table not in allowed:
            raise ValueError(f"unsupported trade row table: {table}")

        td = trade_date.replace("-", "")
        result: dict[str, dict[str, Any]] = {}
        with self._connect() as conn:
            cursor = conn.execute(
                f"SELECT ts_code, payload FROM {table} WHERE trade_date = %s",
                (td,),
            )
            for row in cursor.fetchall():
                ts_code = str(row["ts_code"] or "").strip()
                if not ts_code:
                    continue
                payload = row["payload"]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        payload = {}
                result[ts_code] = payload
        return result

    def get_summary(self) -> TushareStoreSummary:
        with self._connect() as conn:
            cb_row = conn.execute(
                "SELECT COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) FROM olap.ts_cb_daily_ods"
            ).fetchone()
            factor_row = conn.execute(
                "SELECT COUNT(DISTINCT trade_date), MIN(trade_date), MAX(trade_date) FROM olap.ts_cb_factor_daily"
            ).fetchone()
            event_row = conn.execute("SELECT COUNT(1) FROM olap.ts_cb_event_ods").fetchone()

        cb_days = int(cb_row["count"] or 0) if cb_row else 0
        cb_start = self._format_trade_date(cb_row["min"]) if cb_row and cb_row["min"] else None
        cb_end = self._format_trade_date(cb_row["max"]) if cb_row and cb_row["max"] else None
        factor_days = int(factor_row["count"] or 0) if factor_row else 0
        factor_start = self._format_trade_date(factor_row["min"]) if factor_row and factor_row["min"] else None
        factor_end = self._format_trade_date(factor_row["max"]) if factor_row and factor_row["max"] else None
        event_rows = int(event_row["count"] or 0) if event_row else 0

        return TushareStoreSummary(
            cb_trade_days=cb_days,
            cb_date_start=cb_start,
            cb_date_end=cb_end,
            factor_trade_days=factor_days,
            factor_date_start=factor_start,
            factor_date_end=factor_end,
            event_rows=event_rows,
            db_path=str(self._settings.pg_dsn),
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
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO olap.ts_sync_log ("
                "sync_at, mode, source, start_date, end_date, trade_days, "
                "cb_daily_rows, stock_daily_rows, event_rows, factor_rows, snapshot_rows, status, message"
                ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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

    def latest_sync_log(self) -> TushareSyncLog | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT sync_at, mode, source, start_date, end_date, trade_days, "
                "cb_daily_rows, stock_daily_rows, event_rows, factor_rows, snapshot_rows, status, message "
                "FROM olap.ts_sync_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return TushareSyncLog(
            sync_at=str(row["sync_at"]),
            mode=str(row["mode"]),
            source=str(row["source"]),
            start_date=str(row["start_date"]),
            end_date=str(row["end_date"]),
            trade_days=int(row["trade_days"] or 0),
            cb_daily_rows=int(row["cb_daily_rows"] or 0),
            stock_daily_rows=int(row["stock_daily_rows"] or 0),
            event_rows=int(row["event_rows"] or 0),
            factor_rows=int(row["factor_rows"] or 0),
            snapshot_rows=int(row["snapshot_rows"] or 0),
            status=str(row["status"]),
            message=str(row["message"] or ""),
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
        values: list[tuple[str, str, str, str, Jsonb, str]] = []
        for row in rows:
            ts_code = str(row.get("ts_code") or row.get("bond_code") or row.get("code") or "").strip()
            biz_date = self._extract_event_date(row)
            if not ts_code:
                continue
            payload = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            row_hash = self._row_hash(payload)
            values.append((event_type, biz_date, ts_code, row_hash, _jsonb(row), now))
        if not values:
            return 0
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO olap.ts_cb_event_ods (event_type, biz_date, ts_code, row_hash, payload, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT(event_type, biz_date, ts_code, row_hash) DO UPDATE SET "
                "payload=excluded.payload, updated_at=excluded.updated_at",
                values,
            )
        return len(values)

    def load_cb_event_rows(
        self,
        *,
        event_type: str,
        ts_codes: list[str],
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        seen: set[str] = set()
        normalized: list[str] = []
        for raw in ts_codes:
            code = str(raw or "").strip()
            if not code or code in seen:
                continue
            seen.add(code)
            normalized.append(code)
        if not normalized:
            return []

        placeholders = ",".join("%s" for _ in normalized)
        sql = (
            "SELECT payload FROM olap.ts_cb_event_ods "
            f"WHERE event_type = %s AND ts_code IN ({placeholders})"
        )
        params: list[Any] = [event_type, *normalized]
        if end_date:
            sql += " AND biz_date <= %s"
            params.append(end_date.replace("-", ""))
        sql += " ORDER BY ts_code ASC, biz_date DESC, updated_at DESC"

        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            cursor = conn.execute(sql, params)
            for item in cursor.fetchall():
                payload = item["payload"]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        continue
                rows.append(payload)
        return rows

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
        values: list[tuple[str, str, Jsonb, str]] = []
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
                    _jsonb(row),
                    now,
                )
            )

        if not values:
            return 0
        sql = (
            f"INSERT INTO {table} (trade_date, ts_code, payload, updated_at) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT(trade_date, ts_code) DO UPDATE SET "
            "payload=excluded.payload, updated_at=excluded.updated_at"
        )
        with self._connect() as conn:
            conn.executemany(sql, values)
        return len(values)

    @staticmethod
    def _format_trade_date(value: Any) -> str | None:
        text = str(value or "").strip()
        if len(text) == 8 and text.isdigit():
            return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
        if len(text) >= 10 and text[4] == "-":
            return text[:10]
        return None

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
        return hashlib.md5(payload.encode("utf-8")).hexdigest()
