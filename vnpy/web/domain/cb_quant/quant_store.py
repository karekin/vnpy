from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from vnpy.web.base_store import PgStore, _jsonb
from vnpy.web.db import DbSettings


class CbQuantStore(PgStore):
    """PostgreSQL-backed store for cb quant templates and backtest tasks."""

    def __init__(self, settings: DbSettings) -> None:
        super().__init__(settings)

    def load_templates_and_configs(self) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        templates: list[dict[str, Any]] = []
        configs: dict[str, dict[str, Any]] = {}
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT payload FROM oltp.cb_strategy_template ORDER BY updated_at DESC, id DESC"
            ).fetchall():
                try:
                    templates.append(dict(row["payload"]))
                except Exception:
                    continue

            for row in conn.execute(
                "SELECT template_id, config_json FROM oltp.cb_strategy_template_config"
            ).fetchall():
                template_id = str(row["template_id"])
                try:
                    configs[template_id] = dict(row["config_json"])
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
        with self._connect() as conn:
            conn.execute("DELETE FROM oltp.cb_strategy_template")
            conn.execute("DELETE FROM oltp.cb_strategy_template_config")
            for row in templates:
                template_id = str(row.get("id", "")).strip()
                if not template_id:
                    continue
                conn.execute(
                    "INSERT INTO oltp.cb_strategy_template "
                    "(id, name, status, owner, updated_at, payload) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        template_id,
                        str(row.get("name", "")),
                        str(row.get("status", "")),
                        str(row.get("owner", "")),
                        str(row.get("updated_at", now)),
                        _jsonb(row),
                    ),
                )

            for template_id, config in configs.items():
                if not template_id:
                    continue
                conn.execute(
                    "INSERT INTO oltp.cb_strategy_template_config "
                    "(template_id, updated_at, config_json) "
                    "VALUES (%s, %s, %s)",
                    (
                        template_id,
                        str(config.get("updated_at", now)),
                        _jsonb(config),
                    ),
                )

    def load_jobs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT payload, window_name, start_date, end_date, setting_json, cancel_requested, "
                "business_date, created_at "
                "FROM oltp.cb_backtest_job "
                "ORDER BY created_at DESC, job_id DESC"
            ).fetchall():
                try:
                    payload = dict(row["payload"])
                except Exception:
                    continue

                setting: dict[str, Any]
                try:
                    setting = dict(row["setting_json"]) if row["setting_json"] else {}
                except Exception:
                    setting = {}

                rows.append(
                    {
                        "row": payload,
                        "window_name": str(row["window_name"] or "full"),
                        "start_date": str(row["start_date"]) if row["start_date"] else None,
                        "end_date": str(row["end_date"]) if row["end_date"] else None,
                        "setting": setting,
                        "cancel_requested": bool(row["cancel_requested"] or False),
                        "business_date": str(row["business_date"] or ""),
                        "created_at": str(row["created_at"] or ""),
                    }
                )
        return rows

    def get_job_context(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT window_name, start_date, end_date, setting_json, cancel_requested, "
                "business_date, created_at "
                "FROM oltp.cb_backtest_job WHERE job_id = %s LIMIT 1",
                (job_id,),
            ).fetchone()
        if not row:
            return None
        try:
            setting = dict(row["setting_json"]) if row["setting_json"] else {}
        except Exception:
            setting = {}
        return {
            "window_name": str(row["window_name"] or "full"),
            "start_date": str(row["start_date"]) if row["start_date"] else None,
            "end_date": str(row["end_date"]) if row["end_date"] else None,
            "setting": setting,
            "cancel_requested": bool(row["cancel_requested"] or False),
            "business_date": str(row["business_date"] or ""),
            "created_at": str(row["created_at"] or ""),
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
        cancel_requested = bool(context.get("cancel_requested"))
        business_date = str(row.get("business_date") or context.get("business_date") or now[:10])
        created_at = str(row.get("created_at") or context.get("created_at") or now)

        if hasattr(start_date, "isoformat"):
            start_date = start_date.isoformat()
        if hasattr(end_date, "isoformat"):
            end_date = end_date.isoformat()

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO oltp.cb_backtest_job ("
                "job_id, strategy_id, combo_id, rule_pack_id, template, \"window\", status, progress, "
                "business_date, created_at, started_at, eta, worker, updated_at, "
                "window_name, start_date, end_date, setting_json, cancel_requested, payload"
                ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT(job_id) DO UPDATE SET "
                "strategy_id=excluded.strategy_id, combo_id=excluded.combo_id, "
                "rule_pack_id=excluded.rule_pack_id, template=excluded.template, \"window\"=excluded.\"window\", "
                "status=excluded.status, progress=excluded.progress, business_date=excluded.business_date, "
                "created_at=excluded.created_at, started_at=excluded.started_at, eta=excluded.eta, "
                "worker=excluded.worker, updated_at=excluded.updated_at, window_name=excluded.window_name, "
                "start_date=excluded.start_date, end_date=excluded.end_date, "
                "setting_json=excluded.setting_json, cancel_requested=excluded.cancel_requested, "
                "payload=excluded.payload",
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
                    _jsonb(setting),
                    cancel_requested,
                    _jsonb(row),
                ),
            )

    def delete_jobs(self, job_ids: list[str]) -> None:
        normalized = [str(job_id).strip() for job_id in job_ids if str(job_id).strip()]
        if not normalized:
            return
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM oltp.cb_backtest_job WHERE job_id = ANY(%s)",
                (normalized,),
            )

    def replace_leaderboard(self, rows: list[dict[str, Any]]) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("DELETE FROM olap.cb_backtest_leaderboard")
            for item in rows:
                row = item.get("row") or {}
                business_date = str(item.get("business_date") or now[:10])
                combo_id = str(row.get("combo_id", "")).strip()
                rule_pack_id = str(row.get("rule_pack_id", "")).strip()
                window = str(row.get("window", "")).strip()
                if not combo_id or not rule_pack_id or not window:
                    continue
                conn.execute(
                    "INSERT INTO olap.cb_backtest_leaderboard "
                    "(combo_id, rule_pack_id, \"window\", business_date, updated_at, payload) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        combo_id,
                        rule_pack_id,
                        window,
                        business_date,
                        now,
                        _jsonb(row),
                    ),
                )

    def load_leaderboard(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT business_date, payload FROM olap.cb_backtest_leaderboard ORDER BY updated_at DESC"
            ).fetchall():
                try:
                    payload = dict(row["payload"])
                except Exception:
                    continue
                rows.append(
                    {
                        "business_date": str(row["business_date"] or ""),
                        "row": payload,
                    }
                )
        return rows

    def load_optimize_tasks(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT payload FROM oltp.cb_optimize_task ORDER BY created_at DESC, task_id DESC"
            ).fetchall():
                try:
                    rows.append(dict(row["payload"]))
                except Exception:
                    continue
        return rows

    def load_optimize_batches(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT payload FROM oltp.cb_optimize_batch ORDER BY created_at DESC, batch_id DESC"
            ).fetchall():
                try:
                    rows.append(dict(row["payload"]))
                except Exception:
                    continue
        return rows

    def load_optimize_shards(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT payload FROM oltp.cb_optimize_shard ORDER BY task_id, sequence ASC, shard_id ASC"
            ).fetchall():
                try:
                    rows.append(dict(row["payload"]))
                except Exception:
                    continue
        return rows

    def load_optimize_shard_result_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT task_id, shard_id, payload FROM olap.cb_optimize_shard_result "
                "ORDER BY task_id, shard_id, rank ASC"
            ).fetchall():
                try:
                    payload = dict(row["payload"])
                except Exception:
                    continue
                rows.append(
                    {
                        "task_id": str(row["task_id"] or ""),
                        "shard_id": str(row["shard_id"] or ""),
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
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO oltp.cb_optimize_task ("
                "task_id, template_id, status, created_at, updated_at, payload"
                ") VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT(task_id) DO UPDATE SET "
                "template_id=excluded.template_id, status=excluded.status, "
                "created_at=excluded.created_at, updated_at=excluded.updated_at, "
                "payload=excluded.payload",
                (
                    task_id,
                    template_id,
                    status,
                    created_at,
                    now,
                    _jsonb(row),
                ),
            )

    def upsert_optimize_batch(self, *, row: dict[str, Any]) -> None:
        batch_id = str(row.get("batch_id") or "").strip()
        if not batch_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        created_at = str(row.get("created_at") or now)
        status = str(row.get("status") or "queued")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO oltp.cb_optimize_batch ("
                "batch_id, status, created_at, updated_at, payload"
                ") VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT(batch_id) DO UPDATE SET "
                "status=excluded.status, created_at=excluded.created_at, updated_at=excluded.updated_at, "
                "payload=excluded.payload",
                (
                    batch_id,
                    status,
                    created_at,
                    now,
                    _jsonb(row),
                ),
            )

    def delete_optimize_batch(self, batch_id: str) -> None:
        if not batch_id:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM oltp.cb_optimize_batch WHERE batch_id = %s", (batch_id,))

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
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO oltp.cb_optimize_shard ("
                "shard_id, task_id, stage, sequence, status, created_at, updated_at, payload"
                ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT(shard_id) DO UPDATE SET "
                "task_id=excluded.task_id, stage=excluded.stage, sequence=excluded.sequence, "
                "status=excluded.status, created_at=excluded.created_at, updated_at=excluded.updated_at, "
                "payload=excluded.payload",
                (
                    shard_id,
                    task_id,
                    stage,
                    sequence,
                    status,
                    created_at,
                    now,
                    _jsonb(row),
                ),
            )

    def replace_optimize_shards(self, *, task_id: str, rows: list[dict[str, Any]]) -> None:
        if not task_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("DELETE FROM oltp.cb_optimize_shard WHERE task_id = %s", (task_id,))
            for row in rows:
                shard_id = str(row.get("shard_id") or "").strip()
                if not shard_id:
                    continue
                stage = str(row.get("stage") or "full")
                sequence = int(row.get("sequence") or 1)
                status = str(row.get("status") or "queued")
                created_at = str(row.get("created_at") or now)
                conn.execute(
                    "INSERT INTO oltp.cb_optimize_shard ("
                    "shard_id, task_id, stage, sequence, status, created_at, updated_at, payload"
                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        shard_id,
                        task_id,
                        stage,
                        sequence,
                        status,
                        created_at,
                        now,
                        _jsonb(row),
                    ),
                )

    def replace_optimize_shard_result_rows(self, *, task_id: str, shard_id: str, rows: list[dict[str, Any]]) -> None:
        if not task_id or not shard_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM olap.cb_optimize_shard_result WHERE task_id = %s AND shard_id = %s",
                (task_id, shard_id),
            )
            for row in rows:
                combo_id = str(row.get("combo_id") or "").strip()
                if not combo_id:
                    continue
                rank = int(row.get("rank") or 0)
                conn.execute(
                    "INSERT INTO olap.cb_optimize_shard_result ("
                    "task_id, shard_id, combo_id, rank, updated_at, payload"
                    ") VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        task_id,
                        shard_id,
                        combo_id,
                        rank,
                        now,
                        _jsonb(row),
                    ),
                )

    def delete_optimize_shard_result_rows(self, *, task_id: str, shard_id: str | None = None) -> None:
        if not task_id:
            return
        with self._connect() as conn:
            if shard_id:
                conn.execute(
                    "DELETE FROM olap.cb_optimize_shard_result WHERE task_id = %s AND shard_id = %s",
                    (task_id, shard_id),
                )
            else:
                conn.execute(
                    "DELETE FROM olap.cb_optimize_shard_result WHERE task_id = %s",
                    (task_id,),
                )

    def load_optimize_result_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT task_id, payload FROM olap.cb_optimize_result ORDER BY task_id, rank ASC"
            ).fetchall():
                try:
                    payload = dict(row["payload"])
                except Exception:
                    continue
                rows.append(
                    {
                        "task_id": str(row["task_id"]),
                        "row": payload,
                    }
                )
        return rows

    def replace_optimize_result_rows(self, *, task_id: str, rows: list[dict[str, Any]]) -> None:
        if not task_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("DELETE FROM olap.cb_optimize_result WHERE task_id = %s", (task_id,))
            for row in rows:
                combo_id = str(row.get("combo_id") or "").strip()
                if not combo_id:
                    continue
                rank = int(row.get("rank") or 0)
                conn.execute(
                    "INSERT INTO olap.cb_optimize_result ("
                    "task_id, combo_id, rank, updated_at, payload"
                    ") VALUES (%s, %s, %s, %s, %s)",
                    (
                        task_id,
                        combo_id,
                        rank,
                        now,
                        _jsonb(row),
                    ),
                )

    def load_optimize_top_bond_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self._connect() as conn:
            for row in conn.execute(
                "SELECT task_id, payload FROM olap.cb_optimize_top_bond ORDER BY task_id, rank ASC"
            ).fetchall():
                try:
                    payload = dict(row["payload"])
                except Exception:
                    continue
                rows.append(
                    {
                        "task_id": str(row["task_id"]),
                        "row": payload,
                    }
                )
        return rows

    def replace_optimize_top_bond_rows(self, *, task_id: str, rows: list[dict[str, Any]]) -> None:
        if not task_id:
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute("DELETE FROM olap.cb_optimize_top_bond WHERE task_id = %s", (task_id,))
            for row in rows:
                bond_id = str(row.get("bond_id") or "").strip()
                if not bond_id:
                    continue
                rank = int(row.get("rank") or 0)
                conn.execute(
                    "INSERT INTO olap.cb_optimize_top_bond ("
                    "task_id, bond_id, rank, updated_at, payload"
                    ") VALUES (%s, %s, %s, %s, %s)",
                    (
                        task_id,
                        bond_id,
                        rank,
                        now,
                        _jsonb(row),
                    ),
                )

    def load_optimize_task_analysis_snapshot(self, task_id: str) -> dict[str, Any] | None:
        """读取某个优化任务最佳策略的分析快照。"""
        if not task_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT task_id, combo_id, template_id, template_name, window_name, benchmark_name, "
                "initial_capital_wan, used_range_start, used_range_end, summary_json, detail_json, "
                "updated_at "
                "FROM olap.cb_optimize_task_analysis_snapshot "
                "WHERE task_id = %s LIMIT 1",
                (task_id,),
            ).fetchone()
        if not row:
            return None
        try:
            summary = dict(row["summary_json"]) if row["summary_json"] else {}
        except Exception:
            summary = {}
        try:
            detail = dict(row["detail_json"]) if row["detail_json"] else {}
        except Exception:
            detail = {}
        return {
            "task_id": str(row["task_id"] or ""),
            "combo_id": str(row["combo_id"] or ""),
            "template_id": str(row["template_id"] or ""),
            "template_name": str(row["template_name"] or ""),
            "window_name": str(row["window_name"] or "full"),
            "benchmark_name": str(row["benchmark_name"] or ""),
            "initial_capital_wan": float(row["initial_capital_wan"] or 0.0),
            "used_range_start": str(row["used_range_start"]) if row["used_range_start"] else None,
            "used_range_end": str(row["used_range_end"]) if row["used_range_end"] else None,
            "summary": summary if isinstance(summary, dict) else {},
            "detail": detail if isinstance(detail, dict) else {},
            "updated_at": str(row["updated_at"] or ""),
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
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO olap.cb_optimize_task_analysis_snapshot ("
                "task_id, combo_id, template_id, template_name, window_name, benchmark_name, "
                "initial_capital_wan, used_range_start, used_range_end, summary_json, detail_json, updated_at"
                ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
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
                    _jsonb(summary),
                    _jsonb(detail),
                    now,
                ),
            )

    def delete_optimize_task_analysis_snapshot(self, task_id: str) -> None:
        """删除某个优化任务的分析快照。"""
        if not task_id:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM olap.cb_optimize_task_analysis_snapshot WHERE task_id = %s", (task_id,))

    def delete_optimize_task_bundle(self, task_id: str) -> None:
        """删除优化任务及其全部派生结果。"""
        if not task_id:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM oltp.cb_optimize_task WHERE task_id = %s", (task_id,))
            conn.execute("DELETE FROM oltp.cb_optimize_shard WHERE task_id = %s", (task_id,))
            conn.execute("DELETE FROM olap.cb_optimize_shard_result WHERE task_id = %s", (task_id,))
            conn.execute("DELETE FROM olap.cb_optimize_result WHERE task_id = %s", (task_id,))
            conn.execute("DELETE FROM olap.cb_optimize_top_bond WHERE task_id = %s", (task_id,))
            conn.execute("DELETE FROM olap.cb_optimize_task_analysis_snapshot WHERE task_id = %s", (task_id,))
