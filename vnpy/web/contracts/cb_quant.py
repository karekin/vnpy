from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

WindowName = Literal["full", "3y", "1y", "1w"]
JobStatus = Literal["queued", "running", "finished", "failed", "cancelled"]
OptimizeTaskStatus = Literal["queued", "running", "finished", "failed"]
OptimizeShardStatus = Literal["queued", "running", "finished", "failed"]
OptimizeBatchStatus = Literal["queued", "running", "finished", "failed"]
CompareCategory = Literal["return", "risk", "trade"]
RuleSourceMode = Literal["inherit", "candidate", "custom"]
StrategyTemplateStatus = Literal["active", "draft", "archived"]
CandidateSource = Literal["generated", "mock"]


class CandidateRow(BaseModel):
    rank: int
    template_id: str | None = None
    template: str
    combo_id: str
    est_combos: int
    status: str = "pending_backtest"
    pass_rate: float | None = None
    window: WindowName
    source: CandidateSource = "generated"
    run_id: str | None = None
    generated_at: str | None = None


class CandidateListResponse(BaseModel):
    items: list[CandidateRow]
    total: int


class BacktestJobRow(BaseModel):
    job_id: str
    strategy_id: str
    combo_id: str
    rule_pack_id: str
    template: str
    window: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    business_date: str | None = None
    created_at: str | None = None
    started_at: str
    eta: str
    worker: str


class BacktestJobListResponse(BaseModel):
    items: list[BacktestJobRow]
    total: int
    page: int
    page_size: int


class BacktestLeaderboardRow(BaseModel):
    rank: int
    strategy_id: str
    combo_id: str
    rule_pack_id: str
    template: str
    cagr: float
    mdd: float
    calmar: float
    win_rate: float
    turnover: float
    recent_1y: float
    robust_score: float
    window: WindowName


class BacktestLeaderboardResponse(BaseModel):
    items: list[BacktestLeaderboardRow]
    total: int
    page: int
    page_size: int


class BacktestCompareRow(BaseModel):
    metric: str
    category: CompareCategory
    baseline: float
    candidate_a: float
    candidate_b: float
    candidate_c: float


class BacktestCompareResponse(BaseModel):
    items: list[BacktestCompareRow]
    total: int


class BacktestCreateJobsRequest(BaseModel):
    combo_id: str = Field(min_length=3)
    template: str | None = None
    source_mode: RuleSourceMode = "candidate"
    rule_pack_id: str | None = None
    windows: list[WindowName] = Field(default_factory=lambda: ["full", "3y", "1y"])
    business_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    capital_wan: float | None = Field(default=100, gt=0)
    benchmark: str | None = "沪深300"
    est_strategies: int | None = Field(default=None, ge=1)


class BacktestCreateJobsResponse(BaseModel):
    batch_id: str
    combo_id: str
    rule_pack_id: str
    source_mode: RuleSourceMode
    created_count: int
    windows: list[WindowName]
    jobs: list[BacktestJobRow]
    message: str


class BacktestJobBatchDeleteRequest(BaseModel):
    job_ids: list[str] = Field(min_length=1)


class BacktestJobBatchDeleteResponse(BaseModel):
    ok: bool = True
    affected: int = 0
    missing_ids: list[str] = Field(default_factory=list)
    blocked_ids: list[str] = Field(default_factory=list)
    message: str = "ok"


class BacktestStatsResponse(BaseModel):
    running_jobs: int
    queued_jobs: int
    finished_jobs: int
    failed_jobs: int
    cancelled_jobs: int = 0
    rule_pack_count: int
    top_cagr: float


class StrategyTemplateRow(BaseModel):
    id: str
    name: str
    version: str
    status: StrategyTemplateStatus
    factor_count: int = Field(ge=0)
    rebalance: str
    risk_preset: str
    combo_size: int = Field(ge=0)
    owner: str
    updated_at: str


class StrategyTemplateListResponse(BaseModel):
    items: list[StrategyTemplateRow]
    total: int
    page: int
    page_size: int


class StrategyTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    owner: str = Field(default="quant_new", min_length=1, max_length=64)


class StrategyTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    status: StrategyTemplateStatus | None = None
    rebalance: str | None = None
    risk_preset: str | None = None
    owner: str | None = Field(default=None, min_length=1, max_length=64)


class StrategyTemplateBatchEnableRequest(BaseModel):
    template_ids: list[str] = Field(min_length=1)
    status: StrategyTemplateStatus = "active"


class StrategyTemplateBatchDeleteRequest(BaseModel):
    template_ids: list[str] = Field(min_length=1)


class StrategyTemplateBatchResponse(BaseModel):
    ok: bool = True
    affected: int = 0
    missing_ids: list[str] = Field(default_factory=list)
    message: str = "ok"


class StrategyTemplateConfigRequest(BaseModel):
    factor_keys: list[str] = Field(default_factory=list)
    expression_draft: str = ""
    parameter_space: list["StrategyParamSpaceRow"] = Field(default_factory=list)


class StrategyTemplateConfigResponse(BaseModel):
    template_id: str
    factor_keys: list[str]
    expression_draft: str
    parameter_space: list["StrategyParamSpaceRow"] = Field(default_factory=list)
    combo_size: int = Field(default=0, ge=0)
    updated_at: str


class StrategyTemplateDetailResponse(BaseModel):
    template: StrategyTemplateRow
    config: StrategyTemplateConfigResponse


class StrategyExpandFactorCombosRequest(BaseModel):
    min_factor_count: int = Field(default=1, ge=1)
    max_factor_count: int | None = Field(default=None, ge=1)
    max_strategies: int | None = Field(default=None, ge=1)


class StrategyExpandFactorCombosResponse(BaseModel):
    source_template_id: str
    source_template_name: str
    min_factor_count: int
    max_factor_count: int
    total_subsets: int
    created_count: int
    truncated: bool = False
    message: str


class StrategyGenerateStrongPairsResponse(BaseModel):
    factor_count: int
    total_pairs: int
    created_count: int
    message: str


class StrategyParamSpaceRow(BaseModel):
    factor_key: str
    value_type: Literal["number", "enum"] = "number"
    enabled: bool = True
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    enum_values: list[str] = Field(default_factory=list)


class CandidateGenerateRequest(BaseModel):
    windows: list[WindowName] = Field(default_factory=lambda: ["full", "3y", "1y"])
    rows_per_window: int = Field(default=5, ge=1, le=100)


class CandidateGenerateResponse(BaseModel):
    run_id: str
    template_id: str
    template_name: str
    created_count: int
    est_combos: int
    windows: list[WindowName]
    items: list[CandidateRow]
    message: str


class HistoryDataSummaryResponse(BaseModel):
    snapshot_count: int
    date_start: str | None = None
    date_end: str | None = None
    latest_trade_date: str | None = None
    latest_bond_count: int = 0
    data_dir: str


class HistorySyncResponse(BaseModel):
    ok: bool = True
    mode: str
    source: str
    trade_date: str
    upserted: int
    message: str


class HistorySyncStatusResponse(BaseModel):
    has_log: bool
    sync_at: str | None = None
    mode: str | None = None
    source: str | None = None
    trade_date: str | None = None
    upserted: int = 0
    status: str | None = None
    message: str | None = None


class TushareSyncRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    max_trade_days: int = Field(default=1500, ge=0, le=5000)
    incremental: bool = False


class TushareSyncResponse(BaseModel):
    ok: bool = True
    mode: str
    source: str
    start_date: str
    end_date: str
    trade_days: int
    cb_daily_rows: int
    stock_daily_rows: int
    event_rows: int = 0
    factor_rows: int
    snapshot_rows: int
    message: str


class TushareSyncStatusResponse(BaseModel):
    has_log: bool
    sync_at: str | None = None
    mode: str | None = None
    source: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    trade_days: int = 0
    cb_daily_rows: int = 0
    stock_daily_rows: int = 0
    event_rows: int = 0
    factor_rows: int = 0
    snapshot_rows: int = 0
    status: str | None = None
    message: str | None = None


class TushareDataSummaryResponse(BaseModel):
    cb_trade_days: int
    cb_date_start: str | None = None
    cb_date_end: str | None = None
    factor_trade_days: int
    factor_date_start: str | None = None
    factor_date_end: str | None = None
    event_rows: int = 0
    db_path: str


class BacktestTaskConfig(BaseModel):
    initial_capital_wan: float = Field(default=100.0, gt=0)
    benchmark_name: str = "转债等权"
    rebalance_interval_type: Literal["trade_day", "calendar_day", "week", "month"] = "trade_day"
    rebalance_interval_value: int = Field(default=1, ge=1, le=365)
    max_position_pct: float = Field(default=20.0, ge=0, le=100)
    max_hold_count: int = Field(default=12, ge=1, le=200)
    exclude_redeem_days_below: int | None = Field(default=None, ge=0, le=365)
    take_profit_pct: float | None = Field(default=None, ge=0)
    stop_loss_pct: float | None = Field(default=None, ge=0)


class StrategyOptimizeTaskCreateRequest(BaseModel):
    template_id: str = Field(min_length=3)
    batch_id: str | None = None
    windows: list[WindowName] = Field(default_factory=lambda: ["full", "3y", "1y"])
    start_date: date | None = None
    end_date: date | None = None
    top_n: int = Field(default=20, ge=1, le=200)
    max_combinations: int | None = Field(default=None, ge=1)
    current_top_n: int = Field(default=20, ge=1, le=200)
    task_config: BacktestTaskConfig = Field(default_factory=BacktestTaskConfig)


class StrategyOptimizeTaskBatchCreateRequest(BaseModel):
    template_ids: list[str] = Field(min_length=1)
    batch_id: str | None = None
    windows: list[WindowName] = Field(default_factory=lambda: ["full", "3y", "1y"])
    start_date: date | None = None
    end_date: date | None = None
    top_n: int = Field(default=20, ge=1, le=200)
    max_combinations: int | None = Field(default=None, ge=1)
    current_top_n: int = Field(default=20, ge=1, le=200)
    task_config: BacktestTaskConfig = Field(default_factory=BacktestTaskConfig)


class StrategyOptimizeTaskRow(BaseModel):
    task_id: str
    batch_id: str | None = None
    template_id: str
    template_name: str
    status: OptimizeTaskStatus
    progress: int = Field(ge=0, le=100)
    total_combinations: int = Field(ge=0)
    evaluated_combinations: int = Field(ge=0)
    windows: list[WindowName]
    start_date: str | None = None
    end_date: str | None = None
    eta: str = "--"
    message: str = ""
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    shard_count: int = Field(default=0, ge=0)
    queued_shards: int = Field(default=0, ge=0)
    running_shards: int = Field(default=0, ge=0)
    finished_shards: int = Field(default=0, ge=0)
    failed_shards: int = Field(default=0, ge=0)
    top_n: int = Field(default=20, ge=1, le=200)
    current_top_n: int = Field(default=20, ge=1, le=200)
    task_config: BacktestTaskConfig = Field(default_factory=BacktestTaskConfig)


class StrategyOptimizeBatchRow(BaseModel):
    batch_id: str
    status: OptimizeBatchStatus
    task_count: int = Field(default=0, ge=0)
    queued_tasks: int = Field(default=0, ge=0)
    running_tasks: int = Field(default=0, ge=0)
    finished_tasks: int = Field(default=0, ge=0)
    failed_tasks: int = Field(default=0, ge=0)
    total_combinations: int = Field(default=0, ge=0)
    evaluated_combinations: int = Field(default=0, ge=0)
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    message: str = ""


class StrategyOptimizeShardRow(BaseModel):
    shard_id: str
    task_id: str
    stage: Literal["stage1", "stage2", "full"]
    sequence: int = Field(ge=1)
    status: OptimizeShardStatus
    combo_start: int | None = Field(default=None, ge=1)
    combo_end: int | None = Field(default=None, ge=1)
    combo_ids: list[str] = Field(default_factory=list)
    total_combinations: int = Field(default=0, ge=0)
    evaluated_combinations: int = Field(default=0, ge=0)
    result_count: int = Field(default=0, ge=0)
    top_combo_id: str | None = None
    progress: int = Field(default=0, ge=0, le=100)
    eta: str = "--"
    message: str = ""
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class StrategyOptimizeTaskListResponse(BaseModel):
    items: list[StrategyOptimizeTaskRow]
    total: int
    page: int
    page_size: int


class StrategyOptimizeBatchListResponse(BaseModel):
    items: list[StrategyOptimizeBatchRow]
    total: int
    page: int
    page_size: int


class StrategyOptimizeResultRow(BaseModel):
    rank: int
    task_id: str | None = None
    template_id: str | None = None
    template_name: str | None = None
    combo_id: str
    robust_score: float
    cagr: float
    mdd: float
    calmar: float
    win_rate: float
    turnover: float
    recent_1y: float
    total_return_pct: float
    params: dict


class StrategyTopBondRow(BaseModel):
    rank: int
    bond_id: str
    bond_name: str
    price: float
    premium_rt: float
    dblow: float
    amount_wan: float | None = None
    score: float
    update_time: str


class StrategyOptimizeTaskDetailResponse(BaseModel):
    task: StrategyOptimizeTaskRow
    top_strategies: list[StrategyOptimizeResultRow]
    top_bonds: list[StrategyTopBondRow]
    shards: list[StrategyOptimizeShardRow] = Field(default_factory=list)


class StrategyOptimizeBatchDetailResponse(BaseModel):
    batch: StrategyOptimizeBatchRow
    tasks: list[StrategyOptimizeTaskRow]


class StrategyOptimizeTaskCreateResponse(BaseModel):
    task: StrategyOptimizeTaskRow
    message: str


class StrategyOptimizeTaskBatchCreateResponse(BaseModel):
    batch_id: str
    created_count: int = 0
    bundle_count: int = 0
    tasks: list[StrategyOptimizeTaskRow] = Field(default_factory=list)
    failed_template_ids: list[str] = Field(default_factory=list)
    failed_template_names: list[str] = Field(default_factory=list)
    message: str


class StrategyOptimizeSummaryResponse(BaseModel):
    top_strategies: list[StrategyOptimizeResultRow]
    top_bonds: list[StrategyTopBondRow]
    finished_task_count: int = 0
    total_result_count: int = 0
    message: str = ""


class StrategyBacktestMetricRow(BaseModel):
    strategy_combo: str
    total_return_pct: float | None = None
    cumulative_asset_wan: float | None = None
    annual_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    avg_turnover_pct: float | None = None
    trade_cycles: float | None = None
    profit_cycles: float | None = None
    loss_cycles: float | None = None
    win_rate_pct: float | None = None
    profit_loss_ratio: float | None = None
    avg_cycle_return_pct: float | None = None
    max_cycle_profit_pct: float | None = None
    max_cycle_loss_pct: float | None = None
    max_drawdown_duration_days: float | None = None


class StrategyBacktestCurvePoint(BaseModel):
    date: str
    strategy_cum_return_pct: float
    benchmark_cum_return_pct: float
    relative_excess_pct: float
    absolute_excess_pct: float
    drawdown_pct: float
    avg_drawdown_pct: float


class StrategyBacktestDistributionRow(BaseModel):
    period: str
    strategy_return_pct: float
    benchmark_return_pct: float
    excess_return_pct: float


class StrategyBacktestRotationRow(BaseModel):
    rebalance_date: str
    weekday: str
    holdings: str
    holding_count: int
    turnover_pct: float
    period_return_pct: float
    cumulative_return_pct: float
    nav_wan: float


class StrategyOptimizeTaskAnalysisResponse(BaseModel):
    task_id: str
    template_id: str
    template_name: str
    combo_id: str
    benchmark_name: str
    window: WindowName
    metric_rows: list[StrategyBacktestMetricRow]
    curve: list[StrategyBacktestCurvePoint]
    yearly_distribution: list[StrategyBacktestDistributionRow]
    monthly_distribution: list[StrategyBacktestDistributionRow]
    weekly_distribution: list[StrategyBacktestDistributionRow]
    rotations: list[StrategyBacktestRotationRow]
    message: str = ""


class StrategyOptimizeTaskAiInsightRequest(BaseModel):
    combo_id: str | None = None
    initial_capital_wan: float | None = Field(default=None, gt=0)


class StrategyOptimizeTaskAiInsightResponse(BaseModel):
    ok: bool = True
    enabled: bool = True
    provider: str = "kimi"
    model: str = ""
    task_id: str
    combo_id: str
    context_markdown: str = ""
    prompt_markdown: str = ""
    analysis_markdown: str = ""
    executive_summary: str = ""
    return_drivers: list[str] = Field(default_factory=list)
    risk_exposures: list[str] = Field(default_factory=list)
    parameter_interpretation: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    message: str = ""
    generated_at: str | None = None
    cached: bool = False


class StrategyOptimizeTaskAiCompareRequest(BaseModel):
    combo_ids: list[str] = Field(min_length=2, max_length=2)
    initial_capital_wan: float | None = Field(default=None, gt=0)


class StrategyOptimizeTaskAiCompareResponse(BaseModel):
    ok: bool = True
    enabled: bool = True
    provider: str = "kimi"
    model: str = ""
    task_id: str
    combo_ids: list[str] = Field(default_factory=list)
    context_markdown: str = ""
    prompt_markdown: str = ""
    analysis_markdown: str = ""
    executive_summary: str = ""
    winner_combo_id: str = ""
    winner_reason: list[str] = Field(default_factory=list)
    combo_a_strengths: list[str] = Field(default_factory=list)
    combo_a_risks: list[str] = Field(default_factory=list)
    combo_b_strengths: list[str] = Field(default_factory=list)
    combo_b_risks: list[str] = Field(default_factory=list)
    what_to_verify_next: list[str] = Field(default_factory=list)
    message: str = ""
    generated_at: str | None = None
    cached: bool = False


class WsEvent(BaseModel):
    event: str
    payload: dict


class BondMarketRow(BaseModel):
    bond_id: str
    bond_name: str
    price: float
    increase_rt: float
    stock_id: str
    stock_name: str
    stock_price: float | None = None
    stock_increase_rt: float | None = None
    stock_pb: float | None = None
    convert_price: float | None = None
    pure_bond_value: float | None = None
    premium_rt: float
    convert_value: float
    dblow: float
    option_value: float | None = None
    stock_volatility: float | None = None
    put_trigger_price: float | None = None
    redeem_trigger_price: float | None = None
    float_mv_ratio: float | None = None
    fund_holding_ratio: float | None = None
    maturity_date: str | None = None
    remain_years: float | None = None
    remain_scale_yi: float | None = None
    amount_wan: float | None = None
    turnover_rt: float | None = None
    expiry_ytm_pre_tax: float | None = None
    put_ytm: float | None = None
    volume_wan: float
    issue_scale_yi: float | None = None
    rating: str | None = None
    listed_date: str | None = None
    convert_start_date: str | None = None
    subscribe_date: str | None = None
    source: str
    update_time: str


class BondMarketResponse(BaseModel):
    items: list[BondMarketRow]
    total: int
    source: str
    snapshot_time: str
    fallback_used: bool = False
    fallback_reason: str | None = None


class FactorCatalogRow(BaseModel):
    id: str
    factor_name: str
    factor_key: str
    factor_type: int
    expression: str
    expression_type: int
    enabled: bool
    remark: str = ""
    view_style: int = 0
    view_precision: int = 2
    view_color: bool = False
    view_ratio: float = 1
    view_unit: str = ""
    support_level: str = "disabled"
    template_selectable: bool = False
    strategy_kind: str = "plain"
    setting_key: str | None = None
    usage_hint: str = ""
    param_value_type: str | None = None
    param_min_value: float | None = None
    param_max_value: float | None = None
    param_step: float | None = None
    param_enum_values: list[str] = Field(default_factory=list)


class FactorCatalogCategory(BaseModel):
    category_name: str
    category_key: str
    factors: list[FactorCatalogRow]


class FactorCatalogResponse(BaseModel):
    items: list[FactorCatalogCategory]
    total_categories: int
    total_factors: int


class FunctionParameterCatalogRow(BaseModel):
    name: str
    description: str
    type_name: str
    type: str


class FunctionCatalogRow(BaseModel):
    name: str
    formular: str
    description: str
    parameter_size: int
    parameters: list[FunctionParameterCatalogRow]


class FunctionCatalogCategory(BaseModel):
    category_name: str
    category_key: str
    functions: list[FunctionCatalogRow]


class FunctionCatalogResponse(BaseModel):
    items: list[FunctionCatalogCategory]
    total_categories: int
    total_functions: int
