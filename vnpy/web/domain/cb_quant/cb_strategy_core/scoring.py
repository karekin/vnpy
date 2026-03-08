"""可转债多因子过滤与打分逻辑。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from vnpy.web.domain.cb_quant.cb_strategy_core.settings import StrategyParameters
from vnpy.web.domain.cb_quant.snapshot_schema import PutStatus


def filter_multiple_factors(
    df: pd.DataFrame,
    *,
    trade_date: str,
    strategy_parameters: StrategyParameters,
) -> pd.DataFrame:
    """按当前策略核心约定的口径执行多因子筛债。"""
    params = strategy_parameters
    df_filter = df.loc[
        (df["put_status"] != PutStatus.NOT_APPLICABLE.value)
        & (df["is_listed"])
        & (~df["bond_name"].str.contains("EB"))
        & (~df["is_redeem_triggered"])
        & (df["bond_pure_value_ratio"] > 0.5)
        & (df["bond_pure_value_ratio"] < 15)
    ]
    if df_filter.empty:
        return df_filter

    if params.exclude_redeem_days_below is not None and "days_to_redeem" in df_filter.columns:
        days_to_redeem = pd.to_numeric(df_filter["days_to_redeem"], errors="coerce")
        df_filter = df_filter.loc[
            days_to_redeem.isna() | (days_to_redeem > float(params.exclude_redeem_days_below))
        ]
        if df_filter.empty:
            return df_filter

    now_date = datetime.strptime(trade_date, "%Y-%m-%d")
    premium_score = 1 - (df_filter["conversion_premium_pct"] - params.premium_benchmark) / params.premium_benchmark
    price_score = 1 - (df_filter["close_price"] - params.price_benchmark) / params.price_benchmark
    pb_score = (
        1 - (params.pb_benchmark - df_filter["underlying_pb"]) / params.pb_benchmark
    ).clip(lower=params.pb_score_min, upper=1).round(2)

    listing_dates = pd.to_datetime(df_filter["listing_date"], errors="coerce")
    days_elapsed = (now_date - listing_dates).dt.days.fillna(0)
    days_remain = 365 * 6 - days_elapsed
    option_score = pd.Series(1.0, index=df_filter.index)
    option_mask = days_remain < params.option_days_benchmark
    option_score.loc[option_mask] = (
        1 - (params.option_days_benchmark - days_remain.loc[option_mask]) / params.option_days_benchmark
    ).round(2)

    outstanding_amount_score = pd.Series(1.0, index=df_filter.index)
    low_outstanding_mask = df_filter["outstanding_amount_yi"] < params.outstanding_amount_min_yi
    high_outstanding_mask = df_filter["outstanding_amount_yi"] > params.outstanding_amount_max_yi
    outstanding_amount_score.loc[low_outstanding_mask] = (
        1
        - (
            df_filter.loc[low_outstanding_mask, "outstanding_amount_yi"] - params.outstanding_amount_min_yi
        ) / params.outstanding_amount_min_yi
    ).round(2)
    outstanding_amount_score.loc[high_outstanding_mask] = (
        1
        - (
            df_filter.loc[high_outstanding_mask, "outstanding_amount_yi"] - params.outstanding_amount_max_yi
        ) / params.outstanding_amount_max_yi
    ).round(2).clip(lower=params.outstanding_amount_score_min)

    market_cap_score = pd.Series(1.0, index=df_filter.index)
    low_cap_mask = df_filter["underlying_market_cap_yi"] < params.market_cap_min_yi
    high_cap_mask = df_filter["underlying_market_cap_yi"] > params.market_cap_max_yi
    market_cap_score.loc[low_cap_mask] = (
        1
        - (
            df_filter.loc[low_cap_mask, "underlying_market_cap_yi"] - params.market_cap_min_yi
        ) / params.market_cap_min_yi
    ).round(2)
    market_cap_score.loc[high_cap_mask] = (
        1
        - (
            df_filter.loc[high_cap_mask, "underlying_market_cap_yi"] - params.market_cap_max_yi
        ) / params.market_cap_max_yi
    ).round(2)
    market_cap_score = market_cap_score.clip(
        lower=params.market_cap_score_min,
        upper=params.market_cap_score_max,
    )

    volatility_score = (
        1 - (params.volatility_benchmark - df_filter["underlying_volatility"]) / params.volatility_benchmark
    ).round(2).clip(lower=params.volatility_score_min, upper=params.volatility_score_max)

    bond_score = (price_score * params.bond_weight).round(2)
    stock_score = (
        params.stock_weight
        * (
            premium_score * params.premium_weight
            + volatility_score * params.volatility_weight
            + outstanding_amount_score * params.outstanding_amount_weight
            + pb_score * params.pb_weight
            + option_score * params.option_time_weight
            + market_cap_score * params.market_cap_weight
        )
    ).round(2)
    weight_score = bond_score + stock_score

    df_filter = df_filter.copy()
    df_filter["option_score"] = option_score
    df_filter["outstanding_amount_score"] = outstanding_amount_score
    df_filter["pb_score"] = pb_score
    df_filter["volatility_score"] = volatility_score
    df_filter["market_cap_score"] = market_cap_score
    df_filter["bond_score"] = bond_score
    df_filter["stock_score"] = stock_score
    df_filter["weight_score"] = weight_score

    pass_maturity = df_filter["days_to_maturity"] > 90
    pass_weight = df_filter["weight_score"] > 1
    pass_price = df_filter["close_price"] <= params.max_candidate_price
    final_mask = pass_maturity & pass_weight & pass_price

    df_filter = df_filter.loc[final_mask]
    df_filter = df_filter.sort_values(by="weight_score", ascending=False, ignore_index=True)
    return df_filter
