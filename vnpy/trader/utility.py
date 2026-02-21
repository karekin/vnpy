"""
General utility functions.
"""

import json
import sys
from datetime import datetime, time
from pathlib import Path
from collections.abc import Callable
from decimal import Decimal
from math import floor, ceil
from typing import overload, Literal

import numpy as np
import talib
from zoneinfo import ZoneInfo, available_timezones      # noqa

from .object import BarData, TickData
from .constant import Exchange, Interval
from .locale import _


def extract_vt_symbol(vt_symbol: str) -> tuple[str, Exchange]:
    """
    拆分统一合约键 `vt_symbol`。

    `vt_symbol` 在 vn.py 中的标准格式是 `symbol.exchange`，
    例如 `rb2405.SHFE`。本函数把它还原成：
    1. 原始合约代码 `symbol`
    2. 交易所枚举 `Exchange`
    """
    symbol, exchange_str = vt_symbol.rsplit(".", 1)
    return symbol, Exchange(exchange_str)


def generate_vt_symbol(symbol: str, exchange: Exchange) -> str:
    """
    生成统一合约键 `vt_symbol`。

    该键是系统内跨模块引用合约的主键（行情、委托、持仓都会用到），
    格式固定为 `symbol.exchange`。
    """
    return f"{symbol}.{exchange.value}"


def _get_trader_dir(temp_name: str) -> tuple[Path, Path]:
    """
    确定交易终端的工作目录和临时数据目录。

    查找顺序：
    1. 先看当前启动目录下是否已有 `.vntrader`（便于项目内便携部署）
    2. 若没有，则退回用户 Home 目录下的 `.vntrader`（默认方案）

    返回 `(TRADER_DIR, TEMP_DIR)`，后续配置文件、缓存、日志都依赖这两个路径。
    """
    cwd: Path = Path.cwd()
    temp_path: Path = cwd.joinpath(temp_name)

    # 优先使用当前目录下已有的 .vntrader，便于随项目一起管理运行数据。
    if temp_path.exists():
        return cwd, temp_path

    # 当前目录不存在时，回退到用户 Home 目录。
    home_path: Path = Path.home()
    temp_path = home_path.joinpath(temp_name)

    # Home 目录下也不存在则自动创建。
    if not temp_path.exists():
        temp_path.mkdir()

    return home_path, temp_path


TRADER_DIR, TEMP_DIR = _get_trader_dir(".vntrader")
sys.path.append(str(TRADER_DIR))


def get_file_path(filename: str) -> Path:
    """
    返回 `.vntrader` 目录下某个文件的绝对路径。

    用于统一定位配置文件、缓存文件等运行时落盘文件。
    """
    return TEMP_DIR.joinpath(filename)


def get_folder_path(folder_name: str) -> Path:
    """
    返回 `.vntrader` 下指定子目录路径；目录不存在会自动创建。

    常用于存放数据库、回测结果、导出报表等按目录组织的数据。
    """
    folder_path: Path = TEMP_DIR.joinpath(folder_name)
    if not folder_path.exists():
        folder_path.mkdir()
    return folder_path


def get_icon_path(filepath: str, ico_name: str) -> str:
    """
    按 UI 模块文件路径推导图标文件路径。

    约定图标放在模块同级 `ico/` 子目录，便于应用模块自带资源。
    """
    ui_path: Path = Path(filepath).parent
    icon_path: Path = ui_path.joinpath("ico", ico_name)
    return str(icon_path)


def load_json(filename: str) -> dict:
    """
    从 `.vntrader` 目录读取 JSON 文件。

    若文件不存在，会先创建一个空 JSON 文件并返回空字典，
    这样上层调用无需额外处理“首次启动文件缺失”场景。
    """
    filepath: Path = get_file_path(filename)

    if filepath.exists():
        with open(filepath, encoding="UTF-8") as f:
            data: dict = json.load(f)
        return data
    else:
        save_json(filename, {})
        return {}


def save_json(filename: str, data: dict) -> None:
    """
    把数据写入 `.vntrader` 下的 JSON 文件。

    采用 UTF-8 + pretty print，方便手动查看和排查配置问题。
    """
    filepath: Path = get_file_path(filename)
    with open(filepath, mode="w+", encoding="UTF-8") as f:
        json.dump(
            data,
            f,
            indent=4,
            ensure_ascii=False
        )


def round_to(value: float, target: float) -> float:
    """
    按最小变动单位四舍五入。

    典型用于把价格对齐到合约 `pricetick`，避免下单价格精度不合法。
    """
    decimal_value: Decimal = Decimal(str(value))
    decimal_target: Decimal = Decimal(str(target))
    rounded: float = float(int(round(decimal_value / decimal_target)) * decimal_target)
    return rounded


def floor_to(value: float, target: float) -> float:
    """
    按最小变动单位向下取整。

    常用于保守定价：保证结果不高于输入值，且符合交易所跳价规则。
    """
    decimal_value: Decimal = Decimal(str(value))
    decimal_target: Decimal = Decimal(str(target))
    result: float = float(int(floor(decimal_value / decimal_target)) * decimal_target)
    return result


def ceil_to(value: float, target: float) -> float:
    """
    按最小变动单位向上取整。

    常用于积极定价：保证结果不低于输入值，且符合交易所跳价规则。
    """
    decimal_value: Decimal = Decimal(str(value))
    decimal_target: Decimal = Decimal(str(target))
    result: float = float(int(ceil(decimal_value / decimal_target)) * decimal_target)
    return result


def get_digits(value: float) -> int:
    """
    计算浮点数需要保留的小数位数。

    支持普通小数和科学计数法（如 `1e-5`），
    常用于界面格式化和价格精度推导。
    """
    value_str: str = str(value)

    if "e-" in value_str:
        _, buf = value_str.split("e-")
        return int(buf)
    elif "." in value_str:
        _, buf = value_str.split(".")
        return len(buf)
    else:
        return 0


class BarGenerator:
    """
    K线合成器。
    
    用于把 Tick 或 1分钟K 线聚合成更高周期 K 线（分钟/小时/日），
    并在周期完成时通过回调把结果推给策略。
    """

    def __init__(
        self,
        on_bar: Callable,
        window: int = 0,
        on_window_bar: Callable | None = None,
        interval: Interval = Interval.MINUTE,
        daily_end: time | None = None
    ) -> None:
        """
        初始化K线合成参数与回调。
        
        `on_bar` 接收1分钟K，`on_window_bar` 接收目标周期K。
        """
        self.bar: BarData | None = None
        self.on_bar: Callable = on_bar

        self.interval: Interval = interval
        self.interval_count: int = 0

        self.hour_bar: BarData | None = None
        self.daily_bar: BarData | None = None

        self.window: int = window
        self.window_bar: BarData | None = None
        self.on_window_bar: Callable | None = on_window_bar

        self.last_tick: TickData | None = None

        self.daily_end: time | None = daily_end
        if self.interval == Interval.DAILY and not self.daily_end:
            raise RuntimeError(_("合成日K线必须传入每日收盘时间"))

    def update_tick(self, tick: TickData) -> None:
        """
        输入最新 Tick 并更新当前分钟K。
        
        分钟切换时会先回调上一根1分钟K，再开启新分钟。
        """
        new_minute: bool = False

        # Filter tick data with 0 last price
        if not tick.last_price:
            return

        if not self.bar:
            new_minute = True
        elif (
            (self.bar.datetime.minute != tick.datetime.minute)
            or (self.bar.datetime.hour != tick.datetime.hour)
        ):
            self.bar.datetime = self.bar.datetime.replace(
                second=0, microsecond=0
            )
            self.on_bar(self.bar)

            new_minute = True

        if new_minute:
            self.bar = BarData(
                symbol=tick.symbol,
                exchange=tick.exchange,
                interval=Interval.MINUTE,
                datetime=tick.datetime,
                gateway_name=tick.gateway_name,
                open_price=tick.last_price,
                high_price=tick.last_price,
                low_price=tick.last_price,
                close_price=tick.last_price,
                open_interest=tick.open_interest
            )
        elif self.bar:
            self.bar.high_price = max(self.bar.high_price, tick.last_price)
            if self.last_tick and tick.high_price > self.last_tick.high_price:
                self.bar.high_price = max(self.bar.high_price, tick.high_price)

            self.bar.low_price = min(self.bar.low_price, tick.last_price)
            if self.last_tick and tick.low_price < self.last_tick.low_price:
                self.bar.low_price = min(self.bar.low_price, tick.low_price)

            self.bar.close_price = tick.last_price
            self.bar.open_interest = tick.open_interest
            self.bar.datetime = tick.datetime

        if self.last_tick and self.bar:
            volume_change: float = tick.volume - self.last_tick.volume
            self.bar.volume += max(volume_change, 0)

            turnover_change: float = tick.turnover - self.last_tick.turnover
            self.bar.turnover += max(turnover_change, 0)

        self.last_tick = tick

    def update_bar(self, bar: BarData) -> None:
        """
        把 1分钟K 继续聚合到目标周期窗口（分钟/小时/日）。
        """
        if self.interval == Interval.MINUTE:
            self.update_bar_minute_window(bar)
        elif self.interval == Interval.HOUR:
            self.update_bar_hour_window(bar)
        else:
            self.update_bar_daily_window(bar)

    def update_bar_minute_window(self, bar: BarData) -> None:
        """
        把分钟K合成为 N 分钟窗口。
        
        窗口满时通过 `on_window_bar` 输出。
        """
        # If not inited, create window bar object
        if not self.window_bar:
            dt: datetime = bar.datetime.replace(second=0, microsecond=0)
            self.window_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price
            )
        # Otherwise, update high/low price into window bar
        else:
            self.window_bar.high_price = max(
                self.window_bar.high_price,
                bar.high_price
            )
            self.window_bar.low_price = min(
                self.window_bar.low_price,
                bar.low_price
            )

        # Update close price/volume/turnover into window bar
        self.window_bar.close_price = bar.close_price
        self.window_bar.volume += bar.volume
        self.window_bar.turnover += bar.turnover
        self.window_bar.open_interest = bar.open_interest

        # Check if window bar completed
        if not (bar.datetime.minute + 1) % self.window:
            if self.on_window_bar:
                self.on_window_bar(self.window_bar)

            self.window_bar = None

    def update_bar_hour_window(self, bar: BarData) -> None:
        """
        把分钟K合成为小时K，并进一步按 `window` 聚合。
        """
        # If not inited, create window bar object
        if not self.hour_bar:
            dt: datetime = bar.datetime.replace(minute=0, second=0, microsecond=0)
            self.hour_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price,
                close_price=bar.close_price,
                volume=bar.volume,
                turnover=bar.turnover,
                open_interest=bar.open_interest
            )
            return

        finished_bar: BarData | None = None

        # If minute is 59, update minute bar into window bar and push
        if bar.datetime.minute == 59:
            self.hour_bar.high_price = max(
                self.hour_bar.high_price,
                bar.high_price
            )
            self.hour_bar.low_price = min(
                self.hour_bar.low_price,
                bar.low_price
            )

            self.hour_bar.close_price = bar.close_price
            self.hour_bar.volume += bar.volume
            self.hour_bar.turnover += bar.turnover
            self.hour_bar.open_interest = bar.open_interest

            finished_bar = self.hour_bar
            self.hour_bar = None

        # If minute bar of new hour, then push existing window bar
        elif bar.datetime.hour != self.hour_bar.datetime.hour:
            finished_bar = self.hour_bar

            dt = bar.datetime.replace(minute=0, second=0, microsecond=0)
            self.hour_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=dt,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price,
                close_price=bar.close_price,
                volume=bar.volume,
                turnover=bar.turnover,
                open_interest=bar.open_interest
            )
        # Otherwise only update minute bar
        else:
            self.hour_bar.high_price = max(
                self.hour_bar.high_price,
                bar.high_price
            )
            self.hour_bar.low_price = min(
                self.hour_bar.low_price,
                bar.low_price
            )

            self.hour_bar.close_price = bar.close_price
            self.hour_bar.volume += bar.volume
            self.hour_bar.turnover += bar.turnover
            self.hour_bar.open_interest = bar.open_interest

        # Push finished window bar
        if finished_bar:
            self.on_hour_bar(finished_bar)

    def on_hour_bar(self, bar: BarData) -> None:
        """
        处理已完成小时K。
        
        当 `window>1` 时继续拼接成多小时K。
        """
        if self.window == 1:
            if self.on_window_bar:
                self.on_window_bar(bar)
        else:
            if not self.window_bar:
                self.window_bar = BarData(
                    symbol=bar.symbol,
                    exchange=bar.exchange,
                    datetime=bar.datetime,
                    gateway_name=bar.gateway_name,
                    open_price=bar.open_price,
                    high_price=bar.high_price,
                    low_price=bar.low_price
                )
            else:
                self.window_bar.high_price = max(
                    self.window_bar.high_price,
                    bar.high_price
                )
                self.window_bar.low_price = min(
                    self.window_bar.low_price,
                    bar.low_price
                )

            self.window_bar.close_price = bar.close_price
            self.window_bar.volume += bar.volume
            self.window_bar.turnover += bar.turnover
            self.window_bar.open_interest = bar.open_interest

            self.interval_count += 1
            if not self.interval_count % self.window:
                self.interval_count = 0

                if self.on_window_bar:
                    self.on_window_bar(self.window_bar)

                self.window_bar = None

    def update_bar_daily_window(self, bar: BarData) -> None:
        """
        把分钟K聚合为日K。
        
        到达 `daily_end` 指定时间后输出当日K。
        """
        # If not inited, create daily bar object
        if not self.daily_bar:
            self.daily_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=bar.datetime,
                gateway_name=bar.gateway_name,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price
            )
        # Otherwise, update high/low price into daily bar
        else:
            self.daily_bar.high_price = max(
                self.daily_bar.high_price,
                bar.high_price
            )
            self.daily_bar.low_price = min(
                self.daily_bar.low_price,
                bar.low_price
            )

        # Update close price/volume/turnover into daily bar
        self.daily_bar.close_price = bar.close_price
        self.daily_bar.volume += bar.volume
        self.daily_bar.turnover += bar.turnover
        self.daily_bar.open_interest = bar.open_interest

        # Check if daily bar completed
        if bar.datetime.time() == self.daily_end:
            self.daily_bar.datetime = bar.datetime.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )

            if self.on_window_bar:
                self.on_window_bar(self.daily_bar)

            self.daily_bar = None

    def generate(self) -> BarData | None:
        """
        强制结束当前分钟并立即产出一根1分钟K。
        
        常用于收盘或数据流结束时补齐最后一根K。
        """
        bar: BarData | None = self.bar

        if bar:
            bar.datetime = bar.datetime.replace(second=0, microsecond=0)
            self.on_bar(bar)

        self.bar = None
        return bar


class ArrayManager:
    """
    指标计算缓存器。
    
    维护固定窗口的 OHLCV 序列，并封装 TA-Lib 指标接口。
    策略每来一根新K线调用 `update_bar`，随后可直接计算指标。
    """

    def __init__(self, size: int = 100) -> None:
        """
        初始化固定窗口大小和各价格序列缓存数组。
        """
        self.count: int = 0
        self.size: int = size
        self.inited: bool = False

        self.open_array: np.ndarray = np.zeros(size)
        self.high_array: np.ndarray = np.zeros(size)
        self.low_array: np.ndarray = np.zeros(size)
        self.close_array: np.ndarray = np.zeros(size)
        self.volume_array: np.ndarray = np.zeros(size)
        self.turnover_array: np.ndarray = np.zeros(size)
        self.open_interest_array: np.ndarray = np.zeros(size)

    def update_bar(self, bar: BarData) -> None:
        """
        写入最新K线并左移窗口。
        
        当累计数量达到窗口长度后，`inited` 置为 True。
        """
        self.count += 1
        if not self.inited and self.count >= self.size:
            self.inited = True

        self.open_array[:-1] = self.open_array[1:]
        self.high_array[:-1] = self.high_array[1:]
        self.low_array[:-1] = self.low_array[1:]
        self.close_array[:-1] = self.close_array[1:]
        self.volume_array[:-1] = self.volume_array[1:]
        self.turnover_array[:-1] = self.turnover_array[1:]
        self.open_interest_array[:-1] = self.open_interest_array[1:]

        self.open_array[-1] = bar.open_price
        self.high_array[-1] = bar.high_price
        self.low_array[-1] = bar.low_price
        self.close_array[-1] = bar.close_price
        self.volume_array[-1] = bar.volume
        self.turnover_array[-1] = bar.turnover
        self.open_interest_array[-1] = bar.open_interest

    @property
    def open(self) -> np.ndarray:
        """
        返回当前窗口的开盘价序列。
        """
        return self.open_array

    @property
    def high(self) -> np.ndarray:
        """
        返回当前窗口的最高价序列。
        """
        return self.high_array

    @property
    def low(self) -> np.ndarray:
        """
        返回当前窗口的最低价序列。
        """
        return self.low_array

    @property
    def close(self) -> np.ndarray:
        """
        返回当前窗口的收盘价序列。
        """
        return self.close_array

    @property
    def volume(self) -> np.ndarray:
        """
        返回当前窗口的成交量序列。
        """
        return self.volume_array

    @property
    def turnover(self) -> np.ndarray:
        """
        返回当前窗口的成交额序列。
        """
        return self.turnover_array

    @property
    def open_interest(self) -> np.ndarray:
        """
        返回当前窗口的持仓量序列。
        """
        return self.open_interest_array

    @overload
    def sma(self, n: int, array: Literal[False] = False) -> float:
        """
        `sma` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def sma(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `sma` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def sma(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算简单移动平均。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.SMA(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def ema(self, n: int, array: Literal[False] = False) -> float:
        """
        `ema` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def ema(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `ema` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def ema(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算指数移动平均。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.EMA(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def kama(self, n: int, array: Literal[False] = False) -> float:
        """
        `kama` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def kama(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `kama` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def kama(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算自适应均线。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.KAMA(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def wma(self, n: int, array: Literal[False] = False) -> float:
        """
        `wma` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def wma(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `wma` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def wma(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算加权移动平均。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.WMA(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def apo(self, fast_period: int, slow_period: int, matype: int = 0, array: Literal[False] = False) -> float:
        """
        `apo` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def apo(self, fast_period: int, slow_period: int, matype: int = 0, *, array: Literal[True]) -> np.ndarray:
        """
        `apo` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def apo(
        self,
        fast_period: int,
        slow_period: int,
        matype: int = 0,
        array: bool = False
    ) -> float | np.ndarray:
        """
        计算绝对价格振荡器。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.APO(self.close, fast_period, slow_period, matype)      # type: ignore
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def cmo(self, n: int, array: Literal[False] = False) -> float:
        """
        `cmo` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def cmo(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `cmo` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def cmo(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算钱德动量指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.CMO(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def mom(self, n: int, array: Literal[False] = False) -> float:
        """
        `mom` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def mom(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `mom` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def mom(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算动量指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.MOM(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def ppo(self, fast_period: int, slow_period: int, matype: int = 0, array: Literal[False] = False) -> float:
        """
        `ppo` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def ppo(self, fast_period: int, slow_period: int, matype: int = 0, *, array: Literal[True]) -> np.ndarray:
        """
        `ppo` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def ppo(
        self,
        fast_period: int,
        slow_period: int,
        matype: int = 0,
        array: bool = False
    ) -> float | np.ndarray:
        """
        计算百分比价格振荡器。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.PPO(self.close, fast_period, slow_period, matype)      # type: ignore
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def roc(self, n: int, array: Literal[False] = False) -> float:
        """
        `roc` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def roc(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `roc` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def roc(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算变动率。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.ROC(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def rocr(self, n: int, array: Literal[False] = False) -> float:
        """
        `rocr` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def rocr(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `rocr` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def rocr(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算变动比率。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.ROCR(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def rocp(self, n: int, array: Literal[False] = False) -> float:
        """
        `rocp` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def rocp(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `rocp` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def rocp(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算变动百分比。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.ROCP(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def rocr_100(self, n: int, array: Literal[False] = False) -> float:
        """
        `rocr_100` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def rocr_100(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `rocr_100` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def rocr_100(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算百分制变动比率。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.ROCR100(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def trix(self, n: int, array: Literal[False] = False) -> float:
        """
        `trix` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def trix(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `trix` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def trix(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算三重平滑动量指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.TRIX(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def std(self, n: int, nbdev: int = 1, array: Literal[False] = False) -> float:
        """
        `std` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def std(self, n: int, nbdev: int = 1, *, array: Literal[True]) -> np.ndarray:
        """
        `std` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def std(self, n: int, nbdev: int = 1, array: bool = False) -> float | np.ndarray:
        """
        计算标准差。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.STDDEV(self.close, n, nbdev)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def obv(self, array: Literal[False] = False) -> float:
        """
        `obv` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def obv(self, array: Literal[True]) -> np.ndarray:
        """
        `obv` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def obv(self, array: bool = False) -> float | np.ndarray:
        """
        计算能量潮指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.OBV(self.close, self.volume)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def cci(self, n: int, array: Literal[False] = False) -> float:
        """
        `cci` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def cci(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `cci` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def cci(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算顺势指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.CCI(self.high, self.low, self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def atr(self, n: int, array: Literal[False] = False) -> float:
        """
        `atr` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def atr(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `atr` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def atr(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算平均真实波幅。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.ATR(self.high, self.low, self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def natr(self, n: int, array: Literal[False] = False) -> float:
        """
        `natr` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def natr(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `natr` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def natr(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算标准化平均真实波幅。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.NATR(self.high, self.low, self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def rsi(self, n: int, array: Literal[False] = False) -> float:
        """
        `rsi` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def rsi(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `rsi` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def rsi(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算相对强弱指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.RSI(self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def macd(self, fast_period: int, slow_period: int, signal_period: int, array: Literal[False] = False) -> tuple[float, float, float]:
        """
        `macd` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def macd(self, fast_period: int, slow_period: int, signal_period: int, array: Literal[True]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        `macd` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def macd(
        self,
        fast_period: int,
        slow_period: int,
        signal_period: int,
        array: bool = False
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | tuple[float, float, float]:
        """
        计算 MACD。
        
        `array=True` 返回 (DIF, DEA, HIST) 全序列；否则返回最新一组值。
        """
        macd, signal, hist = talib.MACD(
            self.close, fast_period, slow_period, signal_period
        )
        if array:
            return macd, signal, hist
        return macd[-1], signal[-1], hist[-1]

    @overload
    def adx(self, n: int, array: Literal[False] = False) -> float:
        """
        `adx` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def adx(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `adx` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def adx(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算平均趋向指数。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.ADX(self.high, self.low, self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def adxr(self, n: int, array: Literal[False] = False) -> float:
        """
        `adxr` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def adxr(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `adxr` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def adxr(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算平均趋向指数平滑值。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.ADXR(self.high, self.low, self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def dx(self, n: int, array: Literal[False] = False) -> float:
        """
        `dx` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def dx(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `dx` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def dx(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算趋向指数。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.DX(self.high, self.low, self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def minus_di(self, n: int, array: Literal[False] = False) -> float:
        """
        `minus_di` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def minus_di(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `minus_di` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def minus_di(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算负方向指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.MINUS_DI(self.high, self.low, self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def plus_di(self, n: int, array: Literal[False] = False) -> float:
        """
        `plus_di` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def plus_di(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `plus_di` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def plus_di(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算正方向指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.PLUS_DI(self.high, self.low, self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def willr(self, n: int, array: Literal[False] = False) -> float:
        """
        `willr` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def willr(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `willr` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def willr(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算威廉指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.WILLR(self.high, self.low, self.close, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def ultosc(self, time_period1: int = 7, time_period2: int = 14, time_period3: int = 28, array: Literal[False] = False) -> float:
        """
        `ultosc` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def ultosc(self, time_period1: int = 7, time_period2: int = 14, time_period3: int = 28, *, array: Literal[True]) -> np.ndarray:
        """
        `ultosc` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def ultosc(
        self,
        time_period1: int = 7,
        time_period2: int = 14,
        time_period3: int = 28,
        array: bool = False
    ) -> float | np.ndarray:
        """
        计算终极振荡器。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.ULTOSC(self.high, self.low, self.close, time_period1, time_period2, time_period3)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def trange(self, array: Literal[False] = False) -> float:
        """
        `trange` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def trange(self, array: Literal[True]) -> np.ndarray:
        """
        `trange` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def trange(self, array: bool = False) -> float | np.ndarray:
        """
        计算真实波幅。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.TRANGE(self.high, self.low, self.close)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def boll(self, n: int, dev: float, array: Literal[False] = False) -> tuple[float, float]:
        """
        `boll` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def boll(self, n: int, dev: float, array: Literal[True]) -> tuple[np.ndarray, np.ndarray]:
        """
        `boll` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def boll(
        self,
        n: int,
        dev: float,
        array: bool = False
    ) -> tuple[np.ndarray, np.ndarray] | tuple[float, float]:
        """
        计算布林通道上下轨。
        
        `array=True` 返回上下轨序列；否则返回最新上下轨。
        """
        mid_array: np.ndarray = talib.SMA(self.close, n)
        std_array: np.ndarray = talib.STDDEV(self.close, n, 1)

        if array:
            up_array: np.ndarray = mid_array + std_array * dev
            down_array: np.ndarray = mid_array - std_array * dev
            return up_array, down_array
        else:
            mid: float = mid_array[-1]
            std: float = std_array[-1]
            up: float = mid + std * dev
            down: float = mid - std * dev
            return up, down

    @overload
    def keltner(self, n: int, dev: float, array: Literal[False] = False) -> tuple[float, float]:
        """
        `keltner` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def keltner(self, n: int, dev: float, array: Literal[True]) -> tuple[np.ndarray, np.ndarray]:
        """
        `keltner` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def keltner(
        self,
        n: int,
        dev: float,
        array: bool = False
    ) -> tuple[np.ndarray, np.ndarray] | tuple[float, float]:
        """
        计算肯特纳通道上下轨。
        
        `array=True` 返回上下轨序列；否则返回最新上下轨。
        """
        mid_array: np.ndarray = talib.SMA(self.close, n)
        atr_array: np.ndarray = talib.ATR(self.high, self.low, self.close, n)

        if array:
            up_array: np.ndarray = mid_array + atr_array * dev
            down_array: np.ndarray = mid_array - atr_array * dev
            return up_array, down_array
        else:
            mid: float = mid_array[-1]
            atr: float = atr_array[-1]
            up: float = mid + atr * dev
            down: float = mid - atr * dev
            return up, down

    @overload
    def donchian(self, n: int, array: Literal[False] = False) -> tuple[float, float]:
        """
        `donchian` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def donchian(self, n: int, array: Literal[True]) -> tuple[np.ndarray, np.ndarray]:
        """
        `donchian` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def donchian(
        self, n: int, array: bool = False
    ) -> tuple[np.ndarray, np.ndarray] | tuple[float, float]:
        """
        计算唐奇安通道上下轨。
        
        `array=True` 返回上下轨序列；否则返回最新上下轨。
        """
        up: np.ndarray = talib.MAX(self.high, n)
        down: np.ndarray = talib.MIN(self.low, n)

        if array:
            return up, down
        return up[-1], down[-1]

    @overload
    def aroon(self, n: int, array: Literal[False] = False) -> tuple[float, float]:
        """
        `aroon` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def aroon(self, n: int, array: Literal[True]) -> tuple[np.ndarray, np.ndarray]:
        """
        `aroon` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def aroon(
        self,
        n: int,
        array: bool = False
    ) -> tuple[np.ndarray, np.ndarray] | tuple[float, float]:
        """
        计算阿隆指标双线值。
        
        `array=True` 返回两条线的完整序列；否则返回最新值。
        """
        aroon_down, aroon_up = talib.AROON(self.high, self.low, n)

        if array:
            return aroon_up, aroon_down
        return aroon_up[-1], aroon_down[-1]

    @overload
    def aroonosc(self, n: int, array: Literal[False] = False) -> float:
        """
        `aroonosc` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def aroonosc(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `aroonosc` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def aroonosc(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算阿隆振荡器。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.AROONOSC(self.high, self.low, n)

        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def minus_dm(self, n: int, array: Literal[False] = False) -> float:
        """
        `minus_dm` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def minus_dm(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `minus_dm` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def minus_dm(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算负方向动量。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.MINUS_DM(self.high, self.low, n)

        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def plus_dm(self, n: int, array: Literal[False] = False) -> float:
        """
        `plus_dm` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def plus_dm(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `plus_dm` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def plus_dm(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算正方向动量。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.PLUS_DM(self.high, self.low, n)

        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def mfi(self, n: int, array: Literal[False] = False) -> float:
        """
        `mfi` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def mfi(self, n: int, array: Literal[True]) -> np.ndarray:
        """
        `mfi` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def mfi(self, n: int, array: bool = False) -> float | np.ndarray:
        """
        计算资金流量指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.MFI(self.high, self.low, self.close, self.volume, n)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def ad(self, array: Literal[False] = False) -> float:
        """
        `ad` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def ad(self, array: Literal[True]) -> np.ndarray:
        """
        `ad` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def ad(self, array: bool = False) -> float | np.ndarray:
        """
        计算累积/派发线。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.AD(self.high, self.low, self.close, self.volume)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def adosc(self, fast_period: int, slow_period: int, array: Literal[False] = False) -> float:
        """
        `adosc` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def adosc(self, fast_period: int, slow_period: int, array: Literal[True]) -> np.ndarray:
        """
        `adosc` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def adosc(
        self,
        fast_period: int,
        slow_period: int,
        array: bool = False
    ) -> float | np.ndarray:
        """
        计算累积/派发振荡器。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.ADOSC(self.high, self.low, self.close, self.volume, fast_period, slow_period)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def bop(self, array: Literal[False] = False) -> float:
        """
        `bop` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def bop(self, array: Literal[True]) -> np.ndarray:
        """
        `bop` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def bop(self, array: bool = False) -> float | np.ndarray:
        """
        计算买卖均衡指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.BOP(self.open, self.high, self.low, self.close)

        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value

    @overload
    def stoch(self, fastk_period: int, slowk_period: int, slowk_matype: int, slowd_period: int, slowd_matype: int, array: Literal[False] = False) -> tuple[float, float]:
        """
        `stoch` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def stoch(self, fastk_period: int, slowk_period: int, slowk_matype: int, slowd_period: int, slowd_matype: int, array: Literal[True]) -> tuple[np.ndarray, np.ndarray]:
        """
        `stoch` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def stoch(
        self,
        fastk_period: int,
        slowk_period: int,
        slowk_matype: int,
        slowd_period: int,
        slowd_matype: int,
        array: bool = False
    ) -> tuple[float, float] | tuple[np.ndarray, np.ndarray]:
        """
        计算随机指标双线值。
        
        `array=True` 返回两条线的完整序列；否则返回最新值。
        """
        k, d = talib.STOCH(
            self.high,
            self.low,
            self.close,
            fastk_period,
            slowk_period,
            slowk_matype,    # type: ignore
            slowd_period,
            slowd_matype     # type: ignore
        )
        if array:
            return k, d
        return k[-1], d[-1]

    @overload
    def sar(self, acceleration: float, maximum: float, array: Literal[False] = False) -> float:
        """
        `sar` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    @overload
    def sar(self, acceleration: float, maximum: float, array: Literal[True]) -> np.ndarray:
        """
        `sar` 的类型重载声明。
        
        用于约束 `array=True/False` 时的返回类型，不包含运行逻辑。
        """
        ...
    def sar(self, acceleration: float, maximum: float, array: bool = False) -> float | np.ndarray:
        """
        计算抛物转向指标。
        
        `array=True` 返回完整指标序列；`array=False` 返回最新一个值。
        """
        result_array: np.ndarray = talib.SAR(self.high, self.low, acceleration, maximum)
        if array:
            return result_array

        result_value: float = result_array[-1]
        return result_value


def virtual(func: Callable) -> Callable:
    """
    mark a function as "virtual", which means that this function can be override.
    any base class should use this or @abstractmethod to decorate all functions
    that can be (re)implemented by subclasses.
    """
    return func
