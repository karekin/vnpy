from abc import ABC, abstractmethod
from datetime import datetime
from types import ModuleType
from dataclasses import dataclass
from importlib import import_module

from .constant import Interval, Exchange
from .object import BarData, TickData
from .setting import SETTINGS
from .utility import ZoneInfo
from .locale import _


DB_TZ = ZoneInfo(SETTINGS["database.timezone"])


def convert_tz(dt: datetime) -> datetime:
    """
    Convert timezone of datetime object to DB_TZ.
    """
    dt = dt.astimezone(DB_TZ)
    return dt.replace(tzinfo=None)


@dataclass
class BarOverview:
    """
    `BarOverview` 是 K 线数据概览对象，用于记录某合约某周期的历史数据范围和数量。
    
    职责：
    1. 汇总某合约 K 线的起止时间和总条数。
    2. 支持数据管理页面快速展示“是否有数据、覆盖到何时”。
    3. 降低每次全表扫描的开销。
    
    协作：
    1. 被 `database.py` 的具体实现类继承。
    2. 与 `HistoryRequest/BarData/TickData` 等对象协同工作。
    """

    symbol: str = ""
    exchange: Exchange | None = None
    interval: Interval | None = None
    count: int = 0
    start: datetime | None = None
    end: datetime | None = None


@dataclass
class TickOverview:
    """
    `TickOverview` 是 Tick 数据概览对象，用于快速判断本地 Tick 数据可用区间。
    
    职责：
    1. 汇总某合约 Tick 数据范围和条数。
    2. 为数据补齐、清理和校验提供依据。
    3. 辅助回测和研究模块判断数据完整性。
    
    协作：
    1. 被 `database.py` 的具体实现类继承。
    2. 与 `HistoryRequest/BarData/TickData` 等对象协同工作。
    """

    symbol: str = ""
    exchange: Exchange | None = None
    count: int = 0
    start: datetime | None = None
    end: datetime | None = None


class BaseDatabase(ABC):
    """
    `BaseDatabase` 是数据库后端抽象接口，定义行情与成交相关数据的统一存取契约。
    
    职责：
    1. 抽象保存/读取/删除历史行情数据的基础能力。
    2. 屏蔽不同数据库实现细节（SQLite/MySQL/PostgreSQL 等）。
    3. 为回测、图表、数据下载模块提供统一访问入口。
    
    协作：
    1. 被 `database.py` 的具体实现类继承。
    2. 与 `HistoryRequest/BarData/TickData` 等对象协同工作。
    """

    @abstractmethod
    def save_bar_data(self, bars: list[BarData], stream: bool = False) -> bool:
        """
        保存 `bar_data` 相关内容。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `bars` (`list[BarData]`)：输入参数，用于控制该方法的处理行为。
        2. `stream` (`bool`)，默认值 `False`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `bool`：表示操作是否成功或条件是否成立。
        """
        pass

    @abstractmethod
    def save_tick_data(self, ticks: list[TickData], stream: bool = False) -> bool:
        """
        保存 `tick_data` 相关内容。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `ticks` (`list[TickData]`)：输入参数，用于控制该方法的处理行为。
        2. `stream` (`bool`)，默认值 `False`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `bool`：表示操作是否成功或条件是否成立。
        """
        pass

    @abstractmethod
    def load_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime
    ) -> list[BarData]:
        """
        加载 `bar_data` 相关资源。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `symbol` (`str`)：本地或交易所合约代码。
        2. `exchange` (`Exchange`)：交易所标识。
        3. `interval` (`Interval`)：周期参数（如 K 线周期或采样间隔）。
        4. `start` (`datetime`)：起始时间或起始索引。
        5. `end` (`datetime`)：结束时间或结束索引。
        
        返回：
        1. `list[BarData]`：返回按约定组织的数据列表。
        """
        pass

    @abstractmethod
    def load_tick_data(
        self,
        symbol: str,
        exchange: Exchange,
        start: datetime,
        end: datetime
    ) -> list[TickData]:
        """
        加载 `tick_data` 相关资源。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `symbol` (`str`)：本地或交易所合约代码。
        2. `exchange` (`Exchange`)：交易所标识。
        3. `start` (`datetime`)：起始时间或起始索引。
        4. `end` (`datetime`)：结束时间或结束索引。
        
        返回：
        1. `list[TickData]`：返回按约定组织的数据列表。
        """
        pass

    @abstractmethod
    def delete_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval
    ) -> int:
        """
        执行 `delete_bar_data` 相关业务逻辑。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `symbol` (`str`)：本地或交易所合约代码。
        2. `exchange` (`Exchange`)：交易所标识。
        3. `interval` (`Interval`)：周期参数（如 K 线周期或采样间隔）。
        
        返回：
        1. `int`：返回该方法计算或查询得到的结果。
        """
        pass

    @abstractmethod
    def delete_tick_data(
        self,
        symbol: str,
        exchange: Exchange
    ) -> int:
        """
        执行 `delete_tick_data` 相关业务逻辑。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `symbol` (`str`)：本地或交易所合约代码。
        2. `exchange` (`Exchange`)：交易所标识。
        
        返回：
        1. `int`：返回该方法计算或查询得到的结果。
        """
        pass

    @abstractmethod
    def get_bar_overview(self) -> list[BarOverview]:
        """
        获取 `bar_overview` 相关对象或计算结果。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[BarOverview]`：返回按约定组织的数据列表。
        """
        pass

    @abstractmethod
    def get_tick_overview(self) -> list[TickOverview]:
        """
        获取 `tick_overview` 相关对象或计算结果。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[TickOverview]`：返回按约定组织的数据列表。
        """
        pass


database: BaseDatabase | None = None


def get_database() -> BaseDatabase:
    """"""
    # Return database object if already inited
    global database
    if database:
        return database

    # Read database related global setting
    database_name: str = SETTINGS["database.name"]
    module_name: str = f"vnpy_{database_name}"

    # Try to import database module
    try:
        module: ModuleType = import_module(module_name)
    except ModuleNotFoundError:
        print(_("找不到数据库驱动{}，使用默认的SQLite数据库").format(module_name))
        module = import_module("vnpy_sqlite")

    # Create database object from module
    database = module.Database()
    return database
