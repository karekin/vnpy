from datetime import datetime
from enum import Enum
from typing import Union

import polars as pl


class DataProxy:
    """
    `DataProxy` 是数据访问代理，负责把底层行情/因子源封装为统一读取接口。
    
    职责：
    1. 屏蔽数据源细节并提供标准读取方法。
    2. 集中处理时间切片、字段映射和缓存复用。
    3. 减少上层研究代码与底层数据结构耦合。
    
    协作：
    1. 被 `AlphaDataset` 和 `AlphaLab` 复用。
    2. 与外部数据源或本地存储协作。
    """

    def __init__(self, df: pl.DataFrame) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `df` (`pl.DataFrame`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.name: str = df.columns[-1]
        self.df: pl.DataFrame = df.rename({self.name: "data"})

        # Note that for numerical expressions, variables should be placed before numbers. e.g. a * 2

    def result(self, s: pl.Series) -> "DataProxy":
        """
        执行 `result` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `s` (`pl.Series`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        result: pl.DataFrame = self.df[["datetime", "vt_symbol"]]
        result = result.with_columns(other=s)

        return DataProxy(result)

    def __add__(self, other: Union["DataProxy", int, float]) -> "DataProxy":
        """
        执行 `__add__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `other` (`Union['DataProxy', int, float]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        if isinstance(other, DataProxy):
            s: pl.Series = self.df["data"] + other.df["data"]
        else:
            s = self.df["data"] + other
        return self.result(s)

    def __sub__(self, other: Union["DataProxy", int, float]) -> "DataProxy":
        """
        执行 `__sub__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `other` (`Union['DataProxy', int, float]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        if isinstance(other, DataProxy):
            s: pl.Series = self.df["data"] - other.df["data"]
        else:
            s = self.df["data"] - other
        return self.result(s)

    def __mul__(self, other: Union["DataProxy", int, float]) -> "DataProxy":
        """
        执行 `__mul__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `other` (`Union['DataProxy', int, float]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        if isinstance(other, DataProxy):
            s: pl.Series = self.df["data"] * other.df["data"]
        else:
            s = self.df["data"] * other
        return self.result(s)

    def __rmul__(self, other: Union["DataProxy", int, float]) -> "DataProxy":
        """
        执行 `__rmul__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `other` (`Union['DataProxy', int, float]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        if isinstance(other, DataProxy):
            s: pl.Series = self.df["data"] * other.df["data"]
        else:
            s = self.df["data"] * other
        return self.result(s)

    def __truediv__(self, other: Union["DataProxy", int, float]) -> "DataProxy":
        """
        执行 `__truediv__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `other` (`Union['DataProxy', int, float]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        if isinstance(other, DataProxy):
            s: pl.Series = self.df["data"] / other.df["data"]
        else:
            s = self.df["data"] / other
        return self.result(s)

    def __abs__(self) -> "DataProxy":
        """
        执行 `__abs__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        s: pl.Series = self.df["data"].abs()
        return self.result(s)

    def __gt__(self, other: Union["DataProxy", int, float]) -> "DataProxy":
        """
        执行 `__gt__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `other` (`Union['DataProxy', int, float]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        if isinstance(other, DataProxy):
            s: pl.Series = self.df["data"] > other.df["data"]
        else:
            s = self.df["data"] > other
        return self.result(s.cast(pl.Int32))

    def __ge__(self, other: Union["DataProxy", int, float]) -> "DataProxy":
        """
        执行 `__ge__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `other` (`Union['DataProxy', int, float]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        if isinstance(other, DataProxy):
            s: pl.Series = self.df["data"] >= other.df["data"]
        else:
            s = self.df["data"] >= other
        return self.result(s.cast(pl.Int32))

    def __lt__(self, other: Union["DataProxy", int, float]) -> "DataProxy":
        """
        执行 `__lt__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `other` (`Union['DataProxy', int, float]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        if isinstance(other, DataProxy):
            s: pl.Series = self.df["data"] < other.df["data"]
        else:
            s = self.df["data"] < other
        return self.result(s.cast(pl.Int32))

    def __le__(self, other: Union["DataProxy", int, float]) -> "DataProxy":
        """
        执行 `__le__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `other` (`Union['DataProxy', int, float]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        if isinstance(other, DataProxy):
            s: pl.Series = self.df["data"] <= other.df["data"]
        else:
            s = self.df["data"] <= other
        return self.result(s.cast(pl.Int32))

    def __eq__(self, other: Union["DataProxy", int, float]) -> "DataProxy":    # type: ignore
        """
        执行 `__eq__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `other` (`Union['DataProxy', int, float]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `'DataProxy'`：返回该方法计算或查询得到的结果。
        """
        if isinstance(other, DataProxy):
            s = self.df["data"] == other.df["data"]
        else:
            s = self.df["data"] == other
        return self.result(s.cast(pl.Int32))


def calculate_by_expression(df: pl.DataFrame, expression: str) -> pl.DataFrame:
    """Execute calculation based on expression"""
    # Import operators locally to avoid polluting global namespace
    from .ts_function import (              # noqa
        ts_delay,
        ts_min, ts_max,
        ts_argmax, ts_argmin,
        ts_rank, ts_sum,
        ts_mean, ts_std,
        ts_slope, ts_quantile,
        ts_rsquare, ts_resi,
        ts_corr,
        ts_less, ts_greater,
        ts_log, ts_abs,
        ts_delta, ts_cov,
        ts_decay_linear,
        ts_product
    )
    from .cs_function import (              # noqa
        cs_rank,
        cs_mean,
        cs_std,
        cs_sum,
        cs_scale
    )
    from .ta_function import (              # noqa
        ta_rsi,
        ta_atr
    )
    from .math_function import (              # noqa
        less, greater, log, abs,
        sign, pow1, pow2,
        quesval, quesval2
    )

    # Extract feature objects to local space
    d: dict = locals()

    for column in df.columns:
        # Filter index columns
        if column in {"datetime", "vt_symbol"}:
            continue

        # Cache feature df
        column_df = df[["datetime", "vt_symbol", column]]
        d[column] = DataProxy(column_df)

    # Use eval to execute calculation
    other: DataProxy = eval(expression, {}, d)

    # Return result DataFrame
    return other.df


def calculate_by_polars(df: pl.DataFrame, expression: pl.expr.expr.Expr) -> pl.DataFrame:
    """Execute calculation based on Polars expression"""
    return df.select([
        "datetime",
        "vt_symbol",
        expression.alias("data")
    ])


def to_datetime(arg: datetime | str) -> datetime:
    """Convert time data type"""
    if isinstance(arg, str):
        if "-" in arg:
            fmt: str = "%Y-%m-%d"
        else:
            fmt = "%Y%m%d"

        return datetime.strptime(arg, fmt)
    else:
        return arg


class Segment(Enum):
    """
    `Segment` 定义数据集分段枚举，表示训练集、验证集、测试集等阶段。
    
    职责：
    1. 统一不同模块对数据阶段的命名。
    2. 避免字符串硬编码导致的分支错误。
    3. 提升实验配置与结果记录的一致性。
    
    协作：
    1. 用于 `AlphaDataset` 切分与 `AlphaModel` 训练流程。
    2. 可被回测和评估模块识别。
    """

    TRAIN = 1
    VALID = 2
    TEST = 3
