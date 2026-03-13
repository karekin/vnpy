"""可转债多因子过滤与打分逻辑。

该模块负责把原始可转债快照数据转成“候选债池”：
1. 先按照策略约束过滤掉明显不符合要求的标的。
2. 再基于价格、溢价率、波动率、PB、剩余规模、正股市值等维度计算分数。
3. 最后汇总成综合权重分，并按得分从高到低输出候选结果。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from vnpy.web.core.cb_backtest.strategy_config import StrategyParameters
from vnpy.web.domain.cb_quant.strategy_factor_registry import (
    StrategyScoreMode,
    get_strategy_factor_definition,
)
from vnpy.web.domain.cb_quant.snapshot_schema import PutStatus


@dataclass(frozen=True)
class PreparedCandidatePool:
    """单日候选池的预计算结果。

    这层对象只保存“与具体参数组合无关”的静态特征：
    - 第一层基础过滤后的 universe
    - 上市天数 / 剩余天数
    - 动态双因子等执行核需要的输入列

    这样优化阶段在评估不同参数组合时，只需要复用这些特征做数值打分，
    不必反复做字符串过滤、日期解析和派生列计算。
    """

    trade_date: str
    frame: pd.DataFrame
    listing_days: pd.Series
    days_remain: pd.Series
    dynamic_inputs: dict[str, pd.Series]


def build_tradeable_mask(df: pd.DataFrame) -> pd.Series:
    """返回“可近似交易”的布尔掩码。

    当前快照里没有严格的停牌字段，因此这里采用统一代理口径：
    1. 收盘价必须有效
    2. 若已有 `is_tradeable` 列，直接复用
    3. 否则要求成交量或成交额至少一项大于 0
    """
    close_ok = pd.to_numeric(df.get("close_price"), errors="coerce").fillna(0.0) > 0
    if "is_tradeable" in df.columns:
        return close_ok & df["is_tradeable"].fillna(False).astype(bool)
    volume = pd.to_numeric(df.get("volume_hand"), errors="coerce").fillna(0.0)
    amount = pd.to_numeric(df.get("turnover_amount_wan"), errors="coerce").fillna(0.0)
    return close_ok & ((volume > 0) | (amount > 0))


def _score_lower_better(series: pd.Series, benchmark: float) -> pd.Series:
    base = max(abs(float(benchmark)), 1e-6)
    return (1 - (series - benchmark) / base).clip(lower=0.2, upper=1.8).round(2)


def _score_higher_better(series: pd.Series, benchmark: float) -> pd.Series:
    base = max(abs(float(benchmark)), 1e-6)
    return (1 - (benchmark - series) / base).clip(lower=0.2, upper=1.8).round(2)


def _score_abs_lower_better(series: pd.Series, benchmark: float = 0.0) -> pd.Series:
    distance = (series - benchmark).abs()
    base = max(abs(float(benchmark)), 10.0)
    return (1 - distance / base).clip(lower=0.2, upper=1.8).round(2)


def _score_rating(series: pd.Series, expected: Any) -> pd.Series:
    order = {"AA": 1.0, "AA+": 1.1, "AAA": 1.2}
    want = order.get(str(expected).upper(), 1.0)
    values = series.astype(str).str.upper().map(order).fillna(0.8)
    return (1 - (want - values)).clip(lower=0.2, upper=1.5).round(2)


def _build_dynamic_factor_inputs(*, df: pd.DataFrame, listing_days: pd.Series) -> dict[str, pd.Series]:
    pct_divisor = 1 + df["bond_pct_change"].fillna(0.0) / 100.0
    pre_close = df["pre_close_price"].where(df["pre_close_price"] > 0, df["close_price"] / pct_divisor.replace(0, 1.0))
    theory_value = df["pure_bond_value"] + df["option_value"]
    theory_bias = ((df["close_price"] - theory_value) / theory_value.replace(0, 1.0) * 100.0).fillna(0.0)
    conv_value = (df["underlying_close_price"] / df["conversion_price"].replace(0, 1.0) * 100.0).fillna(0.0)
    bond_prem = ((df["close_price"] / df["pure_bond_value"].replace(0, 1.0)) - 1.0) * 100.0
    left_years = df["days_to_maturity"] / 365.0
    remain_cap = df["outstanding_amount_yi"] * df["close_price"] / 100.0
    turnover_metric = df["turnover_rate_pct"].where(df["turnover_rate_pct"] > 0, df["turnover_amount_wan"])

    return {
        "dblow": df["close_price"] + df["conversion_premium_pct"],
        "conv_prem": df["conversion_premium_pct"],
        "bond_prem": bond_prem,
        "theory_bias": theory_bias,
        "theory_value": theory_value,
        "option_value": df["option_value"],
        "pure_value": df["pure_bond_value"],
        "conv_value": conv_value,
        "conv_price": df["conversion_price"],
        "close": df["close_price"],
        "open": df["open_price"],
        "high": df["high_price"],
        "low": df["low_price"],
        "pre_close": pre_close,
        "pct_chg": df["bond_pct_change"],
        "vol": df["volume_hand"],
        "amount": df["turnover_amount_wan"],
        "turnover": turnover_metric,
        "cap_mv_rate": df["outstanding_to_market_cap_ratio"] * 100.0,
        "ytm": df["ytm_to_maturity_pct"],
        "theory_conv_prem": theory_bias,
        "mod_conv_prem": df["conversion_premium_pct"],
        "left_years": left_years,
        "remain_size": df["outstanding_amount_yi"],
        "issue_size": df["issue_size_yi"],
        "remain_cap": remain_cap,
        "list_days": listing_days,
        "limit": df["limit_status"].abs(),
        "rating": df["rating"],
    }


def _build_dynamic_factor_scores(
    *,
    df: pd.DataFrame,
    factor_values: dict[str, Any],
    listing_days: pd.Series,
) -> dict[str, pd.Series]:
    input_map = _build_dynamic_factor_inputs(df=df, listing_days=listing_days)
    return _build_dynamic_factor_scores_from_inputs(
        input_map=input_map,
        factor_values=factor_values,
    )


def _build_dynamic_factor_scores_from_inputs(
    *,
    input_map: dict[str, pd.Series],
    factor_values: dict[str, Any],
) -> dict[str, pd.Series]:
    score_map: dict[str, pd.Series] = {}

    for factor_key, expected in factor_values.items():
        definition = get_strategy_factor_definition(factor_key)
        if definition is None or definition.score_mode is None:
            continue
        series = input_map.get(factor_key)
        if series is None:
            continue

        if definition.score_mode == StrategyScoreMode.LOWER_BETTER:
            score_map[factor_key] = _score_lower_better(series, float(expected))
        elif definition.score_mode == StrategyScoreMode.HIGHER_BETTER:
            score_map[factor_key] = _score_higher_better(series, float(expected))
        elif definition.score_mode == StrategyScoreMode.ABS_LOWER_BETTER:
            score_map[factor_key] = _score_abs_lower_better(series, float(expected))
        elif definition.score_mode == StrategyScoreMode.RATING:
            score_map[factor_key] = _score_rating(series, expected)

    return score_map


def prepare_candidate_pool(
    df: pd.DataFrame,
    *,
    trade_date: str,
) -> PreparedCandidatePool:
    """预计算单日候选池的静态特征。"""
    if df.empty:
        empty = df.iloc[0:0].copy()
        return PreparedCandidatePool(
            trade_date=trade_date,
            frame=empty,
            listing_days=pd.Series(dtype="float64"),
            days_remain=pd.Series(dtype="float64"),
            dynamic_inputs={},
        )

    base_mask = (
        (df["put_status"] != PutStatus.NOT_APPLICABLE.value)
        & (df["is_listed"])
        & build_tradeable_mask(df)
        & (~df["bond_name"].astype(str).str.contains("EB", na=False))
        & (~df["is_redeem_triggered"])
        & (df["bond_pure_value_ratio"] > 0.5)
        & (df["bond_pure_value_ratio"] < 15)
    )
    df_filter = df.loc[base_mask].copy()
    if df_filter.empty:
        return PreparedCandidatePool(
            trade_date=trade_date,
            frame=df_filter,
            listing_days=pd.Series(dtype="float64"),
            days_remain=pd.Series(dtype="float64"),
            dynamic_inputs={},
        )

    now_date = datetime.strptime(trade_date, "%Y-%m-%d")
    listing_dates = pd.to_datetime(df_filter["listing_date"], errors="coerce")
    listing_days = (now_date - listing_dates).dt.days.fillna(0)
    days_remain = 365 * 6 - listing_days
    dynamic_inputs = _build_dynamic_factor_inputs(df=df_filter, listing_days=listing_days)
    return PreparedCandidatePool(
        trade_date=trade_date,
        frame=df_filter,
        listing_days=listing_days,
        days_remain=days_remain,
        dynamic_inputs=dynamic_inputs,
    )


def _filter_prepared_candidate_pool(
    prepared: PreparedCandidatePool,
    *,
    strategy_parameters: StrategyParameters,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, dict[str, pd.Series]]:
    df_filter = prepared.frame
    listing_days = prepared.listing_days
    days_remain = prepared.days_remain
    dynamic_inputs = prepared.dynamic_inputs
    if df_filter.empty:
        return df_filter, listing_days, days_remain, dynamic_inputs

    params = strategy_parameters
    if params.exclude_redeem_days_below is not None and "days_to_redeem" in df_filter.columns:
        days_to_redeem = pd.to_numeric(df_filter["days_to_redeem"], errors="coerce")
        mask = days_to_redeem.isna() | (days_to_redeem > float(params.exclude_redeem_days_below))
        df_filter = df_filter.loc[mask].copy()
        listing_days = listing_days.loc[df_filter.index]
        days_remain = days_remain.loc[df_filter.index]
        dynamic_inputs = {
            factor_key: values.loc[df_filter.index]
            for factor_key, values in dynamic_inputs.items()
        }
    return df_filter, listing_days, days_remain, dynamic_inputs


def _compute_candidate_scores(
    df_filter: pd.DataFrame,
    *,
    strategy_parameters: StrategyParameters,
    listing_days: pd.Series,
    days_remain: pd.Series,
    dynamic_inputs: dict[str, pd.Series],
) -> dict[str, Any]:
    params = strategy_parameters
    premium_score = 1 - (df_filter["conversion_premium_pct"] - params.premium_benchmark) / params.premium_benchmark

    # 债券价格得分：
    # 债价越接近或低于价格基准，得分越高；价格越高，分数越低。
    price_score = 1 - (df_filter["close_price"] - params.price_benchmark) / params.price_benchmark

    # PB 得分：
    # 使用正股 PB 相对基准的偏离度进行打分，并限制最低分与最高分，防止极值放大影响。
    pb_score = (
        1 - (params.pb_benchmark - df_filter["underlying_pb"]) / params.pb_benchmark
    ).clip(lower=params.pb_score_min, upper=1).round(2)

    # 默认期权时间得分为满分 1，只有剩余时间过短时才开始扣分。
    option_score = pd.Series(1.0, index=df_filter.index)
    # 找出剩余时间低于策略基准天数的标的。
    option_mask = days_remain < params.option_days_benchmark
    # 对剩余时间偏短的标的按比例扣分，剩余时间越少，期权得分越低。
    option_score.loc[option_mask] = (
        1 - (params.option_days_benchmark - days_remain.loc[option_mask]) / params.option_days_benchmark
    ).round(2)

    # 剩余规模得分：
    # 默认给满分，只有低于最小规模或高于最大规模时才进行惩罚。
    outstanding_amount_score = pd.Series(1.0, index=df_filter.index)
    # 规模过小可能意味着流动性不足。
    low_outstanding_mask = df_filter["outstanding_amount_yi"] < params.outstanding_amount_min_yi
    # 规模过大可能意味着弹性偏弱，因此也会扣分。
    high_outstanding_mask = df_filter["outstanding_amount_yi"] > params.outstanding_amount_max_yi
    # 对低于最小规模阈值的标的按偏离比例调整得分。
    outstanding_amount_score.loc[low_outstanding_mask] = (
        1
        - (
            df_filter.loc[low_outstanding_mask, "outstanding_amount_yi"] - params.outstanding_amount_min_yi
        ) / params.outstanding_amount_min_yi
    ).round(2)
    # 对高于最大规模阈值的标的按偏离比例扣分，并限制最低分，避免被扣成过低负值。
    outstanding_amount_score.loc[high_outstanding_mask] = (
        1
        - (
            df_filter.loc[high_outstanding_mask, "outstanding_amount_yi"] - params.outstanding_amount_max_yi
        ) / params.outstanding_amount_max_yi
    ).round(2).clip(lower=params.outstanding_amount_score_min)

    # 正股市值得分：
    # 默认满分，过小或过大的市值都会按策略口径进行扣分。
    market_cap_score = pd.Series(1.0, index=df_filter.index)
    # 市值过小说明公司体量偏小，可能伴随更高风险。
    low_cap_mask = df_filter["underlying_market_cap_yi"] < params.market_cap_min_yi
    # 市值过大则可能意味着弹性不足，影响可转债博弈空间。
    high_cap_mask = df_filter["underlying_market_cap_yi"] > params.market_cap_max_yi
    # 市值低于最小阈值时，按偏离比例调整得分。
    market_cap_score.loc[low_cap_mask] = (
        1
        - (
            df_filter.loc[low_cap_mask, "underlying_market_cap_yi"] - params.market_cap_min_yi
        ) / params.market_cap_min_yi
    ).round(2)
    # 市值高于最大阈值时，同样按偏离比例扣分。
    market_cap_score.loc[high_cap_mask] = (
        1
        - (
            df_filter.loc[high_cap_mask, "underlying_market_cap_yi"] - params.market_cap_max_yi
        ) / params.market_cap_max_yi
    ).round(2)
    # 对市值得分做统一截断，确保其始终落在策略允许的区间内。
    market_cap_score = market_cap_score.clip(
        lower=params.market_cap_score_min,
        upper=params.market_cap_score_max,
    )

    # 正股波动率得分：
    # 波动率越接近或高于基准，通常意味着转债弹性更好，因此得分更高；
    # 同时用上下限限制最终得分。
    volatility_score = (
        1 - (params.volatility_benchmark - df_filter["underlying_volatility"]) / params.volatility_benchmark
    ).round(2).clip(lower=params.volatility_score_min, upper=params.volatility_score_max)

    # 债性得分：
    # 当前实现只使用价格得分，并乘以债性总权重。
    bond_score = (price_score * params.bond_weight).round(2)

    # 股性得分：
    # 将多个股性相关因子按各自权重加总，再乘以整体股性权重。
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

    # 综合权重分：
    # 用于后续排序与最终候选过滤，是策略挑选标的的核心分数。
    weight_score = bond_score + stock_score

    # 如果模板显式选择了原始市场因子，则在基准多因子分之上叠加一层“动态因子分”。
    # 这样因子库里选中的因子会真实进入排序，而不是只在模板界面里存在。
    factor_values = dict(params.factor_values or {})
    dynamic_scores = _build_dynamic_factor_scores_from_inputs(
        input_map=dynamic_inputs,
        factor_values=factor_values,
    )
    if dynamic_scores:
        dynamic_factor_score = sum(dynamic_scores.values()) / len(dynamic_scores)
        weight_score = ((weight_score + dynamic_factor_score) / 2.0).round(2)
    else:
        dynamic_factor_score = pd.Series(0.0, index=df_filter.index)

    # 最终候选过滤条件：
    # 1. 距离到期至少还要超过 90 天，避免临近到期的债券。
    pass_maturity = df_filter["days_to_maturity"] > 90
    # 2. 综合权重分必须大于 1，确保候选标的整体质量过线。
    pass_weight = weight_score > 1
    # 3. 债券价格不能超过候选池允许的最高价格。
    pass_price = df_filter["close_price"] <= params.max_candidate_price

    return {
        "weight_score": weight_score,
        "dynamic_scores": dynamic_scores,
        "dynamic_factor_score": dynamic_factor_score,
        "option_score": option_score,
        "outstanding_amount_score": outstanding_amount_score,
        "pb_score": pb_score,
        "volatility_score": volatility_score,
        "market_cap_score": market_cap_score,
        "bond_score": bond_score,
        "stock_score": stock_score,
        "final_mask": pass_maturity & pass_weight & pass_price,
    }


def _score_candidate_frame(
    df_filter: pd.DataFrame,
    *,
    strategy_parameters: StrategyParameters,
    listing_days: pd.Series,
    days_remain: pd.Series,
    dynamic_inputs: dict[str, pd.Series],
    include_details: bool = True,
) -> pd.DataFrame:
    if df_filter.empty:
        return df_filter

    scores = _compute_candidate_scores(
        df_filter,
        strategy_parameters=strategy_parameters,
        listing_days=listing_days,
        days_remain=days_remain,
        dynamic_inputs=dynamic_inputs,
    )
    final_mask = scores["final_mask"]
    if not include_details:
        ranked = pd.DataFrame(
            {
                "bond_code": df_filter.loc[final_mask, "bond_code"].astype(str),
                "weight_score": scores["weight_score"].loc[final_mask],
            }
        )
        return ranked.sort_values(by="weight_score", ascending=False, ignore_index=True)

    # 复制一份过滤后的数据，避免对原始 DataFrame 产生链式赋值副作用。
    df_scored = df_filter.copy()
    # 将各个中间得分写回结果表，便于后续排查、展示和回测分析。
    df_scored["option_score"] = scores["option_score"]
    df_scored["outstanding_amount_score"] = scores["outstanding_amount_score"]
    df_scored["pb_score"] = scores["pb_score"]
    df_scored["volatility_score"] = scores["volatility_score"]
    df_scored["market_cap_score"] = scores["market_cap_score"]
    df_scored["bond_score"] = scores["bond_score"]
    df_scored["stock_score"] = scores["stock_score"]
    df_scored["dynamic_factor_score"] = scores["dynamic_factor_score"]
    for factor_key, score_series in scores["dynamic_scores"].items():
        df_scored[f"{factor_key}_score"] = score_series
    df_scored["weight_score"] = scores["weight_score"]

    # 应用最终过滤条件，留下真正可参与排序的候选标的。
    df_scored = df_scored.loc[final_mask]
    # 按综合权重分从高到低排序，并重置索引，方便后续直接使用。
    df_scored = df_scored.sort_values(by="weight_score", ascending=False, ignore_index=True)
    # 返回最终筛选结果。
    return df_scored


def filter_multiple_factors(
    df: pd.DataFrame,
    *,
    trade_date: str,
    strategy_parameters: StrategyParameters,
) -> pd.DataFrame:
    """按当前策略核心约定的口径执行多因子筛债。"""
    prepared = prepare_candidate_pool(df, trade_date=trade_date)
    df_filter, listing_days, days_remain, dynamic_inputs = _filter_prepared_candidate_pool(
        prepared,
        strategy_parameters=strategy_parameters,
    )
    return _score_candidate_frame(
        df_filter,
        strategy_parameters=strategy_parameters,
        listing_days=listing_days,
        days_remain=days_remain,
        dynamic_inputs=dynamic_inputs,
    )


def build_candidate_codes(
    prepared: PreparedCandidatePool,
    *,
    strategy_parameters: StrategyParameters,
    candidate_count: int,
) -> list[str]:
    """基于预计算候选池快速返回候选代码列表。"""
    df_filter, listing_days, days_remain, dynamic_inputs = _filter_prepared_candidate_pool(
        prepared,
        strategy_parameters=strategy_parameters,
    )
    df_candidate = _score_candidate_frame(
        df_filter,
        strategy_parameters=strategy_parameters,
        listing_days=listing_days,
        days_remain=days_remain,
        dynamic_inputs=dynamic_inputs,
        include_details=False,
    )
    if df_candidate.empty or "bond_code" not in df_candidate.columns:
        return []
    return df_candidate["bond_code"].astype(str).tolist()[: max(1, candidate_count)]
