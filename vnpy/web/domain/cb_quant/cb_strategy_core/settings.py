"""可转债策略核心配置模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vnpy.web.domain.cb_quant.snapshot_schema import SNAPSHOT_FIELD_DEFAULTS, SNAPSHOT_FIELD_LABELS


rename_map = SNAPSHOT_FIELD_LABELS
snapshot_field_defaults = SNAPSHOT_FIELD_DEFAULTS


class StrategyParameters(BaseModel):
    """仅包含筛债打分逻辑使用的参数。"""

    model_config = ConfigDict(extra="ignore")

    stock_weight: float = Field(default=0.3, ge=0)
    bond_weight: float = Field(default=0.7, ge=0)
    price_benchmark: float = Field(default=115.0, gt=0)
    premium_benchmark: float = Field(default=25.0, gt=0)
    premium_weight: float = Field(default=0.3, ge=0)
    volatility_benchmark: float = Field(default=30.0, gt=0)
    volatility_weight: float = Field(default=0.2, ge=0)
    outstanding_amount_weight: float = Field(default=0.15, ge=0)
    market_cap_weight: float = Field(default=0.15, ge=0)
    pb_weight: float = Field(default=0.1, ge=0)
    option_time_weight: float = Field(default=0.1, ge=0)
    option_days_benchmark: float = Field(default=360.0, gt=0)
    outstanding_amount_min_yi: float = Field(default=3.0, ge=0)
    outstanding_amount_max_yi: float = Field(default=30.0, ge=0)
    outstanding_amount_score_min: float = Field(default=0.6, ge=0)
    pb_benchmark: float = Field(default=1.5, gt=0)
    pb_score_min: float = Field(default=0.6, ge=0)
    market_cap_min_yi: float = Field(default=30.0, ge=0)
    market_cap_max_yi: float = Field(default=300.0, ge=0)
    market_cap_score_min: float = Field(default=0.6, ge=0)
    market_cap_score_max: float = Field(default=1.5, ge=0)
    volatility_score_min: float = Field(default=0.6, ge=0)
    volatility_score_max: float = Field(default=1.5, ge=0)
    max_candidate_price: float = Field(default=130.0, gt=0)
    exclude_redeem_days_below: int | None = Field(default=None, ge=0)


class BacktestRuntimeConfig(BaseModel):
    """仅包含回测执行逻辑使用的参数。"""

    model_config = ConfigDict(extra="ignore")

    rebalance_interval_type: str = "trade_day"
    rebalance_interval_value: int = Field(default=1, ge=1)
    max_position_pct: float = Field(default=20.0, ge=0, le=100)
    max_hold_count: int = Field(default=12, ge=1)
    candidate_count: int = Field(default=12, ge=1)
    exclude_redeem_days_below: int | None = Field(default=None, ge=0)
    take_profit_pct: float | None = Field(default=None, ge=0)
    stop_loss_pct: float | None = Field(default=None, ge=0)
    hold_until_profit: bool = False


def default_strategy_parameters() -> StrategyParameters:
    params = StrategyParameters()
    params.bond_weight = round(max(0.0, 1.0 - params.stock_weight), 2)
    return params


def build_strategy_parameters(values: dict[str, Any] | StrategyParameters | None = None) -> StrategyParameters:
    if isinstance(values, StrategyParameters):
        params = values.model_copy(deep=True)
    else:
        params = StrategyParameters.model_validate(values or {})
    params.bond_weight = round(max(0.0, 1.0 - float(params.stock_weight)), 2)
    params.price_benchmark = max(0.01, float(params.price_benchmark))
    params.premium_benchmark = max(0.01, float(params.premium_benchmark))
    params.volatility_benchmark = max(0.01, float(params.volatility_benchmark))
    return params


def build_runtime_config(values: dict[str, Any] | BacktestRuntimeConfig | None = None) -> BacktestRuntimeConfig:
    if isinstance(values, BacktestRuntimeConfig):
        config = values.model_copy(deep=True)
    else:
        config = BacktestRuntimeConfig.model_validate(values or {})
    config.max_hold_count = max(1, int(config.max_hold_count))
    config.candidate_count = max(config.max_hold_count, int(config.candidate_count))
    config.rebalance_interval_value = max(1, int(config.rebalance_interval_value))
    config.max_position_pct = max(0.0, min(100.0, float(config.max_position_pct)))
    return config


multiple_factors_config = default_strategy_parameters().model_dump()
