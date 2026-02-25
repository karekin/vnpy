from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from itertools import combinations, islice, product
import json
from math import ceil, comb, sqrt
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Iterable, TypeVar

from vnpy.web.adapters import CrawlerPhaseABacktestAdapter
from vnpy.web.services.cb_market_service import CbMarketService
from vnpy.web.schemas import (
    BacktestCompareResponse,
    BacktestCompareRow,
    BacktestCreateJobsRequest,
    BacktestCreateJobsResponse,
    BacktestJobListResponse,
    BacktestJobRow,
    BacktestLeaderboardResponse,
    BacktestLeaderboardRow,
    BacktestStatsResponse,
    CandidateGenerateRequest,
    CandidateGenerateResponse,
    CandidateListResponse,
    CandidateRow,
    HistoryDataSummaryResponse,
    StrategyBacktestCurvePoint,
    StrategyBacktestDistributionRow,
    StrategyBacktestMetricRow,
    StrategyBacktestRotationRow,
    StrategyOptimizeResultRow,
    StrategyOptimizeTaskAnalysisResponse,
    StrategyOptimizeTaskCreateRequest,
    StrategyOptimizeTaskCreateResponse,
    StrategyOptimizeTaskDetailResponse,
    StrategyOptimizeTaskListResponse,
    StrategyOptimizeTaskRow,
    StrategyOptimizeSummaryResponse,
    StrategyTopBondRow,
    StrategyTemplateConfigRequest,
    StrategyTemplateConfigResponse,
    StrategyTemplateCreateRequest,
    StrategyTemplateDetailResponse,
    StrategyExpandFactorCombosRequest,
    StrategyExpandFactorCombosResponse,
    StrategyTemplateListResponse,
    StrategyParamSpaceRow,
    StrategyTemplateRow,
    StrategyTemplateUpdateRequest,
    WindowName,
)


T = TypeVar("T")


def _paginate(items: list[T], page: int, page_size: int) -> list[T]:
    safe_page = max(1, page)
    safe_size = max(1, page_size)
    start = (safe_page - 1) * safe_size
    return items[start : start + safe_size]


def _now_hms() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _now_yyyymmdd() -> str:
    return datetime.now().strftime("%Y%m%d")


def _now_readable() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _now_compact() -> str:
    return datetime.now().strftime("%Y%m%d%H%M")


class CbQuantService:
    """In-memory CB Quant service for frontend-backend integration."""

    def __init__(self) -> None:
        self._lock: Lock = Lock()
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cbq-bt")
        self._adapter: CrawlerPhaseABacktestAdapter = CrawlerPhaseABacktestAdapter()
        self._market_service: CbMarketService = CbMarketService()
        self._seq: int = 0
        self._template_seq: int = 0
        self._opt_task_seq: int = 0
        self._candidate_settings: dict[str, dict[str, Any]] = {}
        self._job_context: dict[str, dict[str, Any]] = {}
        self._storage_dir: Path = self._adapter.data_dir / "_cb_quant"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._templates_file: Path = self._storage_dir / "templates.json"

        self._templates, self._template_configs = self._load_templates_and_configs()
        self._templates = self._sync_template_metrics(self._templates, self._template_configs)
        self._template_seq = self._derive_template_seq(self._templates)

        self._candidates: list[CandidateRow] = []
        self._rebuild_candidate_settings()

        self._jobs: list[BacktestJobRow] = []
        self._leaderboard: list[BacktestLeaderboardRow] = []
        self._compare: list[BacktestCompareRow] = []
        self._refresh_compare_rows()

        self._optimize_tasks: list[StrategyOptimizeTaskRow] = []
        self._optimize_results: dict[str, list[StrategyOptimizeResultRow]] = {}
        self._optimize_top_bonds: dict[str, list[StrategyTopBondRow]] = {}
        self._optimize_analysis_cache: dict[tuple[str, str, float, str], StrategyOptimizeTaskAnalysisResponse] = {}

    # ---------- strategy templates ----------
    def list_templates(
        self,
        *,
        keyword: str = "",
        status: str = "all",
        page: int = 1,
        page_size: int = 50,
    ) -> StrategyTemplateListResponse:
        needle = keyword.strip().lower()
        rows: list[StrategyTemplateRow] = []

        for row in self._templates:
            if status != "all" and row.status != status:
                continue
            if needle:
                raw = f"{row.id}|{row.name}|{row.owner}|{row.version}".lower()
                if needle not in raw:
                    continue
            rows.append(row)

        rows.sort(key=lambda item: item.updated_at, reverse=True)
        total = len(rows)
        paged = _paginate(rows, page, page_size)
        return StrategyTemplateListResponse(items=paged, total=total, page=page, page_size=page_size)

    def get_template_detail(self, template_id: str) -> StrategyTemplateDetailResponse | None:
        template = self._find_template(template_id)
        if not template:
            return None

        config = self._template_configs.get(template_id)
        if not config:
            config = self._default_config(template_id=template_id, updated_at=template.updated_at)
            self._template_configs[template_id] = config

        return StrategyTemplateDetailResponse(template=template, config=config)

    def create_template(self, request: StrategyTemplateCreateRequest) -> StrategyTemplateRow:
        with self._lock:
            self._template_seq += 1
            template_id = f"TPL-{self._template_seq:03d}"
            now = _now_readable()
            default_config = self._default_config(template_id=template_id, updated_at=now)
            template = StrategyTemplateRow(
                id=template_id,
                name=request.name,
                version="v0.1.0",
                status="draft",
                factor_count=len(default_config.factor_keys),
                rebalance="weekly",
                risk_preset="balanced",
                combo_size=default_config.combo_size,
                owner=request.owner,
                updated_at=now,
            )
            self._templates.insert(0, template)
            self._template_configs[template_id] = default_config
            self._save_templates_and_configs()
            return template

    def update_template(self, template_id: str, request: StrategyTemplateUpdateRequest) -> StrategyTemplateRow | None:
        with self._lock:
            for idx, row in enumerate(self._templates):
                if row.id != template_id:
                    continue

                updated = StrategyTemplateRow(
                    id=row.id,
                    name=request.name if request.name is not None else row.name,
                    version=row.version,
                    status=request.status if request.status is not None else row.status,
                    factor_count=row.factor_count,
                    rebalance=request.rebalance if request.rebalance is not None else row.rebalance,
                    risk_preset=request.risk_preset if request.risk_preset is not None else row.risk_preset,
                    combo_size=row.combo_size,
                    owner=request.owner if request.owner is not None else row.owner,
                    updated_at=_now_readable(),
                )
                self._templates[idx] = updated
                self._save_templates_and_configs()
                return updated
        return None

    def delete_template(self, template_id: str) -> bool:
        with self._lock:
            before = len(self._templates)
            self._templates = [row for row in self._templates if row.id != template_id]
            deleted = len(self._templates) != before
            if deleted:
                self._template_configs.pop(template_id, None)
                self._candidates = [row for row in self._candidates if row.template_id != template_id]
                self._candidate_settings = {
                    combo_id: setting
                    for combo_id, setting in self._candidate_settings.items()
                    if any(row.combo_id == combo_id for row in self._candidates)
                }
                self._save_templates_and_configs()
            return deleted

    def batch_enable_templates(self, template_ids: list[str], *, status: str = "active") -> tuple[int, list[str]]:
        targets = {item for item in template_ids if item}
        if not targets:
            return 0, []

        with self._lock:
            status_value = status if status in {"active", "draft", "archived"} else "active"
            now = _now_readable()
            found: set[str] = set()
            updated_rows: list[StrategyTemplateRow] = []
            for row in self._templates:
                if row.id not in targets:
                    updated_rows.append(row)
                    continue
                found.add(row.id)
                updated_rows.append(
                    StrategyTemplateRow(
                        id=row.id,
                        name=row.name,
                        version=row.version,
                        status=status_value,
                        factor_count=row.factor_count,
                        rebalance=row.rebalance,
                        risk_preset=row.risk_preset,
                        combo_size=row.combo_size,
                        owner=row.owner,
                        updated_at=now,
                    )
                )

            missing = sorted(targets - found)
            if found:
                self._templates = updated_rows
                self._save_templates_and_configs()
            return len(found), missing

    def batch_delete_templates(self, template_ids: list[str]) -> tuple[int, list[str]]:
        targets = {item for item in template_ids if item}
        if not targets:
            return 0, []

        with self._lock:
            existing = {row.id for row in self._templates}
            found = targets & existing
            missing = sorted(targets - found)
            if not found:
                return 0, missing

            self._templates = [row for row in self._templates if row.id not in found]
            for template_id in found:
                self._template_configs.pop(template_id, None)

            self._candidates = [row for row in self._candidates if row.template_id not in found]
            valid_combo_ids = {row.combo_id for row in self._candidates}
            self._candidate_settings = {
                combo_id: setting
                for combo_id, setting in self._candidate_settings.items()
                if combo_id in valid_combo_ids
            }

            self._save_templates_and_configs()
            return len(found), missing

    def expand_template_factor_combos(
        self,
        template_id: str,
        request: StrategyExpandFactorCombosRequest,
    ) -> StrategyExpandFactorCombosResponse | None:
        template = self._find_template(template_id)
        if not template:
            return None

        config = self._template_configs.get(template_id) or self._default_config(
            template_id=template_id,
            updated_at=template.updated_at,
        )
        factor_keys = list(dict.fromkeys(config.factor_keys))
        factor_count = len(factor_keys)
        if factor_count == 0:
            return StrategyExpandFactorCombosResponse(
                source_template_id=template.id,
                source_template_name=template.name,
                min_factor_count=0,
                max_factor_count=0,
                total_subsets=0,
                created_count=0,
                truncated=False,
                message="策略没有可展开的因子，请先配置参数空间。",
            )

        request_min = max(1, request.min_factor_count)
        request_max = factor_count if request.max_factor_count is None else max(1, request.max_factor_count)
        if request_min > request_max:
            request_min, request_max = request_max, request_min

        min_count = request_min
        max_count = min(factor_count, request_max)
        if min_count > max_count:
            return StrategyExpandFactorCombosResponse(
                source_template_id=template.id,
                source_template_name=template.name,
                min_factor_count=request_min,
                max_factor_count=request_max,
                total_subsets=0,
                created_count=0,
                truncated=False,
                message=f"策略因子数为 {factor_count}，无法生成 {request_min}~{request_max} 因子组合。",
            )

        total_subsets = sum(comb(factor_count, k) for k in range(min_count, max_count + 1))
        max_strategies = request.max_strategies or total_subsets
        created_rows: list[StrategyTemplateRow] = []
        created_configs: dict[str, StrategyTemplateConfigResponse] = {}
        created_count = 0
        truncated = False
        source_row_map: dict[str, StrategyParamSpaceRow] = {
            row.factor_key: row for row in config.parameter_space
        }

        with self._lock:
            for k in range(min_count, max_count + 1):
                for subset in combinations(factor_keys, k):
                    if created_count >= max_strategies:
                        truncated = True
                        break

                    self._template_seq += 1
                    new_id = f"TPL-{self._template_seq:03d}"
                    now = _now_readable()
                    subset_keys = list(subset)
                    subset_space = [
                        source_row_map[key] if key in source_row_map else self._default_param_space_row(key)
                        for key in subset_keys
                    ]
                    normalized_space = self._normalize_parameter_space(
                        factor_keys=subset_keys,
                        parameter_space=subset_space,
                    )
                    combo_size = self._calculate_combo_size(
                        factor_keys=subset_keys,
                        parameter_space=normalized_space,
                    )

                    created_count += 1
                    strategy_name = f"{template.name}-F{k}-{created_count:04d}"
                    row = StrategyTemplateRow(
                        id=new_id,
                        name=strategy_name,
                        version="v0.1.0",
                        status="draft",
                        factor_count=len(subset_keys),
                        rebalance=template.rebalance,
                        risk_preset=template.risk_preset,
                        combo_size=combo_size,
                        owner=template.owner,
                        updated_at=now,
                    )
                    cfg = StrategyTemplateConfigResponse(
                        template_id=new_id,
                        factor_keys=subset_keys,
                        expression_draft=config.expression_draft,
                        parameter_space=normalized_space,
                        combo_size=combo_size,
                        updated_at=now,
                    )
                    created_rows.append(row)
                    created_configs[new_id] = cfg

                if truncated:
                    break

            if created_rows:
                self._templates = [*created_rows, *self._templates]
                self._template_configs.update(created_configs)
                self._save_templates_and_configs()

        message = (
            f"已从策略 {template.name} 展开 {created_count} 个因子组合策略"
            f"（{min_count}~{max_count} 因子，理论共 {total_subsets} 个）。"
        )
        if truncated:
            message += " 已达到本次生成上限。"

        return StrategyExpandFactorCombosResponse(
            source_template_id=template.id,
            source_template_name=template.name,
            min_factor_count=min_count,
            max_factor_count=max_count,
            total_subsets=total_subsets,
            created_count=created_count,
            truncated=truncated,
            message=message,
        )

    def update_template_config(
        self,
        template_id: str,
        request: StrategyTemplateConfigRequest,
    ) -> StrategyTemplateConfigResponse | None:
        template = self._find_template(template_id)
        if not template:
            return None

        normalized_space = self._normalize_parameter_space(
            factor_keys=request.factor_keys,
            parameter_space=request.parameter_space,
        )
        combo_size = self._calculate_combo_size(
            factor_keys=request.factor_keys,
            parameter_space=normalized_space,
        )

        config = StrategyTemplateConfigResponse(
            template_id=template_id,
            factor_keys=request.factor_keys,
            expression_draft=request.expression_draft,
            parameter_space=normalized_space,
            combo_size=combo_size,
            updated_at=_now_readable(),
        )

        with self._lock:
            self._template_configs[template_id] = config
            self._templates = [
                StrategyTemplateRow(
                    id=row.id,
                    name=row.name,
                    version=row.version,
                    status=row.status,
                    factor_count=len(request.factor_keys) if row.id == template_id else row.factor_count,
                    rebalance=row.rebalance,
                    risk_preset=row.risk_preset,
                    combo_size=combo_size if row.id == template_id else row.combo_size,
                    owner=row.owner,
                    updated_at=config.updated_at if row.id == template_id else row.updated_at,
                )
                for row in self._templates
            ]
            template_combo_ids = {
                row.combo_id for row in self._candidates if row.template_id == template_id
            }
            for combo_id in template_combo_ids:
                self._candidate_settings[combo_id] = self._build_candidate_setting(
                    template_id=template_id,
                    combo_id=combo_id,
                )
            self._save_templates_and_configs()

        return config

    def generate_candidates(
        self,
        template_id: str,
        request: CandidateGenerateRequest,
    ) -> CandidateGenerateResponse | None:
        template = self._find_template(template_id)
        if not template:
            return None

        config = self._template_configs.get(template_id) or self._default_config(
            template_id=template_id,
            updated_at=template.updated_at,
        )
        combo_size = max(
            1,
            self._calculate_combo_size(
                factor_keys=config.factor_keys,
                parameter_space=config.parameter_space,
            ),
        )

        windows = self._normalize_windows(request.windows)
        if not windows:
            windows = ["full", "3y", "1y"]

        run_id = f"RUN-{template_id}-{_now_compact()}"
        combo_settings: dict[str, dict[str, Any]] = {}
        preview_settings = list(
            self._iter_template_settings(
                template_id=template_id,
                limit=max(1, request.rows_per_window),
            )
        )
        if not preview_settings:
            preview_settings = [(f"CMB-{100000 + idx}", self._adapter.default_setting()) for idx in range(request.rows_per_window)]

        rows: list[CandidateRow] = []
        for window_name in windows:
            for combo_id, setting in preview_settings:
                combo_settings[combo_id] = dict(setting)
                combo = CandidateRow(
                    rank=0,
                    template_id=template_id,
                    template=template.name,
                    combo_id=combo_id,
                    est_combos=combo_size,
                    status="pending_backtest",
                    pass_rate=None,
                    window=window_name,
                    source="generated",
                    run_id=run_id,
                    generated_at=_now_readable(),
                )
                rows.append(combo)

        rows.sort(key=lambda item: item.est_combos, reverse=True)
        ranked_rows = [
            CandidateRow(
                rank=idx + 1,
                template_id=item.template_id,
                template=item.template,
                combo_id=item.combo_id,
                est_combos=item.est_combos,
                status=item.status,
                pass_rate=item.pass_rate,
                window=item.window,
                source=item.source,
                run_id=item.run_id,
                generated_at=item.generated_at,
            )
            for idx, item in enumerate(rows)
        ]

        with self._lock:
            self._candidates = [
                *ranked_rows,
                *[row for row in self._candidates if row.template_id != template_id],
            ]
            self._candidate_settings.update(combo_settings)
            self._templates = [
                StrategyTemplateRow(
                    id=row.id,
                    name=row.name,
                    version=row.version,
                    status=row.status,
                    factor_count=row.factor_count,
                    rebalance=row.rebalance,
                    risk_preset=row.risk_preset,
                    combo_size=combo_size if row.id == template_id else row.combo_size,
                    owner=row.owner,
                    updated_at=_now_readable() if row.id == template_id else row.updated_at,
                )
                for row in self._templates
            ]

        return CandidateGenerateResponse(
            run_id=run_id,
            template_id=template_id,
            template_name=template.name,
            created_count=len(ranked_rows),
            est_combos=combo_size,
            windows=windows,
            items=ranked_rows,
            message=f"已生成候选集 {run_id}，共 {len(ranked_rows)} 条，参数空间组合数={combo_size}。",
        )

    # ---------- candidates ----------
    def list_candidates(
        self,
        keyword: str = "",
        window: str = "all",
        template_id: str | None = None,
    ) -> CandidateListResponse:
        rows: list[CandidateRow] = []
        needle = keyword.strip().lower()

        for row in self._candidates:
            if window != "all" and row.window != window:
                continue
            if template_id and template_id != "all" and row.template_id != template_id:
                continue
            if needle:
                raw = f"{row.template}|{row.combo_id}|{row.run_id or ''}".lower()
                if needle not in raw:
                    continue
            rows.append(row)

        rows.sort(key=lambda item: (item.generated_at or "", item.est_combos), reverse=True)
        ranked_rows = [
            CandidateRow(
                rank=idx + 1,
                template_id=item.template_id,
                template=item.template,
                combo_id=item.combo_id,
                est_combos=item.est_combos,
                status=item.status,
                pass_rate=item.pass_rate,
                window=item.window,
                source=item.source,
                run_id=item.run_id,
                generated_at=item.generated_at,
            )
            for idx, item in enumerate(rows)
        ]

        return CandidateListResponse(items=ranked_rows, total=len(ranked_rows))

    # ---------- optimize tasks ----------
    def get_history_data_summary(self) -> HistoryDataSummaryResponse:
        try:
            dataset = self._adapter.load_market_data()
        except Exception:
            dataset = []
        normalized = sorted(dataset, key=lambda item: item[0])
        if not normalized:
            return HistoryDataSummaryResponse(
                snapshot_count=0,
                latest_bond_count=0,
                data_dir=str(self._adapter.data_dir / "_cb_quant" / "cb_snapshots.db"),
            )

        latest_df = normalized[-1][1]
        return HistoryDataSummaryResponse(
            snapshot_count=len(normalized),
            date_start=normalized[0][0],
            date_end=normalized[-1][0],
            latest_trade_date=normalized[-1][0],
            latest_bond_count=int(len(latest_df)),
            data_dir=str(self._adapter.data_dir / "_cb_quant" / "cb_snapshots.db"),
        )

    def create_optimize_task(
        self,
        request: StrategyOptimizeTaskCreateRequest,
    ) -> StrategyOptimizeTaskCreateResponse | None:
        template = self._find_template(request.template_id)
        if not template:
            return None

        config = self._template_configs.get(template.id) or self._default_config(
            template_id=template.id,
            updated_at=template.updated_at,
        )
        windows = self._normalize_windows(request.windows)
        if not windows:
            windows = ["full", "3y", "1y"]

        combo_size = max(
            1,
            self._calculate_combo_size(
                factor_keys=config.factor_keys,
                parameter_space=config.parameter_space,
            ),
        )
        capped_total = combo_size if request.max_combinations is None else min(combo_size, request.max_combinations)

        with self._lock:
            self._opt_task_seq += 1
            task_id = f"OPT-{_now_yyyymmdd()}-{self._opt_task_seq:04d}"
            task = StrategyOptimizeTaskRow(
                task_id=task_id,
                template_id=template.id,
                template_name=template.name,
                status="queued",
                progress=0,
                total_combinations=capped_total,
                evaluated_combinations=0,
                windows=windows,
                start_date=request.start_date.isoformat() if request.start_date else None,
                end_date=request.end_date.isoformat() if request.end_date else None,
                eta="--",
                message="任务已入队",
                created_at=_now_readable(),
            )
            self._optimize_tasks = [task, *self._optimize_tasks]
            self._optimize_results[task_id] = []
            self._optimize_top_bonds[task_id] = []

        self._executor.submit(
            self._run_optimize_task,
            task_id,
            request.top_n,
            request.current_top_n,
            request.start_date,
            request.end_date,
        )
        return StrategyOptimizeTaskCreateResponse(
            task=task,
            message=f"已创建优化任务 {task_id}，待评估参数组合数={capped_total}",
        )

    def list_optimize_tasks(
        self,
        *,
        template_id: str = "all",
        status: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> StrategyOptimizeTaskListResponse:
        rows = []
        for row in self._optimize_tasks:
            if template_id != "all" and row.template_id != template_id:
                continue
            if status != "all" and row.status != status:
                continue
            rows.append(row)
        total = len(rows)
        paged = _paginate(rows, page, page_size)
        return StrategyOptimizeTaskListResponse(items=paged, total=total, page=page, page_size=page_size)

    def get_optimize_task_detail(self, task_id: str) -> StrategyOptimizeTaskDetailResponse | None:
        task = self._get_optimize_task(task_id)
        if not task:
            return None
        if task.status != "finished":
            return StrategyOptimizeTaskDetailResponse(
                task=task,
                top_strategies=[],
                top_bonds=[],
            )
        rows = [
            row
            for row in self._optimize_results.get(task_id, [])
            if not (abs(row.total_return_pct) < 1e-9 and row.turnover <= 1e-9)
        ]
        return StrategyOptimizeTaskDetailResponse(
            task=task,
            top_strategies=rows,
            top_bonds=self._optimize_top_bonds.get(task_id, []),
        )

    def get_optimize_task_analysis(
        self,
        *,
        task_id: str,
        combo_id: str | None = None,
        initial_capital_wan: float = 100.0,
    ) -> StrategyOptimizeTaskAnalysisResponse | None:
        task = self._get_optimize_task(task_id)
        if not task:
            return None

        # Keep analysis semantics strict: only finished task has official analysis output.
        if task.status != "finished":
            return StrategyOptimizeTaskAnalysisResponse(
                task_id=task.task_id,
                template_id=task.template_id,
                template_name=task.template_name,
                combo_id=combo_id or "--",
                benchmark_name="转债等权",
                window="full" if "full" in task.windows else (task.windows[0] if task.windows else "full"),
                metric_rows=[],
                curve=[],
                yearly_distribution=[],
                monthly_distribution=[],
                weekly_distribution=[],
                rotations=[],
                message=(
                    f"任务尚未完成（{task.evaluated_combinations}/{task.total_combinations}，状态 {task.status}），"
                    "请等待任务完成后再查看正式回测分析。"
                ),
            )

        ranked_rows = self._optimize_results.get(task_id, [])
        selected_row = None
        if combo_id:
            selected_row = next((row for row in ranked_rows if row.combo_id == combo_id), None)
        if selected_row is None and ranked_rows:
            selected_row = ranked_rows[0]

        selected_combo_id = combo_id or (selected_row.combo_id if selected_row else "CMB-000001")
        state_marker = f"{task.status}:{task.evaluated_combinations}/{task.total_combinations}"
        cache_key = (task_id, selected_combo_id, round(float(initial_capital_wan), 4), state_marker)
        cached = self._optimize_analysis_cache.get(cache_key)
        if cached:
            return cached

        if selected_row is not None:
            setting = dict(selected_row.params)
        else:
            setting = self._resolve_setting_for_combo(combo_id=selected_combo_id, template_name=task.template_name)

        window = "full" if "full" in task.windows else (task.windows[0] if task.windows else "full")
        start_date = self._parse_iso_date(task.start_date)
        end_date = self._parse_iso_date(task.end_date)

        dataset = self._adapter.load_market_data()
        sliced = self._adapter._slice_dataset(
            dataset=dataset,
            window_name=window,
            start_date=start_date,
            end_date=end_date,
        )
        message_parts: list[str] = []
        if not sliced and (start_date or end_date):
            sliced = self._adapter._slice_dataset(
                dataset=dataset,
                window_name=window,
                start_date=None,
                end_date=None,
            )
            if sliced:
                message_parts.append(
                    f"指定区间无可用快照，已回退到 {sliced[0][0]}~{sliced[-1][0]}。"
                )

        if not sliced:
            response = StrategyOptimizeTaskAnalysisResponse(
                task_id=task.task_id,
                template_id=task.template_id,
                template_name=task.template_name,
                combo_id=selected_combo_id,
                benchmark_name="转债等权",
                window=window,
                metric_rows=[],
                curve=[],
                yearly_distribution=[],
                monthly_distribution=[],
                weekly_distribution=[],
                rotations=[],
                message="没有可用历史快照，请先同步历史快照后重试。",
            )
            self._optimize_analysis_cache[cache_key] = response
            return response

        module = self._adapter._load_module()
        strategy = self._simulate_detailed_strategy(
            module=module,
            dataset=sliced,
            setting=setting,
            initial_capital_wan=initial_capital_wan,
        )
        benchmark = self._simulate_equal_weight_benchmark(
            dataset=sliced,
            initial_capital_wan=initial_capital_wan,
        )

        strategy_metrics = self._compute_backtest_metrics(
            daily_returns=strategy["daily_returns"],
            nav_series=strategy["nav_series"],
            initial_capital_wan=initial_capital_wan,
            turnover_pct=strategy["turnover_pct"],
            trade_pnls_pct=strategy["trade_pnls_pct"],
        )
        benchmark_metrics = self._compute_backtest_metrics(
            daily_returns=benchmark["daily_returns"],
            nav_series=benchmark["nav_series"],
            initial_capital_wan=initial_capital_wan,
            turnover_pct=[0.0 for _ in benchmark["daily_returns"]],
            trade_pnls_pct=[ret * 100.0 for ret in benchmark["daily_returns"][1:]],
        )
        metric_rows = self._build_metric_rows(
            strategy_metrics=strategy_metrics,
            benchmark_metrics=benchmark_metrics,
        )

        curve_rows: list[StrategyBacktestCurvePoint] = []
        for index, trade_date in enumerate(strategy["dates"]):
            strategy_cum = strategy["cum_return_pct"][index]
            benchmark_cum = benchmark["cum_return_pct"][index]
            drawdown = strategy["drawdown_pct"][index]
            avg_drawdown = strategy["avg_drawdown_pct"][index]
            curve_rows.append(
                StrategyBacktestCurvePoint(
                    date=trade_date,
                    strategy_cum_return_pct=round(strategy_cum, 4),
                    benchmark_cum_return_pct=round(benchmark_cum, 4),
                    relative_excess_pct=round(strategy_cum - benchmark_cum, 4),
                    absolute_excess_pct=round(strategy_cum, 4),
                    drawdown_pct=round(drawdown, 4),
                    avg_drawdown_pct=round(avg_drawdown, 4),
                )
            )

        yearly_distribution = self._build_distribution_rows(
            dates=strategy["dates"],
            strategy_daily_returns=strategy["daily_returns"],
            benchmark_daily_returns=benchmark["daily_returns"],
            period="yearly",
        )
        monthly_distribution = self._build_distribution_rows(
            dates=strategy["dates"],
            strategy_daily_returns=strategy["daily_returns"],
            benchmark_daily_returns=benchmark["daily_returns"],
            period="monthly",
        )
        weekly_distribution = self._build_distribution_rows(
            dates=strategy["dates"],
            strategy_daily_returns=strategy["daily_returns"],
            benchmark_daily_returns=benchmark["daily_returns"],
            period="weekly",
        )

        if not ranked_rows:
            message_parts.append("当前任务尚未生成榜单，分析结果基于当前参数直接重算。")
        if strategy["effective_trade_count"] <= 0:
            message_parts.append("未产生有效交易策略，请放宽阈值或调整参数范围。")

        response = StrategyOptimizeTaskAnalysisResponse(
            task_id=task.task_id,
            template_id=task.template_id,
            template_name=task.template_name,
            combo_id=selected_combo_id,
            benchmark_name="转债等权",
            window=window,
            metric_rows=metric_rows,
            curve=curve_rows,
            yearly_distribution=yearly_distribution,
            monthly_distribution=monthly_distribution,
            weekly_distribution=weekly_distribution,
            rotations=strategy["rotations"],
            message=" ".join(message_parts).strip(),
        )
        self._optimize_analysis_cache[cache_key] = response
        if len(self._optimize_analysis_cache) > 200:
            self._optimize_analysis_cache.clear()
        return response

    def get_optimize_summary(
        self,
        *,
        top_n: int = 20,
        current_top_n: int = 20,
    ) -> StrategyOptimizeSummaryResponse:
        safe_top_n = max(1, min(200, int(top_n)))
        safe_current_top_n = max(1, min(200, int(current_top_n)))

        finished_tasks = [row for row in self._optimize_tasks if row.status == "finished"]
        finished_task_ids = {row.task_id for row in finished_tasks}
        if not finished_task_ids:
            return StrategyOptimizeSummaryResponse(
                top_strategies=[],
                top_bonds=[],
                finished_task_count=0,
                total_result_count=0,
                message="暂无已完成任务，请先执行回测搜索。",
            )

        merged_rows: list[StrategyOptimizeResultRow] = []
        for task in finished_tasks:
            rows = self._optimize_results.get(task.task_id, [])
            if not rows:
                continue
            for row in rows:
                if abs(row.total_return_pct) < 1e-9 and row.turnover <= 1e-9:
                    continue
                merged_rows.append(
                    row.model_copy(
                        update={
                            "task_id": task.task_id,
                            "template_id": task.template_id,
                            "template_name": task.template_name,
                        }
                    )
                )

        if not merged_rows:
            return StrategyOptimizeSummaryResponse(
                top_strategies=[],
                top_bonds=[],
                finished_task_count=len(finished_task_ids),
                total_result_count=0,
                message="暂无可汇总的策略结果。",
            )

        merged_rows.sort(key=lambda item: (item.robust_score, item.cagr, -item.mdd), reverse=True)
        ranked_top = [
            row.model_copy(update={"rank": idx + 1})
            for idx, row in enumerate(merged_rows[:safe_top_n])
        ]

        top_bonds: list[StrategyTopBondRow] = []
        market_warning = ""
        best_params = ranked_top[0].params if ranked_top else {}
        if best_params:
            try:
                top_bonds, market_source = self._score_current_market(best_params, limit=safe_current_top_n)
                if not market_source.startswith("eastmoney."):
                    market_warning = f"；Top20基于 {market_source}（非实时）"
            except Exception as exc:
                market_warning = f"；实时Top20计算失败: {str(exc)[:80]}"

        return StrategyOptimizeSummaryResponse(
            top_strategies=ranked_top,
            top_bonds=top_bonds,
            finished_task_count=len(finished_task_ids),
            total_result_count=len(merged_rows),
            message=f"已汇总 {len(finished_task_ids)} 个完成任务，共 {len(merged_rows)} 条策略结果{market_warning}",
        )

    def _run_optimize_task(
        self,
        task_id: str,
        top_n: int,
        current_top_n: int,
        start_date: date | None,
        end_date: date | None,
    ) -> None:
        task = self._get_optimize_task(task_id)
        if not task:
            return
        template = self._find_template(task.template_id)
        if not template:
            self._update_optimize_task(task_id, status="failed", eta="--", message="template not found")
            return

        module = self._adapter._load_module()
        dataset = self._adapter.load_market_data()

        self._update_optimize_task(
            task_id,
            status="running",
            progress=1,
            started_at=_now_readable(),
            eta="loading",
            message="正在加载历史快照并初始化参数空间",
        )

        ranking_rows: list[StrategyOptimizeResultRow] = []
        total = max(1, task.total_combinations)
        evaluated = 0
        skipped_no_trade = 0
        start_at = datetime.now()

        try:
            for combo_id, setting in self._iter_template_settings(
                template_id=task.template_id,
                limit=task.total_combinations,
            ):
                evaluated += 1
                row = self._evaluate_combo(
                    module=module,
                    task_id=task_id,
                    template_id=task.template_id,
                    template_name=task.template_name,
                    dataset=dataset,
                    combo_id=combo_id,
                    windows=task.windows,
                    start_date=start_date,
                    end_date=end_date,
                    setting=setting,
                )
                if abs(row.total_return_pct) < 1e-9 and row.turnover <= 1e-9:
                    skipped_no_trade += 1
                    continue
                ranking_rows.append(row)
                ranking_rows.sort(
                    key=lambda item: (item.robust_score, item.cagr, -item.mdd),
                    reverse=True,
                )
                ranking_rows = ranking_rows[:top_n]

                if (
                    evaluated == 1
                    or evaluated == total
                    or evaluated % max(1, total // 100) == 0
                    or evaluated % 500 == 0
                ):
                    ranked_snapshot = [
                        item.model_copy(update={"rank": idx + 1})
                        for idx, item in enumerate(
                            sorted(
                                ranking_rows,
                                key=lambda item: (item.robust_score, item.cagr, -item.mdd),
                                reverse=True,
                            )
                        )
                    ]
                    self._optimize_results[task_id] = ranked_snapshot

                    elapsed_seconds = max(1.0, (datetime.now() - start_at).total_seconds())
                    remain = max(0, total - evaluated)
                    per_cost = elapsed_seconds / evaluated
                    eta_minutes = int((remain * per_cost) / 60)
                    self._update_optimize_task(
                        task_id,
                        evaluated_combinations=evaluated,
                        progress=max(1, min(99, ceil(evaluated / total * 100))),
                        eta=f"{eta_minutes}m" if remain else "done",
                        message=f"已评估 {evaluated}/{total}",
                    )

            ranked = [
                row.model_copy(update={"rank": idx + 1})
                for idx, row in enumerate(
                    sorted(ranking_rows, key=lambda item: (item.robust_score, item.cagr, -item.mdd), reverse=True)
                )
            ]
            if not ranked:
                self._optimize_results[task_id] = []
                self._optimize_top_bonds[task_id] = []
                self._update_optimize_task(
                    task_id,
                    status="finished",
                    progress=100,
                    evaluated_combinations=evaluated,
                    eta="done",
                    finished_at=_now_readable(),
                    message=f"优化完成，但未产生有效交易策略（无交易组合 {skipped_no_trade}/{evaluated}）。",
                )
                return
            best_setting = ranked[0].params if ranked else {}
            self._optimize_results[task_id] = ranked
            top_bonds: list[StrategyTopBondRow] = []
            market_warning = ""
            strategy_warning = ""
            if ranked and abs(ranked[0].total_return_pct) < 1e-9 and ranked[0].turnover <= 1e-9:
                strategy_warning = "；当前参数空间未产生有效交易，建议放宽筛选阈值或调整因子范围"
            if best_setting:
                try:
                    top_bonds, market_source = self._score_current_market(best_setting, limit=current_top_n)
                    if not market_source.startswith("eastmoney."):
                        market_warning = f"；Top20基于 {market_source}（非实时）"
                except Exception as exc:
                    market_warning = f"；实时Top20计算失败: {str(exc)[:80]}"
            self._optimize_top_bonds[task_id] = top_bonds
            self._update_optimize_task(
                task_id,
                status="finished",
                progress=100,
                evaluated_combinations=evaluated,
                eta="done",
                finished_at=_now_readable(),
                message=f"优化完成，最佳策略 {ranked[0].combo_id if ranked else '--'}{strategy_warning}{market_warning}",
            )
        except Exception as exc:
            self._update_optimize_task(
                task_id,
                status="failed",
                progress=max(1, min(99, ceil(evaluated / total * 100))) if evaluated > 0 else 0,
                evaluated_combinations=evaluated,
                eta="--",
                finished_at=_now_readable(),
                message=f"error: {str(exc)[:160]}",
            )

    # ---------- backtest ----------
    def list_jobs(
        self,
        keyword: str = "",
        status: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> BacktestJobListResponse:
        rows: list[BacktestJobRow] = []
        needle = keyword.strip().lower()

        for row in self._jobs:
            if status != "all" and row.status != status:
                continue
            if needle:
                raw = f"{row.job_id}|{row.strategy_id}|{row.combo_id}|{row.rule_pack_id}|{row.template}|{row.worker}".lower()
                if needle not in raw:
                    continue
            rows.append(row)

        total = len(rows)
        paged = _paginate(rows, page, page_size)
        return BacktestJobListResponse(items=paged, total=total, page=page, page_size=page_size)

    def list_leaderboard(
        self,
        keyword: str = "",
        window: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> BacktestLeaderboardResponse:
        rows: list[BacktestLeaderboardRow] = []
        needle = keyword.strip().lower()

        for row in self._leaderboard:
            if window != "all" and row.window != window:
                continue
            if needle:
                raw = f"{row.strategy_id}|{row.combo_id}|{row.rule_pack_id}|{row.template}".lower()
                if needle not in raw:
                    continue
            rows.append(row)

        total = len(rows)
        paged = _paginate(rows, page, page_size)
        return BacktestLeaderboardResponse(items=paged, total=total, page=page, page_size=page_size)

    def list_compare(self, keyword: str = "", category: str = "all") -> BacktestCompareResponse:
        rows: list[BacktestCompareRow] = []
        needle = keyword.strip().lower()

        for row in self._compare:
            if category != "all" and row.category != category:
                continue
            if needle and needle not in row.metric.lower():
                continue
            rows.append(row)

        return BacktestCompareResponse(items=rows, total=len(rows))

    def get_stats(self) -> BacktestStatsResponse:
        running = sum(1 for row in self._jobs if row.status == "running")
        queued = sum(1 for row in self._jobs if row.status == "queued")
        finished = sum(1 for row in self._jobs if row.status == "finished")
        failed = sum(1 for row in self._jobs if row.status == "failed")
        rule_pack_count = len({row.rule_pack_id for row in self._jobs})
        top_cagr = max((row.cagr for row in self._leaderboard), default=0.0)

        return BacktestStatsResponse(
            running_jobs=running,
            queued_jobs=queued,
            finished_jobs=finished,
            failed_jobs=failed,
            rule_pack_count=rule_pack_count,
            top_cagr=top_cagr,
        )

    def create_jobs(self, request: BacktestCreateJobsRequest) -> BacktestCreateJobsResponse:
        windows = self._normalize_windows(request.windows)
        if not windows:
            windows = ["full", "3y", "1y"]

        candidate = self._find_candidate(request.combo_id)
        template_name = request.template or (candidate.template if candidate else "未命名模板")
        rule_pack_id = request.rule_pack_id or self._build_rule_pack_id(request)

        with self._lock:
            created: list[BacktestJobRow] = []
            setting = self._resolve_setting_for_combo(
                combo_id=request.combo_id,
                template_name=template_name,
            )
            for window_name in windows:
                self._seq += 1
                seq = self._seq
                row = BacktestJobRow(
                    job_id=f"BT-{_now_yyyymmdd()}-{seq:03d}",
                    strategy_id=f"STR-{seq:03d}",
                    combo_id=request.combo_id,
                    rule_pack_id=rule_pack_id,
                    template=template_name,
                    window=self._window_label(window_name),
                    status="queued",
                    progress=0,
                    started_at=_now_hms(),
                    eta="--",
                    worker=f"wk-0{(seq % 5) + 1}",
                )
                created.append(row)
                self._job_context[row.job_id] = {
                    "window_name": window_name,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                    "setting": setting,
                }

            self._jobs = [*created, *self._jobs]

        for row in created:
            self._executor.submit(self._run_job, row.job_id)

        window_text = "、".join([self._window_label(name) for name in windows])
        message = f"已入队 {len(created)} 个窗口任务（{window_text}）：{request.combo_id} × {rule_pack_id}"

        return BacktestCreateJobsResponse(
            batch_id=f"BATCH-{_now_yyyymmdd()}-{self._seq:03d}",
            combo_id=request.combo_id,
            rule_pack_id=rule_pack_id,
            source_mode=request.source_mode,
            created_count=len(created),
            windows=windows,
            jobs=created,
            message=message,
        )

    def _run_job(self, job_id: str) -> None:
        context = self._job_context.get(job_id)
        if not context:
            self._update_job(job_id, status="failed", eta="missing context")
            return

        window_name = str(context.get("window_name", "full"))
        start_date = context.get("start_date")
        end_date = context.get("end_date")
        setting = dict(context.get("setting", self._adapter.default_setting()))

        ticker_stop = Event()
        ticker = Thread(
            target=self._progress_ticker,
            args=(job_id, ticker_stop),
            daemon=True,
        )

        self._update_job(job_id, status="running", progress=3, eta="loading data")
        ticker.start()

        try:
            stats = self._adapter.run_backtest(
                setting=setting,
                window_name=window_name,
                start_date=start_date,
                end_date=end_date,
            )
            metrics = self._derive_leaderboard_metrics(stats=stats, window_name=window_name)
            job = self._get_job(job_id)
            if not job:
                return
            row = BacktestLeaderboardRow(
                rank=0,
                strategy_id=job.strategy_id,
                combo_id=job.combo_id,
                rule_pack_id=job.rule_pack_id,
                template=job.template,
                cagr=metrics["cagr"],
                mdd=metrics["mdd"],
                calmar=metrics["calmar"],
                win_rate=metrics["win_rate"],
                turnover=metrics["turnover"],
                recent_1y=metrics["recent_1y"],
                robust_score=metrics["robust_score"],
                window=window_name,
            )
            self._upsert_leaderboard_row(row)
            done_eta = "done"
            if bool(stats.get("fallback_used")):
                done_eta = "done (auto-range)"
            self._update_job(job_id, status="finished", progress=100, eta=done_eta)
            self._refresh_candidate_status(job.combo_id)
            self._refresh_compare_rows()
        except Exception as exc:
            reason = str(exc).splitlines()[0][:42] if str(exc) else "error"
            self._update_job(job_id, status="failed", eta=f"error: {reason}")
            job = self._get_job(job_id)
            if job:
                self._refresh_candidate_status(job.combo_id)
        finally:
            ticker_stop.set()
            with self._lock:
                self._job_context.pop(job_id, None)

    def _progress_ticker(self, job_id: str, stop: Event) -> None:
        while not stop.wait(timeout=2.0):
            job = self._get_job(job_id)
            if not job or job.status != "running":
                return
            next_progress = min(90, max(5, job.progress + 7))
            eta_minutes = max(1, int((100 - next_progress) / 7) * 2)
            self._update_job(job_id, progress=next_progress, eta=f"{eta_minutes}m")

    def _get_job(self, job_id: str) -> BacktestJobRow | None:
        with self._lock:
            for row in self._jobs:
                if row.job_id == job_id:
                    return row
        return None

    def _update_job(self, job_id: str, **updates: Any) -> BacktestJobRow | None:
        with self._lock:
            for index, row in enumerate(self._jobs):
                if row.job_id != job_id:
                    continue
                merged = row.model_copy(update=updates)
                self._jobs[index] = merged
                return merged
        return None

    def _get_optimize_task(self, task_id: str) -> StrategyOptimizeTaskRow | None:
        with self._lock:
            for row in self._optimize_tasks:
                if row.task_id == task_id:
                    return row
        return None

    def _update_optimize_task(self, task_id: str, **updates: Any) -> StrategyOptimizeTaskRow | None:
        with self._lock:
            for index, row in enumerate(self._optimize_tasks):
                if row.task_id != task_id:
                    continue
                merged = row.model_copy(update=updates)
                self._optimize_tasks[index] = merged
                return merged
        return None

    def _evaluate_combo(
        self,
        *,
        module: Any,
        task_id: str,
        template_id: str,
        template_name: str,
        dataset: list[tuple[str, Any]],
        combo_id: str,
        windows: list[WindowName],
        start_date: date | None,
        end_date: date | None,
        setting: dict[str, Any],
    ) -> StrategyOptimizeResultRow:
        head_count = max(1, int(round(self._to_float(setting.get("head_count"), 10.0))))
        max_hold_num = max(1, int(round(self._to_float(setting.get("max_hold_num"), 12.0))))
        until_win = bool(setting.get("until_win", False))
        cfg = module.build_strategy_config(setting)

        all_metrics: list[dict[str, float]] = []
        all_returns: list[float] = []
        for window_name in windows:
            sliced = self._adapter._slice_dataset(
                dataset=dataset,
                window_name=window_name,
                start_date=start_date,
                end_date=end_date,
            )
            if not sliced:
                continue
            stats = module.run_backtest(
                dataset=sliced,
                cfg=cfg,
                head_count=head_count,
                max_hold_num=max_hold_num,
                until_win=until_win,
            )
            stats["sample_days"] = len(sliced)
            stats["rebalanced_days"] = max(0, len(sliced) - 1)
            metrics = self._derive_leaderboard_metrics(stats=stats, window_name=window_name)
            all_metrics.append(metrics)
            all_returns.append(self._to_float(stats.get("total_return_pct"), 0.0))

        if not all_metrics:
            for window_name in windows:
                sliced = self._adapter._slice_dataset(
                    dataset=dataset,
                    window_name=window_name,
                    start_date=None,
                    end_date=None,
                )
                if not sliced:
                    continue
                stats = module.run_backtest(
                    dataset=sliced,
                    cfg=cfg,
                    head_count=head_count,
                    max_hold_num=max_hold_num,
                    until_win=until_win,
                )
                stats["sample_days"] = len(sliced)
                stats["rebalanced_days"] = max(0, len(sliced) - 1)
                metrics = self._derive_leaderboard_metrics(stats=stats, window_name=window_name)
                all_metrics.append(metrics)
                all_returns.append(self._to_float(stats.get("total_return_pct"), 0.0))

        if not all_metrics:
            raise RuntimeError("No market snapshots available for selected window")

        cagr = sum(item["cagr"] for item in all_metrics) / len(all_metrics)
        mdd = max(item["mdd"] for item in all_metrics)
        calmar = cagr / mdd if mdd > 0 else cagr
        win_rate = sum(item["win_rate"] for item in all_metrics) / len(all_metrics)
        turnover = sum(item["turnover"] for item in all_metrics) / len(all_metrics)
        recent_1y = next((item["recent_1y"] for item, w in zip(all_metrics, windows) if w == "1y"), cagr)
        robust_score = sum(item["robust_score"] for item in all_metrics) / len(all_metrics)
        total_return_pct = sum(all_returns) / len(all_returns)

        return StrategyOptimizeResultRow(
            rank=0,
            task_id=task_id,
            template_id=template_id,
            template_name=template_name,
            combo_id=combo_id,
            robust_score=round(robust_score, 4),
            cagr=round(cagr, 6),
            mdd=round(mdd, 6),
            calmar=round(calmar, 6),
            win_rate=round(win_rate, 4),
            turnover=round(turnover, 6),
            recent_1y=round(recent_1y, 6),
            total_return_pct=round(total_return_pct, 4),
            params=self._serialize_setting(setting),
        )

    def _iter_template_settings(self, *, template_id: str, limit: int) -> Iterable[tuple[str, dict[str, Any]]]:
        cfg = self._template_configs.get(template_id)
        if not cfg:
            return

        enabled_rows = [row for row in cfg.parameter_space if row.enabled and row.factor_key in cfg.factor_keys]
        if not enabled_rows:
            return [(f"CMB-{idx:06d}", self._adapter.default_setting()) for idx in range(1, limit + 1)]

        factor_keys = [row.factor_key for row in enabled_rows]
        all_choices = [self._choices_for_param_row(row) for row in enabled_rows]

        yielded = 0
        for combo_values in islice(product(*all_choices), limit):
            yielded += 1
            factor_values = dict(zip(factor_keys, combo_values))
            combo_id = f"CMB-{yielded:06d}"
            yield combo_id, self._build_setting_from_factor_values(factor_values)

    def _choices_for_param_row(self, row: StrategyParamSpaceRow) -> list[Any]:
        if row.value_type == "enum":
            values = [value for value in row.enum_values if value.strip()]
            return values or ["default"]
        if row.min_value is None or row.max_value is None or row.step is None or row.step <= 0:
            return [0.0]
        count = self._count_choices(row)
        precision = 0
        text = str(row.step)
        if "." in text:
            precision = len(text.split(".", 1)[1].rstrip("0"))
        values: list[float] = []
        for idx in range(count):
            values.append(round(row.min_value + row.step * idx, min(6, max(0, precision))))
        return values

    def _build_setting_from_factor_values(self, values: dict[str, Any]) -> dict[str, Any]:
        setting = self._adapter.default_setting()
        direct_map: dict[str, str] = {
            "price_bemchmark": "price_bemchmark",
            "premium_bemchmark": "premium_bemchmark",
            "stock_ratio": "stock_ratio",
            "premium_ratio": "premium_ratio",
            "stock_stdevry_bemchmark": "stock_stdevry_bemchmark",
            "max_price": "max_price",
            "head_count": "head_count",
            "remain_ratio": "remain_ratio",
            "max_hold_num": "max_hold_num",
        }
        for factor_key, setting_key in direct_map.items():
            if factor_key in values:
                setting[setting_key] = values[factor_key]

        if "premium_max" in values and "premium_bemchmark" not in values:
            setting["premium_bemchmark"] = self._to_float(values["premium_max"], 25.0)
        if "conv_prem" in values and "premium_bemchmark" not in values:
            setting["premium_bemchmark"] = self._to_float(values["conv_prem"], 25.0)
        if "price_max" in values:
            setting["max_price"] = self._to_float(values["price_max"], setting.get("max_price", 130.0))
        if "remain_size" in values and "remain_ratio" not in values:
            remain_size = self._to_float(values["remain_size"], 12.0)
            setting["remain_ratio"] = max(0.05, min(0.50, remain_size / 100.0))
        if "turnover" in values and "stock_stdevry_bemchmark" not in values:
            turnover = self._to_float(values["turnover"], 2.0)
            setting["stock_stdevry_bemchmark"] = max(10.0, min(60.0, turnover * 4.0 + 12.0))
        if "dblow" in values and "price_bemchmark" not in values:
            dblow = self._to_float(values["dblow"], 140.0)
            premium = self._to_float(setting.get("premium_bemchmark"), 25.0)
            setting["price_bemchmark"] = max(90.0, min(180.0, dblow - premium))
        if "rating" in values:
            rating = str(values["rating"]).upper()
            if rating == "AAA":
                setting["premium_ratio"] = 0.2
                setting["max_price"] = min(130.0, self._to_float(setting.get("max_price"), 130.0))
            elif rating == "AA+":
                setting["premium_ratio"] = 0.25
            else:
                setting["premium_ratio"] = 0.3

        setting["head_count"] = max(1, int(round(self._to_float(setting.get("head_count"), 10.0))))
        setting["max_hold_num"] = max(1, int(round(self._to_float(setting.get("max_hold_num"), 12.0))))
        setting["stock_ratio"] = max(0.0, min(1.0, self._to_float(setting.get("stock_ratio"), 0.3)))
        setting["premium_ratio"] = max(0.0, min(1.0, self._to_float(setting.get("premium_ratio"), 0.3)))
        setting["until_win"] = bool(setting.get("until_win", False))
        return setting

    def _score_current_market(self, setting: dict[str, Any], limit: int = 20) -> tuple[list[StrategyTopBondRow], str]:
        market = self._market_service.list_bonds(min_volume_wan=0)
        if market.source.startswith("fallback.mock"):
            raise RuntimeError(f"realtime market source unavailable: {market.source}")
        rows = []
        price_b = max(1.0, self._to_float(setting.get("price_bemchmark"), 115.0))
        premium_b = max(1.0, self._to_float(setting.get("premium_bemchmark"), 25.0))
        stock_ratio = max(0.0, min(1.0, self._to_float(setting.get("stock_ratio"), 0.3)))
        bond_ratio = max(0.0, min(1.0, 1.0 - stock_ratio))
        premium_ratio = max(0.0, min(1.0, self._to_float(setting.get("premium_ratio"), 0.3)))
        remain_ratio = max(0.0, min(1.0, self._to_float(setting.get("remain_ratio"), 0.1)))
        stdev_b = max(5.0, self._to_float(setting.get("stock_stdevry_bemchmark"), 30.0))
        max_price = self._to_float(setting.get("max_price"), 130.0)

        for item in market.items:
            if item.price > max_price:
                continue
            if item.premium_rt > 200:
                continue

            premium_score = 1 - (item.premium_rt - premium_b) / premium_b
            price_score = 1 - (item.price - price_b) / price_b

            remain_amount = self._to_float(item.remain_scale_yi, 10.0)
            if remain_amount < 3:
                remain_score = 1 - (remain_amount - 3) / 3
            elif remain_amount > 30:
                remain_score = max(0.6, 1 - (remain_amount - 30) / 30)
            else:
                remain_score = 1.0

            pb = self._to_float(item.stock_pb, 1.5)
            pb_score = min(1.0, max(0.6, 1 - (1.5 - pb) / 1.5))

            stock_vol = self._to_float(item.stock_volatility, stdev_b)
            stdev_score = min(1.5, max(0.6, 1 - (stdev_b - stock_vol) / stdev_b))

            score = round(
                bond_ratio * price_score
                + stock_ratio * (premium_score * premium_ratio + stdev_score * 0.2 + remain_score * remain_ratio + pb_score * 0.1),
                4,
            )
            if score <= 0:
                continue
            rows.append(
                StrategyTopBondRow(
                    rank=0,
                    bond_id=item.bond_id,
                    bond_name=item.bond_name,
                    price=item.price,
                    premium_rt=item.premium_rt,
                    dblow=item.dblow,
                    amount_wan=item.amount_wan,
                    score=score,
                    update_time=item.update_time,
                )
            )
        rows.sort(key=lambda item: (item.score, item.amount_wan or 0.0), reverse=True)
        ranked = [row.model_copy(update={"rank": idx + 1}) for idx, row in enumerate(rows[: max(1, limit)])]
        return ranked, market.source

    @staticmethod
    def _serialize_setting(setting: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in setting.items():
            if isinstance(value, (int, float, str, bool)) or value is None:
                payload[key] = value
        return payload

    def _simulate_detailed_strategy(
        self,
        *,
        module: Any,
        dataset: list[tuple[str, Any]],
        setting: dict[str, Any],
        initial_capital_wan: float,
    ) -> dict[str, Any]:
        cfg = module.build_strategy_config(setting)
        head_count = max(1, int(round(self._to_float(setting.get("head_count"), 10.0))))
        max_hold_num = max(1, int(round(self._to_float(setting.get("max_hold_num"), 12.0))))
        until_win = bool(setting.get("until_win", False))
        per_position = 1.0 / max_hold_num if max_hold_num > 0 else 0.0

        dates: list[str] = []
        daily_returns: list[float] = []
        nav_series: list[float] = []
        cum_return_pct: list[float] = []
        drawdown_pct: list[float] = []
        avg_drawdown_pct: list[float] = []
        turnover_pct: list[float] = []
        trade_pnls_pct: list[float] = []
        rotations: list[StrategyBacktestRotationRow] = []

        holdings: list[dict[str, Any]] = []
        nav = 1.0
        peak = 1.0
        drawdown_sum = 0.0
        drawdown_count = 0
        effective_trade_count = 0
        prev_codes: set[str] = set()

        for index, (trade_date, df_all) in enumerate(dataset):
            candidate = module.build_candidates(df_all, trade_date, cfg, head_count)
            if candidate is None:
                candidate = df_all.iloc[0:0]
            if candidate is None or candidate.empty:
                candidate_codes: set[str] = set()
            else:
                candidate_codes = set(candidate["cb_code"].astype(str).tolist())

            if index == 0:
                if candidate is not None and not candidate.empty:
                    for _, row in candidate.head(max_hold_num).iterrows():
                        price = self._to_float(row.get("price"), 0.0)
                        if price <= 0:
                            continue
                        holdings.append(
                            {
                                "code": str(row.get("cb_code", "")),
                                "buy_price": price,
                                "last_price": price,
                                "ratio": per_position,
                            }
                        )
                prev_codes = {item["code"] for item in holdings}
                dates.append(trade_date)
                daily_returns.append(0.0)
                nav_series.append(nav)
                cum_return_pct.append(0.0)
                drawdown_pct.append(0.0)
                avg_drawdown_pct.append(0.0)
                turnover_pct.append(0.0)
                rotations.append(
                    StrategyBacktestRotationRow(
                        rebalance_date=trade_date,
                        weekday=self._weekday_cn(trade_date),
                        holdings=self._format_holdings_text(holdings=holdings, frame=df_all),
                        holding_count=len(holdings),
                        turnover_pct=0.0,
                        period_return_pct=0.0,
                        cumulative_return_pct=0.0,
                        nav_wan=round(initial_capital_wan * nav, 4),
                    )
                )
                continue

            day_return = 0.0
            for item in holdings:
                code = str(item.get("code", ""))
                if code not in df_all.index:
                    continue
                row = df_all.loc[code]
                cur_price = self._to_float(row.get("price"), self._to_float(item.get("last_price"), 0.0))
                last_price = max(1e-8, self._to_float(item.get("last_price"), cur_price))
                ratio = self._to_float(item.get("ratio"), 0.0)
                day_return += ((cur_price - last_price) / last_price) * ratio
                item["last_price"] = cur_price

            nav *= 1.0 + day_return
            if nav > peak:
                peak = nav
            drawdown = (nav / peak - 1.0) * 100 if peak > 0 else 0.0
            drawdown_sum += drawdown
            drawdown_count += 1

            keep_list: list[dict[str, Any]] = []
            sell_list: list[dict[str, Any]] = []

            for item in holdings:
                code = str(item.get("code", ""))
                if code not in df_all.index:
                    sell_list.append(item)
                    continue
                row = df_all.loc[code]
                cur_price = self._to_float(row.get("price"), self._to_float(item.get("last_price"), 0.0))
                is_ransom = str(row.get("is_ransom_flag", "False")) == "True"
                if is_ransom:
                    sell_list.append(item)
                    continue
                if until_win and cur_price <= self._to_float(item.get("buy_price"), cur_price):
                    keep_list.append(item)
                    continue
                if code in candidate_codes:
                    keep_list.append(item)
                else:
                    sell_list.append(item)

            for item in sell_list:
                code = str(item.get("code", ""))
                if code in df_all.index:
                    row = df_all.loc[code]
                    sell_price = self._to_float(row.get("price"), self._to_float(item.get("last_price"), 0.0))
                else:
                    sell_price = self._to_float(item.get("last_price"), 0.0)
                buy_price = max(1e-8, self._to_float(item.get("buy_price"), sell_price))
                pnl_pct = (sell_price - buy_price) / buy_price * 100.0
                trade_pnls_pct.append(pnl_pct)
                effective_trade_count += 1

            existing_codes = {str(item.get("code", "")) for item in keep_list}
            for _, row in candidate.iterrows():
                if len(keep_list) >= max_hold_num:
                    break
                code = str(row.get("cb_code", ""))
                if code in existing_codes:
                    continue
                price = self._to_float(row.get("price"), 0.0)
                if price <= 0:
                    continue
                keep_list.append(
                    {
                        "code": code,
                        "buy_price": price,
                        "last_price": price,
                        "ratio": per_position,
                    }
                )
                existing_codes.add(code)

            current_codes = {str(item.get("code", "")) for item in keep_list}
            if prev_codes:
                changed_count = len(prev_codes - current_codes) + len(current_codes - prev_codes)
                day_turnover = changed_count / max(1, len(prev_codes)) * 100.0
            else:
                changed_count = len(current_codes)
                day_turnover = changed_count / max(1, max_hold_num) * 100.0

            holdings = keep_list
            prev_codes = current_codes

            dates.append(trade_date)
            daily_returns.append(day_return)
            nav_series.append(nav)
            cum_return_pct.append((nav - 1.0) * 100.0)
            drawdown_pct.append(drawdown)
            avg_drawdown_pct.append(drawdown_sum / max(1, drawdown_count))
            turnover_pct.append(day_turnover)

            if changed_count > 0 or index == len(dataset) - 1:
                rotations.append(
                    StrategyBacktestRotationRow(
                        rebalance_date=trade_date,
                        weekday=self._weekday_cn(trade_date),
                        holdings=self._format_holdings_text(holdings=holdings, frame=df_all),
                        holding_count=len(holdings),
                        turnover_pct=round(day_turnover, 4),
                        period_return_pct=round(day_return * 100.0, 4),
                        cumulative_return_pct=round((nav - 1.0) * 100.0, 4),
                        nav_wan=round(initial_capital_wan * nav, 4),
                    )
                )

        return {
            "dates": dates,
            "daily_returns": daily_returns,
            "nav_series": nav_series,
            "cum_return_pct": cum_return_pct,
            "drawdown_pct": drawdown_pct,
            "avg_drawdown_pct": avg_drawdown_pct,
            "turnover_pct": turnover_pct,
            "trade_pnls_pct": trade_pnls_pct,
            "rotations": rotations,
            "effective_trade_count": effective_trade_count,
        }

    def _simulate_equal_weight_benchmark(
        self,
        *,
        dataset: list[tuple[str, Any]],
        initial_capital_wan: float,
    ) -> dict[str, Any]:
        dates: list[str] = []
        daily_returns: list[float] = []
        nav_series: list[float] = []
        cum_return_pct: list[float] = []

        nav = 1.0
        for index, (trade_date, frame) in enumerate(dataset):
            if index == 0:
                dates.append(trade_date)
                daily_returns.append(0.0)
                nav_series.append(nav)
                cum_return_pct.append(0.0)
                continue

            prev_frame = dataset[index - 1][1]
            daily_ret = 0.0
            try:
                common_idx = prev_frame.index.intersection(frame.index)
                if len(common_idx) > 0 and "price" in prev_frame.columns and "price" in frame.columns:
                    prev_prices = prev_frame.loc[common_idx, "price"].astype(float)
                    cur_prices = frame.loc[common_idx, "price"].astype(float)
                    valid = prev_prices > 0
                    if bool(valid.any()):
                        returns = (cur_prices[valid] - prev_prices[valid]) / prev_prices[valid]
                        daily_ret = float(returns.mean())
            except Exception:
                daily_ret = 0.0

            nav *= 1.0 + daily_ret
            dates.append(trade_date)
            daily_returns.append(daily_ret)
            nav_series.append(nav)
            cum_return_pct.append((nav - 1.0) * 100.0)

        return {
            "dates": dates,
            "daily_returns": daily_returns,
            "nav_series": nav_series,
            "cum_return_pct": cum_return_pct,
            "final_asset_wan": round(initial_capital_wan * nav, 4),
        }

    def _compute_backtest_metrics(
        self,
        *,
        daily_returns: list[float],
        nav_series: list[float],
        initial_capital_wan: float,
        turnover_pct: list[float] | None = None,
        trade_pnls_pct: list[float] | None = None,
    ) -> dict[str, float | None]:
        if not nav_series:
            nav_series = [1.0]
        eval_returns = daily_returns[1:] if len(daily_returns) > 1 else list(daily_returns)
        sample_days = len(eval_returns)
        final_nav = nav_series[-1]

        total_return_pct = (final_nav - 1.0) * 100.0
        cumulative_asset_wan = initial_capital_wan * final_nav
        years = max(sample_days / 244.0, 1.0 / 244.0)
        annual_return_pct = (((max(final_nav, 1e-9)) ** (1.0 / years)) - 1.0) * 100.0

        peak = nav_series[0]
        worst_drawdown = 0.0
        drawdown_duration = 0
        max_drawdown_duration = 0
        for nav in nav_series:
            if nav > peak:
                peak = nav
                drawdown_duration = 0
            drawdown = nav / peak - 1.0 if peak > 0 else 0.0
            if drawdown < 0:
                drawdown_duration += 1
                if drawdown_duration > max_drawdown_duration:
                    max_drawdown_duration = drawdown_duration
            if drawdown < worst_drawdown:
                worst_drawdown = drawdown

        mean_daily = sum(eval_returns) / sample_days if sample_days else 0.0
        if sample_days > 1:
            variance = sum((value - mean_daily) ** 2 for value in eval_returns) / (sample_days - 1)
            daily_std = sqrt(max(variance, 0.0))
        else:
            daily_std = 0.0
        downside_values = [value for value in eval_returns if value < 0]
        downside_std = sqrt(sum(value * value for value in downside_values) / len(downside_values)) if downside_values else 0.0
        sharpe = mean_daily / daily_std * sqrt(244.0) if daily_std > 1e-12 else 0.0
        sortino = mean_daily / downside_std * sqrt(244.0) if downside_std > 1e-12 else 0.0
        max_drawdown_pct = worst_drawdown * 100.0
        calmar = annual_return_pct / abs(max_drawdown_pct) if abs(max_drawdown_pct) > 1e-9 else 0.0

        turnover_values = turnover_pct or []
        avg_turnover_pct = sum(turnover_values) / len(turnover_values) if turnover_values else 0.0

        cycle_returns = trade_pnls_pct or []
        trade_cycles = len(cycle_returns)
        profit_cycles = len([value for value in cycle_returns if value > 0])
        loss_cycles = len([value for value in cycle_returns if value <= 0])
        win_rate_pct = (profit_cycles / trade_cycles * 100.0) if trade_cycles > 0 else 0.0
        avg_cycle_return_pct = (sum(cycle_returns) / trade_cycles) if trade_cycles > 0 else None
        max_cycle_profit_pct = max(cycle_returns) if trade_cycles > 0 else None
        max_cycle_loss_pct = min(cycle_returns) if trade_cycles > 0 else None
        avg_profit = (
            sum(value for value in cycle_returns if value > 0) / profit_cycles
            if profit_cycles > 0
            else None
        )
        avg_loss = (
            abs(sum(value for value in cycle_returns if value <= 0) / loss_cycles)
            if loss_cycles > 0
            else None
        )
        if avg_profit is None or avg_loss is None or avg_loss <= 1e-9:
            profit_loss_ratio = None
        else:
            profit_loss_ratio = avg_profit / avg_loss

        return {
            "total_return_pct": round(total_return_pct, 4),
            "cumulative_asset_wan": round(cumulative_asset_wan, 4),
            "annual_return_pct": round(annual_return_pct, 4),
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "sharpe": round(sharpe, 4),
            "sortino": round(sortino, 4),
            "calmar": round(calmar, 4),
            "avg_turnover_pct": round(avg_turnover_pct, 4),
            "trade_cycles": float(trade_cycles),
            "profit_cycles": float(profit_cycles),
            "loss_cycles": float(loss_cycles),
            "win_rate_pct": round(win_rate_pct, 4),
            "profit_loss_ratio": round(profit_loss_ratio, 4) if profit_loss_ratio is not None else None,
            "avg_cycle_return_pct": round(avg_cycle_return_pct, 4) if avg_cycle_return_pct is not None else None,
            "max_cycle_profit_pct": round(max_cycle_profit_pct, 4) if max_cycle_profit_pct is not None else None,
            "max_cycle_loss_pct": round(max_cycle_loss_pct, 4) if max_cycle_loss_pct is not None else None,
            "max_drawdown_duration_days": float(max_drawdown_duration),
        }

    def _build_metric_rows(
        self,
        *,
        strategy_metrics: dict[str, float | None],
        benchmark_metrics: dict[str, float | None],
    ) -> list[StrategyBacktestMetricRow]:
        metric_keys = [
            "total_return_pct",
            "cumulative_asset_wan",
            "annual_return_pct",
            "max_drawdown_pct",
            "sharpe",
            "sortino",
            "calmar",
            "avg_turnover_pct",
            "trade_cycles",
            "profit_cycles",
            "loss_cycles",
            "win_rate_pct",
            "profit_loss_ratio",
            "avg_cycle_return_pct",
            "max_cycle_profit_pct",
            "max_cycle_loss_pct",
            "max_drawdown_duration_days",
        ]

        relative_metrics: dict[str, float | None] = {}
        absolute_metrics: dict[str, float | None] = {}
        for key in metric_keys:
            strategy_value = strategy_metrics.get(key)
            benchmark_value = benchmark_metrics.get(key)
            if strategy_value is None or benchmark_value is None:
                relative_metrics[key] = None
            else:
                relative_metrics[key] = round(strategy_value - benchmark_value, 4)
            absolute_metrics[key] = strategy_value

        return [
            StrategyBacktestMetricRow(strategy_combo="当前策略", **strategy_metrics),
            StrategyBacktestMetricRow(strategy_combo="基准策略", **benchmark_metrics),
            StrategyBacktestMetricRow(strategy_combo="相对超额", **relative_metrics),
            StrategyBacktestMetricRow(strategy_combo="绝对超额", **absolute_metrics),
        ]

    def _build_distribution_rows(
        self,
        *,
        dates: list[str],
        strategy_daily_returns: list[float],
        benchmark_daily_returns: list[float],
        period: str,
    ) -> list[StrategyBacktestDistributionRow]:
        grouped: dict[str, dict[str, float]] = {}
        ordered_keys: list[str] = []
        for index in range(1, min(len(dates), len(strategy_daily_returns), len(benchmark_daily_returns))):
            date_text = dates[index]
            try:
                trade_dt = datetime.strptime(date_text, "%Y-%m-%d")
            except ValueError:
                continue

            if period == "yearly":
                key = f"{trade_dt.year}年"
            elif period == "monthly":
                key = f"{trade_dt.year}-{trade_dt.month:02d}"
            else:
                iso = trade_dt.isocalendar()
                key = f"{iso.year}-W{iso.week:02d}"

            if key not in grouped:
                grouped[key] = {"strategy": 1.0, "benchmark": 1.0}
                ordered_keys.append(key)

            grouped[key]["strategy"] *= 1.0 + strategy_daily_returns[index]
            grouped[key]["benchmark"] *= 1.0 + benchmark_daily_returns[index]

        rows: list[StrategyBacktestDistributionRow] = []
        for key in ordered_keys:
            strategy_ret = (grouped[key]["strategy"] - 1.0) * 100.0
            benchmark_ret = (grouped[key]["benchmark"] - 1.0) * 100.0
            rows.append(
                StrategyBacktestDistributionRow(
                    period=key,
                    strategy_return_pct=round(strategy_ret, 4),
                    benchmark_return_pct=round(benchmark_ret, 4),
                    excess_return_pct=round(strategy_ret - benchmark_ret, 4),
                )
            )
        return rows

    def _format_holdings_text(self, *, holdings: list[dict[str, Any]], frame: Any) -> str:
        if not holdings:
            return "--"
        labels: list[str] = []
        for item in holdings[:12]:
            code = str(item.get("code", ""))
            name = ""
            if code in frame.index:
                row = frame.loc[code]
                if hasattr(row, "iloc") and not isinstance(row, dict):
                    try:
                        row = row.iloc[0]
                    except Exception:
                        pass
                if hasattr(row, "to_dict"):
                    row = row.to_dict()
                if isinstance(row, dict):
                    name = str(row.get("cb_name", "")).strip()
            if not name:
                name = code
            labels.append(f"{name}({code})")
        suffix = f" 等{len(holdings)}只" if len(holdings) > 12 else ""
        return "，".join(labels) + suffix

    @staticmethod
    def _weekday_cn(date_text: str) -> str:
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        try:
            idx = datetime.strptime(date_text, "%Y-%m-%d").weekday()
            return weekdays[idx]
        except ValueError:
            return "--"

    @staticmethod
    def _parse_iso_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    def _resolve_setting_for_combo(self, *, combo_id: str, template_name: str) -> dict[str, Any]:
        setting = self._candidate_settings.get(combo_id)
        if setting:
            return dict(setting)

        template_id = ""
        candidate = self._find_candidate(combo_id)
        if candidate and candidate.template_id:
            template_id = candidate.template_id
        elif template_name:
            for row in self._templates:
                if row.name == template_name:
                    template_id = row.id
                    break

        if not template_id:
            resolved = self._adapter.default_setting()
            self._candidate_settings[combo_id] = dict(resolved)
            return resolved
        resolved = self._build_candidate_setting(template_id=template_id, combo_id=combo_id)
        self._candidate_settings[combo_id] = dict(resolved)
        return resolved

    def _build_candidate_setting(self, *, template_id: str, combo_id: str) -> dict[str, Any]:
        cfg = self._template_configs.get(template_id) or self._default_config(
            template_id=template_id,
            updated_at=_now_readable(),
        )

        row_map: dict[str, StrategyParamSpaceRow] = {
            row.factor_key: row for row in cfg.parameter_space if row.enabled
        }
        values: dict[str, Any] = {}
        for factor_key, row in row_map.items():
            values[factor_key] = self._pick_param_value(combo_id=combo_id, row=row)
        return self._build_setting_from_factor_values(values)

    def _pick_param_value(self, *, combo_id: str, row: StrategyParamSpaceRow) -> Any:
        seed = self._hash(f"{combo_id}|{row.factor_key}")
        if row.value_type == "enum":
            values = [value for value in row.enum_values if value.strip()]
            if not values:
                return "default"
            return values[seed % len(values)]

        if row.min_value is None or row.max_value is None or row.step is None or row.step <= 0:
            return row.min_value if row.min_value is not None else 0.0

        count = self._count_choices(row)
        idx = seed % count
        raw = row.min_value + row.step * idx
        precision = 0
        text = f"{row.step}"
        if "." in text:
            precision = len(text.split(".", 1)[1].rstrip("0"))
        return round(raw, min(6, max(0, precision)))

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _derive_leaderboard_metrics(self, *, stats: dict[str, Any], window_name: WindowName) -> dict[str, float]:
        total_return_pct = self._to_float(stats.get("total_return_pct"), 0.0)
        max_drawdown_pct = self._to_float(stats.get("max_drawdown_pct"), 0.0)
        win_rate_pct = self._to_float(stats.get("win_rate_pct"), 0.0)
        trade_count = self._to_float(stats.get("trade_count"), 0.0)
        sample_days = max(1.0, self._to_float(stats.get("sample_days"), 1.0))
        rebalanced_days = max(1.0, self._to_float(stats.get("rebalanced_days"), sample_days))

        total_return = total_return_pct / 100.0
        mdd = max(0.0, max_drawdown_pct / 100.0)
        years = max(0.1, sample_days / 244.0)
        cagr = (1 + total_return) ** (1 / years) - 1 if total_return > -0.999 else -0.999
        calmar = cagr / mdd if mdd > 0 else max(0.0, cagr)
        turnover = min(2.0, max(0.0, trade_count / rebalanced_days))
        recent_1y = total_return if window_name == "1y" else cagr
        robust_score = self._calculate_robust_score(
            cagr=cagr,
            mdd=mdd,
            calmar=calmar,
            win_rate_pct=win_rate_pct,
            turnover=turnover,
            window_name=window_name,
        )
        return {
            "cagr": round(cagr, 6),
            "mdd": round(mdd, 6),
            "calmar": round(calmar, 6),
            "win_rate": round(win_rate_pct, 4),
            "turnover": round(turnover, 6),
            "recent_1y": round(recent_1y, 6),
            "robust_score": robust_score,
        }

    @staticmethod
    def _calculate_robust_score(
        *,
        cagr: float,
        mdd: float,
        calmar: float,
        win_rate_pct: float,
        turnover: float,
        window_name: WindowName,
    ) -> float:
        # Strongly penalize zero/negative return strategies to avoid ranking no-trade combos at top.
        if cagr <= 0.0001:
            base = 10.0
            base += max(-4.0, min(4.0, (win_rate_pct - 50.0) * 0.08))
            base += max(-4.0, min(4.0, (0.08 - turnover) * 10.0))
            if turnover < 0.01:
                base = min(base, 6.0)
            return round(max(0.0, min(25.0, base)), 1)

        score = 55.0
        score += max(-35.0, min(35.0, cagr * 120.0))
        score += max(-20.0, min(22.0, (0.25 - mdd) * 80.0))
        score += max(-8.0, min(18.0, calmar * 6.0))
        score += max(-10.0, min(12.0, (win_rate_pct - 50.0) * 0.6))
        score += max(-8.0, min(8.0, (0.30 - turnover) * 20.0))
        if window_name == "full":
            score += 2.0
        return round(max(0.0, min(100.0, score)), 1)

    def _upsert_leaderboard_row(self, row: BacktestLeaderboardRow) -> None:
        with self._lock:
            replaced = False
            for index, item in enumerate(self._leaderboard):
                same_key = (
                    item.combo_id == row.combo_id
                    and item.rule_pack_id == row.rule_pack_id
                    and item.window == row.window
                )
                if not same_key:
                    continue
                self._leaderboard[index] = row
                replaced = True
                break
            if not replaced:
                self._leaderboard.append(row)

            ordered = sorted(
                self._leaderboard,
                key=lambda item: (item.robust_score, item.cagr, -item.mdd),
                reverse=True,
            )
            self._leaderboard = [
                item.model_copy(update={"rank": idx + 1})
                for idx, item in enumerate(ordered)
            ]

    def _refresh_compare_rows(self) -> None:
        with self._lock:
            top = self._leaderboard[:3]
            baseline = {
                "cagr": 0.214,
                "recent_1y": 0.112,
                "mdd": 0.286,
                "calmar": 0.750,
                "turnover": 0.440,
                "win_rate": 49.0,
            }
            c1 = top[0] if len(top) > 0 else None
            c2 = top[1] if len(top) > 1 else None
            c3 = top[2] if len(top) > 2 else None
            self._compare = [
                BacktestCompareRow(
                    metric="CAGR",
                    category="return",
                    baseline=baseline["cagr"],
                    candidate_a=c1.cagr if c1 else 0.0,
                    candidate_b=c2.cagr if c2 else 0.0,
                    candidate_c=c3.cagr if c3 else 0.0,
                ),
                BacktestCompareRow(
                    metric="近1年收益",
                    category="return",
                    baseline=baseline["recent_1y"],
                    candidate_a=c1.recent_1y if c1 else 0.0,
                    candidate_b=c2.recent_1y if c2 else 0.0,
                    candidate_c=c3.recent_1y if c3 else 0.0,
                ),
                BacktestCompareRow(
                    metric="最大回撤",
                    category="risk",
                    baseline=baseline["mdd"],
                    candidate_a=c1.mdd if c1 else 0.0,
                    candidate_b=c2.mdd if c2 else 0.0,
                    candidate_c=c3.mdd if c3 else 0.0,
                ),
                BacktestCompareRow(
                    metric="Calmar",
                    category="risk",
                    baseline=baseline["calmar"],
                    candidate_a=c1.calmar if c1 else 0.0,
                    candidate_b=c2.calmar if c2 else 0.0,
                    candidate_c=c3.calmar if c3 else 0.0,
                ),
                BacktestCompareRow(
                    metric="年化换手",
                    category="trade",
                    baseline=baseline["turnover"],
                    candidate_a=c1.turnover if c1 else 0.0,
                    candidate_b=c2.turnover if c2 else 0.0,
                    candidate_c=c3.turnover if c3 else 0.0,
                ),
                BacktestCompareRow(
                    metric="胜率",
                    category="trade",
                    baseline=baseline["win_rate"] / 100.0,
                    candidate_a=(c1.win_rate / 100.0) if c1 else 0.0,
                    candidate_b=(c2.win_rate / 100.0) if c2 else 0.0,
                    candidate_c=(c3.win_rate / 100.0) if c3 else 0.0,
                ),
            ]

    def _refresh_candidate_status(self, combo_id: str) -> None:
        with self._lock:
            combo_jobs = [row for row in self._jobs if row.combo_id == combo_id]
            if not combo_jobs:
                return

            total = len(combo_jobs)
            finished = sum(1 for row in combo_jobs if row.status == "finished")
            failed = sum(1 for row in combo_jobs if row.status == "failed")
            running = sum(1 for row in combo_jobs if row.status == "running")
            queued = sum(1 for row in combo_jobs if row.status == "queued")

            done = finished + failed
            has_running = running > 0 or queued > 0
            combo_rows = [
                row
                for row in self._leaderboard
                if row.combo_id == combo_id
            ]
            pass_count = sum(1 for row in combo_rows if row.cagr >= 0.20 and row.mdd <= 0.30)
            pass_rate = (pass_count / max(1, len(combo_rows))) if combo_rows else None
            if has_running:
                status = "running_backtest"
            elif failed > 0 and finished == 0:
                status = "backtest_failed"
            elif done >= total and finished > 0:
                status = "backtested"
            else:
                status = "pending_backtest"

            self._candidates = [
                row.model_copy(
                    update={
                        "status": status if row.combo_id == combo_id else row.status,
                        "pass_rate": pass_rate if row.combo_id == combo_id else row.pass_rate,
                    }
                )
                for row in self._candidates
            ]

    def _rebuild_candidate_settings(self) -> None:
        settings: dict[str, dict[str, Any]] = {}
        for candidate in self._candidates:
            if candidate.combo_id in settings:
                continue
            template_id = candidate.template_id
            if not template_id:
                for row in self._templates:
                    if row.name == candidate.template:
                        template_id = row.id
                        break
            if not template_id:
                settings[candidate.combo_id] = self._adapter.default_setting()
                continue
            settings[candidate.combo_id] = self._build_candidate_setting(
                template_id=template_id,
                combo_id=candidate.combo_id,
            )
        self._candidate_settings = settings

    # ---------- helpers ----------
    def _find_candidate(self, combo_id: str) -> CandidateRow | None:
        for row in self._candidates:
            if row.combo_id == combo_id:
                return row
        return None

    def _find_template(self, template_id: str) -> StrategyTemplateRow | None:
        for row in self._templates:
            if row.id == template_id:
                return row
        return None

    def _default_config(self, template_id: str, updated_at: str) -> StrategyTemplateConfigResponse:
        factor_keys: list[str] = []
        parameter_space = self._normalize_parameter_space(
            factor_keys=factor_keys,
            parameter_space=[],
        )
        return StrategyTemplateConfigResponse(
            template_id=template_id,
            factor_keys=factor_keys,
            expression_draft="",
            parameter_space=parameter_space,
            combo_size=self._calculate_combo_size(factor_keys=factor_keys, parameter_space=parameter_space),
            updated_at=updated_at,
        )

    def _sync_template_metrics(
        self,
        templates: list[StrategyTemplateRow],
        configs: dict[str, StrategyTemplateConfigResponse],
    ) -> list[StrategyTemplateRow]:
        synced: list[StrategyTemplateRow] = []
        for template in templates:
            config = configs.get(template.id)
            if not config:
                synced.append(template)
                continue
            synced.append(
                StrategyTemplateRow(
                    id=template.id,
                    name=template.name,
                    version=template.version,
                    status=template.status,
                    factor_count=len(config.factor_keys),
                    rebalance=template.rebalance,
                    risk_preset=template.risk_preset,
                    combo_size=config.combo_size,
                    owner=template.owner,
                    updated_at=template.updated_at,
                )
            )
        return synced

    def _normalize_parameter_space(
        self,
        *,
        factor_keys: list[str],
        parameter_space: list[StrategyParamSpaceRow],
    ) -> list[StrategyParamSpaceRow]:
        keyed: dict[str, StrategyParamSpaceRow] = {row.factor_key: row for row in parameter_space}
        normalized: list[StrategyParamSpaceRow] = []

        for factor_key in factor_keys:
            row = keyed.get(factor_key) or self._default_param_space_row(factor_key)
            if row.value_type == "number":
                min_value = row.min_value
                max_value = row.max_value
                step = row.step
                if min_value is None or max_value is None or step is None or step <= 0 or max_value < min_value:
                    fallback = self._default_param_space_row(factor_key)
                    min_value = fallback.min_value
                    max_value = fallback.max_value
                    step = fallback.step
                normalized.append(
                    StrategyParamSpaceRow(
                        factor_key=factor_key,
                        value_type="number",
                        enabled=row.enabled,
                        min_value=min_value,
                        max_value=max_value,
                        step=step,
                        enum_values=[],
                    )
                )
            else:
                values = [value.strip() for value in row.enum_values if value.strip()]
                if not values:
                    fallback = self._default_param_space_row(factor_key)
                    values = fallback.enum_values or ["default"]
                normalized.append(
                    StrategyParamSpaceRow(
                        factor_key=factor_key,
                        value_type="enum",
                        enabled=row.enabled,
                        min_value=None,
                        max_value=None,
                        step=None,
                        enum_values=values,
                    )
                )
        return normalized

    def _default_param_space_row(self, factor_key: str) -> StrategyParamSpaceRow:
        numeric_defaults: dict[str, tuple[float, float, float]] = {
            "dblow": (100, 180, 5),
            "conv_prem": (0, 40, 2),
            "turnover": (0.2, 8.0, 0.2),
            "remain_size": (1, 80, 1),
            "price_max": (105, 150, 1),
            "premium_max": (5, 35, 0.5),
            "price_bemchmark": (106, 124, 2),
            "premium_bemchmark": (16, 34, 2),
            "stock_ratio": (0.20, 0.35, 0.05),
            "premium_ratio": (0.15, 0.35, 0.05),
            "stock_stdevry_bemchmark": (20, 35, 5),
            "max_price": (130, 200, 10),
            "head_count": (5, 15, 5),
            "remain_ratio": (0.10, 0.20, 0.05),
            "max_hold_num": (5, 10, 5),
        }
        enum_defaults: dict[str, list[str]] = {
            "rating": ["AA", "AA+", "AAA"],
        }
        if factor_key in enum_defaults:
            return StrategyParamSpaceRow(
                factor_key=factor_key,
                value_type="enum",
                enabled=True,
                enum_values=enum_defaults[factor_key],
            )
        min_value, max_value, step = numeric_defaults.get(factor_key, (0, 10, 1))
        return StrategyParamSpaceRow(
            factor_key=factor_key,
            value_type="number",
            enabled=True,
            min_value=min_value,
            max_value=max_value,
            step=step,
        )

    def _calculate_combo_size(
        self,
        *,
        factor_keys: list[str],
        parameter_space: list[StrategyParamSpaceRow],
    ) -> int:
        if not factor_keys:
            return 0
        row_map: dict[str, StrategyParamSpaceRow] = {row.factor_key: row for row in parameter_space}
        combo_size = 1
        for factor_key in factor_keys:
            row = row_map.get(factor_key) or self._default_param_space_row(factor_key)
            if not row.enabled:
                continue
            combo_size *= self._count_choices(row)
        return max(combo_size, 1)

    @staticmethod
    def _count_choices(row: StrategyParamSpaceRow) -> int:
        if row.value_type == "enum":
            return max(1, len([value for value in row.enum_values if value.strip()]))

        if row.min_value is None or row.max_value is None or row.step is None:
            return 1
        if row.step <= 0 or row.max_value < row.min_value:
            return 1

        span = row.max_value - row.min_value
        count = int((span + 1e-12) // row.step) + 1
        return max(1, count)

    def _build_rule_pack_id(self, request: BacktestCreateJobsRequest) -> str:
        mode_prefix = {
            "inherit": "INH",
            "candidate": "CAN",
            "custom": "CUS",
        }.get(request.source_mode, "CAN")

        est = request.est_strategies or 251220
        digest = str(est).zfill(6)[-6:]
        return f"RP-{mode_prefix}-{digest}"

    @staticmethod
    def _normalize_windows(values: Iterable[WindowName]) -> list[WindowName]:
        seen: set[WindowName] = set()
        normalized: list[WindowName] = []

        for value in values:
            if value in seen:
                continue
            seen.add(value)
            normalized.append(value)

        return normalized

    @staticmethod
    def _window_label(window_name: WindowName) -> str:
        if window_name == "full":
            return "2018-2025"
        if window_name == "3y":
            return "近3年"
        return "近1年"

    @staticmethod
    def _hash(value: str) -> int:
        state = 0
        for char in value:
            state = (state * 131 + ord(char)) & 0xFFFFFFFF
        return state

    @staticmethod
    def _make_random(seed: int):
        state = seed & 0xFFFFFFFF

        def _next() -> float:
            nonlocal state
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            return state / 0x100000000

        return _next

    def _load_templates_and_configs(
        self,
    ) -> tuple[list[StrategyTemplateRow], dict[str, StrategyTemplateConfigResponse]]:
        if self._templates_file.exists():
            try:
                payload = json.loads(self._templates_file.read_text(encoding="utf-8"))
                templates = [StrategyTemplateRow.model_validate(item) for item in payload.get("templates", [])]
                configs = {
                    template_id: StrategyTemplateConfigResponse.model_validate(config)
                    for template_id, config in (payload.get("configs", {}) or {}).items()
                }
                if templates:
                    return templates, configs
            except Exception:
                pass

        now = _now_readable()
        template = StrategyTemplateRow(
            id="TPL-001",
            name="双低稳健A",
            version="v1.0.0",
            status="active",
            factor_count=5,
            rebalance="weekly",
            risk_preset="balanced",
            combo_size=0,
            owner="system",
            updated_at=now,
        )
        config = self._default_config(template_id=template.id, updated_at=now)
        template = template.model_copy(
            update={"factor_count": len(config.factor_keys), "combo_size": config.combo_size}
        )
        self._templates_file.write_text(
            json.dumps(
                {
                    "templates": [template.model_dump()],
                    "configs": {template.id: config.model_dump()},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return [template], {template.id: config}

    def _save_templates_and_configs(self) -> None:
        payload = {
            "templates": [row.model_dump() for row in self._templates],
            "configs": {key: value.model_dump() for key, value in self._template_configs.items()},
        }
        self._templates_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _derive_template_seq(templates: list[StrategyTemplateRow]) -> int:
        max_seq = 0
        for item in templates:
            if not item.id.startswith("TPL-"):
                continue
            try:
                max_seq = max(max_seq, int(item.id.split("-", 1)[1]))
            except Exception:
                continue
        return max_seq
