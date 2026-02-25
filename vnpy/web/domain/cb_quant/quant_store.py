from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Any


class CbQuantStore:
    """SQLite-backed store for cb quant templates and backtest tasks."""

    def __init__(self, db_path: Path) -> None:
        self._db_path: Path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock: Lock = Lock()
        self._ensure_schema()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def load_templates_and_configs(self) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        templates: list[dict[str, Any]] = []
        configs: dict[str, dict[str, Any]] = {}
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT row_json FROM cb_strategy_template ORDER BY updated_at DESC, id DESC"
            ).fetchall():
                try:
                    templates.append(json.loads(str(row[0])))
                except Exception:
                    continue

            for row in conn.execute(
                "SELECT template_id, config_json FROM cb_strategy_template_config"
            ).fetchall():
                template_id = str(row[0])
                try:
                    configs[template_id] = json.loads(str(row[1]))
                except Exception:
                    continue
        return templates, configs

    def replace_templates_and_configs(
        self,
        *,
        templates: list[dict[str, Any]],
        configs: dict[str, dict[str, Any]],
    ) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM cb_strategy_template")
            conn.execute("DELETE FROM cb_strategy_template_config")
            for row in templates:
                template_id = str(row.get("id", "")).strip()
                if not template_id:
                    continue
                conn.execute(
                    "INSERT INTO cb_strategy_template "
                    "(id, name, status, owner, updated_at, row_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        template_id,
                        str(row.get("name", "")),
                        str(row.get("status", "")),
                        str(row.get("owner", "")),
                        str(row.get("updated_at", now)),
                        json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                    ),
                )

            for template_id, config in configs.items():
                if not template_id:
                    continue
                conn.execute(
                    "INSERT INTO cb_strategy_template_config "
                    "(template_id, updated_at, config_json) "
                    "VALUES (?, ?, ?)",
                    (
                        template_id,
                        str(config.get("updated_at", now)),
                        json.dumps(config, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
            conn.commit()

    def load_jobs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT row_json, window_name, start_date, end_date, setting_json, cancel_requested, "
                "business_date, created_at "
                "FROM cb_backtest_job "
                "ORDER BY created_at DESC, job_id DESC"
            ).fetchall():
                try:
                    payload = json.loads(str(row[0]))
                except Exception:
                    continue

                setting: dict[str, Any]
                try:
                    setting = json.loads(str(row[4]))
                except Exception:
                    setting = {}

                rows.append(
                    {
                        "row": payload,
                        "window_name": str(row[1] or "full"),
                        "start_date": str(row[2]) if row[2] else None,
                        "end_date": str(row[3]) if row[3] else None,
                        "setting": setting,
                        "cancel_requested": bool(int(row[5] or 0)),
                        "business_date": str(row[6] or ""),
                        "created_at": str(row[7] or ""),
                    }
                )
        return rows

    def get_job_context(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT window_name, start_date, end_date, setting_json, cancel_requested, "
                "business_date, created_at "
                "FROM cb_backtest_job WHERE job_id = ? LIMIT 1",
                (job_id,),
            ).fetchone()
        if not row:
            return None
        try:
            setting = json.loads(str(row[3]))
        except Exception:
            setting = {}
        return {
            "window_name": str(row[0] or "full"),
            "start_date": str(row[1]) if row[1] else None,
            "end_date": str(row[2]) if row[2] else None,
            "setting": setting,
            "cancel_requested": bool(int(row[4] or 0)),
            "business_date": str(row[5] or ""),
            "created_at": str(row[6] or ""),
        }

    def upsert_job(self, *, row: dict[str, Any], context: dict[str, Any]) -> None:
        job_id = str(row.get("job_id") or "").strip()
        if not job_id:
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        window_name = str(context.get("window_name") or "full")
        start_date = context.get("start_date")
        end_date = context.get("end_date")
        setting = context.get("setting") or {}
        cancel_requested = 1 if bool(context.get("cancel_requested")) else 0
        business_date = str(row.get("business_date") or context.get("business_date") or now[:10])
        created_at = str(row.get("created_at") or context.get("created_at") or now)

        if hasattr(start_date, "isoformat"):
            start_date = start_date.isoformat()
        if hasattr(end_date, "isoformat"):
            end_date = end_date.isoformat()

        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO cb_backtest_job ("
                "job_id, strategy_id, combo_id, rule_pack_id, template, window, status, progress, "
                "business_date, created_at, started_at, eta, worker, updated_at, "
                "window_name, start_date, end_date, setting_json, cancel_requested, row_json"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(job_id) DO UPDATE SET "
                "strategy_id=excluded.strategy_id, combo_id=excluded.combo_id, "
                "rule_pack_id=excluded.rule_pack_id, template=excluded.template, window=excluded.window, "
                "status=excluded.status, progress=excluded.progress, business_date=excluded.business_date, "
                "created_at=excluded.created_at, started_at=excluded.started_at, eta=excluded.eta, "
                "worker=excluded.worker, updated_at=excluded.updated_at, window_name=excluded.window_name, "
                "start_date=excluded.start_date, end_date=excluded.end_date, "
                "setting_json=excluded.setting_json, cancel_requested=excluded.cancel_requested, "
                "row_json=excluded.row_json",
                (
                    job_id,
                    str(row.get("strategy_id", "")),
                    str(row.get("combo_id", "")),
                    str(row.get("rule_pack_id", "")),
                    str(row.get("template", "")),
                    str(row.get("window", "")),
                    str(row.get("status", "")),
                    int(row.get("progress", 0)),
                    business_date,
                    created_at,
                    str(row.get("started_at", "")),
                    str(row.get("eta", "")),
                    str(row.get("worker", "")),
                    now,
                    window_name,
                    str(start_date) if start_date else None,
                    str(end_date) if end_date else None,
                    json.dumps(setting, ensure_ascii=False, separators=(",", ":")),
                    cancel_requested,
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            conn.commit()

    def replace_leaderboard(self, rows: list[dict[str, Any]]) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM cb_backtest_leaderboard")
            for item in rows:
                row = item.get("row") or {}
                business_date = str(item.get("business_date") or now[:10])
                combo_id = str(row.get("combo_id", "")).strip()
                rule_pack_id = str(row.get("rule_pack_id", "")).strip()
                window = str(row.get("window", "")).strip()
                if not combo_id or not rule_pack_id or not window:
                    continue
                conn.execute(
                    "INSERT INTO cb_backtest_leaderboard "
                    "(combo_id, rule_pack_id, window, business_date, updated_at, row_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        combo_id,
                        rule_pack_id,
                        window,
                        business_date,
                        now,
                        json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
            conn.commit()

    def load_leaderboard(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT business_date, row_json FROM cb_backtest_leaderboard ORDER BY updated_at DESC"
            ).fetchall():
                try:
                    payload = json.loads(str(row[1]))
                except Exception:
                    continue
                rows.append(
                    {
                        "business_date": str(row[0] or ""),
                        "row": payload,
                    }
                )
        return rows

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False)

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_strategy_template ("
                "id TEXT PRIMARY KEY, "
                "name TEXT NOT NULL, "
                "status TEXT NOT NULL, "
                "owner TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "row_json TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_strategy_template_updated "
                "ON cb_strategy_template (updated_at DESC)"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_strategy_template_config ("
                "template_id TEXT PRIMARY KEY, "
                "updated_at TEXT NOT NULL, "
                "config_json TEXT NOT NULL"
                ")"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_backtest_job ("
                "job_id TEXT PRIMARY KEY, "
                "strategy_id TEXT NOT NULL, "
                "combo_id TEXT NOT NULL, "
                "rule_pack_id TEXT NOT NULL, "
                "template TEXT NOT NULL, "
                "window TEXT NOT NULL, "
                "status TEXT NOT NULL, "
                "progress INTEGER NOT NULL, "
                "business_date TEXT NOT NULL, "
                "created_at TEXT NOT NULL, "
                "started_at TEXT NOT NULL, "
                "eta TEXT NOT NULL, "
                "worker TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "window_name TEXT NOT NULL, "
                "start_date TEXT, "
                "end_date TEXT, "
                "setting_json TEXT NOT NULL, "
                "cancel_requested INTEGER NOT NULL DEFAULT 0, "
                "row_json TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_backtest_job_status_date "
                "ON cb_backtest_job (status, business_date, created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_backtest_job_combo "
                "ON cb_backtest_job (combo_id)"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_backtest_leaderboard ("
                "combo_id TEXT NOT NULL, "
                "rule_pack_id TEXT NOT NULL, "
                "window TEXT NOT NULL, "
                "business_date TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "row_json TEXT NOT NULL, "
                "PRIMARY KEY (combo_id, rule_pack_id, window)"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_backtest_leaderboard_date "
                "ON cb_backtest_leaderboard (business_date, updated_at DESC)"
            )
            conn.commit()
