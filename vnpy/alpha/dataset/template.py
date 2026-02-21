import time
from datetime import datetime
from typing import cast
from collections.abc import Callable
from multiprocessing import get_context
from multiprocessing.context import BaseContext

import polars as pl
import pandas as pd
from tqdm import tqdm
from alphalens.utils import get_clean_factor_and_forward_returns    # type: ignore
from alphalens.tears import create_full_tear_sheet                  # type: ignore

from ..logger import logger
from .utility import (
    to_datetime,
    Segment,
    calculate_by_expression,
    calculate_by_polars
)


class AlphaDataset:
    """
    Alpha 研究数据集基类。

    负责把原始行情表转换为可直接用于模型训练和信号推理的数据：
    1. 计算表达式特征和标签
    2. 合并外部特征结果
    3. 按时间切分训练/验证/测试区间
    4. 分别维护 `infer`（推理）和 `learn`（训练）两条预处理流水线
    """

    def __init__(
        self,
        df: pl.DataFrame,
        train_period: tuple[str, str],
        valid_period: tuple[str, str],
        test_period: tuple[str, str],
        process_type: str = "append"
    ) -> None:
        """
        初始化数据集配置和缓存容器。

        `process_type` 决定训练预处理是否在推理预处理结果基础上继续追加：
        1. `append`：`learn` 以 `infer` 结果为起点（常用，保持线上线下处理一致）
        2. 其他值：`learn` 从原始特征数据单独处理
        """
        self.df: pl.DataFrame = df

        # 各阶段数据缓存。
        self.result_df: pl.DataFrame
        self.raw_df: pl.DataFrame
        self.infer_df: pl.DataFrame
        self.learn_df: pl.DataFrame

        # 数据分段时间窗口。
        self.data_periods: dict[Segment, tuple[str, str]] = {
            Segment.TRAIN: train_period,
            Segment.VALID: valid_period,
            Segment.TEST: test_period
        }

        self.feature_expressions: dict[str, str | pl.expr.expr.Expr] = {}
        self.feature_results: dict[str, pl.DataFrame] = {}
        self.label_expression: str = ""

        self.process_type: str = process_type
        self.infer_processors: list = []
        self.learn_processors: list = []

    def add_feature(
        self,
        name: str,
        expression: str | pl.expr.expr.Expr | None = None,
        result: pl.DataFrame | None = None
    ) -> None:
        """
        注册一个特征。

        两种来源二选一：
        1. `expression`：由表达式在 `prepare_data` 阶段并行计算
        2. `result`：外部已计算好的特征表（需含 `datetime/vt_symbol/data`）
        """
        if expression is not None and result is not None:
            raise ValueError("Only one of 'expression' or 'result' can be provided")

        if expression is not None:
            self.feature_expressions[name] = expression
        elif result is not None:
            self.feature_results[name] = result

    def set_label(self, expression: str) -> None:
        """
        设置标签表达式。

        标签会在 `prepare_data` 中与特征同批次计算，并固定放到最后一列。
        """
        self.label_expression = expression

    def add_processor(self, task: str, processor: Callable[[pl.DataFrame], None]) -> None:
        """
        注册预处理算子。

        `task="infer"` 表示推理链算子；其他值默认进入训练链算子。
        """
        if task == "infer":
            self.infer_processors.append(processor)
        else:
            self.learn_processors.append(processor)

    def prepare_data(self, filters: dict | None = None, max_workers: int | None = None) -> None:
        """
        构建基础特征表（`raw_df`）。

        主要步骤：
        1. 并行计算表达式特征与标签
        2. 合并外部特征结果
        3. 可选按成分过滤样本（只保留某标的在某时间段内数据）
        4. 初始化 `raw/infer/learn` 三份数据缓存
        """
        # 表达式计算结果列表。
        results: list = []

        # 收集待计算表达式。
        expressions: list[tuple[str, str | pl.expr.expr.Expr]] = list(self.feature_expressions.items())

        if self.label_expression:
            expressions.append(("label", self.label_expression))

        # 使用多进程并行计算表达式特征。
        logger.info("开始计算表达式因子特征")

        args: list[tuple] = [(self.df, name, expression) for name, expression in expressions]

        context: BaseContext = get_context("spawn")

        with context.Pool(processes=max_workers) as pool:
            # 并行执行特征计算。
            it = pool.imap(calculate_feature, args)

            # 收集结果列。
            for result in tqdm(it, total=len(args)):
                results.append(result)

        self.result_df = self.df.with_columns(results)

        # 合并外部结果型特征。
        logger.info("开始合并结果数据因子特征")

        label_exist: bool = "label" in self.result_df
        for name, feature_result in tqdm(self.feature_results.items()):
            feature_result = feature_result.rename({"data": name})
            self.result_df = self.result_df.join(feature_result, on=["datetime", "vt_symbol"], how="left")

        if label_exist:
            # 标签列固定放最后，便于后续按列切片。
            cols: list = [col for col in self.result_df.columns if col != "label"] + ["label"]
            self.result_df = self.result_df.select(cols).sort(["datetime", "vt_symbol"])

        # Generate raw data
        raw_df = self.result_df.fill_null(float("nan"))

        if filters:
            logger.info("开始筛选成分股数据")

            dfs: list[pl.DataFrame] = []

            for vt_symbol, ranges in tqdm(filters.items(), total=len(filters)):
                for start, end in ranges:
                    temp_df = raw_df.filter(
                        (pl.col("vt_symbol") == vt_symbol)
                        & (pl.col("datetime") >= pl.lit(start))
                        & (pl.col("datetime") <= pl.lit(end))
                    )
                    dfs.append(temp_df)

            raw_df = pl.concat(dfs)

        # 仅保留新增特征列（原始行情基础列不进入建模特征表）。
        select_columns: list[str] = ["datetime", "vt_symbol"] + raw_df.columns[self.df.width:]
        self.raw_df = raw_df.select(select_columns).sort(["datetime", "vt_symbol"])

        self.infer_df = self.raw_df
        self.learn_df = self.raw_df

    def process_data(self) -> None:
        """
        执行预处理流水线，生成 `infer_df` 和 `learn_df`。

        处理顺序：
        1. 先对 `infer_df` 依次执行推理链算子
        2. 再根据 `process_type` 决定训练链起点，并执行训练链算子
        """
        # 生成推理数据。
        for processor in self.infer_processors:
            self.infer_df = processor(df=self.infer_df)

        # 生成训练数据。
        if self.process_type == "append":
            self.learn_df = self.infer_df

        for processor in self.learn_processors:
            self.learn_df = processor(df=self.learn_df)

    def fetch_raw(self, segment: Segment) -> pl.DataFrame:
        """
        读取指定分段的原始特征表（未经过任何 processor）。
        """
        start, end = self.data_periods[segment]
        return query_by_time(self.raw_df, start, end)

    def fetch_infer(self, segment: Segment) -> pl.DataFrame:
        """
        读取指定分段的推理数据（应用了 infer processors）。
        """
        start, end = self.data_periods[segment]
        return query_by_time(self.infer_df, start, end)

    def fetch_learn(self, segment: Segment) -> pl.DataFrame:
        """
        读取指定分段的训练数据（应用了 learn processors）。
        """
        start, end = self.data_periods[segment]
        return query_by_time(self.learn_df, start, end)

    def show_feature_performance(self, name: str) -> None:
        """
        使用 Alphalens 评估单因子表现。

        评估区间覆盖 train/valid/test 三段并集，使用收盘价构造远期收益，
        生成分组收益、IC、换手等完整报告。
        """
        starts: list[datetime] = []
        ends: list[datetime] = []

        for period in self.data_periods.values():
            starts.append(to_datetime(period[0]))
            ends.append(to_datetime(period[1]))

        start: datetime = min(starts)
        end: datetime = max(ends)

        # 截取评估区间数据。
        result_df: pl.DataFrame = query_by_time(self.result_df, start, end)
        learn_df: pl.DataFrame = query_by_time(self.learn_df, start, end)

        merged_df = (
            result_df
            .select(["datetime", "vt_symbol", "close"])
            .join(
                learn_df.select(["datetime", "vt_symbol", name]),
                on=["datetime", "vt_symbol"],
                how="inner"
            )
        )

        # 清理缺失。
        merged_df = merged_df.fill_nan(None).drop_nulls()

        # 准备因子序列。
        feature_df: pd.DataFrame = merged_df.select(["datetime", "vt_symbol", name]).to_pandas()
        feature_df.set_index(["datetime", "vt_symbol"], inplace=True)

        feature_s: pd.Series = feature_df[name]

        # 准备价格矩阵。
        price_df: pd.DataFrame = merged_df.select(["datetime", "vt_symbol", "close"]).to_pandas()
        price_df = price_df.pivot(index="datetime", columns="vt_symbol", values="close")

        # 对齐因子与远期收益标签。
        clean_data: pd.DataFrame = get_clean_factor_and_forward_returns(feature_s, price_df, quantiles=10)

        # 输出完整因子分析报告。
        create_full_tear_sheet(clean_data)

    def show_signal_performance(self, signal: pl.DataFrame) -> None:
        """
        使用 Alphalens 评估外部信号表现。

        输入 `signal` 需包含 `datetime/vt_symbol/signal`，
        方法会自动对齐价格并生成分组收益和超额表现报告。
        """
        # 信号覆盖时间范围。
        start: datetime = cast(datetime, signal["datetime"].min())
        end: datetime = cast(datetime, signal["datetime"].max())

        # 截取对应价格区间。
        df: pl.DataFrame = query_by_time(self.result_df, start, end)

        # 准备信号序列。
        signal_df: pd.DataFrame = signal.to_pandas()
        signal_df.set_index(["datetime", "vt_symbol"], inplace=True)
        signal_s: pd.Series = signal_df["signal"]

        # 准备价格矩阵。
        price_df: pd.DataFrame = df.select(["datetime", "vt_symbol", "close"]).to_pandas()
        price_df = price_df.pivot(index="datetime", columns="vt_symbol", values="close")

        # 对齐信号与远期收益。
        clean_data: pd.DataFrame = get_clean_factor_and_forward_returns(
            signal_s,
            price_df,
            max_loss=1.0,
            quantiles=10
        )

        # 输出完整信号分析报告。
        create_full_tear_sheet(clean_data)


def query_by_time(df: pl.DataFrame, start: datetime | str = "", end: datetime | str = "") -> pl.DataFrame:
    """
    按时间区间筛选数据（闭区间），并按时间和标的排序返回。
    """
    if start:
        start = to_datetime(start)
        df = df.filter(pl.col("datetime") >= start)

    if end:
        end = to_datetime(end)
        df = df.filter(pl.col("datetime") <= end)

    return df.sort(["datetime", "vt_symbol"])


def calculate_feature(args: tuple[pl.DataFrame, str, str | pl.expr.expr.Expr]) -> pl.Series:
    """
    特征计算工作函数（供多进程调用）。

    根据表达式类型选择计算器，返回命名后的单列结果。
    """
    start = time.time()

    df, name, expression = args

    if isinstance(expression, pl.expr.expr.Expr):
        result = calculate_by_polars(df, expression)["data"].alias(name)
    else:
        result = calculate_by_expression(df, expression)["data"].alias(name)

    end = time.time()
    print(f"Feature calculation {name} took: {end - start} seconds | {expression}")

    return result
