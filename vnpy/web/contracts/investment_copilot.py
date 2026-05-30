from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ActionSeverity = Literal["info", "watch", "warning", "critical"]
ActionSource = Literal["portfolio", "research", "cb_quant", "data_quality"]
ActionStatus = Literal["pending", "accepted", "ignored", "executed", "reviewed"]
LedgerAssetType = Literal["cash", "equity", "etf", "bond", "convertible_bond", "option", "fund", "crypto", "other"]
LedgerImportFormat = Literal["generic_csv", "schwab_positions", "ibkr_positions"]


class InvestmentCopilotSourceHealth(BaseModel):
    source: str
    ok: bool
    summary: str
    detail: str = ""


class InvestmentCopilotPortfolioBrief(BaseModel):
    total_equity: float
    health_score: int
    risk_level: str
    cash_value: float = 0.0
    options_value: float = 0.0
    cash_gap: float
    options_excess: float
    margin_used: float
    margin_limit: float
    guardrail_count: int
    blocking_guardrail_count: int
    top_guardrails: list[str] = Field(default_factory=list)


class InvestmentCopilotResearchCandidate(BaseModel):
    symbol: str
    name: str
    score: int
    risk_level: str
    thesis: str
    next_event: str = ""


class InvestmentCopilotResearchBrief(BaseModel):
    market: str
    universe: str
    snapshot_at: str
    candidate_count: int
    theme_count: int
    watchlist_count: int
    top_candidates: list[InvestmentCopilotResearchCandidate] = Field(default_factory=list)
    hot_themes: list[str] = Field(default_factory=list)


class InvestmentCopilotCbQuantBrief(BaseModel):
    latest_trade_date: str | None = None
    latest_bond_count: int = 0
    snapshot_count: int = 0
    running_jobs: int = 0
    queued_jobs: int = 0
    finished_jobs: int = 0
    failed_jobs: int = 0
    active_optimize_tasks: int = 0
    top_strategy: str = ""
    top_cagr: float | None = None
    top_drawdown: float | None = None


class InvestmentLedgerAccountRequest(BaseModel):
    account_id: str = Field(min_length=1)
    name: str
    account_type: str = "brokerage"
    currency: str = "USD"
    base_currency: str = "USD"
    active: bool = True


class InvestmentLedgerAccountRow(InvestmentLedgerAccountRequest):
    updated_at: str


class InvestmentLedgerHoldingRequest(BaseModel):
    account_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    asset_type: LedgerAssetType = "equity"
    quantity: float = 0.0
    market_value: float
    currency: str = "USD"
    cost_basis: float | None = None
    as_of_date: str | None = None


class InvestmentLedgerHoldingRow(InvestmentLedgerHoldingRequest):
    updated_at: str


class InvestmentLedgerCashflowRequest(BaseModel):
    account_id: str = Field(min_length=1)
    event_type: str = "manual_adjustment"
    amount: float
    currency: str = "USD"
    symbol: str | None = None
    event_date: str | None = None
    note: str = ""


class InvestmentLedgerCashflowRow(InvestmentLedgerCashflowRequest):
    event_id: str
    created_at: str


class InvestmentLedgerTopPosition(BaseModel):
    symbol: str
    asset_type: LedgerAssetType
    market_value: float
    weight: float
    account_id: str


class InvestmentLedgerSummaryResponse(BaseModel):
    account_count: int = 0
    holding_count: int = 0
    total_equity: float = 0.0
    cash_value: float = 0.0
    invested_value: float = 0.0
    options_value: float = 0.0
    largest_position_weight: float = 0.0
    base_currency: str = "USD"
    top_positions: list[InvestmentLedgerTopPosition] = Field(default_factory=list)
    updated_at: str | None = None


class InvestmentLedgerReconciliationResponse(BaseModel):
    ok: bool = True
    summary: str = ""
    total_equity_delta: float = 0.0
    cash_delta: float = 0.0
    options_delta: float = 0.0
    delta_ratio: float = 0.0
    tolerance_ratio: float = 0.02


class InvestmentLedgerBootstrapRequest(BaseModel):
    accounts: list[InvestmentLedgerAccountRequest] = Field(default_factory=list)
    holdings: list[InvestmentLedgerHoldingRequest] = Field(default_factory=list)
    cashflows: list[InvestmentLedgerCashflowRequest] = Field(default_factory=list)


class InvestmentLedgerBootstrapResponse(BaseModel):
    account_count: int
    holding_count: int
    cashflow_count: int
    summary: InvestmentLedgerSummaryResponse


class InvestmentLedgerCsvImportRequest(BaseModel):
    account: InvestmentLedgerAccountRequest
    raw_csv: str = Field(min_length=1)
    format: LedgerImportFormat = "generic_csv"
    default_currency: str = "USD"
    as_of_date: str | None = None


class InvestmentLedgerCsvImportError(BaseModel):
    row_number: int
    message: str
    raw: dict[str, str] = Field(default_factory=dict)


class InvestmentLedgerCsvImportResponse(BaseModel):
    account: InvestmentLedgerAccountRow
    imported_holding_count: int
    rejected_row_count: int
    summary: InvestmentLedgerSummaryResponse
    errors: list[InvestmentLedgerCsvImportError] = Field(default_factory=list)


class InvestmentCopilotActionCard(BaseModel):
    id: str
    source: ActionSource
    severity: ActionSeverity
    priority: int
    title: str
    rationale: str
    suggested_action: str
    evidence: list[str] = Field(default_factory=list)
    href: str = ""
    requires_confirmation: bool = True
    status: ActionStatus = "pending"
    user_note: str = ""
    decision_reason: str = ""
    decided_at: str | None = None


class InvestmentCopilotActionDecisionRequest(BaseModel):
    status: ActionStatus
    user_note: str = ""
    decision_reason: str = ""


class InvestmentCopilotActionDecisionResponse(InvestmentCopilotActionDecisionRequest):
    action_id: str
    updated_at: str


class InvestmentCopilotActionPreflightRequest(BaseModel):
    market: str = "US"
    intended_action: str = ""
    acknowledged_human_confirmation: bool = False


class InvestmentCopilotActionPreflightResponse(BaseModel):
    action_id: str
    allowed: bool
    requires_human_confirmation: bool
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)
    generated_at: str


class InvestmentCopilotInvestorPolicy(BaseModel):
    profile_name: str = "默认投资政策"
    stance: str = "human_approved_copilot"
    cash_floor_ratio: float = Field(default=0.05, ge=0, le=1)
    max_single_stock_ratio: float = Field(default=0.10, ge=0, le=1)
    max_options_ratio: float = Field(default=0.25, ge=0, le=1)
    max_margin_ratio: float = Field(default=0.25, ge=0, le=1)
    require_human_confirmation: bool = True
    allow_leaps: bool = True
    allow_wheel: bool = True
    allow_cb_quant: bool = True
    forbidden_symbols: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class InvestmentCopilotDecisionPolicy(BaseModel):
    stance: str
    hard_rules: list[str] = Field(default_factory=list)
    review_questions: list[str] = Field(default_factory=list)


class InvestmentCopilotDailyBriefResponse(BaseModel):
    generated_at: str
    headline: str
    portfolio: InvestmentCopilotPortfolioBrief
    ledger: InvestmentLedgerSummaryResponse
    reconciliation: InvestmentLedgerReconciliationResponse
    research: InvestmentCopilotResearchBrief
    cb_quant: InvestmentCopilotCbQuantBrief
    source_health: list[InvestmentCopilotSourceHealth] = Field(default_factory=list)
    action_cards: list[InvestmentCopilotActionCard] = Field(default_factory=list)
    decision_policy: InvestmentCopilotDecisionPolicy
    investor_policy: InvestmentCopilotInvestorPolicy


class InvestmentCopilotAgentContextResponse(BaseModel):
    generated_at: str
    daily_brief: InvestmentCopilotDailyBriefResponse
    action_decisions: list[InvestmentCopilotActionDecisionResponse] = Field(default_factory=list)
    ledger_accounts: list[InvestmentLedgerAccountRow] = Field(default_factory=list)
    ledger_holdings: list[InvestmentLedgerHoldingRow] = Field(default_factory=list)
    ledger_cashflows: list[InvestmentLedgerCashflowRow] = Field(default_factory=list)
