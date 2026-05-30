from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import uuid4


class IncomeStatus(str, Enum):
    STABLE = "stable"
    UNSTABLE = "unstable"
    RETIRED = "retired"


class RiskLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"


@dataclass(frozen=True)
class AllocationProfile:
    age: int
    income_status: IncomeStatus
    id: str = field(default_factory=lambda: f"SAP-{uuid4().hex[:10]}")
    name: str = "智能仓位默认方案"
    rebalance_threshold: Decimal = Decimal("0.05")
    allow_bull_market_leaps_relaxation: bool = False
    qqqm_symbol: str = "QQQM.US"
    voo_symbol: str = "VOO.US"
    quality_stock_symbols: tuple[str, ...] = ()
    wheel_symbols: tuple[str, ...] = ()
    leaps_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class AllocationTargets:
    dca_ratio: Decimal
    cash_ratio: Decimal
    options_ratio: Decimal
    dca_value: Decimal
    cash_value: Decimal
    options_value: Decimal
    qqqm_value: Decimal
    voo_value: Decimal
    quality_stock_value: Decimal
    single_stock_limit: Decimal
    wheel_value: Decimal
    leaps_value: Decimal
    margin_limit: Decimal


@dataclass(frozen=True)
class AllocationSnapshot:
    total_equity: Decimal
    cash_value: Decimal
    dca_value: Decimal
    options_value: Decimal
    wheel_value: Decimal = Decimal("0")
    leaps_value: Decimal = Decimal("0")
    margin_used: Decimal = Decimal("0")
    unclassified_value: Decimal = Decimal("0")
    single_stock_values: dict[str, Decimal] = field(default_factory=dict)
    latest_rsi_by_symbol: dict[str, Decimal] = field(default_factory=dict)
    open_leaps_symbols: list[str] = field(default_factory=list)
    source_inputs: dict[str, str] = field(default_factory=dict)
    snapshot_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class GuardrailViolation:
    rule_code: str
    risk_level: RiskLevel
    message: str
    actual_value: Decimal
    limit_value: Decimal
    recommended_action: str
    blocking: bool = False


@dataclass(frozen=True)
class RebalanceRecommendation:
    recommendation_type: str
    priority: int
    amount: Decimal
    reason: str
    before_state: dict[str, float]
    after_state: dict[str, float]
    id: str = ""
    status: str = "pending"
    symbol: str | None = None
    user_note: str = ""


@dataclass(frozen=True)
class CashflowEvent:
    event_type: str
    amount: Decimal
    source_bucket: str = "options"
    target_bucket: str = "cash"
    symbol: str | None = None
    note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class WaterfallTransfer:
    amount: Decimal
    source_bucket: str
    target_bucket: str
    target_sub_bucket: str | None
    reason: str


@dataclass(frozen=True)
class LeapsCandidate:
    symbol: str
    rsi: Decimal
    status: str
    reason: str


@dataclass(frozen=True)
class WheelCandidate:
    symbol: str
    source: str
    score: int
    status: str
    estimated_cash_required: Decimal
    max_contracts: int
    reason: str
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class WheelCandidatePoolSource:
    name: str
    count: int
    symbols: tuple[str, ...]
    rule: str


@dataclass(frozen=True)
class WheelDailyRecommendation:
    scan_date: str
    account_equity: Decimal
    wheel_target: Decimal
    wheel_available: Decimal
    candidate_count: int
    actionable_count: int
    candidates: tuple[WheelCandidate, ...]
    pool_sources: tuple[WheelCandidatePoolSource, ...]
    methodology: tuple[str, ...]
