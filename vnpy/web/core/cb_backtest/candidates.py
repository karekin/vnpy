"""可转债策略候选池生成逻辑。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vnpy.web.core.cb_backtest.scoring import filter_multiple_factors
from vnpy.web.core.cb_backtest.settings import (
    StrategyParameters,
    build_strategy_parameters as normalize_strategy_parameters,
)


def build_strategy_parameters(setting: dict[str, Any] | StrategyParameters) -> StrategyParameters:
    """把外部参数组合整理成筛债逻辑使用的标准参数模型。"""
    return normalize_strategy_parameters(setting)


def build_candidates(
    df_all: pd.DataFrame,
    trade_date: str,
    strategy_parameters: StrategyParameters,
    candidate_count: int,
) -> pd.DataFrame:
    """给定单日全市场快照，生成按得分排序的候选债列表。"""
    try:
        df_candidate = filter_multiple_factors(
            df_all.copy(),
            trade_date=trade_date,
            strategy_parameters=strategy_parameters,
        )
    except KeyError:
        return pd.DataFrame(columns=df_all.columns)

    if candidate_count > 0:
        df_candidate = df_candidate.head(candidate_count)
    return df_candidate
