"""CB Quant 核心业务服务。

这个模块是整个可转债量化 Web 端的“编排层”：

1. 管理策略模板与参数空间
2. 生成候选组合
3. 创建/执行参数优化任务
4. 创建/执行单次回测作业
5. 汇总排行榜、对比面板和分析详情

大部分复杂度都不在某个单一算法，而在于“状态如何流转”：
模板 -> 候选 -> 优化任务/回测任务 -> 排行 -> 分析详情。
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date, datetime
from itertools import combinations, islice, product
import json
from math import ceil, comb, sqrt
import os
from pathlib import Path
import re
from threading import Event, Lock, Thread, current_thread
from typing import Any, Iterable, TypeVar

import requests

from vnpy.web.adapters import CrawlerPhaseABacktestAdapter
from vnpy.web.domain.cb_quant import cb_strategy_core
from vnpy.web.domain.cb_quant.quant_store import CbQuantStore
from vnpy.web.services.cb_market_service import CbMarketService
from vnpy.web.schemas import (
    BacktestTaskConfig,
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
    StrategyOptimizeTaskAiCompareResponse,
    StrategyOptimizeTaskAnalysisResponse,
    StrategyOptimizeTaskAiInsightResponse,
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
    """通用分页切片。"""
    safe_page = max(1, page)
    safe_size = max(1, page_size)
    start = (safe_page - 1) * safe_size
    return items[start : start + safe_size]


def _now_hms() -> str:
    """返回 HH:MM:SS，主要给任务运行态展示。"""
    return datetime.now().strftime("%H:%M:%S")


def _now_yyyymmdd() -> str:
    """返回 YYYYMMDD，主要用于生成任务编号。"""
    return datetime.now().strftime("%Y%m%d")


def _now_readable() -> str:
    """返回前端直接展示的时间文本。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _now_compact() -> str:
    """返回紧凑时间戳，用于 run_id 等非展示字段。"""
    return datetime.now().strftime("%Y%m%d%H%M")


class CbQuantService:
    _LEGACY_FACTOR_KEY_ALIASES: dict[str, str] = {
        "stock_stdevry_bemchmark": "volatility_benchmark",
    }

    """CB Quant 主服务。

    可以把它理解成一个“内存态 + SQLite 持久化”的任务编排器：
    - 内存里维护当前模板、候选、任务、排行榜
    - SQLite 负责在重启后恢复状态
    - 线程池负责执行回测和参数优化
    """

    def __init__(self) -> None:
        """初始化全部运行态缓存，并从本地存储恢复历史状态。"""
        self._lock: Lock = Lock()
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cbq-bt")
        self._adapter: CrawlerPhaseABacktestAdapter = CrawlerPhaseABacktestAdapter()
        self._market_service: CbMarketService = CbMarketService()
        self._seq: int = 0
        self._template_seq: int = 0
        self._opt_task_seq: int = 0
        self._candidate_settings: dict[str, dict[str, Any]] = {}
        self._job_context: dict[str, dict[str, Any]] = {}
        self._leaderboard_business_dates: dict[tuple[str, str, str], str] = {}
        self._storage_dir: Path = self._adapter.data_dir / "_cb_quant"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._store: CbQuantStore = CbQuantStore(self._storage_dir / "cb_quant.db")
        self._templates_file: Path = self._storage_dir / "templates.json"

        self._templates, self._template_configs = self._load_templates_and_configs()
        self._templates = self._sync_template_metrics(self._templates, self._template_configs)
        self._template_seq = self._derive_template_seq(self._templates)

        self._candidates: list[CandidateRow] = []
        self._rebuild_candidate_settings()

        self._jobs, self._job_context = self._load_jobs_and_context()
        self._seq = self._derive_job_seq(self._jobs)
        self._leaderboard, self._leaderboard_business_dates = self._load_leaderboard_rows()
        self._mark_unfinished_jobs_as_failed_after_restart()
        self._compare: list[BacktestCompareRow] = []
        self._refresh_compare_rows()

        self._optimize_tasks, self._optimize_results, self._optimize_top_bonds = self._load_optimize_state()
        self._opt_task_seq = self._derive_opt_task_seq(self._optimize_tasks)
        self._mark_unfinished_optimize_tasks_as_failed_after_restart()
        self._optimize_analysis_cache: dict[tuple[str, str, float, str], StrategyOptimizeTaskAnalysisResponse] = {}
        self._optimize_ai_cache: dict[tuple[str, str, float, str], StrategyOptimizeTaskAiInsightResponse] = {}
        self._optimize_ai_compare_cache: dict[tuple[str, tuple[str, str], float, str], StrategyOptimizeTaskAiCompareResponse] = {}

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
        """读取回测快照库摘要，供前端判断是否具备回测条件。"""
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
        """创建参数优化任务并提交到线程池。

        这个方法本身只负责“准备任务”，不负责真正执行优化计算。

        它做的事情主要有四步：
        1. 根据 template_id 找到模板和参数空间配置
        2. 计算这次任务理论上需要评估多少个参数组合
        3. 生成一条 queued 状态的任务记录并持久化
        4. 把真正的执行入口 `_run_optimize_task(...)` 提交给线程池

        真正的计算链路在这里：
        - `create_optimize_task(...)`
        - `_run_optimize_task(...)`
        - `_iter_combo_results_parallel(...)`
        - `_evaluate_combo(...)`
        - `_run_backtest_from_candidate_map(...)`

        这条链路里几个最容易问到的问题是：
        - 历史数据在哪查：
          `_run_optimize_task` 里通过 `self._adapter.load_market_data()` 读取，
          adapter 优先从 `CbHistoryStore.load_market_dataset()` 的本地快照库读取，
          读不到时返回空数据集，由上层决定是否提示同步
        - 配置在哪读：
          这里的 `config = self._template_configs.get(template.id)` 读取模板配置，
          里面包含 factor_keys 和 parameter_space，决定参数组合总数；
          任务级临时配置来自 `request.task_config`
        - 历史数据在哪加工成结果：
          `_prepare_window_dataset_map(...)` 先按窗口切历史切片，
          `_evaluate_combo(...)` 对单个组合构造候选池并按窗口回测，
          `_run_backtest_from_candidate_map(...)` 把日级快照回放成收益、回撤、胜率等结果

        所以“创建成功”只表示任务已入队，不代表优化已经开始执行或执行成功。
        """
        template = self._find_template(request.template_id)
        if not template:
            return None

        # 模板配置来自内存态/持久化恢复的 `_template_configs`。
        # 这里决定了这次优化能枚举出哪些参数组合，是“参数空间”的源头。
        config = self._template_configs.get(template.id) or self._default_config(
            template_id=template.id,
            updated_at=template.updated_at,
        )

        # windows 只是回测窗口定义，不在这里切数据；真正切片在 `_run_optimize_task`
        # -> `_prepare_window_dataset_map` -> `adapter._slice_dataset(...)`。
        windows = self._normalize_windows(request.windows)
        if not windows:
            windows = ["full", "3y", "1y"]

        # 根据模板里的 factor_keys / parameter_space 计算组合总数。
        # 这一步还没有真正跑回测，只是在估算参数空间大小，用来创建任务和控制上限。
        combo_size = max(
            1,
            self._calculate_combo_size(
                factor_keys=config.factor_keys,
                parameter_space=config.parameter_space,
            ),
        )
        capped_total = combo_size if request.max_combinations is None else min(combo_size, request.max_combinations)

        # task_config 是“本次任务附加到策略 setting 上的运行时配置”，
        # 比如仓位、调仓、止盈止损之类；真正生效在 `_evaluate_combo` 里通过
        # `_apply_task_config_to_setting(...)` 写回 setting。
        task_config = self._normalize_task_config(request.task_config)

        with self._lock:
            # 先持久化一份 queued 状态，确保进程中途退出后仍能恢复任务记录。
            # 到这里仍然没有开始计算，只是把“待执行任务”注册到内存和 SQLite。
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
                task_config=task_config,
            )
            self._optimize_tasks = [task, *self._optimize_tasks]
            self._optimize_results[task_id] = []
            self._optimize_top_bonds[task_id] = []
        self._store.upsert_optimize_task(row=task.model_dump())
        self._sync_optimize_task_as_backtest_job(task)

        submit_error: str | None = None
        try:
            # 真正的优化计算从这里开始异步提交。
            # 当前请求返回后，后台线程才会进入 `_run_optimize_task(...)`：
            # 1. `self._adapter.load_market_data()` 读取历史快照
            # 2. `_prepare_window_dataset_map(...)` 按 full/3y/1y/1w 等窗口切片
            # 3. `_iter_combo_results_parallel(...)` 并行遍历参数组合
            # 4. `_evaluate_combo(...)` 评估单个组合
            # 5. `_run_backtest_from_candidate_map(...)` 产出收益/回撤/胜率等指标
            self._executor.submit(
                self._run_optimize_task,
                task_id,
                request.top_n,
                request.current_top_n,
                request.start_date,
                request.end_date,
                task_config,
            )
        except Exception as exc:
            submit_error = str(exc)[:120]
            # 只有线程池提交失败，才会在这里直接把任务标成 failed。
            # 如果是后续执行时失败，会在 `_run_optimize_task` 里更新状态。
            self._update_optimize_task(
                task_id,
                status="failed",
                progress=0,
                eta="submit-failed",
                finished_at=_now_readable(),
                message=f"任务提交失败: {submit_error}",
            )

        response_task = self._get_optimize_task(task_id) or task
        response_message = (
            f"已创建优化任务 {task_id}，但提交执行失败：{submit_error}"
            if submit_error
            else f"已创建优化任务 {task_id}，待评估参数组合数={capped_total}"
        )
        return StrategyOptimizeTaskCreateResponse(
            task=response_task,
            message=response_message,
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
        initial_capital_wan: float | None = None,
    ) -> StrategyOptimizeTaskAnalysisResponse | None:
        """返回单个优化任务下某个组合的详细分析结果。

        这条链路不会直接复用“优化阶段的粗粒度指标”，而是重新做一次详细模拟，
        以产出净值曲线、轮动记录、年度/月度/周度收益分布等可视化数据。
        """
        task = self._get_optimize_task(task_id)
        if not task:
            return None
        if initial_capital_wan is None:
            initial_capital_wan = self._normalize_task_config(task.task_config).initial_capital_wan
        task_config = self._normalize_task_config(task.task_config)
        benchmark_name = "转债等权"
        if task_config.benchmark_name and task_config.benchmark_name != "转债等权":
            benchmark_name = f"{task_config.benchmark_name}（暂按转债等权测算）"

        # 这里故意要求“任务必须 finished”才返回正式分析，
        # 避免前端把中间结果误当成最终结论。
        # Keep analysis semantics strict: only finished task has official analysis output.
        if task.status != "finished":
            return StrategyOptimizeTaskAnalysisResponse(
                task_id=task.task_id,
                template_id=task.template_id,
                template_name=task.template_name,
                combo_id=combo_id or "--",
                benchmark_name=benchmark_name,
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
        setting = self._apply_task_config_to_setting(setting, task_config)

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
                benchmark_name=benchmark_name,
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

        strategy = self._simulate_detailed_strategy(
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
        if task_config.benchmark_name and task_config.benchmark_name != "转债等权":
            message_parts.append(f"已记录任务基准“{task_config.benchmark_name}”，当前分析暂按转债等权进行对比。")
        response = StrategyOptimizeTaskAnalysisResponse(
            task_id=task.task_id,
            template_id=task.template_id,
            template_name=task.template_name,
            combo_id=selected_combo_id,
            benchmark_name=benchmark_name,
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

    def get_optimize_task_ai_insight(
        self,
        *,
        task_id: str,
        combo_id: str | None = None,
        initial_capital_wan: float | None = None,
    ) -> StrategyOptimizeTaskAiInsightResponse | None:
        """调用 Kimi 对单个组合的回测结果做白盒解读。

        白盒的含义不是“只返回一段结论”，而是把：
        1. 喂给模型的事实上下文
        2. 给模型的提示词
        3. 模型最终输出
        一并返回给前端，方便使用者核对大模型到底看到了什么。
        """
        task = self._get_optimize_task(task_id)
        if not task:
            return None
        if initial_capital_wan is None:
            initial_capital_wan = self._normalize_task_config(task.task_config).initial_capital_wan

        detail = self.get_optimize_task_detail(task_id)
        ranked_rows = detail.top_strategies if detail else []
        selected_row = self._resolve_selected_optimize_row(ranked_rows, combo_id)

        analysis = self.get_optimize_task_analysis(
            task_id=task_id,
            combo_id=combo_id or (selected_row.combo_id if selected_row else None),
            initial_capital_wan=initial_capital_wan,
        )
        if not analysis:
            return None

        selected_combo_id = analysis.combo_id
        if selected_row is None and selected_combo_id:
            selected_row = self._resolve_selected_optimize_row(ranked_rows, selected_combo_id)

        model = self._llm_model()
        context_markdown = self._build_optimize_ai_context_markdown(
            task=task,
            selected_row=selected_row,
            analysis=analysis,
            initial_capital_wan=float(initial_capital_wan),
            top_bonds=(detail.top_bonds if detail else [])[:10],
        )
        prompt_markdown = self._build_optimize_ai_prompt(context_markdown)
        api_key = self._llm_api_key()
        cache_key = (task_id, selected_combo_id, round(float(initial_capital_wan), 4), model)
        cached = self._optimize_ai_cache.get(cache_key)
        if cached:
            return cached.model_copy(update={"cached": True})

        if not api_key:
            return StrategyOptimizeTaskAiInsightResponse(
                ok=False,
                enabled=False,
                provider="kimi",
                model=model,
                task_id=task_id,
                combo_id=selected_combo_id,
                context_markdown=context_markdown,
                prompt_markdown=prompt_markdown,
                analysis_markdown="",
                executive_summary="",
                return_drivers=[],
                risk_exposures=[],
                parameter_interpretation=[],
                next_steps=[],
                message="未配置 MOONSHOT_API_KEY，当前仅返回白盒上下文和提示词预览。",
                generated_at=_now_readable(),
            )

        try:
            analysis_markdown = self._call_kimi(prompt_markdown)
            parsed = self._parse_ai_json_payload(
                analysis_markdown,
                default={
                    "executive_summary": "",
                    "return_drivers": [],
                    "risk_exposures": [],
                    "parameter_interpretation": [],
                    "next_steps": [],
                },
            )
        except Exception as exc:
            return StrategyOptimizeTaskAiInsightResponse(
                ok=False,
                enabled=True,
                provider="kimi",
                model=model,
                task_id=task_id,
                combo_id=selected_combo_id,
                context_markdown=context_markdown,
                prompt_markdown=prompt_markdown,
                analysis_markdown="",
                executive_summary="",
                return_drivers=[],
                risk_exposures=[],
                parameter_interpretation=[],
                next_steps=[],
                message=f"Kimi 调用失败：{exc}",
                generated_at=_now_readable(),
            )

        response = StrategyOptimizeTaskAiInsightResponse(
            ok=True,
            enabled=True,
            provider="kimi",
            model=model,
            task_id=task_id,
            combo_id=selected_combo_id,
            context_markdown=context_markdown,
            prompt_markdown=prompt_markdown,
            analysis_markdown=analysis_markdown,
            executive_summary=str(parsed.get("executive_summary", "")).strip(),
            return_drivers=self._normalize_text_list(parsed.get("return_drivers")),
            risk_exposures=self._normalize_text_list(parsed.get("risk_exposures")),
            parameter_interpretation=self._normalize_text_list(parsed.get("parameter_interpretation")),
            next_steps=self._normalize_text_list(parsed.get("next_steps")),
            message="Kimi 白盒解读已生成。",
            generated_at=_now_readable(),
            cached=False,
        )
        self._optimize_ai_cache[cache_key] = response
        if len(self._optimize_ai_cache) > 100:
            self._optimize_ai_cache.clear()
        return response

    def compare_optimize_task_ai_insight(
        self,
        *,
        task_id: str,
        combo_ids: list[str],
        initial_capital_wan: float | None = None,
    ) -> StrategyOptimizeTaskAiCompareResponse | None:
        task = self._get_optimize_task(task_id)
        if not task:
            return None
        normalized_combo_ids = [str(item).strip() for item in combo_ids if str(item).strip()]
        if len(normalized_combo_ids) != 2:
            raise ValueError("combo_ids must contain exactly two combo ids")
        if initial_capital_wan is None:
            initial_capital_wan = self._normalize_task_config(task.task_config).initial_capital_wan

        detail = self.get_optimize_task_detail(task_id)
        ranked_rows = detail.top_strategies if detail else []
        row_a = self._resolve_selected_optimize_row(ranked_rows, normalized_combo_ids[0])
        row_b = self._resolve_selected_optimize_row(ranked_rows, normalized_combo_ids[1])
        if row_a is None or row_b is None:
            raise ValueError("selected combos are not available in current task leaderboard")

        analysis_a = self.get_optimize_task_analysis(
            task_id=task_id,
            combo_id=row_a.combo_id,
            initial_capital_wan=initial_capital_wan,
        )
        analysis_b = self.get_optimize_task_analysis(
            task_id=task_id,
            combo_id=row_b.combo_id,
            initial_capital_wan=initial_capital_wan,
        )
        if not analysis_a or not analysis_b:
            raise ValueError("unable to build analysis for selected combos")

        model = self._llm_model()
        combo_pair = tuple(sorted([row_a.combo_id, row_b.combo_id]))
        context_markdown = self._build_optimize_ai_compare_context_markdown(
            task=task,
            row_a=row_a,
            row_b=row_b,
            analysis_a=analysis_a,
            analysis_b=analysis_b,
            initial_capital_wan=float(initial_capital_wan),
        )
        prompt_markdown = self._build_optimize_ai_compare_prompt(context_markdown, row_a.combo_id, row_b.combo_id)
        cache_key = (task_id, combo_pair, round(float(initial_capital_wan), 4), model)
        cached = self._optimize_ai_compare_cache.get(cache_key)
        if cached:
            return cached.model_copy(update={"cached": True})

        if not self._llm_api_key():
            return StrategyOptimizeTaskAiCompareResponse(
                ok=False,
                enabled=False,
                provider="kimi",
                model=model,
                task_id=task_id,
                combo_ids=[row_a.combo_id, row_b.combo_id],
                context_markdown=context_markdown,
                prompt_markdown=prompt_markdown,
                analysis_markdown="",
                executive_summary="",
                winner_combo_id="",
                winner_reason=[],
                combo_a_strengths=[],
                combo_a_risks=[],
                combo_b_strengths=[],
                combo_b_risks=[],
                what_to_verify_next=[],
                message="未配置 MOONSHOT_API_KEY，当前仅返回对比上下文和提示词预览。",
                generated_at=_now_readable(),
            )

        try:
            analysis_markdown = self._call_kimi(prompt_markdown)
            parsed = self._parse_ai_json_payload(
                analysis_markdown,
                default={
                    "executive_summary": "",
                    "winner_combo_id": "",
                    "winner_reason": [],
                    "combo_a_strengths": [],
                    "combo_a_risks": [],
                    "combo_b_strengths": [],
                    "combo_b_risks": [],
                    "what_to_verify_next": [],
                },
            )
        except Exception as exc:
            return StrategyOptimizeTaskAiCompareResponse(
                ok=False,
                enabled=True,
                provider="kimi",
                model=model,
                task_id=task_id,
                combo_ids=[row_a.combo_id, row_b.combo_id],
                context_markdown=context_markdown,
                prompt_markdown=prompt_markdown,
                analysis_markdown="",
                executive_summary="",
                winner_combo_id="",
                winner_reason=[],
                combo_a_strengths=[],
                combo_a_risks=[],
                combo_b_strengths=[],
                combo_b_risks=[],
                what_to_verify_next=[],
                message=f"Kimi 对比调用失败：{exc}",
                generated_at=_now_readable(),
            )

        response = StrategyOptimizeTaskAiCompareResponse(
            ok=True,
            enabled=True,
            provider="kimi",
            model=model,
            task_id=task_id,
            combo_ids=[row_a.combo_id, row_b.combo_id],
            context_markdown=context_markdown,
            prompt_markdown=prompt_markdown,
            analysis_markdown=analysis_markdown,
            executive_summary=str(parsed.get("executive_summary", "")).strip(),
            winner_combo_id=str(parsed.get("winner_combo_id", "")).strip(),
            winner_reason=self._normalize_text_list(parsed.get("winner_reason")),
            combo_a_strengths=self._normalize_text_list(parsed.get("combo_a_strengths")),
            combo_a_risks=self._normalize_text_list(parsed.get("combo_a_risks")),
            combo_b_strengths=self._normalize_text_list(parsed.get("combo_b_strengths")),
            combo_b_risks=self._normalize_text_list(parsed.get("combo_b_risks")),
            what_to_verify_next=self._normalize_text_list(parsed.get("what_to_verify_next")),
            message="Kimi 横向优劣分析已生成。",
            generated_at=_now_readable(),
            cached=False,
        )
        self._optimize_ai_compare_cache[cache_key] = response
        if len(self._optimize_ai_compare_cache) > 50:
            self._optimize_ai_compare_cache.clear()
        return response

    @staticmethod
    def _resolve_selected_optimize_row(
        ranked_rows: list[StrategyOptimizeResultRow],
        combo_id: str | None,
    ) -> StrategyOptimizeResultRow | None:
        if combo_id:
            row = next((item for item in ranked_rows if item.combo_id == combo_id), None)
            if row:
                return row
        return ranked_rows[0] if ranked_rows else None

    def _build_optimize_ai_context_markdown(
        self,
        *,
        task: StrategyOptimizeTaskRow,
        selected_row: StrategyOptimizeResultRow | None,
        analysis: StrategyOptimizeTaskAnalysisResponse,
        initial_capital_wan: float,
        top_bonds: list[StrategyTopBondRow],
    ) -> str:
        metric = analysis.metric_rows[0] if analysis.metric_rows else None
        latest_curve = analysis.curve[-1] if analysis.curve else None
        yearly = self._format_distribution_rows(analysis.yearly_distribution, limit=6)
        monthly = self._format_distribution_rows(analysis.monthly_distribution, limit=8)
        rotations = analysis.rotations[-8:]
        top_bond_lines = [
            f"- #{row.rank} {row.bond_id} {row.bond_name}，现价 {row.price:.2f}，溢价率 {row.premium_rt:.2f}%，双低 {row.dblow:.2f}，评分 {row.score:.2f}"
            for row in top_bonds
        ]
        rotation_lines = [
            f"- {row.rebalance_date} 持仓 {row.holdings}，换手 {row.turnover_pct:.2f}%，阶段收益 {row.period_return_pct:.2f}%，累计 {row.cumulative_return_pct:.2f}%"
            for row in rotations
        ]
        params_text = json.dumps(selected_row.params if selected_row else {}, ensure_ascii=False, indent=2, sort_keys=True)
        summary_lines = [
            f"- 任务ID：{task.task_id}",
            f"- 模板：{task.template_name}（{task.template_id}）",
            f"- 组合ID：{analysis.combo_id}",
            f"- 回测窗口：{analysis.window}",
            f"- 基准：{analysis.benchmark_name}",
            f"- 初始资金：{initial_capital_wan:.2f} 万",
            f"- 任务状态：{task.status}",
            f"- 任务消息：{task.message or '--'}",
        ]
        metric_lines = [
            f"- 总收益率：{metric.total_return_pct:.2f}%" if metric and metric.total_return_pct is not None else "- 总收益率：--",
            f"- 年化收益率：{metric.annual_return_pct:.2f}%" if metric and metric.annual_return_pct is not None else "- 年化收益率：--",
            f"- 最大回撤：{metric.max_drawdown_pct:.2f}%" if metric and metric.max_drawdown_pct is not None else "- 最大回撤：--",
            f"- Sharpe：{metric.sharpe:.3f}" if metric and metric.sharpe is not None else "- Sharpe：--",
            f"- Sortino：{metric.sortino:.3f}" if metric and metric.sortino is not None else "- Sortino：--",
            f"- Calmar：{metric.calmar:.3f}" if metric and metric.calmar is not None else "- Calmar：--",
            f"- 胜率：{metric.win_rate_pct:.2f}%" if metric and metric.win_rate_pct is not None else "- 胜率：--",
            f"- 日均换手：{metric.avg_turnover_pct:.2f}%" if metric and metric.avg_turnover_pct is not None else "- 日均换手：--",
            f"- 最大回撤持续天数：{metric.max_drawdown_duration_days:.0f}" if metric and metric.max_drawdown_duration_days is not None else "- 最大回撤持续天数：--",
        ]
        curve_lines = [
            f"- 最新策略累计收益：{latest_curve.strategy_cum_return_pct:.2f}%" if latest_curve else "- 最新策略累计收益：--",
            f"- 最新基准累计收益：{latest_curve.benchmark_cum_return_pct:.2f}%" if latest_curve else "- 最新基准累计收益：--",
            f"- 最新相对超额：{latest_curve.relative_excess_pct:.2f}%" if latest_curve else "- 最新相对超额：--",
            f"- 最新回撤：{latest_curve.drawdown_pct:.2f}%" if latest_curve else "- 最新回撤：--",
        ]
        return "\n".join(
            [
                "## 任务概况",
                *summary_lines,
                "",
                "## 参数",
                "```json",
                params_text,
                "```",
                "",
                "## 核心指标",
                *metric_lines,
                "",
                "## 曲线摘要",
                *curve_lines,
                "",
                "## 年度收益分布",
                *(yearly or ["- --"]),
                "",
                "## 月度收益分布（最近）",
                *(monthly or ["- --"]),
                "",
                "## 最近调仓记录",
                *(rotation_lines or ["- --"]),
                "",
                "## 当前市场 Top 债",
                *(top_bond_lines or ["- --"]),
                "",
                "## 后端提示",
                f"- {analysis.message or '无'}",
            ]
        )

    @staticmethod
    def _build_optimize_ai_prompt(context_markdown: str) -> str:
        return "\n".join(
            [
                "你是可转债量化研究助手。",
                "",
                "请严格只基于下面给出的回测事实做分析，不要编造未提供的数据。",
                "请只输出一个 JSON 对象，不要输出 markdown 代码块，不要输出额外解释。",
                "JSON schema:",
                '{"executive_summary":"一句话总结","return_drivers":["..."],"risk_exposures":["..."],"parameter_interpretation":["..."],"next_steps":["..."]}',
                "要求：",
                "1. 每个数组 2-4 条。",
                "2. 尽量引用具体指标数值。",
                "3. 如果证据不足，就明确写“证据不足”。",
                "",
                "以下是白盒上下文：",
                "",
                context_markdown,
            ]
        )

    def _build_optimize_ai_compare_context_markdown(
        self,
        *,
        task: StrategyOptimizeTaskRow,
        row_a: StrategyOptimizeResultRow,
        row_b: StrategyOptimizeResultRow,
        analysis_a: StrategyOptimizeTaskAnalysisResponse,
        analysis_b: StrategyOptimizeTaskAnalysisResponse,
        initial_capital_wan: float,
    ) -> str:
        return "\n\n".join(
            [
                f"## 任务\n- 任务ID：{task.task_id}\n- 模板：{task.template_name}（{task.template_id}）\n- 初始资金：{initial_capital_wan:.2f} 万\n- 窗口：{analysis_a.window}",
                f"## 组合A：{row_a.combo_id}\n{self._build_optimize_ai_context_markdown(task=task, selected_row=row_a, analysis=analysis_a, initial_capital_wan=initial_capital_wan, top_bonds=[])}",
                f"## 组合B：{row_b.combo_id}\n{self._build_optimize_ai_context_markdown(task=task, selected_row=row_b, analysis=analysis_b, initial_capital_wan=initial_capital_wan, top_bonds=[])}",
            ]
        )

    @staticmethod
    def _build_optimize_ai_compare_prompt(context_markdown: str, combo_a: str, combo_b: str) -> str:
        return "\n".join(
            [
                "你是可转债量化研究助手。",
                "",
                "请严格只基于下面给出的两组回测事实做横向优劣分析，不要编造未提供的数据。",
                "请只输出一个 JSON 对象，不要输出 markdown 代码块，不要输出额外解释。",
                "JSON schema:",
                '{"executive_summary":"一句话总结","winner_combo_id":"更优组合ID","winner_reason":["..."],"combo_a_strengths":["..."],"combo_a_risks":["..."],"combo_b_strengths":["..."],"combo_b_risks":["..."],"what_to_verify_next":["..."]}',
                f"winner_combo_id 只能填写 {combo_a} 或 {combo_b}。",
                "每个数组 2-4 条，尽量引用具体指标数值。",
                "",
                "以下是白盒上下文：",
                "",
                context_markdown,
            ]
        )

    @staticmethod
    def _format_distribution_rows(
        rows: list[StrategyBacktestDistributionRow],
        *,
        limit: int,
    ) -> list[str]:
        if not rows:
            return []
        picked = rows[-limit:]
        return [
            f"- {row.period}：策略 {row.strategy_return_pct:.2f}%，基准 {row.benchmark_return_pct:.2f}%，超额 {row.excess_return_pct:.2f}%"
            for row in picked
        ]

    @staticmethod
    def _normalize_text_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @staticmethod
    def _parse_ai_json_payload(raw_text: str, *, default: dict[str, Any]) -> dict[str, Any]:
        text = str(raw_text or "").strip()
        if not text:
            return dict(default)
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return {**default, **data}
        except Exception:
            pass
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    return {**default, **data}
            except Exception:
                pass
        return dict(default)

    def _call_kimi(self, prompt_markdown: str) -> str:
        api_key = self._llm_api_key()
        if not api_key:
            raise RuntimeError("missing MOONSHOT_API_KEY")
        base_url = self._llm_base_url()
        payload = {
            "model": self._llm_model(),
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一名谨慎、可审计的可转债量化研究员，只能依据提供的事实分析。",
                },
                {
                    "role": "user",
                    "content": prompt_markdown,
                },
            ],
        }
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=(10, 120),
        )
        response.raise_for_status()
        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError("empty choices from Kimi")
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    chunks.append(str(item.get("text", "")))
            text = "\n".join([chunk for chunk in chunks if chunk.strip()]).strip()
            if text:
                return text
        raise RuntimeError("empty content from Kimi")

    @staticmethod
    def _load_local_env_map() -> dict[str, str]:
        project_root = Path(__file__).resolve().parents[3]
        env_file = project_root / ".env.tushare.local"
        if not env_file.exists():
            return {}
        result: dict[str, str] = {}
        pattern = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$")
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = pattern.match(line)
            if not match:
                continue
            key = match.group(1)
            value = match.group(2).strip()
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            result[key] = value
        return result

    @classmethod
    def _env_or_local(cls, name: str, default: str = "") -> str:
        value = os.getenv(name, "").strip()
        if value:
            return value
        return cls._load_local_env_map().get(name, default).strip()

    @classmethod
    def _llm_api_key(cls) -> str:
        return cls._env_or_local("MOONSHOT_API_KEY")

    @classmethod
    def _llm_base_url(cls) -> str:
        return cls._env_or_local("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1").rstrip("/")

    @classmethod
    def _llm_model(cls) -> str:
        return cls._env_or_local("MOONSHOT_MODEL", "kimi-latest")

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
        best_row = ranked_top[0] if ranked_top else None
        best_params = best_row.params if best_row else {}
        best_task_id = str(best_row.task_id or "") if best_row else ""

        persisted_top = self._optimize_top_bonds.get(best_task_id, []) if best_task_id else []
        if persisted_top:
            top_bonds = [
                row.model_copy(update={"rank": idx + 1})
                for idx, row in enumerate(persisted_top[:safe_current_top_n])
            ]
            market_warning = "；Top20沿用任务完成时快照"
        elif best_params:
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
        task_config: BacktestTaskConfig,
    ) -> None:
        """优化任务工作线程入口。

        这是 `create_optimize_task(...)` 提交到线程池后的真正执行入口。

        它负责把“一个待执行优化任务”完整跑完，主流程如下：

        1. 读取任务记录与模板，校验任务仍然存在
        2. 加载 phase_a 策略模块与历史快照数据集
        3. 按用户选择的回测窗口切好历史数据
        4. 决定是否启用两阶段筛选
           - 参数空间大：stage1 粗筛 + stage2 复评
           - 参数空间小：直接全量遍历
        5. 对每个参数组合调用 `_evaluate_combo(...)`
        6. 持续刷新任务进度、ETA、阶段性排行榜
        7. 汇总最终最优策略、实时 Top 债，并持久化结果
        8. 失败时写回 failed 状态，供前端和任务列表查询

        这层本身不直接做逐日回测，真正的单组合评估在：
        - `_iter_combo_results_parallel(...)`
        - `_evaluate_combo(...)`
        - `_run_backtest_from_candidate_map(...)`
        """
        # 先从内存/持久化恢复的任务列表里取出任务实体。
        # 如果任务已经不存在（例如进程状态变化后被清理），这里直接退出。
        task = self._get_optimize_task(task_id)
        if not task:
            return

        # 模板是参数空间和展示名称的根来源；模板不存在时，本任务已经无法继续执行。
        template = self._find_template(task.template_id)
        if not template:
            self._update_optimize_task(task_id, status="failed", eta="--", message="template not found")
            return

        # 任务进入 running，说明已经从线程池真正出队开始执行。
        self._update_optimize_task(
            task_id,
            status="running",
            progress=1,
            started_at=task.started_at or _now_readable(),
            eta="initializing",
            message="任务已出队，正在初始化引擎与加载数据",
        )

        # 读取历史快照数据集。adapter 会优先从 cb_snapshots.db 读取标准化日快照；
        # 如果本地快照库没有数据，就返回空数据集，由当前任务统一走“无数据失败”分支。
        dataset = self._adapter.load_market_data()
        total = max(1, task.total_combinations)

        # workers 控制参数组合评估时的并行度；不是数据库连接数，也不是 Web 请求并发数。
        workers = self._optimize_worker_count()

        # 这里把一整份历史数据预先切成多个窗口数据集，避免每个组合再重复切片。
        # 例如 full / 3y / 1y / 1w 都会得到一份独立的 dataset。
        window_dataset_map = self._prepare_window_dataset_map(
            dataset=dataset,
            windows=task.windows,
            start_date=start_date,
            end_date=end_date,
        )

        # 如果所有窗口都切不出数据，说明历史快照覆盖范围不足，任务直接失败。
        if not any(bool(window_dataset_map.get(window_name)) for window_name in task.windows):
            self._update_optimize_task(
                task_id,
                status="failed",
                eta="--",
                finished_at=_now_readable(),
                message="No market snapshots available for selected window",
            )
            return

        # 到这里说明：cb_strategy_core 已直接引用、历史快照已读取、窗口切片已准备完毕。
        self._update_optimize_task(
            task_id,
            status="running",
            progress=3,
            eta="loading",
            message=f"正在加载历史快照并初始化参数空间（workers={workers}）",
        )

        ranking_rows: list[StrategyOptimizeResultRow] = []
        evaluated_primary = 0
        evaluated_secondary = 0
        skipped_no_trade = 0
        start_at = datetime.now()

        try:
            # 这里决定是否启用“两阶段评估”：
            # - 开：先拿短窗口做低成本粗筛，再对 shortlist 做全窗口复评
            # - 关：直接全量遍历所有组合
            # 这个判断只和参数空间大小、窗口数量有关，不和数据库有关。
            screening_enabled = self._should_enable_stage1_screening(total=total, windows=task.windows)
            stage1_window = self._pick_stage1_window(task.windows)
            stage1_windows: list[WindowName] = [stage1_window]
            stage1_sample_limit = self._stage1_sample_limit(total=total, top_n=top_n) if screening_enabled else total
            stage2_shortlist_limit = self._stage2_shortlist_limit(
                total=total,
                top_n=top_n,
                current_top_n=current_top_n,
            )

            if screening_enabled:
                # stage1_best_rows 只保存粗筛阶段表现最好的 shortlist，不保存全部组合。
                stage1_best_rows: list[StrategyOptimizeResultRow] = []
                stage1_combo_iter = self._iter_sampled_template_settings(
                    template_id=task.template_id,
                    total=total,
                    sample_limit=stage1_sample_limit,
                )
                stage1_map = {stage1_window: window_dataset_map.get(stage1_window, [])}
                # 阶段1只在一个较短窗口上跑抽样组合，目标是尽快得到“值得复评”的 shortlist。
                # 这里保留 stage2_shortlist_limit 条最佳结果，避免把明显较差的组合带入完整回测。
                for row in self._iter_combo_results_parallel(
                    task_id=task_id,
                    template_id=task.template_id,
                    template_name=task.template_name,
                    dataset=dataset,
                    combo_iter=stage1_combo_iter,
                    windows=stage1_windows,
                    start_date=start_date,
                    end_date=end_date,
                    window_dataset_map=stage1_map,
                    workers=workers,
                    task_config=task_config,
                ):
                    # evaluated_primary 记录“主筛阶段”已经评估了多少个组合。
                    evaluated_primary += 1

                    # 零收益且零换手的组合，通常意味着根本没有触发有效交易。
                    # 这类组合会计入统计，但不放进候选排行榜。
                    if abs(row.total_return_pct) < 1e-9 and row.turnover <= 1e-9:
                        skipped_no_trade += 1
                    else:
                        stage1_best_rows.append(row)
                        stage1_best_rows.sort(
                            key=lambda item: (item.robust_score, item.cagr, -item.mdd),
                            reverse=True,
                        )
                        stage1_best_rows = stage1_best_rows[:stage2_shortlist_limit]

                    # 不是每评估一个组合都刷新前端状态，否则锁竞争和持久化开销会偏大。
                    # 这里只在关键节点或固定步长更新一次任务进度和临时排行榜。
                    should_emit = (
                        evaluated_primary == 1
                        or evaluated_primary == stage1_sample_limit
                        or evaluated_primary % max(1, stage1_sample_limit // 100) == 0
                        or evaluated_primary % 200 == 0
                    )
                    if not should_emit:
                        continue
                    elapsed_seconds = max(1.0, (datetime.now() - start_at).total_seconds())
                    remain = max(0, stage1_sample_limit - evaluated_primary)
                    per_cost = elapsed_seconds / max(1, evaluated_primary)
                    eta_minutes = int((remain * per_cost) / 60)

                    # 优化过程中，前端列表看到的是“阶段性 top_n”，不是最终结果。
                    self._optimize_results[task_id] = self._rank_optimize_rows(stage1_best_rows[:top_n])
                    self._update_optimize_task(
                        task_id,
                        evaluated_combinations=min(total, evaluated_primary),
                        progress=max(1, min(70, ceil(evaluated_primary / max(1, stage1_sample_limit) * 70))),
                        eta=f"{eta_minutes}m" if remain else "stage1-done",
                        message=(
                            f"阶段1({stage1_window})筛选 {evaluated_primary}/{stage1_sample_limit}，"
                            f"入围 {min(len(stage1_best_rows), stage2_shortlist_limit)}"
                        ),
                    )

                # 阶段2对 shortlist 做全窗口复评。
                # 到这一步才会使用用户真正选择的 window 集合，因此这里的结果才接近最终排行榜。
                shortlist = sorted(
                    stage1_best_rows,
                    key=lambda item: (item.robust_score, item.cagr, -item.mdd),
                    reverse=True,
                )[:stage2_shortlist_limit]
                stage2_total = len(shortlist)
                if stage2_total == 0:
                    # 粗筛完全没有留下可复评组合时，最终结果必然为空。
                    ranking_rows = []
                else:
                    # 阶段2直接复用 stage1 已经挑出来的参数 settings，
                    # 不再重新遍历整个模板参数空间。
                    stage2_combo_iter = (
                        (row.combo_id, dict(row.params))
                        for row in shortlist
                    )
                    for row in self._iter_combo_results_parallel(
                        task_id=task_id,
                        template_id=task.template_id,
                        template_name=task.template_name,
                        dataset=dataset,
                        combo_iter=stage2_combo_iter,
                        windows=task.windows,
                        start_date=start_date,
                        end_date=end_date,
                        window_dataset_map=window_dataset_map,
                        workers=workers,
                        task_config=task_config,
                    ):
                        # evaluated_secondary 只统计复评阶段数量。
                        evaluated_secondary += 1
                        if abs(row.total_return_pct) < 1e-9 and row.turnover <= 1e-9:
                            skipped_no_trade += 1
                            continue
                        ranking_rows.append(row)
                        ranking_rows.sort(
                            key=lambda item: (item.robust_score, item.cagr, -item.mdd),
                            reverse=True,
                        )
                        ranking_rows = ranking_rows[:top_n]

                        # 复评阶段的进度区间固定映射到 70%~99%，和 stage1 区分开。
                        should_emit = (
                            evaluated_secondary == 1
                            or evaluated_secondary == stage2_total
                            or evaluated_secondary % max(1, stage2_total // 50) == 0
                            or evaluated_secondary % 100 == 0
                        )
                        if not should_emit:
                            continue
                        elapsed_seconds = max(1.0, (datetime.now() - start_at).total_seconds())
                        remain = max(0, stage2_total - evaluated_secondary)
                        per_cost = elapsed_seconds / max(1, evaluated_primary + evaluated_secondary)
                        eta_minutes = int((remain * per_cost) / 60)
                        self._optimize_results[task_id] = self._rank_optimize_rows(ranking_rows)
                        stage2_progress = 70 + ceil(evaluated_secondary / max(1, stage2_total) * 29)
                        self._update_optimize_task(
                            task_id,
                            evaluated_combinations=min(total, evaluated_primary),
                            progress=max(70, min(99, stage2_progress)),
                            eta=f"{eta_minutes}m" if remain else "done",
                            message=f"阶段2复评 {evaluated_secondary}/{stage2_total}",
                        )
            else:
                # 参数空间不大时直接全量遍历，避免两阶段策略带来的额外复杂度和重复计算。
                # 这里 `combo_iter` 会按模板配置展开全部参数组合。
                # 这一分支的特点是：
                # - 不做 stage1 抽样
                # - 不做 shortlist 复评
                # - 所有组合都直接进入 `_evaluate_combo(...)`
                # 因此逻辑更直观，但当组合数较大时耗时也会线性增长。
                combo_iter = self._iter_template_settings(
                    template_id=task.template_id,
                    limit=task.total_combinations,
                )
                # `_iter_combo_results_parallel(...)` 会逐个取出参数组合并执行评估：
                # - workers=1 时实际是串行
                # - workers>1 时会并行提交多个 `_evaluate_combo(...)`
                # 无论底层是否并行，这里拿到的都是“一个组合评估完成后的结果行”。
                for row in self._iter_combo_results_parallel(
                    task_id=task_id,
                    template_id=task.template_id,
                    template_name=task.template_name,
                    dataset=dataset,
                    combo_iter=combo_iter,
                    windows=task.windows,
                    start_date=start_date,
                    end_date=end_date,
                    window_dataset_map=window_dataset_map,
                    workers=workers,
                    task_config=task_config,
                ):
                    # 这里的 evaluated_primary 表示：
                    # “全量遍历分支已经完成了多少个组合评估”。
                    # 因为当前没有 stage2，所以它也等同于主进度计数器。
                    evaluated_primary += 1

                    # total_return_pct≈0 且 turnover≈0，通常意味着：
                    # - 这个组合没有真正形成交易
                    # - 或者交易极少，几乎没有形成有效收益曲线
                    # 这类组合会计入“无交易组合”统计，但不参与排行榜。
                    if abs(row.total_return_pct) < 1e-9 and row.turnover <= 1e-9:
                        skipped_no_trade += 1
                        continue

                    # 把当前组合结果加入候选排行榜。
                    ranking_rows.append(row)

                    # 每加入一个结果，都立即按核心排序规则重排一次：
                    # 1. robust_score 越高越好
                    # 2. cagr 越高越好
                    # 3. mdd 越低越好（因此这里用 -item.mdd）
                    ranking_rows.sort(
                        key=lambda item: (item.robust_score, item.cagr, -item.mdd),
                        reverse=True,
                    )

                    # 只保留前 top_n 条临时最优结果，避免内存里累计保存全部组合结果。
                    # 这一步是优化过程中“滚动维护 TopN”的关键。
                    ranking_rows = ranking_rows[:top_n]

                    # 不是每评估一个组合都写一次任务状态。
                    # 否则频繁更新会带来额外锁竞争和持久化开销。
                    # 这里选择几个关键时刻更新：
                    # - 第 1 个组合完成时
                    # - 最后 1 个组合完成时
                    # - 按总量的 1% 步长更新
                    # - 或每满 200 个组合更新一次
                    if (
                        evaluated_primary == 1
                        or evaluated_primary == total
                        or evaluated_primary % max(1, total // 100) == 0
                        or evaluated_primary % 200 == 0
                    ):
                        # 先把当前临时 TopN 写回内存态，供前端轮询查看“过程中的排行榜”。
                        self._optimize_results[task_id] = self._rank_optimize_rows(ranking_rows)

                        # 用“当前累计耗时 / 已完成组合数”估算单组合平均耗时，
                        # 再乘以剩余组合数，得到粗略 ETA。
                        elapsed_seconds = max(1.0, (datetime.now() - start_at).total_seconds())
                        remain = max(0, total - evaluated_primary)
                        per_cost = elapsed_seconds / max(1, evaluated_primary)
                        eta_minutes = int((remain * per_cost) / 60)

                        # progress 在这个分支里近似等于：
                        # 已完成组合数 / 总组合数
                        # 但上限先卡到 99%，把 100% 留给最终收尾和持久化完成时统一写入。
                        self._update_optimize_task(
                            task_id,
                            evaluated_combinations=evaluated_primary,
                            progress=max(1, min(99, ceil(evaluated_primary / total * 100))),
                            eta=f"{eta_minutes}m" if remain else "done",
                            message=f"已评估 {evaluated_primary}/{total}",
                        )

            # 统一按稳健分 / CAGR / MDD 对最终候选结果排序，并补 rank 字段。
            ranked = [
                row.model_copy(update={"rank": idx + 1})
                for idx, row in enumerate(
                    sorted(ranking_rows, key=lambda item: (item.robust_score, item.cagr, -item.mdd), reverse=True)
                )
            ]
            if not ranked:
                # 没有任何有效策略时，清空持久化结果表，避免前端看到旧任务残留结果。
                self._optimize_results[task_id] = []
                self._optimize_top_bonds[task_id] = []
                self._store.replace_optimize_result_rows(task_id=task_id, rows=[])
                self._store.replace_optimize_top_bond_rows(task_id=task_id, rows=[])
                self._update_optimize_task(
                    task_id,
                    status="finished",
                    progress=100,
                    evaluated_combinations=min(total, evaluated_primary),
                    eta="done",
                    finished_at=_now_readable(),
                    message=f"优化完成，但未产生有效交易策略（无交易组合 {skipped_no_trade}/{max(1, evaluated_primary + evaluated_secondary)}）。",
                )
                return

            # best_setting 是后续生成“当前市场 Top 债”的输入，不再重新求最佳参数。
            best_setting = ranked[0].params if ranked else {}
            self._optimize_results[task_id] = ranked
            top_bonds: list[StrategyTopBondRow] = []
            market_warning = ""
            strategy_warning = ""
            if ranked and abs(ranked[0].total_return_pct) < 1e-9 and ranked[0].turnover <= 1e-9:
                strategy_warning = "；当前参数空间未产生有效交易，建议放宽筛选阈值或调整因子范围"
            if best_setting:
                try:
                    # 这里的 Top 债不是历史回测结果，而是“当前市场快照 + 最优参数”的即时评分结果。
                    top_bonds, market_source = self._score_current_market(best_setting, limit=current_top_n)
                    if not market_source.startswith("eastmoney."):
                        market_warning = f"；Top20基于 {market_source}（非实时）"
                except Exception as exc:
                    # Top 债生成失败不应让整个优化任务失败，所以这里只记录 warning。
                    market_warning = f"；实时Top20计算失败: {str(exc)[:80]}"

            # 排行榜结果和 Top 债都要同时写入内存态与 SQLite，
            # 这样前端刷新页面或服务重启后都能恢复。
            self._optimize_top_bonds[task_id] = top_bonds
            self._store.replace_optimize_result_rows(
                task_id=task_id,
                rows=[row.model_dump() for row in ranked],
            )
            self._store.replace_optimize_top_bond_rows(
                task_id=task_id,
                rows=[row.model_dump() for row in top_bonds],
            )
            self._update_optimize_task(
                task_id,
                status="finished",
                progress=100,
                evaluated_combinations=min(total, evaluated_primary),
                eta="done",
                finished_at=_now_readable(),
                message=(
                    f"优化完成，最佳策略 {ranked[0].combo_id if ranked else '--'}"
                    f"{strategy_warning}{market_warning}"
                    f"；主筛={evaluated_primary}/{total}, 复评={evaluated_secondary}"
                ),
            )
        except Exception as exc:
            # 任意阶段抛出的异常都会统一落到这里，任务状态改为 failed。
            # 这里不会抛回到 Web 请求，因为这是后台线程。
            self._update_optimize_task(
                task_id,
                status="failed",
                progress=max(1, min(99, ceil(evaluated_primary / total * 100))) if evaluated_primary > 0 else 0,
                evaluated_combinations=min(total, evaluated_primary),
                eta="--",
                finished_at=_now_readable(),
                message=f"error: {str(exc)[:160]}",
            )

    # ---------- backtest ----------
    def list_jobs(
        self,
        keyword: str = "",
        status: str = "all",
        business_date: str = "",
        business_date_from: str | None = None,
        business_date_to: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> BacktestJobListResponse:
        self._ensure_optimize_tasks_synced_as_backtest_jobs()
        rows: list[BacktestJobRow] = []
        needle = keyword.strip().lower()
        biz = business_date.strip()
        biz_from = (business_date_from or "").strip() or None
        biz_to = (business_date_to or "").strip() or None

        for row in self._jobs:
            if not self._is_displayable_backtest_job(row):
                continue
            if status != "all" and row.status != status:
                continue
            job_biz_date = str(row.business_date or "")
            if biz and job_biz_date != biz:
                continue
            if biz_from and (not job_biz_date or job_biz_date < biz_from):
                continue
            if biz_to and (not job_biz_date or job_biz_date > biz_to):
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
        self._ensure_optimize_tasks_synced_as_backtest_jobs()
        visible_jobs = [row for row in self._jobs if self._is_displayable_backtest_job(row)]
        running = sum(1 for row in visible_jobs if row.status == "running")
        queued = sum(1 for row in visible_jobs if row.status == "queued")
        finished = sum(1 for row in visible_jobs if row.status == "finished")
        failed = sum(1 for row in visible_jobs if row.status == "failed")
        cancelled = sum(1 for row in visible_jobs if row.status == "cancelled")
        rule_pack_count = len({row.rule_pack_id for row in visible_jobs})
        top_cagr = max((row.cagr for row in self._leaderboard), default=0.0)

        return BacktestStatsResponse(
            running_jobs=running,
            queued_jobs=queued,
            finished_jobs=finished,
            failed_jobs=failed,
            cancelled_jobs=cancelled,
            rule_pack_count=rule_pack_count,
            top_cagr=top_cagr,
        )

    def create_jobs(self, request: BacktestCreateJobsRequest) -> BacktestCreateJobsResponse:
        """创建单次回测作业。

        与优化任务不同，这里是“给定组合 + 给定窗口”的直接回测，
        更适合验证某个候选组合或做规则包的单独回放。
        """
        windows = self._normalize_windows(request.windows)
        if not windows:
            windows = ["full", "3y", "1y"]
        business_date = request.business_date.isoformat() if request.business_date else date.today().isoformat()

        request_template = str(request.template or "").strip()
        candidate = self._find_candidate(
            request.combo_id,
            template_name=request_template if request_template else None,
        )
        if not candidate:
            raise ValueError(
                f"unknown combo_id/template: combo_id={request.combo_id}, template={request_template or '--'}; "
                "please choose an existing candidate combo."
            )
        template_name = candidate.template
        rule_pack_id = request.rule_pack_id or self._build_rule_pack_id(request)

        with self._lock:
            # 先把回测作业和上下文一并落库，保证后续线程真正执行前状态已可恢复。
            created: list[BacktestJobRow] = []
            setting = self._resolve_setting_for_combo(
                combo_id=request.combo_id,
                template_name=template_name,
            )
            created_at = _now_readable()
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
                    business_date=business_date,
                    created_at=created_at,
                    started_at="",
                    eta="--",
                    worker="",
                )
                created.append(row)
                context = {
                    "window_name": window_name,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                    "setting": setting,
                    "cancel_requested": False,
                    "business_date": business_date,
                    "created_at": created_at,
                }
                self._job_context[row.job_id] = context
                self._store.upsert_job(row=row.model_dump(), context=context)

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

    def cancel_job(self, job_id: str) -> BacktestJobRow | None:
        cancelled_job: BacktestJobRow | None = None
        with self._lock:
            for index, row in enumerate(self._jobs):
                if row.job_id != job_id:
                    continue

                if row.status in {"finished", "failed", "cancelled"}:
                    cancelled_job = row
                    break

                context = self._job_context.get(job_id) or self._store.get_job_context(job_id) or {}
                context["cancel_requested"] = True
                self._job_context[job_id] = context
                cancelled_job = row.model_copy(
                    update={
                        "status": "cancelled",
                        "eta": "cancelled",
                    }
                )
                self._jobs[index] = cancelled_job
                self._store.upsert_job(row=cancelled_job.model_dump(), context=context)
                break

        if cancelled_job:
            self._refresh_candidate_status(cancelled_job.combo_id)
            self._refresh_compare_rows()
        return cancelled_job

    def _run_job(self, job_id: str) -> None:
        """单个回测作业的工作线程入口。"""
        context = self._job_context.get(job_id) or self._store.get_job_context(job_id)
        if not context:
            self._update_job(job_id, status="failed", eta="missing context")
            return

        if bool(context.get("cancel_requested")):
            self._update_job(job_id, status="cancelled", eta="cancelled")
            return

        window_name = str(context.get("window_name", "full"))
        start_raw = context.get("start_date")
        end_raw = context.get("end_date")
        start_date = self._parse_iso_date(start_raw) if isinstance(start_raw, str) else start_raw
        end_date = self._parse_iso_date(end_raw) if isinstance(end_raw, str) else end_raw
        setting = dict(context.get("setting", self._adapter.default_setting()))

        ticker_stop = Event()
        ticker = Thread(
            target=self._progress_ticker,
            args=(job_id, ticker_stop),
            daemon=True,
        )

        self._update_job(
            job_id,
            status="running",
            progress=3,
            eta="loading data",
            started_at=_now_hms(),
            worker=current_thread().name,
        )
        ticker.start()

        try:
            if self._is_job_cancel_requested(job_id):
                self._update_job(job_id, status="cancelled", eta="cancelled")
                return
            stats = self._adapter.run_backtest(
                setting=setting,
                window_name=window_name,
                start_date=start_date,
                end_date=end_date,
            )
            if self._is_job_cancel_requested(job_id):
                self._update_job(job_id, status="cancelled", eta="cancelled")
                return
            metrics = self._derive_leaderboard_metrics(stats=stats, window_name=window_name)
            job = self._get_job(job_id)
            if not job:
                return
            if job.status == "cancelled" or self._is_job_cancel_requested(job_id):
                self._update_job(job_id, status="cancelled", eta="cancelled")
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
            self._upsert_leaderboard_row(row, business_date=job.business_date)
            done_eta = "done"
            if bool(stats.get("fallback_used")):
                done_eta = "done (auto-range)"
            self._update_job(job_id, status="finished", progress=100, eta=done_eta)
            self._refresh_candidate_status(job.combo_id)
            self._refresh_compare_rows()
        except Exception as exc:
            if self._is_job_cancel_requested(job_id):
                self._update_job(job_id, status="cancelled", eta="cancelled")
                return
            reason = str(exc).splitlines()[0][:42] if str(exc) else "error"
            self._update_job(job_id, status="failed", eta=f"error: {reason}")
            job = self._get_job(job_id)
            if job:
                self._refresh_candidate_status(job.combo_id)
        finally:
            ticker_stop.set()

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
                context = self._job_context.get(job_id) or self._store.get_job_context(job_id) or {
                    "window_name": "full",
                    "setting": self._adapter.default_setting(),
                    "start_date": None,
                    "end_date": None,
                    "cancel_requested": False,
                    "business_date": merged.business_date or date.today().isoformat(),
                    "created_at": merged.created_at or _now_readable(),
                }
                if "cancel_requested" in updates:
                    context["cancel_requested"] = bool(updates["cancel_requested"])
                self._job_context[job_id] = context
                self._store.upsert_job(row=merged.model_dump(), context=context)
                return merged
        return None

    def _get_optimize_task(self, task_id: str) -> StrategyOptimizeTaskRow | None:
        with self._lock:
            for row in self._optimize_tasks:
                if row.task_id == task_id:
                    return row
        return None

    def _update_optimize_task(self, task_id: str, **updates: Any) -> StrategyOptimizeTaskRow | None:
        merged_row: StrategyOptimizeTaskRow | None = None
        with self._lock:
            for index, row in enumerate(self._optimize_tasks):
                if row.task_id != task_id:
                    continue
                merged_row = row.model_copy(update=updates)
                self._optimize_tasks[index] = merged_row
                break
        if merged_row is not None:
            self._store.upsert_optimize_task(row=merged_row.model_dump())
            self._sync_optimize_task_as_backtest_job(merged_row)
        return merged_row

    def _ensure_optimize_tasks_synced_as_backtest_jobs(self) -> None:
        with self._lock:
            tasks_snapshot = list(self._optimize_tasks)
        for task in tasks_snapshot:
            self._sync_optimize_task_as_backtest_job(task)

    def _sync_optimize_task_as_backtest_job(self, task: StrategyOptimizeTaskRow) -> None:
        best_row = (self._optimize_results.get(task.task_id) or [None])[0]
        combo_id = best_row.combo_id if best_row is not None else "--"
        setting = dict(best_row.params) if best_row is not None else self._adapter.default_setting()
        setting = self._apply_task_config_to_setting(setting, task.task_config)
        status = task.status if task.status in {"queued", "running", "finished", "failed"} else "failed"
        business_date = (task.created_at or "")[:10] or date.today().isoformat()
        window_text = "/".join(task.windows) if task.windows else "full"
        row = BacktestJobRow(
            job_id=task.task_id,
            strategy_id=task.template_id,
            combo_id=combo_id,
            rule_pack_id=f"OPT-{task.template_id}",
            template=task.template_name,
            window=window_text,
            status=status,
            progress=max(0, min(100, int(task.progress))),
            business_date=business_date,
            created_at=task.created_at,
            started_at=task.started_at or "",
            eta=task.eta or "--",
            worker="optimize",
        )

        context = {
            "window_name": window_text,
            "start_date": task.start_date,
            "end_date": task.end_date,
            "setting": setting,
            "cancel_requested": False,
            "business_date": business_date,
            "created_at": task.created_at or _now_readable(),
        }

        with self._lock:
            replaced = False
            for index, item in enumerate(self._jobs):
                if item.job_id != row.job_id:
                    continue
                self._jobs[index] = row
                replaced = True
                break
            if not replaced:
                self._jobs = [row, *self._jobs]
            self._job_context[row.job_id] = context

        self._store.upsert_job(row=row.model_dump(), context=context)

    @staticmethod
    def _rank_optimize_rows(rows: list[StrategyOptimizeResultRow]) -> list[StrategyOptimizeResultRow]:
        return [
            row.model_copy(update={"rank": idx + 1})
            for idx, row in enumerate(
                sorted(rows, key=lambda item: (item.robust_score, item.cagr, -item.mdd), reverse=True)
            )
        ]

    def _prepare_window_dataset_map(
        self,
        *,
        dataset: list[tuple[str, Any]],
        windows: list[WindowName],
        start_date: date | None,
        end_date: date | None,
    ) -> dict[WindowName, list[tuple[str, Any]]]:
        sliced_map: dict[WindowName, list[tuple[str, Any]]] = {}
        for window_name in self._normalize_windows(windows):
            sliced = self._adapter._slice_dataset(
                dataset=dataset,
                window_name=window_name,
                start_date=start_date,
                end_date=end_date,
            )
            if not sliced and (start_date or end_date):
                sliced = self._adapter._slice_dataset(
                    dataset=dataset,
                    window_name=window_name,
                    start_date=None,
                    end_date=None,
                )
            sliced_map[window_name] = sliced
        return sliced_map

    @staticmethod
    def _pick_stage1_window(windows: list[WindowName]) -> WindowName:
        if "1w" in windows:
            return "1w"
        if "1y" in windows:
            return "1y"
        if "3y" in windows:
            return "3y"
        return "full"

    @staticmethod
    def _env_int(name: str, default: int, *, low: int = 1, high: int = 1_000_000) -> int:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except Exception:
            return default
        return max(low, min(high, value))

    @staticmethod
    def _env_float(name: str, default: float, *, low: float = 0.0, high: float = 1.0) -> float:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except Exception:
            return default
        return max(low, min(high, value))

    def _optimize_worker_count(self) -> int:
        return self._env_int("CBQ_OPT_WORKERS", 1, low=1, high=32)

    def _should_enable_stage1_screening(self, *, total: int, windows: list[WindowName]) -> bool:
        threshold = self._env_int("CBQ_OPT_STAGE1_THRESHOLD", 500, low=10, high=5_000_000)
        return total >= threshold and len(windows) >= 2

    def _stage1_sample_limit(self, *, total: int, top_n: int) -> int:
        ratio = self._env_float("CBQ_OPT_STAGE1_RATIO", 0.1, low=0.01, high=1.0)
        min_sample = self._env_int("CBQ_OPT_STAGE1_MIN", 400, low=20, high=1_000_000)
        max_sample = self._env_int("CBQ_OPT_STAGE1_MAX", 12_000, low=50, high=2_000_000)
        base = max(min_sample, int(total * ratio), max(20, top_n * 20))
        return max(1, min(total, min(max_sample, base)))

    def _stage2_shortlist_limit(self, *, total: int, top_n: int, current_top_n: int) -> int:
        multiplier = self._env_int("CBQ_OPT_SHORTLIST_MULTIPLIER", 8, low=2, high=50)
        min_shortlist = self._env_int("CBQ_OPT_SHORTLIST_MIN", 120, low=20, high=20_000)
        max_shortlist = self._env_int("CBQ_OPT_SHORTLIST_MAX", 3_000, low=50, high=100_000)
        base = max(min_shortlist, max(top_n, current_top_n) * multiplier)
        return max(1, min(total, min(max_shortlist, base)))

    @staticmethod
    def _sample_combo_indices(total: int, sample_limit: int) -> list[int]:
        if total <= 0:
            return []
        if sample_limit >= total:
            return list(range(1, total + 1))
        if sample_limit <= 1:
            return [1]

        step = (total - 1) / (sample_limit - 1)
        seeded = [1 + int(round(idx * step)) for idx in range(sample_limit)]
        seen: set[int] = set()
        indices: list[int] = []
        for value in seeded:
            safe = max(1, min(total, value))
            if safe in seen:
                continue
            seen.add(safe)
            indices.append(safe)

        if len(indices) < sample_limit:
            for value in range(1, total + 1):
                if value in seen:
                    continue
                indices.append(value)
                seen.add(value)
                if len(indices) >= sample_limit:
                    break
        indices.sort()
        return indices[:sample_limit]

    def _iter_sampled_template_settings(
        self,
        *,
        template_id: str,
        total: int,
        sample_limit: int,
    ) -> Iterable[tuple[str, dict[str, Any]]]:
        if sample_limit >= total:
            yield from self._iter_template_settings(template_id=template_id, limit=total)
            return

        for combo_seq in self._sample_combo_indices(total, sample_limit):
            combo_id = f"CMB-{combo_seq:06d}"
            setting = self._build_candidate_setting(template_id=template_id, combo_id=combo_id)
            if not setting:
                continue
            yield combo_id, setting

    def _iter_combo_results_parallel(
        self,
        *,
        task_id: str,
        template_id: str,
        template_name: str,
        dataset: list[tuple[str, Any]],
        combo_iter: Iterable[tuple[str, dict[str, Any]]],
        windows: list[WindowName],
        start_date: date | None,
        end_date: date | None,
        window_dataset_map: dict[WindowName, list[tuple[str, Any]]] | None,
        workers: int,
        task_config: BacktestTaskConfig,
    ) -> Iterable[StrategyOptimizeResultRow]:
        """按给定参数组合迭代器，逐个产出组合评估结果。

        这个方法的职责很单一：
        - 输入：一串待评估的 `(combo_id, setting)`
        - 调度：按串行或线程池并行方式调用 `_evaluate_combo(...)`
        - 输出：谁先评估完，就先 yield 谁的 `StrategyOptimizeResultRow`

        它本身不关心 stage1/stage2，也不负责排序，只负责“把组合送去评估”。
        """
        # 先把任意 Iterable 统一转成显式迭代器，便于后面串行/并行两种模式共用。
        combo_iterator = iter(combo_iter)
        if workers <= 1:
            # workers <= 1 时不启用线程池，完全按顺序逐个评估。
            # 这种模式最容易调试，也最稳定，但速度取决于单核串行执行能力。
            for combo_id, setting in combo_iterator:
                # 每取出一个组合，就直接调用 `_evaluate_combo(...)` 得到结果。
                # yield 返回后，调用方可以立刻更新进度和临时排行榜。
                yield self._evaluate_combo(
                    task_id=task_id,
                    template_id=template_id,
                    template_name=template_name,
                    dataset=dataset,
                    combo_id=combo_id,
                    windows=windows,
                    start_date=start_date,
                    end_date=end_date,
                    setting=setting,
                    window_dataset_map=window_dataset_map,
                    task_config=task_config,
                )
            return

        # workers > 1 时启用线程池并行评估。
        # 注意：这里是“组合级并行”，不是交易日级并行。
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cbq-opt-eval") as pool:
            # inflight 保存“已经提交到线程池、但还没返回结果”的 future。
            # value 里记 combo_id 主要是为了调试和后续扩展时可追踪。
            inflight: dict[Any, str] = {}

            def submit_next() -> bool:
                # 从组合迭代器里继续取下一个参数组合。
                try:
                    combo_id, setting = next(combo_iterator)
                except StopIteration:
                    # 没有更多组合可提交了。
                    return False

                # 把单个组合评估任务提交给线程池。
                # 真正耗时的逻辑仍然在 `_evaluate_combo(...)` 里。
                future = pool.submit(
                    self._evaluate_combo,
                    task_id=task_id,
                    template_id=template_id,
                    template_name=template_name,
                    dataset=dataset,
                    combo_id=combo_id,
                    windows=windows,
                    start_date=start_date,
                    end_date=end_date,
                    setting=setting,
                    window_dataset_map=window_dataset_map,
                    task_config=task_config,
                )

                # 记录这个 future 对应哪个 combo_id，表示它已经在执行中了。
                inflight[future] = combo_id
                return True

            # 先预填一批任务到线程池，避免线程池空转。
            # 这里用 `workers * 2`，是为了让“已执行中 + 等待调度”保持一定流水深度，
            # 通常比只提交 workers 个任务更容易把线程池喂满。
            for _ in range(max(1, workers * 2)):
                if not submit_next():
                    break

            # 只要还有任何未完成任务，就持续等待最先完成的一批结果。
            while inflight:
                # FIRST_COMPLETED 表示：只要有任意一个 future 完成，就立刻返回。
                # 这样可以做到“谁先算完，谁先进入下一轮处理”，提升整体吞吐。
                done, _ = wait(set(inflight.keys()), return_when=FIRST_COMPLETED)
                for future in done:
                    # 先把已完成任务从 inflight 中移除，避免重复处理。
                    inflight.pop(future, None)

                    # 这里 yield 的顺序不是 combo_iter 的原始顺序，而是“完成顺序”。
                    # 因此上层如果要做排行榜维护，必须按结果内容重排，不能依赖输入顺序。
                    yield future.result()

                    # 每消费掉一个已完成任务，就立刻补提交一个新任务，
                    # 尽量让线程池始终维持满载或接近满载状态。
                    submit_next()

    def _build_candidate_code_map(
        self,
        *,
        dataset: list[tuple[str, Any]],
        strategy_parameters: cb_strategy_core.StrategyParameters,
        candidate_count: int,
    ) -> dict[str, list[str]]:
        """预先为每个交易日构建候选代码列表。

        这样后续在多窗口评估时，不必重复执行同一轮候选筛选逻辑。
        """
        candidate_code_map: dict[str, list[str]] = {}
        for trade_date, frame in dataset:
            try:
                candidate = cb_strategy_core.build_candidates(
                    frame,
                    trade_date,
                    strategy_parameters,
                    candidate_count,
                )
            except Exception:
                candidate = None
            if candidate is None or getattr(candidate, "empty", True):
                candidate_code_map[trade_date] = []
                continue
            try:
                codes = candidate["bond_code"].astype(str).tolist()
            except Exception:
                candidate_code_map[trade_date] = []
                continue
            candidate_code_map[trade_date] = codes[: max(1, candidate_count)]
        return candidate_code_map

    def _run_backtest_from_candidate_map(
        self,
        *,
        dataset: list[tuple[str, Any]],
        candidate_code_map: dict[str, list[str]],
        setting: dict[str, Any],
    ) -> dict[str, Any]:
        """基于“已生成的候选池”执行轻量回测。

        这是优化阶段使用的快路径。

        过去这里单独维护了一套轻量回测状态机，导致它和 `cb_strategy_core.run_backtest(...)`
        长期存在“逻辑非常相似、但又不是同一份代码”的问题。现在优化链路也直接
        委托给 `cb_strategy_core.run_backtest_from_candidates(...)`，把持仓轮动、调仓频率、
        强赎、止盈止损、`hold_until_profit` 等规则统一到同一套核心实现上。
        """
        return cb_strategy_core.run_backtest_from_candidates(
            dataset=dataset,
            candidate_code_map=candidate_code_map,
            runtime_config=cb_strategy_core.build_runtime_config(setting),
        )

    def _evaluate_combo(
        self,
        *,
        task_id: str,
        template_id: str,
        template_name: str,
        dataset: list[tuple[str, Any]],
        combo_id: str,
        windows: list[WindowName],
        start_date: date | None,
        end_date: date | None,
        setting: dict[str, Any],
        window_dataset_map: dict[WindowName, list[tuple[str, Any]]] | None = None,
        task_config: BacktestTaskConfig,
    ) -> StrategyOptimizeResultRow:
        """评估单个参数组合在多个窗口下的综合表现。

        这是优化链路里的“单组合评估核心”。

        输入是一组已经展开好的参数 setting，输出是一条可直接参与排行榜排序的
        `StrategyOptimizeResultRow`。它本身不负责模板展开，也不负责任务调度，只负责：

        1. 把任务级配置覆盖到当前组合 setting 上
        2. 构造策略模块能识别的 cfg
        3. 预先生成每日候选池代码映射 `candidate_code_map`
        4. 按每个 window 执行轻量回测
        5. 把多窗口结果聚合成 CAGR / MDD / Calmar / 稳健分等指标
        6. 返回一条最终结果行给 `_run_optimize_task(...)`

        这里的结果是“优化排序用结果”，不是分析页那种带净值曲线和轮动明细的结果。
        """
        # 先把任务级运行配置叠加到参数组合 setting 上。
        # 例如调仓频率、仓位、止盈止损等，最终都要以这里的 setting 为准。
        setting = self._apply_task_config_to_setting(setting, task_config)
        candidate_count = max(1, int(round(self._to_float(setting.get("candidate_count"), 10.0))))
        max_hold_count = max(1, int(round(self._to_float(setting.get("max_hold_count"), 12.0))))
        hold_until_profit = bool(setting.get("hold_until_profit", False))

        # 把通用 setting 转成 cb_strategy_core 真正用于筛债的 cfg。
        # 后面 `build_candidates(...)` 会直接使用这个 cfg。
        strategy_parameters = cb_strategy_core.build_strategy_parameters(setting)
        base_dataset: list[tuple[str, Any]] = []
        if window_dataset_map is not None:
            # 当调用方已经提前准备好多个窗口切片时，这里优先挑“长度最大”的一份数据集，
            # 用来一次性预计算候选池，避免每个窗口都重复 build_candidates。
            for window_name in windows:
                candidate_dataset = window_dataset_map.get(window_name) or []
                if len(candidate_dataset) > len(base_dataset):
                    base_dataset = candidate_dataset
        if not base_dataset:
            # 如果没有传入预切片，就退回到整份 dataset 自己做候选池预计算。
            base_dataset = dataset
        # 候选池基于“可用范围最大的一份数据集”预计算一次，避免多窗口重复生成。
        candidate_code_map = self._build_candidate_code_map(
            dataset=base_dataset,
            strategy_parameters=strategy_parameters,
            candidate_count=candidate_count,
        )

        all_metrics: list[dict[str, float]] = []
        all_returns: list[float] = []

        # 逐个窗口执行轻量回测。
        # 这里不会直接生成详细曲线，而是只提取优化排序需要的核心指标。
        for window_name in windows:
            sliced = None
            if window_dataset_map is not None:
                # 优先复用上层提前切好的窗口数据，减少重复切片开销。
                sliced = window_dataset_map.get(window_name)
            if sliced is None:
                # 如果调用方没提供该窗口数据，这里再现场切一遍。
                sliced = self._adapter._slice_dataset(
                    dataset=dataset,
                    window_name=window_name,
                    start_date=start_date,
                    end_date=end_date,
                )
            if not sliced:
                # 当前窗口没有可用样本时，不直接报错，先跳过，
                # 后面还有一轮“兜底重切”的 fallback。
                continue

            # 轻量回测会基于 candidate_code_map 逐日回放，产出收益、回撤、胜率、换手等统计。
            stats = self._run_backtest_from_candidate_map(
                dataset=sliced,
                candidate_code_map=candidate_code_map,
                setting=setting,
            )
            stats["sample_days"] = len(sliced)

            # 不同窗口下的原始回测结果会先统一转换成排行榜口径的 metrics。
            metrics = self._derive_leaderboard_metrics(stats=stats, window_name=window_name)
            all_metrics.append(metrics)
            all_returns.append(self._to_float(stats.get("total_return_pct"), 0.0))

        if not all_metrics:
            # 如果按用户指定的日期范围/窗口切片后一个结果都没拿到，
            # 再退回到“忽略 start/end 限制，只按窗口默认范围切片”重试一次。
            # 这样可以兼容用户选了过窄日期，或者历史库覆盖范围不足的情况。
            for window_name in windows:
                sliced = None
                if window_dataset_map is not None:
                    sliced = window_dataset_map.get(window_name)
                if sliced is None or not sliced:
                    sliced = self._adapter._slice_dataset(
                        dataset=dataset,
                        window_name=window_name,
                        start_date=None,
                        end_date=None,
                    )
                if not sliced:
                    continue
                stats = self._run_backtest_from_candidate_map(
                    dataset=sliced,
                    candidate_code_map=candidate_code_map,
                    setting=setting,
                )
                stats["sample_days"] = len(sliced)
                metrics = self._derive_leaderboard_metrics(stats=stats, window_name=window_name)
                all_metrics.append(metrics)
                all_returns.append(self._to_float(stats.get("total_return_pct"), 0.0))

        if not all_metrics:
            # 连 fallback 之后都没有数据，说明该组合在当前任务窗口下完全无法评估。
            raise RuntimeError("No market snapshots available for selected window")

        # 下面开始把多个窗口结果聚合成一条总结果：
        # - CAGR / win_rate / turnover 取均值
        # - MDD 取最差窗口（最大回撤最大）
        # - Calmar 用聚合后的 CAGR / MDD 计算
        cagr = sum(item["cagr"] for item in all_metrics) / len(all_metrics)
        mdd = max(item["mdd"] for item in all_metrics)
        calmar = cagr / mdd if mdd > 0 else cagr
        win_rate = sum(item["win_rate"] for item in all_metrics) / len(all_metrics)
        turnover = sum(item["turnover"] for item in all_metrics) / len(all_metrics)

        # recent_1y 优先拿 1y / 1w 这样的“近期窗口”结果；如果没有近期窗口，就退回 CAGR。
        recent_1y = next((item["recent_1y"] for item, w in zip(all_metrics, windows) if w in {"1y", "1w"}), cagr)
        robust_score = sum(item["robust_score"] for item in all_metrics) / len(all_metrics)
        total_return_pct = sum(all_returns) / len(all_returns)

        # params 只保留可序列化字段，便于后续写入结果表和前端展示。
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
            "price_benchmark": "price_benchmark",
            "premium_benchmark": "premium_benchmark",
            "stock_weight": "stock_weight",
            "premium_weight": "premium_weight",
            "volatility_benchmark": "volatility_benchmark",
            "max_candidate_price": "max_candidate_price",
            "candidate_count": "candidate_count",
            "outstanding_amount_weight": "outstanding_amount_weight",
            "max_hold_count": "max_hold_count",
        }
        for factor_key, setting_key in direct_map.items():
            if factor_key in values:
                setting[setting_key] = values[factor_key]

        if "premium_max" in values and "premium_benchmark" not in values:
            setting["premium_benchmark"] = self._to_float(values["premium_max"], 25.0)
        if "conv_prem" in values and "premium_benchmark" not in values:
            setting["premium_benchmark"] = self._to_float(values["conv_prem"], 25.0)
        if "price_max" in values:
            setting["max_candidate_price"] = self._to_float(values["price_max"], setting.get("max_candidate_price", 130.0))
        if "remain_size" in values and "outstanding_amount_weight" not in values:
            remain_size = self._to_float(values["remain_size"], 12.0)
            setting["outstanding_amount_weight"] = max(0.05, min(0.50, remain_size / 100.0))
        if "turnover" in values and "volatility_benchmark" not in values:
            turnover = self._to_float(values["turnover"], 2.0)
            setting["volatility_benchmark"] = max(10.0, min(60.0, turnover * 4.0 + 12.0))
        if "dblow" in values and "price_benchmark" not in values:
            dblow = self._to_float(values["dblow"], 140.0)
            premium = self._to_float(setting.get("premium_benchmark"), 25.0)
            setting["price_benchmark"] = max(90.0, min(180.0, dblow - premium))
        if "rating" in values:
            rating = str(values["rating"]).upper()
            if rating == "AAA":
                setting["premium_weight"] = 0.2
                setting["max_candidate_price"] = min(130.0, self._to_float(setting.get("max_candidate_price"), 130.0))
            elif rating == "AA+":
                setting["premium_weight"] = 0.25
            else:
                setting["premium_weight"] = 0.3

        setting["candidate_count"] = max(1, int(round(self._to_float(setting.get("candidate_count"), 10.0))))
        setting["max_hold_count"] = max(1, int(round(self._to_float(setting.get("max_hold_count"), 12.0))))
        setting["stock_weight"] = max(0.0, min(1.0, self._to_float(setting.get("stock_weight"), 0.3)))
        setting["premium_weight"] = max(0.0, min(1.0, self._to_float(setting.get("premium_weight"), 0.3)))
        setting["hold_until_profit"] = bool(setting.get("hold_until_profit", False))
        return setting

    def _score_current_market(self, setting: dict[str, Any], limit: int = 20) -> tuple[list[StrategyTopBondRow], str]:
        market = self._market_service.list_bonds(min_volume_wan=0)
        if market.source.startswith("fallback.mock"):
            raise RuntimeError(f"realtime market source unavailable: {market.source}")
        rows = []
        price_b = max(1.0, self._to_float(setting.get("price_benchmark"), 115.0))
        premium_b = max(1.0, self._to_float(setting.get("premium_benchmark"), 25.0))
        stock_weight = max(0.0, min(1.0, self._to_float(setting.get("stock_weight"), 0.3)))
        bond_weight = max(0.0, min(1.0, 1.0 - stock_weight))
        premium_weight = max(0.0, min(1.0, self._to_float(setting.get("premium_weight"), 0.3)))
        outstanding_amount_weight = max(0.0, min(1.0, self._to_float(setting.get("outstanding_amount_weight"), 0.1)))
        stdev_b = max(5.0, self._to_float(setting.get("volatility_benchmark"), 30.0))
        max_candidate_price = self._to_float(setting.get("max_candidate_price"), 130.0)

        for item in market.items:
            if item.price > max_candidate_price:
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
                bond_weight * price_score
                + stock_weight * (premium_score * premium_weight + stdev_score * 0.2 + remain_score * outstanding_amount_weight + pb_score * 0.1),
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
        dataset: list[tuple[str, Any]],
        setting: dict[str, Any],
        initial_capital_wan: float,
    ) -> dict[str, Any]:
        """执行带明细输出的详细策略回放。

        相比 `_run_backtest_from_candidate_map`，这里会额外保留：
        - 每日净值
        - 每日回撤
        - 每日换手
        - 每次轮动后的持仓快照
        """
        strategy_parameters = cb_strategy_core.build_strategy_parameters(setting)
        candidate_count = max(1, int(round(self._to_float(setting.get("candidate_count"), 10.0))))
        max_hold_count = max(1, int(round(self._to_float(setting.get("max_hold_count"), 12.0))))
        hold_until_profit = bool(setting.get("hold_until_profit", False))
        per_position = self._position_ratio(setting=setting, max_hold_count=max_hold_count)

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
        rebalanced_days = 0
        last_rebalance_date: str | None = None
        last_rebalance_index = 0

        for index, (trade_date, df_all) in enumerate(dataset):
            candidate = cb_strategy_core.build_candidates(
                df_all,
                trade_date,
                strategy_parameters,
                candidate_count,
            )
            if candidate is None:
                candidate = df_all.iloc[0:0]
            if candidate is None or candidate.empty:
                candidate_codes: set[str] = set()
            else:
                candidate_codes = set(candidate["bond_code"].astype(str).tolist())
            rebalance_due = self._should_rebalance(
                index=index,
                trade_date=trade_date,
                last_rebalance_date=last_rebalance_date,
                last_rebalance_index=last_rebalance_index,
                setting=setting,
            )

            if index == 0:
                # 首个交易日不计算收益，只负责用当日候选池初始化持仓。
                # 这样从第二个交易日起，收益率才有明确的“昨收 -> 今收”基准。
                if candidate is not None and not candidate.empty:
                    for _, row in candidate.head(max_hold_count).iterrows():
                        price = self._to_float(row.get("close_price"), 0.0)
                        if price <= 0:
                            continue
                        holdings.append(
                            {
                                "code": str(row.get("bond_code", "")),
                                "buy_price": price,
                                "last_price": price,
                                "ratio": per_position,
                            }
                        )
                prev_codes = {item["code"] for item in holdings}
                last_rebalance_date = trade_date
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
            # 先按昨持仓计算当日收益，再决定是否卖出/补仓。
            # 这样调仓发生在收盘后视角，避免把“当天新买入仓位”提前计入当天收益。
            for item in holdings:
                code = str(item.get("code", ""))
                if code not in df_all.index:
                    continue
                row = df_all.loc[code]
                cur_price = self._to_float(row.get("close_price"), self._to_float(item.get("last_price"), 0.0))
                last_price = self._to_float(item.get("last_price"), cur_price)
                ratio = self._to_float(item.get("ratio"), 0.0)
                if last_price > 0:
                    day_return += ((cur_price - last_price) / last_price) * ratio
                item["last_price"] = cur_price

            nav *= 1.0 + day_return
            if nav > peak:
                peak = nav
            drawdown = (nav / peak - 1.0) * 100 if peak > 0 else 0.0
            drawdown_sum += drawdown
            drawdown_count += 1

            # 详细模拟里保留了每次调仓的变化，用于分析页展示轮动记录。
            keep_list: list[dict[str, Any]] = []
            sell_list: list[dict[str, Any]] = []

            # 先做卖出/留仓判断：
            # - 不在快照中的券直接卖出
            # - 强赎、止盈止损命中则卖出
            # - hold_until_profit 打开时，亏损仓位可延迟退出
            # - 到调仓日后，再根据 candidate_codes 判定是否继续持有
            for item in holdings:
                code = str(item.get("code", ""))
                if code not in df_all.index:
                    sell_list.append(item)
                    continue
                row = df_all.loc[code]
                cur_price = self._to_float(row.get("close_price"), self._to_float(item.get("last_price"), 0.0))
                is_redeem_triggered = bool(row.get("is_redeem_triggered", False))
                if is_redeem_triggered:
                    sell_list.append(item)
                    continue
                if self._should_exit_by_price_limits(setting=setting, item=item, current_price=cur_price):
                    sell_list.append(item)
                    continue
                if hold_until_profit and cur_price <= self._to_float(item.get("buy_price"), cur_price):
                    keep_list.append(item)
                    continue
                if not rebalance_due:
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
                    sell_price = self._to_float(row.get("close_price"), self._to_float(item.get("last_price"), 0.0))
                else:
                    sell_price = self._to_float(item.get("last_price"), 0.0)
                buy_price = self._to_float(item.get("buy_price"), sell_price)
                pnl_pct = (sell_price - buy_price) / buy_price * 100.0 if buy_price > 0 else 0.0
                trade_pnls_pct.append(pnl_pct)
                effective_trade_count += 1

            existing_codes = {str(item.get("code", "")) for item in keep_list}
            if rebalance_due:
                # 只有调仓日才会从候选池补买，且补到 max_hold_count 为止。
                # 非调仓日即使有更高分标的出现，也不会主动替换现有持仓。
                for _, row in candidate.iterrows():
                    if len(keep_list) >= max_hold_count:
                        break
                    code = str(row.get("bond_code", ""))
                    if code in existing_codes:
                        continue
                    price = self._to_float(row.get("close_price"), 0.0)
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

            # 换手率按“前后持仓代码集合差异”估算，主要用于分析页展示，不参与交易决策。
            current_codes = {str(item.get("code", "")) for item in keep_list}
            if prev_codes:
                changed_count = len(prev_codes - current_codes) + len(current_codes - prev_codes)
                day_turnover = changed_count / max(1, len(prev_codes)) * 100.0
            else:
                changed_count = len(current_codes)
                day_turnover = changed_count / max(1, max_hold_count) * 100.0

            holdings = keep_list
            prev_codes = current_codes
            if rebalance_due:
                rebalanced_days += 1
                last_rebalance_date = trade_date
                last_rebalance_index = index

            dates.append(trade_date)
            daily_returns.append(day_return)
            nav_series.append(nav)
            cum_return_pct.append((nav - 1.0) * 100.0)
            drawdown_pct.append(drawdown)
            avg_drawdown_pct.append(drawdown_sum / max(1, drawdown_count))
            turnover_pct.append(day_turnover)

            # 只在发生持仓变化或到达最后一天时记录一条轮动快照，避免分析页出现大量重复记录。
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
            "rebalanced_days": rebalanced_days,
        }

    def _simulate_equal_weight_benchmark(
        self,
        *,
        dataset: list[tuple[str, Any]],
        initial_capital_wan: float,
    ) -> dict[str, Any]:
        """构造一个简单的转债等权基准，用于分析页做对照。"""
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
        """把净值序列、收益序列和交易结果汇总成分析指标。"""
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
                    name = str(row.get("bond_name", "")).strip()
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

    @staticmethod
    def _normalize_task_config(task_config: BacktestTaskConfig | dict[str, Any] | None) -> BacktestTaskConfig:
        """把外部传入的任务参数做一次统一归一化。

        目的不是校验 schema；schema 在 API 层已经做过。
        这里主要处理运行态兜底，例如：
        - 最少持仓不能大于最多持仓
        - 百分比不能越界
        - 可空止盈/止损参数要转成明确值
        """
        if isinstance(task_config, BacktestTaskConfig):
            config = task_config
        else:
            try:
                config = BacktestTaskConfig.model_validate(task_config or {})
            except Exception:
                config = BacktestTaskConfig()
        max_hold = max(1, int(config.max_hold_count))
        freq_value = max(1, int(config.rebalance_interval_value))
        initial_capital_wan = max(0.0001, float(config.initial_capital_wan))
        max_position_pct = max(0.0, min(100.0, float(config.max_position_pct)))
        exclude_redeem_days_below = config.exclude_redeem_days_below
        if exclude_redeem_days_below is not None:
            exclude_redeem_days_below = max(0, int(exclude_redeem_days_below))
        take_profit_pct = config.take_profit_pct
        stop_loss_pct = config.stop_loss_pct
        if take_profit_pct is not None:
            take_profit_pct = max(0.0, float(take_profit_pct))
        if stop_loss_pct is not None:
            stop_loss_pct = max(0.0, float(stop_loss_pct))
        return config.model_copy(
            update={
                "initial_capital_wan": initial_capital_wan,
                "max_hold_count": max_hold,
                "rebalance_interval_value": freq_value,
                "max_position_pct": max_position_pct,
                "exclude_redeem_days_below": exclude_redeem_days_below,
                "take_profit_pct": take_profit_pct,
                "stop_loss_pct": stop_loss_pct,
            }
        )

    def _apply_task_config_to_setting(
        self,
        setting: dict[str, Any],
        task_config: BacktestTaskConfig | dict[str, Any] | None,
    ) -> dict[str, Any]:
        """把任务级参数覆盖到策略参数上，形成最终回测 setting。"""
        config = self._normalize_task_config(task_config)
        merged = dict(setting)
        merged["initial_capital_wan"] = config.initial_capital_wan
        merged["benchmark_name"] = config.benchmark_name
        merged["rebalance_interval_type"] = config.rebalance_interval_type
        merged["rebalance_interval_value"] = config.rebalance_interval_value
        merged["max_position_pct"] = config.max_position_pct
        merged["max_hold_count"] = config.max_hold_count
        merged["exclude_redeem_days_below"] = config.exclude_redeem_days_below
        merged["take_profit_pct"] = config.take_profit_pct
        merged["stop_loss_pct"] = config.stop_loss_pct
        merged["candidate_count"] = max(
            int(round(self._to_float(merged.get("candidate_count"), float(config.max_hold_count)))),
            config.max_hold_count,
        )
        return merged

    def _position_ratio(self, *, setting: dict[str, Any], max_hold_count: int) -> float:
        """根据持仓数和单标的上限，计算单个仓位的目标权重。"""
        if max_hold_count <= 0:
            return 0.0
        base_ratio = 1.0 / max_hold_count
        cap_ratio = self._to_float(setting.get("max_position_pct"), 100.0) / 100.0
        cap_ratio = max(0.0, min(1.0, cap_ratio))
        return min(base_ratio, cap_ratio if cap_ratio > 0 else base_ratio)

    def _should_rebalance(
        self,
        *,
        index: int,
        trade_date: str,
        last_rebalance_date: str | None,
        last_rebalance_index: int,
        setting: dict[str, Any],
    ) -> bool:
        """根据任务配置判断今天是否到达调仓日。"""
        if index == 0:
            return True
        freq_type = str(setting.get("rebalance_interval_type", "trade_day") or "trade_day")
        freq_value = max(1, int(round(self._to_float(setting.get("rebalance_interval_value"), 1.0))))
        if freq_type == "trade_day":
            return (index - last_rebalance_index) >= freq_value

        current_date = self._parse_iso_date(trade_date)
        previous_date = self._parse_iso_date(last_rebalance_date)
        if not current_date or not previous_date:
            return True
        if freq_type == "calendar_day":
            return (current_date - previous_date).days >= freq_value
        if freq_type == "week":
            return (current_date - previous_date).days >= 7 * freq_value
        if freq_type == "month":
            month_delta = (current_date.year - previous_date.year) * 12 + (current_date.month - previous_date.month)
            return month_delta >= freq_value
        return (index - last_rebalance_index) >= freq_value

    def _should_exit_by_price_limits(
        self,
        *,
        setting: dict[str, Any],
        item: dict[str, Any],
        current_price: float,
    ) -> bool:
        """根据止盈/止损阈值判断是否应当强制卖出。"""
        buy_price = self._to_float(item.get("buy_price"), current_price)
        if buy_price <= 0 or current_price <= 0:
            return False
        pnl_pct = (current_price - buy_price) / buy_price * 100.0
        take_profit_pct = setting.get("take_profit_pct")
        if take_profit_pct is not None and pnl_pct >= self._to_float(take_profit_pct, 0.0):
            return True
        stop_loss_pct = setting.get("stop_loss_pct")
        if stop_loss_pct is not None and pnl_pct <= -self._to_float(stop_loss_pct, 0.0):
            return True
        return False

    def _resolve_setting_for_combo(self, *, combo_id: str, template_name: str) -> dict[str, Any]:
        template_id = ""
        candidate = self._find_candidate(combo_id, template_name=template_name if template_name else None)
        if candidate and candidate.template_id:
            template_id = candidate.template_id
        if not template_id and template_name:
            for row in self._templates:
                if row.name == template_name:
                    template_id = row.id
                    break

        if not template_id:
            raise ValueError(f"unknown template for combo: combo_id={combo_id}, template={template_name or '--'}")
        resolved = self._build_candidate_setting(template_id=template_id, combo_id=combo_id)
        if not resolved:
            raise ValueError(f"invalid combo for template: combo_id={combo_id}, template={template_name or template_id}")
        self._candidate_settings[combo_id] = dict(resolved)
        return resolved

    def _build_candidate_setting(self, *, template_id: str, combo_id: str) -> dict[str, Any]:
        cfg = self._template_configs.get(template_id) or self._default_config(
            template_id=template_id,
            updated_at=_now_readable(),
        )
        combo_seq = self._parse_combo_sequence(combo_id)
        enabled_rows = [row for row in cfg.parameter_space if row.enabled and row.factor_key in cfg.factor_keys]
        if not enabled_rows:
            return self._adapter.default_setting()
        if combo_seq is None or combo_seq <= 0:
            # Backward compatibility fallback for legacy/custom combo ids.
            row_map: dict[str, StrategyParamSpaceRow] = {row.factor_key: row for row in enabled_rows}
            values: dict[str, Any] = {}
            for factor_key, row in row_map.items():
                values[factor_key] = self._pick_param_value(combo_id=combo_id, row=row)
            return self._build_setting_from_factor_values(values)

        factor_keys = [row.factor_key for row in enabled_rows]
        all_choices = [self._choices_for_param_row(row) for row in enabled_rows]
        for choices in all_choices:
            if not choices:
                return self._adapter.default_setting()

        total_combos = 1
        for choices in all_choices:
            total_combos *= len(choices)
        if combo_seq > total_combos:
            return {}

        idx0 = combo_seq - 1
        picked: list[Any] = [None for _ in all_choices]
        # Match _iter_template_settings() product order without building cartesian list.
        for pos in range(len(all_choices) - 1, -1, -1):
            choices = all_choices[pos]
            picked[pos] = choices[idx0 % len(choices)]
            idx0 //= len(choices)

        return self._build_setting_from_factor_values(dict(zip(factor_keys, picked)))

    @staticmethod
    def _parse_combo_sequence(combo_id: str) -> int | None:
        text = str(combo_id or "").strip().upper()
        if not text.startswith("CMB-"):
            return None
        suffix = text.split("-", 1)[1]
        if not suffix.isdigit():
            return None
        try:
            value = int(suffix)
        except Exception:
            return None
        return value if value > 0 else None

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
        """把原始回测统计值映射成排行榜使用的指标。"""
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
        recent_1y = total_return if window_name in {"1y", "1w"} else cagr
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
        """计算组合稳健分。

        这是项目内部定义的综合评分，不是标准金融指标；
        主要用于在多个回测指标之间给出一个可排序的“综合质量分”。
        """
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

    def _upsert_leaderboard_row(self, row: BacktestLeaderboardRow, *, business_date: str | None = None) -> None:
        persisted_entries: list[dict[str, Any]] = []
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
                self._leaderboard_business_dates[(row.combo_id, row.rule_pack_id, row.window)] = (
                    business_date or self._leaderboard_business_dates.get((row.combo_id, row.rule_pack_id, row.window)) or date.today().isoformat()
                )
                replaced = True
                break
            if not replaced:
                self._leaderboard.append(row)
                self._leaderboard_business_dates[(row.combo_id, row.rule_pack_id, row.window)] = (
                    business_date or date.today().isoformat()
                )

            ordered = sorted(
                self._leaderboard,
                key=lambda item: (item.robust_score, item.cagr, -item.mdd),
                reverse=True,
            )
            self._leaderboard = [
                item.model_copy(update={"rank": idx + 1})
                for idx, item in enumerate(ordered)
            ]
            for item in self._leaderboard:
                key = (item.combo_id, item.rule_pack_id, item.window)
                persisted_entries.append(
                    {
                        "business_date": self._leaderboard_business_dates.get(key, date.today().isoformat()),
                        "row": item.model_dump(),
                    }
                )

        self._store.replace_leaderboard(persisted_entries)

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
            cancelled = sum(1 for row in combo_jobs if row.status == "cancelled")
            running = sum(1 for row in combo_jobs if row.status == "running")
            queued = sum(1 for row in combo_jobs if row.status == "queued")

            done = finished + failed + cancelled
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
            elif cancelled > 0 and finished == 0:
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
    def _candidate_matches(self, combo_id: str, *, template_name: str | None = None) -> list[CandidateRow]:
        combo = str(combo_id or "").strip()
        if not combo:
            return []
        template_filter = str(template_name or "").strip()
        matched: list[CandidateRow] = []
        for row in self._candidates:
            if row.combo_id != combo:
                continue
            if template_filter and row.template != template_filter:
                continue
            matched.append(row)
        return matched

    def _find_candidate(self, combo_id: str, template_name: str | None = None) -> CandidateRow | None:
        matched = self._candidate_matches(combo_id, template_name=template_name)
        if not matched:
            return None
        if template_name:
            return matched[0]

        # Without template filter, reject ambiguous combo ids across templates.
        template_names = {row.template for row in matched}
        if len(template_names) > 1:
            return None
        return matched[0]

    def _is_displayable_backtest_job(self, row: BacktestJobRow) -> bool:
        if str(row.job_id).startswith("OPT-"):
            return self._get_optimize_task(row.job_id) is not None
        if not row.combo_id or not row.template:
            return False

        combo_seq = self._parse_combo_sequence(row.combo_id)
        if combo_seq is None:
            return False

        template_id = ""
        for template in self._templates:
            if template.name == row.template:
                template_id = template.id
                break
        if not template_id:
            return False

        cfg = self._template_configs.get(template_id)
        if not cfg:
            return False
        if cfg.combo_size > 0 and combo_seq > cfg.combo_size:
            return False
        return True

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
        normalized_factor_keys = [self._normalize_factor_key_name(key) for key in factor_keys]
        keyed: dict[str, StrategyParamSpaceRow] = {}
        for row in parameter_space:
            normalized_key = self._normalize_factor_key_name(row.factor_key)
            keyed[normalized_key] = row.model_copy(update={"factor_key": normalized_key})
        normalized: list[StrategyParamSpaceRow] = []

        for factor_key in normalized_factor_keys:
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
            "price_benchmark": (106, 124, 2),
            "premium_benchmark": (16, 34, 2),
            "stock_weight": (0.20, 0.35, 0.05),
            "premium_weight": (0.15, 0.35, 0.05),
            "volatility_benchmark": (20, 35, 5),
            "max_candidate_price": (130, 200, 10),
            "candidate_count": (5, 15, 5),
            "outstanding_amount_weight": (0.10, 0.20, 0.05),
            "max_hold_count": (5, 10, 5),
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
            return "全周期"
        if window_name == "3y":
            return "近3年"
        if window_name == "1w":
            return "近1周"
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
        # Prefer SQLite store; fallback to legacy JSON once for migration.
        stored_templates, stored_configs = self._store.load_templates_and_configs()
        if stored_templates:
            templates = [StrategyTemplateRow.model_validate(item) for item in stored_templates]
            configs = {
                template_id: self._normalize_template_config(
                    StrategyTemplateConfigResponse.model_validate(config)
                )
                for template_id, config in stored_configs.items()
            }
            return templates, configs

        if self._templates_file.exists():
            try:
                payload = json.loads(self._templates_file.read_text(encoding="utf-8"))
                templates = [StrategyTemplateRow.model_validate(item) for item in payload.get("templates", [])]
                configs = {
                    template_id: self._normalize_template_config(
                        StrategyTemplateConfigResponse.model_validate(config)
                    )
                    for template_id, config in (payload.get("configs", {}) or {}).items()
                }
                if templates:
                    self._store.replace_templates_and_configs(
                        templates=[row.model_dump() for row in templates],
                        configs={key: value.model_dump() for key, value in configs.items()},
                    )
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
        self._store.replace_templates_and_configs(
            templates=[template.model_dump()],
            configs={template.id: config.model_dump()},
        )
        return [template], {template.id: config}

    def _save_templates_and_configs(self) -> None:
        self._store.replace_templates_and_configs(
            templates=[row.model_dump() for row in self._templates],
            configs={key: value.model_dump() for key, value in self._template_configs.items()},
        )

    @classmethod
    def _normalize_factor_key_name(cls, factor_key: str) -> str:
        return cls._LEGACY_FACTOR_KEY_ALIASES.get(str(factor_key), str(factor_key))

    def _normalize_template_config(
        self,
        config: StrategyTemplateConfigResponse,
    ) -> StrategyTemplateConfigResponse:
        factor_keys: list[str] = []
        seen_keys: set[str] = set()
        for factor_key in config.factor_keys:
            normalized_key = self._normalize_factor_key_name(factor_key)
            if normalized_key in seen_keys:
                continue
            seen_keys.add(normalized_key)
            factor_keys.append(normalized_key)

        normalized_rows: list[StrategyParamSpaceRow] = []
        seen_rows: set[str] = set()
        for row in config.parameter_space:
            normalized_key = self._normalize_factor_key_name(row.factor_key)
            if normalized_key in seen_rows:
                continue
            seen_rows.add(normalized_key)
            normalized_rows.append(row.model_copy(update={"factor_key": normalized_key}))

        normalized_rows = self._normalize_parameter_space(
            factor_keys=factor_keys,
            parameter_space=normalized_rows,
        )
        combo_size = self._calculate_combo_size(
            factor_keys=factor_keys,
            parameter_space=normalized_rows,
        )
        return config.model_copy(
            update={
                "factor_keys": factor_keys,
                "parameter_space": normalized_rows,
                "combo_size": combo_size,
            }
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

    def _load_jobs_and_context(self) -> tuple[list[BacktestJobRow], dict[str, dict[str, Any]]]:
        jobs: list[BacktestJobRow] = []
        context_map: dict[str, dict[str, Any]] = {}
        for item in self._store.load_jobs():
            payload = dict(item.get("row") or {})
            payload.setdefault("business_date", item.get("business_date") or date.today().isoformat())
            payload.setdefault("created_at", item.get("created_at") or _now_readable())
            try:
                row = BacktestJobRow.model_validate(payload)
            except Exception:
                continue
            jobs.append(row)
            context_map[row.job_id] = {
                "window_name": item.get("window_name") or "full",
                "start_date": self._parse_iso_date(item.get("start_date")),
                "end_date": self._parse_iso_date(item.get("end_date")),
                "setting": dict(item.get("setting") or self._adapter.default_setting()),
                "cancel_requested": bool(item.get("cancel_requested")),
                "business_date": row.business_date or date.today().isoformat(),
                "created_at": row.created_at or _now_readable(),
            }
        return jobs, context_map

    def _load_leaderboard_rows(self) -> tuple[list[BacktestLeaderboardRow], dict[tuple[str, str, str], str]]:
        rows: list[BacktestLeaderboardRow] = []
        business_dates: dict[tuple[str, str, str], str] = {}
        for item in self._store.load_leaderboard():
            payload = item.get("row") or {}
            try:
                row = BacktestLeaderboardRow.model_validate(payload)
            except Exception:
                continue
            rows.append(row)
            key = (row.combo_id, row.rule_pack_id, row.window)
            business_dates[key] = str(item.get("business_date") or date.today().isoformat())

        ordered = sorted(
            rows,
            key=lambda item: (item.robust_score, item.cagr, -item.mdd),
            reverse=True,
        )
        ranked = [row.model_copy(update={"rank": idx + 1}) for idx, row in enumerate(ordered)]
        return ranked, business_dates

    def _load_optimize_state(
        self,
    ) -> tuple[
        list[StrategyOptimizeTaskRow],
        dict[str, list[StrategyOptimizeResultRow]],
        dict[str, list[StrategyTopBondRow]],
    ]:
        tasks: list[StrategyOptimizeTaskRow] = []
        for payload in self._store.load_optimize_tasks():
            try:
                row = StrategyOptimizeTaskRow.model_validate(payload)
            except Exception:
                continue
            tasks.append(row)
        tasks.sort(key=lambda item: (item.created_at, item.task_id), reverse=True)

        results: dict[str, list[StrategyOptimizeResultRow]] = {}
        for item in self._store.load_optimize_result_rows():
            task_id = str(item.get("task_id") or "")
            payload = item.get("row") or {}
            if not task_id:
                continue
            try:
                row = StrategyOptimizeResultRow.model_validate(payload)
            except Exception:
                continue
            results.setdefault(task_id, []).append(row)
        for task_id, rows in results.items():
            results[task_id] = self._rank_optimize_rows(rows)

        top_bonds: dict[str, list[StrategyTopBondRow]] = {}
        for item in self._store.load_optimize_top_bond_rows():
            task_id = str(item.get("task_id") or "")
            payload = item.get("row") or {}
            if not task_id:
                continue
            try:
                row = StrategyTopBondRow.model_validate(payload)
            except Exception:
                continue
            top_bonds.setdefault(task_id, []).append(row)
        for task_id, rows in top_bonds.items():
            ordered = sorted(rows, key=lambda item: item.rank)
            top_bonds[task_id] = [row.model_copy(update={"rank": idx + 1}) for idx, row in enumerate(ordered)]

        return tasks, results, top_bonds

    def _mark_unfinished_jobs_as_failed_after_restart(self) -> None:
        stale: list[tuple[BacktestJobRow, dict[str, Any]]] = []
        with self._lock:
            updated_rows: list[BacktestJobRow] = []
            for row in self._jobs:
                if row.status not in {"queued", "running"}:
                    updated_rows.append(row)
                    continue
                recovered = row.model_copy(
                    update={
                        "status": "failed",
                        "eta": "interrupted-after-restart",
                    }
                )
                updated_rows.append(recovered)
                context = self._job_context.get(row.job_id, {})
                stale.append((recovered, context))
            self._jobs = updated_rows

        for row, context in stale:
            self._store.upsert_job(row=row.model_dump(), context=context)

    def _mark_unfinished_optimize_tasks_as_failed_after_restart(self) -> None:
        stale: list[StrategyOptimizeTaskRow] = []
        with self._lock:
            updated_rows: list[StrategyOptimizeTaskRow] = []
            for row in self._optimize_tasks:
                if row.status not in {"queued", "running"}:
                    updated_rows.append(row)
                    continue
                recovered = row.model_copy(
                    update={
                        "status": "failed",
                        "progress": row.progress if row.progress > 0 else 1,
                        "eta": "--",
                        "finished_at": _now_readable(),
                        "message": "interrupted-after-restart",
                    }
                )
                updated_rows.append(recovered)
                stale.append(recovered)
            self._optimize_tasks = updated_rows

        for row in stale:
            self._store.upsert_optimize_task(row=row.model_dump())
            self._sync_optimize_task_as_backtest_job(row)

    def _is_job_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            context = self._job_context.get(job_id)
            if context is not None:
                return bool(context.get("cancel_requested"))
        context = self._store.get_job_context(job_id)
        if not context:
            return False
        return bool(context.get("cancel_requested"))

    @staticmethod
    def _derive_job_seq(jobs: list[BacktestJobRow]) -> int:
        max_seq = 0
        for item in jobs:
            try:
                max_seq = max(max_seq, int(item.strategy_id.split("-", 1)[1]))
            except Exception:
                pass
            try:
                suffix = item.job_id.rsplit("-", 1)[1]
                max_seq = max(max_seq, int(suffix))
            except Exception:
                pass
        return max_seq

    @staticmethod
    def _derive_opt_task_seq(tasks: list[StrategyOptimizeTaskRow]) -> int:
        max_seq = 0
        for item in tasks:
            task_id = str(item.task_id or "")
            if not task_id.startswith("OPT-"):
                continue
            try:
                suffix = task_id.rsplit("-", 1)[1]
                max_seq = max(max_seq, int(suffix))
            except Exception:
                continue
        return max_seq
