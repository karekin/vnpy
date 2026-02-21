"""
横截面算子集合。

约定在同一 `datetime` 下，对全部 `vt_symbol` 的 `data` 做截面统计，
常用于因子标准化、排序分组和组合权重归一化。
"""

import polars as pl

from .utility import DataProxy


def cs_rank(feature: DataProxy) -> DataProxy:
    """
    按交易时点做截面排名。

    每个时点把所有标的的因子值转成相对名次，便于做分层选股/分组回测。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rank().over("datetime")
    )
    return DataProxy(df)


def cs_mean(feature: DataProxy) -> DataProxy:
    """
    计算每个时点的截面均值并回填到每个标的。

    结果常作为去均值或行业/市场中性化的基准项。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").mean().over("datetime")
    )
    return DataProxy(df)


def cs_std(feature: DataProxy) -> DataProxy:
    """
    计算每个时点的截面标准差并回填到每个标的。

    结果常用于把原始因子转成 z-score 或控制当日横截面波动尺度。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").std().over("datetime")
    )
    return DataProxy(df)


def cs_sum(feature: DataProxy) -> DataProxy:
    """
    计算每个时点的截面总和并回填到每个标的。

    常用于构造归一化分母，例如权重总和约束。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").sum().over("datetime")
    )
    return DataProxy(df)


def cs_scale(feature: DataProxy) -> DataProxy:
    """
    对每个时点做绝对值和归一化。

    处理后满足同一时点 `sum(abs(data)) = 1`（分母为 0 时置 0），
    常用于把信号直接映射为组合权重。
    """
    abs_feature = abs(feature)
    sum_abs = cs_sum(abs_feature)

    df_merged: pl.DataFrame = feature.df.join(sum_abs.df, on=["datetime", "vt_symbol"], suffix="_sum")

    df: pl.DataFrame = df_merged.with_columns(
        pl.when(pl.col("data_sum") != 0)
        .then(pl.col("data") / pl.col("data_sum"))
        .otherwise(0)
        .alias("data")
    ).select(["datetime", "vt_symbol", "data"])

    return DataProxy(df)
