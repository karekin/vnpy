"""
技术指标算子。

该模块把 `DataProxy` 数据转换为 TA-Lib 可处理的 pandas 结构，
计算完成后再转回 polars，便于接入现有特征工程流水线。
"""

import talib
import polars as pl
import pandas as pd

from .utility import DataProxy


def to_pd_series(feature: DataProxy) -> pd.Series:
    """
    把 `DataProxy` 转为 pandas `Series`（多重索引：`datetime/vt_symbol`）。

    供 TA-Lib 指标函数直接使用。
    """
    series: pd.Series = feature.df.to_pandas().set_index(["datetime", "vt_symbol"])["data"]
    return series


def to_pl_dataframe(series: pd.Series) -> pl.DataFrame:
    """
    把 TA-Lib 输出的 pandas `Series` 转回标准三列表结构。

    输出列固定为：`datetime`, `vt_symbol`, `data`。
    """
    return pl.from_pandas(series.reset_index().rename(columns={0: "data"}))


def ta_rsi(close: DataProxy, window: int) -> DataProxy:
    """
    按合约计算 RSI 动量指标。

    业务上常用于判断短期超买超卖和反转强度。
    """
    close_: pd.Series = to_pd_series(close)

    result: pd.Series = talib.RSI(close_, timeperiod=window)   # type: ignore

    df: pl.DataFrame = to_pl_dataframe(result)
    return DataProxy(df)


def ta_atr(high: DataProxy, low: DataProxy, close: DataProxy, window: int) -> DataProxy:
    """
    按合约计算 ATR 波动率指标。

    业务上常用于仓位规模控制、止损阈值设置和波动率过滤。
    """
    high_: pd.Series = to_pd_series(high)
    low_: pd.Series = to_pd_series(low)
    close_: pd.Series = to_pd_series(close)

    result: pd.Series = talib.ATR(high_, low_, close_, timeperiod=window)   # type: ignore

    df: pl.DataFrame = to_pl_dataframe(result)
    return DataProxy(df)
