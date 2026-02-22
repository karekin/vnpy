from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

WindowName = Literal["full", "3y", "1y"]
JobStatus = Literal["queued", "running", "finished", "failed"]
CompareCategory = Literal["return", "risk", "trade"]
RuleSourceMode = Literal["inherit", "candidate", "custom"]


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "vnpy-web"
    version: str = "v1"


class CandidateRow(BaseModel):
    rank: int
    template: str
    combo_id: str
    est_combos: int
    pass_rate: float
    window: WindowName


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
    start_date: date | None = None
    end_date: date | None = None
    capital_wan: float | None = Field(default=100, gt=0)
    fee_permille: float | None = Field(default=1, ge=0)
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


class BacktestStatsResponse(BaseModel):
    running_jobs: int
    queued_jobs: int
    finished_jobs: int
    failed_jobs: int
    rule_pack_count: int
    top_cagr: float


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
