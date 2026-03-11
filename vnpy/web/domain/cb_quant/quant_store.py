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

    def delete_jobs(self, job_ids: list[str]) -> None:
        normalized = [str(job_id).strip() for job_id in job_ids if str(job_id).strip()]
        if not normalized:
            return
        with self._lock, self._connect() as conn:
            conn.executemany(
                "DELETE FROM cb_backtest_job WHERE job_id = ?",
                [(job_id,) for job_id in normalized],
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

    def load_optimize_tasks(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT row_json FROM cb_optimize_task ORDER BY created_at DESC, task_id DESC"
            ).fetchall():
                try:
                    rows.append(json.loads(str(row[0])))
                except Exception:
                    continue
        return rows

    def load_optimize_batches(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT row_json FROM cb_optimize_batch ORDER BY created_at DESC, batch_id DESC"
            ).fetchall():
                try:
                    rows.append(json.loads(str(row[0])))
                except Exception:
                    continue
        return rows

    def load_optimize_shards(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT row_json FROM cb_optimize_shard ORDER BY task_id, sequence ASC, shard_id ASC"
            ).fetchall():
                try:
                    rows.append(json.loads(str(row[0])))
                except Exception:
                    continue
        return rows

    def load_optimize_shard_result_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT task_id, shard_id, row_json FROM cb_optimize_shard_result "
                "ORDER BY task_id, shard_id, rank ASC"
            ).fetchall():
                try:
                    payload = json.loads(str(row[2]))
                except Exception:
                    continue
                rows.append(
                    {
                        "task_id": str(row[0] or ""),
                        "shard_id": str(row[1] or ""),
                        "row": payload,
                    }
                )
        return rows

    def upsert_optimize_task(self, *, row: dict[str, Any]) -> None:
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        created_at = str(row.get("created_at") or now)
        status = str(row.get("status") or "queued")
        template_id = str(row.get("template_id") or "")
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO cb_optimize_task ("
                "task_id, template_id, status, created_at, updated_at, row_json"
                ") VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(task_id) DO UPDATE SET "
                "template_id=excluded.template_id, status=excluded.status, "
                "created_at=excluded.created_at, updated_at=excluded.updated_at, "
                "row_json=excluded.row_json",
                (
                    task_id,
                    template_id,
                    status,
                    created_at,
                    now,
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            conn.commit()

    def upsert_optimize_batch(self, *, row: dict[str, Any]) -> None:
        batch_id = str(row.get("batch_id") or "").strip()
        if not batch_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        created_at = str(row.get("created_at") or now)
        status = str(row.get("status") or "queued")
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO cb_optimize_batch ("
                "batch_id, status, created_at, updated_at, row_json"
                ") VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(batch_id) DO UPDATE SET "
                "status=excluded.status, created_at=excluded.created_at, updated_at=excluded.updated_at, "
                "row_json=excluded.row_json",
                (
                    batch_id,
                    status,
                    created_at,
                    now,
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            conn.commit()

    def delete_optimize_batch(self, batch_id: str) -> None:
        if not batch_id:
            return
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM cb_optimize_batch WHERE batch_id = ?", (batch_id,))
            conn.commit()

    def upsert_optimize_shard(self, *, row: dict[str, Any]) -> None:
        shard_id = str(row.get("shard_id") or "").strip()
        task_id = str(row.get("task_id") or "").strip()
        if not shard_id or not task_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        created_at = str(row.get("created_at") or now)
        status = str(row.get("status") or "queued")
        stage = str(row.get("stage") or "full")
        sequence = int(row.get("sequence") or 1)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO cb_optimize_shard ("
                "shard_id, task_id, stage, sequence, status, created_at, updated_at, row_json"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(shard_id) DO UPDATE SET "
                "task_id=excluded.task_id, stage=excluded.stage, sequence=excluded.sequence, "
                "status=excluded.status, created_at=excluded.created_at, updated_at=excluded.updated_at, "
                "row_json=excluded.row_json",
                (
                    shard_id,
                    task_id,
                    stage,
                    sequence,
                    status,
                    created_at,
                    now,
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            conn.commit()

    def replace_optimize_shards(self, *, task_id: str, rows: list[dict[str, Any]]) -> None:
        if not task_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM cb_optimize_shard WHERE task_id = ?", (task_id,))
            for row in rows:
                shard_id = str(row.get("shard_id") or "").strip()
                if not shard_id:
                    continue
                stage = str(row.get("stage") or "full")
                sequence = int(row.get("sequence") or 1)
                status = str(row.get("status") or "queued")
                created_at = str(row.get("created_at") or now)
                conn.execute(
                    "INSERT INTO cb_optimize_shard ("
                    "shard_id, task_id, stage, sequence, status, created_at, updated_at, row_json"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        shard_id,
                        task_id,
                        stage,
                        sequence,
                        status,
                        created_at,
                        now,
                        json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
            conn.commit()

    def replace_optimize_shard_result_rows(self, *, task_id: str, shard_id: str, rows: list[dict[str, Any]]) -> None:
        if not task_id or not shard_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM cb_optimize_shard_result WHERE task_id = ? AND shard_id = ?",
                (task_id, shard_id),
            )
            for row in rows:
                combo_id = str(row.get("combo_id") or "").strip()
                if not combo_id:
                    continue
                rank = int(row.get("rank") or 0)
                conn.execute(
                    "INSERT INTO cb_optimize_shard_result ("
                    "task_id, shard_id, combo_id, rank, updated_at, row_json"
                    ") VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        task_id,
                        shard_id,
                        combo_id,
                        rank,
                        now,
                        json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
            conn.commit()

    def delete_optimize_shard_result_rows(self, *, task_id: str, shard_id: str | None = None) -> None:
        if not task_id:
            return
        with self._lock, self._connect() as conn:
            if shard_id:
                conn.execute(
                    "DELETE FROM cb_optimize_shard_result WHERE task_id = ? AND shard_id = ?",
                    (task_id, shard_id),
                )
            else:
                conn.execute(
                    "DELETE FROM cb_optimize_shard_result WHERE task_id = ?",
                    (task_id,),
                )
            conn.commit()

    def load_optimize_result_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT task_id, row_json FROM cb_optimize_result ORDER BY task_id, rank ASC"
            ).fetchall():
                try:
                    payload = json.loads(str(row[1]))
                except Exception:
                    continue
                rows.append(
                    {
                        "task_id": str(row[0]),
                        "row": payload,
                    }
                )
        return rows

    def replace_optimize_result_rows(self, *, task_id: str, rows: list[dict[str, Any]]) -> None:
        if not task_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM cb_optimize_result WHERE task_id = ?", (task_id,))
            for row in rows:
                combo_id = str(row.get("combo_id") or "").strip()
                if not combo_id:
                    continue
                rank = int(row.get("rank") or 0)
                conn.execute(
                    "INSERT INTO cb_optimize_result ("
                    "task_id, combo_id, rank, updated_at, row_json"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (
                        task_id,
                        combo_id,
                        rank,
                        now,
                        json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
            conn.commit()

    def load_optimize_top_bond_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT task_id, row_json FROM cb_optimize_top_bond ORDER BY task_id, rank ASC"
            ).fetchall():
                try:
                    payload = json.loads(str(row[1]))
                except Exception:
                    continue
                rows.append(
                    {
                        "task_id": str(row[0]),
                        "row": payload,
                    }
                )
        return rows

    def replace_optimize_top_bond_rows(self, *, task_id: str, rows: list[dict[str, Any]]) -> None:
        if not task_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM cb_optimize_top_bond WHERE task_id = ?", (task_id,))
            for row in rows:
                bond_id = str(row.get("bond_id") or "").strip()
                if not bond_id:
                    continue
                rank = int(row.get("rank") or 0)
                conn.execute(
                    "INSERT INTO cb_optimize_top_bond ("
                    "task_id, bond_id, rank, updated_at, row_json"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (
                        task_id,
                        bond_id,
                        rank,
                        now,
                        json.dumps(row, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
            conn.commit()

    def load_optimize_task_analysis_snapshot(self, task_id: str) -> dict[str, Any] | None:
        """读取某个优化任务最佳策略的分析快照。"""
        if not task_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT task_id, combo_id, template_id, template_name, window_name, benchmark_name, "
                "initial_capital_wan, used_range_start, used_range_end, summary_json, detail_json, "
                "updated_at "
                "FROM cb_optimize_task_analysis_snapshot "
                "WHERE task_id = ? LIMIT 1",
                (task_id,),
            ).fetchone()
        if not row:
            return None
        try:
            summary = json.loads(str(row[9]))
        except Exception:
            summary = {}
        try:
            detail = json.loads(str(row[10]))
        except Exception:
            detail = {}
        return {
            "task_id": str(row[0] or ""),
            "combo_id": str(row[1] or ""),
            "template_id": str(row[2] or ""),
            "template_name": str(row[3] or ""),
            "window_name": str(row[4] or "full"),
            "benchmark_name": str(row[5] or ""),
            "initial_capital_wan": float(row[6] or 0.0),
            "used_range_start": str(row[7]) if row[7] else None,
            "used_range_end": str(row[8]) if row[8] else None,
            "summary": summary if isinstance(summary, dict) else {},
            "detail": detail if isinstance(detail, dict) else {},
            "updated_at": str(row[11] or ""),
        }

    def save_optimize_task_analysis_snapshot(
        self,
        *,
        task_id: str,
        combo_id: str,
        template_id: str,
        template_name: str,
        window_name: str,
        benchmark_name: str,
        initial_capital_wan: float,
        used_range_start: str | None,
        used_range_end: str | None,
        summary: dict[str, Any],
        detail: dict[str, Any],
    ) -> None:
        """保存某个优化任务最佳策略的分析快照。"""
        if not task_id or not combo_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO cb_optimize_task_analysis_snapshot ("
                "task_id, combo_id, template_id, template_name, window_name, benchmark_name, "
                "initial_capital_wan, used_range_start, used_range_end, summary_json, detail_json, updated_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(task_id) DO UPDATE SET "
                "combo_id=excluded.combo_id, template_id=excluded.template_id, "
                "template_name=excluded.template_name, window_name=excluded.window_name, "
                "benchmark_name=excluded.benchmark_name, initial_capital_wan=excluded.initial_capital_wan, "
                "used_range_start=excluded.used_range_start, used_range_end=excluded.used_range_end, "
                "summary_json=excluded.summary_json, detail_json=excluded.detail_json, "
                "updated_at=excluded.updated_at",
                (
                    task_id,
                    combo_id,
                    template_id,
                    template_name,
                    window_name,
                    benchmark_name,
                    float(initial_capital_wan),
                    used_range_start,
                    used_range_end,
                    json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
                    json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
                    now,
                ),
            )
            conn.commit()

    def delete_optimize_task_analysis_snapshot(self, task_id: str) -> None:
        """删除某个优化任务的分析快照。"""
        if not task_id:
            return
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM cb_optimize_task_analysis_snapshot WHERE task_id = ?", (task_id,))
            conn.commit()

    def delete_optimize_task_bundle(self, task_id: str) -> None:
        """删除优化任务及其全部派生结果。"""
        if not task_id:
            return
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM cb_optimize_task WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM cb_optimize_shard WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM cb_optimize_shard_result WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM cb_optimize_result WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM cb_optimize_top_bond WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM cb_optimize_task_analysis_snapshot WHERE task_id = ?", (task_id,))
            conn.commit()

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

            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_optimize_batch ("
                "batch_id TEXT PRIMARY KEY, "
                "status TEXT NOT NULL, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "row_json TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_optimize_batch_status "
                "ON cb_optimize_batch (status, created_at DESC)"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_optimize_task ("
                "task_id TEXT PRIMARY KEY, "
                "template_id TEXT NOT NULL, "
                "status TEXT NOT NULL, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "row_json TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_optimize_task_status "
                "ON cb_optimize_task (status, created_at DESC)"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_optimize_shard ("
                "shard_id TEXT PRIMARY KEY, "
                "task_id TEXT NOT NULL, "
                "stage TEXT NOT NULL, "
                "sequence INTEGER NOT NULL DEFAULT 1, "
                "status TEXT NOT NULL, "
                "created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, "
                "row_json TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_optimize_shard_task_stage "
                "ON cb_optimize_shard (task_id, stage, sequence ASC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_optimize_shard_status "
                "ON cb_optimize_shard (status, created_at DESC)"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_optimize_result ("
                "task_id TEXT NOT NULL, "
                "combo_id TEXT NOT NULL, "
                "rank INTEGER NOT NULL DEFAULT 0, "
                "updated_at TEXT NOT NULL, "
                "row_json TEXT NOT NULL, "
                "PRIMARY KEY (task_id, combo_id)"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_optimize_result_task_rank "
                "ON cb_optimize_result (task_id, rank ASC)"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_optimize_shard_result ("
                "task_id TEXT NOT NULL, "
                "shard_id TEXT NOT NULL, "
                "combo_id TEXT NOT NULL, "
                "rank INTEGER NOT NULL DEFAULT 0, "
                "updated_at TEXT NOT NULL, "
                "row_json TEXT NOT NULL, "
                "PRIMARY KEY (task_id, shard_id, combo_id)"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_optimize_shard_result_task_shard_rank "
                "ON cb_optimize_shard_result (task_id, shard_id, rank ASC)"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_optimize_top_bond ("
                "task_id TEXT NOT NULL, "
                "bond_id TEXT NOT NULL, "
                "rank INTEGER NOT NULL DEFAULT 0, "
                "updated_at TEXT NOT NULL, "
                "row_json TEXT NOT NULL, "
                "PRIMARY KEY (task_id, bond_id)"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cb_optimize_top_bond_task_rank "
                "ON cb_optimize_top_bond (task_id, rank ASC)"
            )

            conn.execute(
                "CREATE TABLE IF NOT EXISTS cb_optimize_task_analysis_snapshot ("
                "task_id TEXT PRIMARY KEY, "
                "combo_id TEXT NOT NULL, "
                "template_id TEXT NOT NULL, "
                "template_name TEXT NOT NULL, "
                "window_name TEXT NOT NULL, "
                "benchmark_name TEXT NOT NULL, "
                "initial_capital_wan REAL NOT NULL, "
                "used_range_start TEXT, "
                "used_range_end TEXT, "
                "summary_json TEXT NOT NULL, "
                "detail_json TEXT NOT NULL, "
                "updated_at TEXT NOT NULL"
                ")"
            )
            conn.commit()
