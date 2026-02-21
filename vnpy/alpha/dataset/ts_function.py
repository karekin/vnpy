"""
时间序列算子集合。

所有计算均在单个 `vt_symbol` 的时间轴上滚动进行，
用于构建动量、波动、趋势、相关性等时序因子。
"""

from typing import cast

from scipy import stats
import polars as pl
import numpy as np

from .utility import DataProxy


def ts_delay(feature: DataProxy, window: int) -> DataProxy:
    """
    获取滞后值（向后平移 `window` 个周期）。

    常用于构造收益率、差分特征，或避免未来数据泄露。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").shift(window).over("vt_symbol")
    )
    return DataProxy(df)


def ts_min(feature: DataProxy, window: int) -> DataProxy:
    """
    计算滚动窗口最小值。

    可用于刻画短期下沿、回撤低点或区间支撑位。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rolling_min(window, min_samples=1).over("vt_symbol")
    )
    return DataProxy(df)


def ts_max(feature: DataProxy, window: int) -> DataProxy:
    """
    计算滚动窗口最大值。

    可用于刻画短期上沿、突破高点或区间压力位。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rolling_max(window, min_samples=1).over("vt_symbol")
    )
    return DataProxy(df)


def ts_argmax(feature: DataProxy, window: int) -> DataProxy:
    """
    返回窗口内最大值位置（1-based）。

    结果可理解为“距离阶段高点的位置索引”，常用于趋势状态特征。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rolling_map(lambda s: cast(int, s.arg_max()) + 1, window).over("vt_symbol")
    )
    return DataProxy(df)


def ts_argmin(feature: DataProxy, window: int) -> DataProxy:
    """
    返回窗口内最小值位置（1-based）。

    结果可理解为“距离阶段低点的位置索引”。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rolling_map(lambda s: cast(int, s.arg_min()) + 1, window).over("vt_symbol")
    )
    return DataProxy(df)


def ts_rank(feature: DataProxy, window: int) -> DataProxy:
    """
    计算当前值在滚动窗口内的分位排名（0~1）。

    常用于把原始值映射为相对强弱，降低量纲影响。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rolling_map(lambda s: stats.percentileofscore(s, s[-1]) / 100, window).over("vt_symbol")
    )
    return DataProxy(df)


def ts_sum(feature: DataProxy, window: int) -> DataProxy:
    """
    计算滚动窗口求和。

    可用于累计成交量、累计收益等聚合特征。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rolling_sum(window).over("vt_symbol")
    )
    return DataProxy(df)


def ts_mean(feature: DataProxy, window: int) -> DataProxy:
    """
    计算滚动均值（忽略 NaN）。

    常用于平滑噪声并构造均值回归类因子。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rolling_map(lambda s: np.nanmean(s), window, min_samples=1).over("vt_symbol")
    )
    return DataProxy(df)


def ts_std(feature: DataProxy, window: int) -> DataProxy:
    """
    计算滚动标准差（总体标准差口径，`ddof=0`）。

    常用于波动率估计和风险约束特征。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rolling_map(lambda s: np.nanstd(s, ddof=0), window, min_samples=1).over("vt_symbol")
    )
    return DataProxy(df)


def ts_slope(feature: DataProxy, window: int) -> DataProxy:
    """
    计算滚动线性回归斜率（优化实现）。

    斜率反映窗口内序列的线性趋势方向与强度。
    """
    # 预计算 x 相关的常数 (x = 0, 1, 2, ..., window-1)
    n = window
    sum_x = n * (n - 1) / 2  # 等差数列求和
    sum_x2 = (n - 1) * n * (2 * n - 1) / 6  # 平方和公式
    denominator = n * sum_x2 - sum_x * sum_x

    # 计算 sum(i * y[t-window+1+i]) for i in 0..window-1
    # 等价于 sum((window-1-j) * y[t-j]) for j in 0..window-1
    sum_xy_expr: pl.Expr = pl.sum_horizontal([
        (window - 1 - j) * pl.col("data").shift(j)
        for j in range(window)
    ])

    df: pl.DataFrame = feature.df.with_columns([
        pl.col("data").rolling_sum(window, min_samples=window).over("vt_symbol").alias("sum_y"),
        sum_xy_expr.over("vt_symbol").alias("sum_xy")
    ])

    df = df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        ((n * pl.col("sum_xy") - sum_x * pl.col("sum_y")) / denominator).alias("data")
    )
    return DataProxy(df)


def ts_quantile(feature: DataProxy, window: int, quantile: float) -> DataProxy:
    """
    计算滚动分位值。

    可用于动态阈值构造，例如分位突破或分位回归策略。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rolling_map(lambda s: s.quantile(quantile=quantile, interpolation="linear"), window).over("vt_symbol")
    )
    return DataProxy(df)


def ts_rsquare(feature: DataProxy, window: int) -> DataProxy:
    """
    计算滚动线性回归的 R²（优化实现）。

    R² 越高表示当前窗口越接近线性趋势，可用于筛选“趋势可解释性”更强的样本。
    """
    # 预计算 x 相关的常数 (x = 0, 1, 2, ..., window-1)
    n = window
    sum_x2 = (n - 1) * n * (2 * n - 1) / 6  # 平方和公式
    mean_x = (n - 1) / 2
    var_x = sum_x2 / n - mean_x * mean_x  # 总体方差

    # 计算 sum(i * y[t-window+1+i]) for i in 0..window-1
    sum_xy_expr: pl.Expr = pl.sum_horizontal([
        (window - 1 - j) * pl.col("data").shift(j)
        for j in range(window)
    ])

    df: pl.DataFrame = feature.df.with_columns([
        pl.col("data").rolling_sum(window, min_samples=window).over("vt_symbol").alias("sum_y"),
        pl.col("data").rolling_var(window, min_samples=window, ddof=0).over("vt_symbol").alias("var_y"),
        sum_xy_expr.over("vt_symbol").alias("sum_xy")
    ])

    # mean_y 和 cov(x, y) = E(xy) - E(x)E(y)
    df = df.with_columns([
        (pl.col("sum_y") / n).alias("mean_y"),
    ])

    df = df.with_columns([
        (pl.col("sum_xy") / n - mean_x * pl.col("mean_y")).alias("cov_xy")
    ])

    # r = cov(x,y) / (std_x * std_y), r^2 = cov(x,y)^2 / (var_x * var_y)
    df = df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        (pl.col("cov_xy").pow(2) / (var_x * pl.col("var_y"))).alias("data")
    )

    df = df.with_columns(
        pl.when(pl.col("data").is_infinite() | pl.col("data").is_nan())
        .then(None)
        .otherwise(pl.col("data"))
        .alias("data")
    )

    return DataProxy(df)


def ts_resi(feature: DataProxy, window: int) -> DataProxy:
    """
    计算滚动线性回归残差（优化实现）。

    残差表示当前值相对拟合趋势线的偏离，常用于异常偏离或回归修正信号。
    """
    # 预计算 x 相关的常数 (x = 0, 1, 2, ..., window-1)
    n = window
    sum_x = n * (n - 1) / 2  # 等差数列求和
    sum_x2 = (n - 1) * n * (2 * n - 1) / 6  # 平方和公式
    mean_x = (n - 1) / 2
    denominator = n * sum_x2 - sum_x * sum_x

    # 计算 sum(i * y[t-window+1+i]) for i in 0..window-1
    sum_xy_expr: pl.Expr = pl.sum_horizontal([
        (window - 1 - j) * pl.col("data").shift(j)
        for j in range(window)
    ])

    df: pl.DataFrame = feature.df.with_columns([
        pl.col("data").rolling_sum(window, min_samples=window).over("vt_symbol").alias("sum_y"),
        sum_xy_expr.over("vt_symbol").alias("sum_xy")
    ])

    # 计算 slope 和 intercept
    df = df.with_columns([
        ((n * pl.col("sum_xy") - sum_x * pl.col("sum_y")) / denominator).alias("slope"),
        (pl.col("sum_y") / n).alias("mean_y"),
    ])

    df = df.with_columns([
        (pl.col("mean_y") - pl.col("slope") * mean_x).alias("intercept")
    ])

    # residual = y - (slope * (n-1) + intercept)，最后一个点的 x = n-1
    df = df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        (pl.col("data") - (pl.col("slope") * (n - 1) + pl.col("intercept"))).alias("data")
    )

    return DataProxy(df)


def ts_corr(feature1: DataProxy, feature2: DataProxy, window: int) -> DataProxy:
    """
    计算两路特征的滚动相关系数。

    用于刻画因子间联动强度、共振关系或去冗余分析。
    """
    df_merged: pl.DataFrame = feature1.df.join(feature2.df, on=["datetime", "vt_symbol"])

    df: pl.DataFrame = df_merged.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.rolling_corr("data", "data_right", window_size=window, min_samples=1).over("vt_symbol").alias("data")
    )

    df = df.with_columns(
        pl.when(pl.col("data").is_infinite()).then(None).otherwise(pl.col("data")).alias("data")
    )

    return DataProxy(df)


def ts_less(feature1: DataProxy, feature2: DataProxy | float) -> DataProxy:
    """
    逐样本取两路输入较小值。

    常用于时序特征截断上界。
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


def ts_greater(feature1: DataProxy, feature2: DataProxy | float) -> DataProxy:
    """
    逐样本取两路输入较大值。

    常用于时序特征设置下界。
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


def ts_log(feature: DataProxy) -> DataProxy:
    """
    对时序特征做自然对数变换。

    常用于压缩长尾分布，提升模型稳定性。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").log().over("vt_symbol")
    )
    return DataProxy(df)


def ts_abs(feature: DataProxy) -> DataProxy:
    """
    取时序特征绝对值。

    适用于仅关心波动幅度、忽略方向的场景。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").abs().over("vt_symbol")
    )
    return DataProxy(df)


def ts_delta(feature: DataProxy, window: int) -> DataProxy:
    """
    计算差分：当前值减去 `window` 周期前的值。

    是最常用的动量/变化率基础构件。
    """
    return feature - ts_delay(feature, window)


def ts_cov(feature1: DataProxy, feature2: DataProxy, window: int) -> DataProxy:
    """
    计算两路特征的滚动协方差。

    通过 `corr * std1 * std2` 组合得到，反映共同波动方向与幅度。
    """
    return ts_corr(feature1, feature2, window) * ts_std(feature1, window) * ts_std(feature2, window)


def ts_decay_linear(feature: DataProxy, window: int) -> DataProxy:
    """
    计算滚动线性衰减加权平均。

    常用于“近期更重要”的平滑特征构造。
    """
    def decay_func(s: pl.Series) -> float:
        """对单个窗口序列计算线性权重均值。"""
        weights = pl.Series(range(window, 0, -1))
        return float((s * weights).sum() / (window * (window + 1) / 2))

    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rolling_map(lambda s: decay_func(s), window).over("vt_symbol")
    )
    return DataProxy(df)


def ts_product(feature: DataProxy, window: int) -> DataProxy:
    """
    计算滚动窗口连乘。

    常用于构造复合增长类特征或多期比例累计项。
    """
    df: pl.DataFrame = feature.df.select(
        pl.col("datetime"),
        pl.col("vt_symbol"),
        pl.col("data").rolling_map(lambda s: s.product(), window).over("vt_symbol")
    )
    return DataProxy(df)
