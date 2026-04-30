from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


IncomeStatusLiteral = Literal["stable", "unstable", "retired"]
RiskLevelLiteral = Literal["green", "yellow", "orange", "red"]


class SmartAllocationProfileRequest(BaseModel):
    age: int = Field(28, ge=0, le=120)
    income_status: IncomeStatusLiteral = "stable"
    name: str = "智能仓位默认方案"
    rebalance_threshold: float = Field(0.05, ge=0, le=1)
    allow_bull_market_leaps_relaxation: bool = False
    quality_stock_symbols: list[str] = Field(default_factory=list)
    wheel_symbols: list[str] = Field(default_factory=list)
    leaps_symbols: list[str] = Field(default_factory=list)


class SmartAllocationProfileResponse(SmartAllocationProfileRequest):
    id: str
    qqqm_symbol: str = "QQQM.US"
    voo_symbol: str = "VOO.US"


class SmartAllocationSnapshotRequest(BaseModel):
    total_equity: float = Field(..., ge=0)
    cash_value: float = Field(0, ge=0)
    dca_value: float = Field(0, ge=0)
    options_value: float = Field(0, ge=0)
    wheel_value: float = Field(0, ge=0)
    leaps_value: float = Field(0, ge=0)
    margin_used: float = Field(0, ge=0)
    unclassified_value: float = Field(0, ge=0)
    single_stock_values: dict[str, float] = Field(default_factory=dict)
    latest_rsi_by_symbol: dict[str, float] = Field(default_factory=dict)
    open_leaps_symbols: list[str] = Field(default_factory=list)


class SmartAllocationTargetsResponse(BaseModel):
    dca_ratio: float
    cash_ratio: float
    options_ratio: float
    dca_value: float
    cash_value: float
    options_value: float
    qqqm_value: float
    voo_value: float
    quality_stock_value: float
    single_stock_limit: float
    wheel_value: float
    leaps_value: float
    margin_limit: float


class SmartAllocationSnapshotResponse(SmartAllocationSnapshotRequest):
    snapshot_at: str


class SmartAllocationGuardrailResponse(BaseModel):
    rule_code: str
    risk_level: RiskLevelLiteral
    message: str
    actual_value: float
    limit_value: float
    recommended_action: str
    blocking: bool = False


class SmartAllocationRecommendationResponse(BaseModel):
    id: str
    recommendation_type: str
    priority: int
    amount: float
    reason: str
    before_state: dict[str, float]
    after_state: dict[str, float]
    status: str = "pending"
    symbol: str | None = None
    user_note: str = ""


class SmartAllocationRecommendationStatusRequest(BaseModel):
    user_note: str = ""


class SmartAllocationCashflowEventRequest(BaseModel):
    event_type: str = "wheel_premium_received"
    amount: float = Field(..., gt=0)
    source_bucket: str = "options"
    target_bucket: str = "cash"
    symbol: str | None = None
    note: str = ""


class SmartAllocationCashflowEventResponse(SmartAllocationCashflowEventRequest):
    created_at: str


class SmartAllocationWaterfallTransferResponse(BaseModel):
    amount: float
    source_bucket: str
    target_bucket: str
    target_sub_bucket: str | None
    reason: str


class SmartAllocationLeapsCandidateResponse(BaseModel):
    symbol: str
    rsi: float
    status: str
    reason: str


class SmartAllocationWheelCandidateResponse(BaseModel):
    symbol: str
    source: str
    score: int
    status: str
    estimated_cash_required: float
    max_contracts: int
    reason: str
    blockers: list[str] = Field(default_factory=list)


class SmartAllocationWheelCandidatePoolSourceResponse(BaseModel):
    name: str
    count: int
    symbols: list[str] = Field(default_factory=list)
    rule: str


class SmartAllocationWheelDailyRecommendationResponse(BaseModel):
    scan_date: str
    account_equity: float
    wheel_target: float
    wheel_available: float
    candidate_count: int
    actionable_count: int
    candidates: list[SmartAllocationWheelCandidateResponse]
    pool_sources: list[SmartAllocationWheelCandidatePoolSourceResponse]
    methodology: list[str]


class SmartAllocationCallSpreadCandidateResponse(BaseModel):
    symbol: str
    source: str
    score: int
    status: str
    expiration_date: str | None = None
    long_strike: float | None = None
    short_strike: float | None = None
    net_debit: float
    max_profit: float
    max_loss: float
    reward_risk: float
    break_even: float | None = None
    max_contracts: int
    underlying_price: float | None = None
    reason: str
    blockers: list[str] = Field(default_factory=list)


class SmartAllocationCallSpreadDailyRecommendationResponse(BaseModel):
    scan_date: str
    account_equity: float
    options_available: float
    per_trade_limit: float
    candidate_count: int
    actionable_count: int
    candidates: list[SmartAllocationCallSpreadCandidateResponse]
    methodology: list[str]


class SmartAllocationDashboardResponse(BaseModel):
    profile: SmartAllocationProfileResponse
    snapshot: SmartAllocationSnapshotResponse
    targets: SmartAllocationTargetsResponse
    guardrails: list[SmartAllocationGuardrailResponse]
    recommendations: list[SmartAllocationRecommendationResponse]
    health_score: int
    risk_level: RiskLevelLiteral
    data_warnings: list[str] = Field(default_factory=list)
    profile_source: str = "persistent"
    snapshot_source: str = "persistent"
