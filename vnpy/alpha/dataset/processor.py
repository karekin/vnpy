from datetime import datetime

import numpy as np
import polars as pl

from .utility import to_datetime


def process_drop_na(df: pl.DataFrame, names: list[str] | None = None) -> pl.DataFrame:
    """
    删除指定特征列存在缺失值的样本行。

    默认处理 `datetime/vt_symbol` 之后、`label` 之前的特征列，
    常用于训练前严格样本清洗。
    """
    if names is None:
        names = df.columns[2:-1]

    for name in names:
        df = df.with_columns(
            pl.col(name).fill_nan(None)
        )
    df = df.drop_nulls(subset=names)
    return df


def process_fill_na(df: pl.DataFrame, fill_value: float, fill_label: bool = True) -> pl.DataFrame:
    """
    用固定值填充缺失值。

    `fill_label=True` 时连同标签列一起填充；
    否则只填充特征列，保留标签缺失用于后续过滤。
    """
    if fill_label:
        df = df.fill_null(fill_value)
        df = df.fill_nan(fill_value)
    else:
        df = df.with_columns(
            [pl.col(col).fill_null(fill_value).fill_nan(fill_value) for col in df.columns[2:-1]]
        )
    return df


def process_cs_norm(
    df: pl.DataFrame,
    names: list[str],
    method: str         # robust/zscore
) -> pl.DataFrame:
    """
    按交易时点做截面标准化。

    支持两种口径：
    1. `robust`：使用中位数和 MAD，抗极端值能力更强。
    2. 其他值：使用均值和标准差的 z-score。
    """
    _df: pl.DataFrame = df.fill_nan(None)

    # 鲁棒标准化：x -> (x - median) / (MAD * 1.4826)，并裁剪到 [-3, 3]。
    if method == "robust":
        for col in names:
            df = df.with_columns(
                _df.select(
                    (pl.col(col) - pl.col(col).median()).over("datetime").alias(col),
                )
            )

            df = df.with_columns(
                df.select(
                    pl.col(col).abs().median().over("datetime").alias("mad"),
                )
            )

            df = df.with_columns(
                (pl.col(col) / pl.col("mad") / 1.4826).clip(-3, 3).alias(col)
            ).drop(["mad"])
    # 经典 z-score：x -> (x - mean) / std。
    else:
        for col in names:
            df = df.with_columns(
                _df.select(
                    pl.col(col).mean().over("datetime").alias("mean"),
                    pl.col(col).std().over("datetime").alias("std"),
                )
            )

            df = df.with_columns(
                (pl.col(col) - pl.col("mean")) / pl.col("std").alias(col)
            ).drop(["mean", "std"])

    return df


def process_robust_zscore_norm(
    df: pl.DataFrame,
    fit_start_time: datetime | str | None = None,
    fit_end_time: datetime | str | None = None,
    clip_outlier: bool = True
) -> pl.DataFrame:
    """
    使用“训练窗口统计量”做鲁棒 z-score 标准化。

    处理逻辑：
    1. 先在 `fit_start_time~fit_end_time`（若提供）估计中位数和 MAD。
    2. 再把该统计量应用到整张表，避免未来数据泄露。
    3. 可选裁剪到 [-3, 3] 降低极端值影响。
    """
    _df: pl.DataFrame = df.fill_nan(None)

    if fit_start_time and fit_end_time:
        fit_start_time = to_datetime(fit_start_time)
        fit_end_time = to_datetime(fit_end_time)
        _df = _df.filter((pl.col("datetime") >= fit_start_time) & (pl.col("datetime") <= fit_end_time))

    cols = df.columns[2:-1]
    X = _df.select(cols).to_numpy()

    mean_train = np.nanmedian(X, axis=0)
    std_train = np.nanmedian(np.abs(X - mean_train), axis=0)
    std_train += 1e-12
    std_train *= 1.4826

    for name in cols:
        normalized_col = (
            (pl.col(name) - mean_train[cols.index(name)]) / std_train[cols.index(name)]
        ).cast(pl.Float64)

        if clip_outlier:
            normalized_col = normalized_col.clip(-3, 3)

        df = df.with_columns(normalized_col.alias(name))

    return df


def process_cs_rank_norm(df: pl.DataFrame, names: list[str]) -> pl.DataFrame:
    """
    按交易时点做截面排名归一化。

    先把排名映射到 (0,1)，再平移缩放到近似标准正态区间，
    适合仅关心相对顺序而非绝对数值的因子。
    """
    _df: pl.DataFrame = df.fill_nan(None)

    _df = _df.with_columns([
        ((pl.col(col).rank("average").over("datetime") / pl.col("datetime").count().over("datetime")) - 0.5) * 3.46
        for col in names
    ])

    df = df.with_columns([
        _df[col].alias(col) for col in names
    ])

    return df
