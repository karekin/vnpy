"""Phase A 多因子过滤与打分逻辑。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd


def filter_multiple_factors(df: pd.DataFrame, *, date: str, multiple_factors_config: dict[str, object]) -> pd.DataFrame:
    """按 crawler 既有口径执行多因子筛债。"""
    bond_ratio = float(multiple_factors_config.get("bond_ratio", 0.7))
    stock_ratio = float(multiple_factors_config.get("stock_ratio", 0.3))
    price_bemchmark = float(multiple_factors_config.get("price_bemchmark", 115))
    premium_bemchmark = float(multiple_factors_config.get("premium_bemchmark", 25))
    premium_ratio = float(multiple_factors_config.get("premium_ratio", 0.3))
    stock_option_ratio = float(multiple_factors_config.get("stock_option_ratio", 0.1))
    stock_option_bemchmark_days = float(multiple_factors_config.get("stock_option_bemchmark_days", 360))
    remain_ratio = float(multiple_factors_config.get("remain_ratio", 0.15))
    remain_bemchmark_min = float(multiple_factors_config.get("remain_bemchmark_min", 3))
    remain_bemchmark_max = float(multiple_factors_config.get("remain_bemchmark_max", 30))
    remain_score_min = float(multiple_factors_config.get("remain_score_min", 0.6))
    stock_pb_ratio = float(multiple_factors_config.get("stock_pb_ratio", 0.1))
    pb_bemchmark = float(multiple_factors_config.get("pb_bemchmark", 1.5))
    pb_score_min = float(multiple_factors_config.get("pb_score_min", 0.6))
    stock_market_cap_ratio = float(multiple_factors_config.get("stock_market_cap_ratio", 0.15))
    stock_market_cap_bemchmark_min = float(multiple_factors_config.get("stock_market_cap_bemchmark_min", 30))
    stock_market_cap_bemchmark_max = float(multiple_factors_config.get("stock_market_cap_bemchmark_max", 300))
    stock_market_cap_score_min = float(multiple_factors_config.get("stock_market_cap_score_min", 0.6))
    stock_market_cap_score_max = float(multiple_factors_config.get("stock_market_cap_score_max", 1.5))
    stock_stdevry_ratio = float(multiple_factors_config.get("stock_stdevry_ratio", 0.2))
    stock_stdevry_bemchmark = float(multiple_factors_config.get("stock_stdevry_bemchmark", 30))
    stock_stdevry_score_max = float(multiple_factors_config.get("stock_stdevry_score_max", 1.5))
    stock_stdevry_score_min = float(multiple_factors_config.get("stock_stdevry_score_min", 0.6))
    max_price = float(multiple_factors_config.get("max_price", 130))
    redeem_remain_days_limit = multiple_factors_config.get("redeem_remain_days_limit")

    df_filter = df.loc[
        (df["date_return_distance"] != "无权")
        & (df["is_unlist"] == "N")
        & (~df["cb_name"].str.contains("EB"))
        & (df["is_ransom_flag"] == "False")
        & (df["cb_to_pb"] > 0.5)
        & (df["cb_to_pb"] < 15)
    ]
    if df_filter.empty:
        return df_filter

    if redeem_remain_days_limit is not None and "redeem_remain_days" in df_filter.columns:
        redeem_remain_days = pd.to_numeric(df_filter["redeem_remain_days"], errors="coerce")
        df_filter = df_filter.loc[
            redeem_remain_days.isna() | (redeem_remain_days > float(redeem_remain_days_limit))
        ]
        if df_filter.empty:
            return df_filter

    now_date = datetime.strptime(date, "%Y-%m-%d")
    premium_score = 1 - (df_filter["premium_rate"] - premium_bemchmark) / premium_bemchmark
    price_score = 1 - (df_filter["price"] - price_bemchmark) / price_bemchmark
    pb_score = (1 - (pb_bemchmark - df_filter["pb"]) / pb_bemchmark).clip(lower=pb_score_min, upper=1).round(2)

    issue_dates = pd.to_datetime(df_filter["issue_date"], errors="coerce")
    days_elapsed = (now_date - issue_dates).dt.days.fillna(0)
    days_remain = 365 * 6 - days_elapsed
    stock_option_score = pd.Series(1.0, index=df_filter.index)
    option_mask = days_remain < stock_option_bemchmark_days
    stock_option_score.loc[option_mask] = (
        1 - (stock_option_bemchmark_days - days_remain.loc[option_mask]) / stock_option_bemchmark_days
    ).round(2)

    remain_score = pd.Series(1.0, index=df_filter.index)
    low_remain_mask = df_filter["remain_amount"] < remain_bemchmark_min
    high_remain_mask = df_filter["remain_amount"] > remain_bemchmark_max
    remain_score.loc[low_remain_mask] = (
        1 - (df_filter.loc[low_remain_mask, "remain_amount"] - remain_bemchmark_min) / remain_bemchmark_min
    ).round(2)
    remain_score.loc[high_remain_mask] = (
        1 - (df_filter.loc[high_remain_mask, "remain_amount"] - remain_bemchmark_max) / remain_bemchmark_max
    ).round(2).clip(lower=remain_score_min)

    stock_market_cap_score = pd.Series(1.0, index=df_filter.index)
    low_cap_mask = df_filter["market_cap"] < stock_market_cap_bemchmark_min
    high_cap_mask = df_filter["market_cap"] > stock_market_cap_bemchmark_max
    stock_market_cap_score.loc[low_cap_mask] = (
        1 - (
            df_filter.loc[low_cap_mask, "market_cap"] - stock_market_cap_bemchmark_min
        ) / stock_market_cap_bemchmark_min
    ).round(2)
    stock_market_cap_score.loc[high_cap_mask] = (
        1 - (
            df_filter.loc[high_cap_mask, "market_cap"] - stock_market_cap_bemchmark_max
        ) / stock_market_cap_bemchmark_max
    ).round(2)
    stock_market_cap_score = stock_market_cap_score.clip(
        lower=stock_market_cap_score_min,
        upper=stock_market_cap_score_max,
    )

    stock_stdevry_score = (
        1 - (stock_stdevry_bemchmark - df_filter["stock_stdevry"]) / stock_stdevry_bemchmark
    ).round(2).clip(lower=stock_stdevry_score_min, upper=stock_stdevry_score_max)

    bond_score = (price_score * bond_ratio).round(2)
    stock_score = (
        stock_ratio
        * (
            premium_score * premium_ratio
            + stock_stdevry_score * stock_stdevry_ratio
            + remain_score * remain_ratio
            + pb_score * stock_pb_ratio
            + stock_option_score * stock_option_ratio
            + stock_market_cap_score * stock_market_cap_ratio
        )
    ).round(2)
    weight_score = bond_score + stock_score

    df_filter = df_filter.copy()
    df_filter["option"] = stock_option_score
    df_filter["remain"] = remain_score
    df_filter["pb_score"] = pb_score
    df_filter["stdevry"] = stock_stdevry_score
    df_filter["stock_market_cap"] = stock_market_cap_score
    df_filter["bond"] = bond_score
    df_filter["stock"] = stock_score
    df_filter["weight"] = weight_score

    date_remain_text = df_filter["date_remain_distance"].astype(str)
    day_mask = date_remain_text.str.contains("天", regex=False) & ~date_remain_text.str.contains("年", regex=False)
    day_count = pd.to_numeric(date_remain_text.str.replace("天", "", regex=False), errors="coerce")
    pass_day = day_count > 90
    pass_weight = df_filter["weight"] > 1
    pass_non_day = (df_filter["price"] <= max_price) & pass_weight
    final_mask = (day_mask & pass_day & pass_weight) | (~day_mask & pass_non_day)

    df_filter = df_filter.loc[final_mask]
    df_filter = df_filter.sort_values(by="weight", ascending=False, ignore_index=True)
    return df_filter
