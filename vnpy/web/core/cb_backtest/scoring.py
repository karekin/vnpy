"""可转债多因子过滤与打分逻辑。

该模块负责把原始可转债快照数据转成“候选债池”：
1. 先按照策略约束过滤掉明显不符合要求的标的。
2. 再基于价格、溢价率、波动率、PB、剩余规模、正股市值等维度计算分数。
3. 最后汇总成综合权重分，并按得分从高到低输出候选结果。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from vnpy.web.core.cb_backtest.settings import StrategyParameters
from vnpy.web.domain.cb_quant.snapshot_schema import PutStatus


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


def _build_dynamic_factor_scores(
    *,
    df: pd.DataFrame,
    factor_values: dict[str, Any],
    listing_days: pd.Series,
) -> dict[str, pd.Series]:
    pct_divisor = 1 + df["bond_pct_change"].fillna(0.0) / 100.0
    pre_close = df["pre_close_price"].where(df["pre_close_price"] > 0, df["close_price"] / pct_divisor.replace(0, 1.0))
    theory_value = df["pure_bond_value"] + df["option_value"]
    theory_bias = ((df["close_price"] - theory_value) / theory_value.replace(0, 1.0) * 100.0).fillna(0.0)
    dblow = df["close_price"] + df["conversion_premium_pct"]
    conv_value = (df["underlying_close_price"] / df["conversion_price"].replace(0, 1.0) * 100.0).fillna(0.0)
    bond_prem = ((df["close_price"] / df["pure_bond_value"].replace(0, 1.0)) - 1.0) * 100.0
    left_years = df["days_to_maturity"] / 365.0
    remain_cap = df["outstanding_amount_yi"] * df["close_price"] / 100.0
    cap_mv_rate = df["outstanding_to_market_cap_ratio"] * 100.0
    turnover_metric = df["turnover_rate_pct"].where(df["turnover_rate_pct"] > 0, df["turnover_amount_wan"])
    limit_metric = df["limit_status"].abs()

    series_map: dict[str, pd.Series] = {
        "dblow": _score_lower_better(dblow, float(factor_values.get("dblow", 0.0))),
        "conv_prem": _score_lower_better(df["conversion_premium_pct"], float(factor_values.get("conv_prem", 0.0))),
        "bond_prem": _score_lower_better(bond_prem, float(factor_values.get("bond_prem", 0.0))),
        "theory_bias": _score_abs_lower_better(theory_bias, float(factor_values.get("theory_bias", 0.0))),
        "theory_value": _score_higher_better(theory_value, float(factor_values.get("theory_value", 1.0))),
        "option_value": _score_higher_better(df["option_value"], float(factor_values.get("option_value", 1.0))),
        "pure_value": _score_higher_better(df["pure_bond_value"], float(factor_values.get("pure_value", 1.0))),
        "conv_value": _score_higher_better(conv_value, float(factor_values.get("conv_value", 1.0))),
        "conv_price": _score_lower_better(df["conversion_price"], float(factor_values.get("conv_price", 1.0))),
        "close": _score_lower_better(df["close_price"], float(factor_values.get("close", 1.0))),
        "open": _score_lower_better(df["open_price"], float(factor_values.get("open", 1.0))),
        "high": _score_lower_better(df["high_price"], float(factor_values.get("high", 1.0))),
        "low": _score_lower_better(df["low_price"], float(factor_values.get("low", 1.0))),
        "pre_close": _score_lower_better(pre_close, float(factor_values.get("pre_close", 1.0))),
        "pct_chg": _score_abs_lower_better(df["bond_pct_change"], float(factor_values.get("pct_chg", 0.0))),
        "vol": _score_higher_better(df["volume_hand"], float(factor_values.get("vol", 1.0))),
        "amount": _score_higher_better(df["turnover_amount_wan"], float(factor_values.get("amount", 1.0))),
        "turnover": _score_higher_better(turnover_metric, float(factor_values.get("turnover", 1.0))),
        "cap_mv_rate": _score_lower_better(cap_mv_rate, float(factor_values.get("cap_mv_rate", 1.0))),
        "ytm": _score_higher_better(df["ytm_to_maturity_pct"], float(factor_values.get("ytm", 1.0))),
        "theory_conv_prem": _score_abs_lower_better(theory_bias, float(factor_values.get("theory_conv_prem", 0.0))),
        "mod_conv_prem": _score_lower_better(df["conversion_premium_pct"], float(factor_values.get("mod_conv_prem", 1.0))),
        "left_years": _score_higher_better(left_years, float(factor_values.get("left_years", 1.0))),
        "remain_size": _score_lower_better(df["outstanding_amount_yi"], float(factor_values.get("remain_size", 1.0))),
        "issue_size": _score_lower_better(df["issue_size_yi"], float(factor_values.get("issue_size", 1.0))),
        "remain_cap": _score_lower_better(remain_cap, float(factor_values.get("remain_cap", 1.0))),
        "list_days": _score_higher_better(listing_days, float(factor_values.get("list_days", 1.0))),
        "limit": _score_abs_lower_better(limit_metric, float(factor_values.get("limit", 0.0))),
    }

    if "rating" in factor_values:
        series_map["rating"] = _score_rating(df["rating"], factor_values.get("rating"))

    return {key: value for key, value in series_map.items() if key in factor_values}


def filter_multiple_factors(
    df: pd.DataFrame,
    *,
    trade_date: str,
    strategy_parameters: StrategyParameters,
) -> pd.DataFrame:
    """按当前策略核心约定的口径执行多因子筛债。

    参数说明：
    - df: 当日可转债快照数据，每一行代表一只债券。
    - trade_date: 交易日，格式固定为 ``YYYY-MM-DD``，用于计算上市天数等时间因子。
    - strategy_parameters: 策略参数对象，包含各类阈值、基准值和权重配置。

    返回值说明：
    - 返回经过基础过滤、因子打分、最终二次过滤后的候选可转债列表。
    - 若任一过滤阶段后数据为空，则直接返回空 DataFrame。
    """
    # 为了后续代码书写更紧凑，这里先给策略参数起一个局部别名。
    params = strategy_parameters

    # 第一层基础过滤：
    # 1. 必须存在回售状态，排除不适用的标的。
    # 2. 必须已经上市，避免未上市债券进入候选池。
    # 3. 排除名称中包含 EB 的品种，通常表示与当前可转债策略口径不一致。
    # 4. 排除已经触发强赎的债券，避免临近退出的标的干扰策略。
    # 5. 纯债价值比限制在合理区间内，剔除极端异常值或数据质量较差的记录。
    df_filter = df.loc[
        (df["put_status"] != PutStatus.NOT_APPLICABLE.value)
        & (df["is_listed"])
        & (~df["bond_name"].str.contains("EB"))
        & (~df["is_redeem_triggered"])
        & (df["bond_pure_value_ratio"] > 0.5)
        & (df["bond_pure_value_ratio"] < 15)
    ]
    # 如果基础过滤后已经没有数据，就没有继续打分的意义，直接返回。
    if df_filter.empty:
        return df_filter

    # 第二层可选过滤：
    # 如果策略配置了“距赎回日最低剩余天数”，并且数据中存在该列，则进一步剔除
    # 快到赎回日的标的；空值保留，表示未知时不过度过滤。
    if params.exclude_redeem_days_below is not None and "days_to_redeem" in df_filter.columns:
        # 统一转成数值类型，无法转换的值记为 NaN，避免字符串脏数据影响比较逻辑。
        days_to_redeem = pd.to_numeric(df_filter["days_to_redeem"], errors="coerce")
        # 保留空值或剩余赎回天数大于阈值的记录。
        df_filter = df_filter.loc[
            days_to_redeem.isna() | (days_to_redeem > float(params.exclude_redeem_days_below))
        ]
        # 如果过滤后为空，同样直接返回。
        if df_filter.empty:
            return df_filter

    # 将交易日字符串转成 datetime，后续用于计算上市已过天数和期权时间价值因子。
    now_date = datetime.strptime(trade_date, "%Y-%m-%d")

    # 溢价率得分：
    # 溢价率越接近或低于基准值，得分越高；高于基准值越多，得分越低。
    premium_score = 1 - (df_filter["conversion_premium_pct"] - params.premium_benchmark) / params.premium_benchmark

    # 债券价格得分：
    # 债价越接近或低于价格基准，得分越高；价格越高，分数越低。
    price_score = 1 - (df_filter["close_price"] - params.price_benchmark) / params.price_benchmark

    # PB 得分：
    # 使用正股 PB 相对基准的偏离度进行打分，并限制最低分与最高分，防止极值放大影响。
    pb_score = (
        1 - (params.pb_benchmark - df_filter["underlying_pb"]) / params.pb_benchmark
    ).clip(lower=params.pb_score_min, upper=1).round(2)

    # 解析上市日期。无法解析的日期会变成 NaT，后续统一按缺失值处理。
    listing_dates = pd.to_datetime(df_filter["listing_date"], errors="coerce")
    # 计算距离上市已经过去了多少天；缺失值按 0 天处理，避免中断打分。
    days_elapsed = (now_date - listing_dates).dt.days.fillna(0)
    # 可转债通常按 6 年存续期粗略估算剩余时间，用于衡量期权时间价值。
    days_remain = 365 * 6 - days_elapsed
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
    dynamic_scores = _build_dynamic_factor_scores(
        df=df_filter,
        factor_values=factor_values,
        listing_days=days_elapsed,
    )
    if dynamic_scores:
        dynamic_factor_score = sum(dynamic_scores.values()) / len(dynamic_scores)
        weight_score = ((weight_score + dynamic_factor_score) / 2.0).round(2)
    else:
        dynamic_factor_score = pd.Series(0.0, index=df_filter.index)

    # 复制一份过滤后的数据，避免对原始 DataFrame 产生链式赋值副作用。
    df_filter = df_filter.copy()
    # 将各个中间得分写回结果表，便于后续排查、展示和回测分析。
    df_filter["option_score"] = option_score
    df_filter["outstanding_amount_score"] = outstanding_amount_score
    df_filter["pb_score"] = pb_score
    df_filter["volatility_score"] = volatility_score
    df_filter["market_cap_score"] = market_cap_score
    df_filter["bond_score"] = bond_score
    df_filter["stock_score"] = stock_score
    df_filter["dynamic_factor_score"] = dynamic_factor_score
    for factor_key, score_series in dynamic_scores.items():
        df_filter[f"{factor_key}_score"] = score_series
    df_filter["weight_score"] = weight_score

    # 最终候选过滤条件：
    # 1. 距离到期至少还要超过 90 天，避免临近到期的债券。
    pass_maturity = df_filter["days_to_maturity"] > 90
    # 2. 综合权重分必须大于 1，确保候选标的整体质量过线。
    pass_weight = df_filter["weight_score"] > 1
    # 3. 债券价格不能超过候选池允许的最高价格。
    pass_price = df_filter["close_price"] <= params.max_candidate_price
    # 三个条件同时满足，才进入最终候选池。
    final_mask = pass_maturity & pass_weight & pass_price

    # 应用最终过滤条件，留下真正可参与排序的候选标的。
    df_filter = df_filter.loc[final_mask]
    # 按综合权重分从高到低排序，并重置索引，方便后续直接使用。
    df_filter = df_filter.sort_values(by="weight_score", ascending=False, ignore_index=True)
    # 返回最终筛选结果。
    return df_filter
