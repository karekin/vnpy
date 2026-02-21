"""
因子表达式常用数学算子。

输入输出均为 `DataProxy`，并保持 `(datetime, vt_symbol, data)` 三列结构，
便于在特征工程流水线中链式组合。
"""

import polars as pl

from .utility import DataProxy


def less(feature1: DataProxy, feature2: DataProxy | float) -> DataProxy:
    """
    逐样本取两路输入的较小值。

    常用于截断上界，例如 `min(raw_factor, cap)` 防止极端值主导模型。
    """
    if isinstance(feature2, DataProxy):
        df_merged: pl.DataFrame = feature1.df.join(feature2.df, on=["datetime", "vt_symbol"])
    else:
        df_merged = feature1.df.with_columns(pl.lit(feature2).alias("data_right"))

    df: pl.DataFrame = df_merged.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.min_horizontal("data", "data_right").over("vt_symbol").alias("data")
    )

    return DataProxy(df)


def greater(feature1: DataProxy, feature2: DataProxy | float) -> DataProxy:
    """
    逐样本取两路输入的较大值。

    常用于设置下界，例如 `max(raw_factor, floor)`。
    """
    if isinstance(feature2, DataProxy):
        df_merged: pl.DataFrame = feature1.df.join(feature2.df, on=["datetime", "vt_symbol"])

    else:
        df_merged = feature1.df.with_columns(pl.lit(feature2).alias("data_right"))

    df: pl.DataFrame = df_merged.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.max_horizontal("data", "data_right").over("vt_symbol").alias("data")
    )

    return DataProxy(df)


def log(feature: DataProxy) -> DataProxy:
    """
    对因子做自然对数变换。

    适合压缩长尾分布（如成交额、规模类特征）的量级差异。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").log().over("vt_symbol")
    )
    return DataProxy(df)


def abs(feature: DataProxy) -> DataProxy:
    """
    取因子绝对值。

    常用于只关心偏离幅度、不关心方向的场景。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").abs().over("vt_symbol")
    )
    return DataProxy(df)


def sign(feature: DataProxy) -> DataProxy:
    """
    提取因子方向符号（1/-1/0）。

    可把连续信号离散为方向信号，用于方向约束或状态判别。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.when(pl.col("data") > 0).then(1).when(pl.col("data") < 0).then(-1).otherwise(0).alias("data")
    )
    return DataProxy(df)


def quesval(threshold: float, feature1: DataProxy, feature2: DataProxy | float | int, feature3: DataProxy | float | int) -> DataProxy:
    """
    条件选择算子（阈值为常数版本）。

    当 `feature1 > threshold` 时返回 `feature2`，否则返回 `feature3`，
    常用于分段因子或状态切换逻辑。
    """
    df_merged = feature1.df

    if isinstance(feature2, DataProxy):
        df_merged = df_merged.join(feature2.df, on=["datetime", "vt_symbol"], suffix="_true")
    else:
        df_merged = df_merged.with_columns(pl.lit(feature2).alias("data_true"))

    if isinstance(feature3, DataProxy):
        df_merged = df_merged.join(feature3.df, on=["datetime", "vt_symbol"], suffix="_false")
    else:
        df_merged = df_merged.with_columns(pl.lit(feature3).alias("data_false"))

    df: pl.DataFrame = df_merged.with_columns(
        pl.when(threshold < pl.col("data"))
        .then(pl.col("data_true"))
        .otherwise(pl.col("data_false"))
        .alias("data")
    ).select(["datetime", "vt_symbol", "data"])

    return DataProxy(df)


def quesval2(threshold: DataProxy, feature1: DataProxy, feature2: DataProxy | float | int, feature3: DataProxy | float | int) -> DataProxy:
    """
    条件选择算子（阈值为时变特征版本）。

    当 `feature1 > threshold` 时返回 `feature2`，否则返回 `feature3`，
    适合做“动态阈值”规则，例如与波动率或均线比较。
    """
    df_merged: pl.DataFrame = threshold.df.join(feature1.df, on=["datetime", "vt_symbol"], suffix="_cond")

    if isinstance(feature2, DataProxy):
        df_merged = df_merged.join(feature2.df, on=["datetime", "vt_symbol"], suffix="_true")
    else:
        df_merged = df_merged.with_columns(pl.lit(feature2).alias("data_true"))

    if isinstance(feature3, DataProxy):
        df_merged = df_merged.join(feature3.df, on=["datetime", "vt_symbol"], suffix="_false")
    else:
        df_merged = df_merged.with_columns(pl.lit(feature3).alias("data_false"))

    df: pl.DataFrame = df_merged.with_columns(
        pl.when(pl.col("data_cond") < pl.col("data"))
        .then(pl.col("data_true"))
        .otherwise(pl.col("data_false"))
        .alias("data")
    ).select(["datetime", "vt_symbol", "data"])

    return DataProxy(df)


def pow1(base: DataProxy, exponent: float) -> DataProxy:
    """
    幂运算（指数为常数）并兼容负底数。

    规则：
    1. `base > 0`：直接 `base ** exponent`
    2. `base < 0`：返回 `- |base| ** exponent`，保留方向信息
    3. `base = 0`：返回 0
    """
    df: pl.DataFrame = base.df.with_columns(
        pl.when(pl.col("data") > 0)
        .then(pl.col("data").pow(exponent))
        .when(pl.col("data") < 0)
        .then(pl.lit(-1) * pl.col("data").abs().pow(exponent))
        .otherwise(0)
        .alias("data")
    )

    return DataProxy(df)


def pow2(base: DataProxy, exponent: DataProxy) -> DataProxy:
    """
    幂运算（指数为时变特征）并处理数值安全边界。

    规则：
    1. `base > 0`：计算 `base ** exponent`
    2. `base < 0` 且 `exponent` 为整数：计算 `- |base| ** exponent`
    3. 其余情况（`base=0`、指数 NaN、负底数配非整数指数）统一返回 0

    说明：
    使用 `floor()==自身` 判断整数指数，避免 NaN 转整数报错。
    """
    base_renamed = base.df.rename({"data": "base_data"})
    exp_renamed = exponent.df.rename({"data": "exp_data"})

    df_merged: pl.DataFrame = base_renamed.join(exp_renamed, on=["datetime", "vt_symbol"], how="left")

    df: pl.DataFrame = df_merged.with_columns(
        pl.when(pl.col("base_data") > 0)
        .then(pl.col("base_data").pow(pl.col("exp_data")))
        .when(
            (pl.col("base_data") < 0) &
            (~pl.col("exp_data").is_nan()) &
            (pl.col("exp_data").floor() == pl.col("exp_data"))
        )
        .then((-1) * pl.col("base_data").abs().pow(pl.col("exp_data")))
        .otherwise(pl.lit(None))
        .fill_nan(None)
        .fill_null(0)
        .alias("data")
    ).select(["datetime", "vt_symbol", "data"])

    return DataProxy(df)

