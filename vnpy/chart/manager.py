from datetime import datetime
from _collections_abc import dict_keys

from vnpy.trader.object import BarData

from .base import to_int


class BarManager:
    """
    `BarManager` 是图表数据管理器，维护 K 线序列及索引检索能力。
    
    职责：
    1. 保存并更新图表使用的 `BarData` 序列。
    2. 提供按索引或时间快速访问 K 线数据。
    3. 为光标、绘图项和坐标轴提供统一数据源。
    
    协作：
    1. 被 `ChartWidget`、`ChartCursor`、`ChartItem` 共享使用。
    2. 与行情更新流程协作进行增量刷新。
    """

    def __init__(self) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self._bars: dict[datetime, BarData] = {}
        self._datetime_index_map: dict[datetime, int] = {}
        self._index_datetime_map: dict[int, datetime] = {}

        self._price_ranges: dict[tuple[int, int], tuple[float, float]] = {}
        self._volume_ranges: dict[tuple[int, int], tuple[float, float]] = {}

    def update_history(self, history: list[BarData]) -> None:
        """
        更新 `history` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `history` (`list[BarData]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        # Put all new bars into dict
        for bar in history:
            self._bars[bar.datetime] = bar

        # Sort bars dict according to bar.datetime
        self._bars = dict(sorted(self._bars.items(), key=lambda tp: tp[0]))

        # Update map relationiship
        ix_list: range = range(len(self._bars))
        dt_list: dict_keys = self._bars.keys()

        self._datetime_index_map = dict(zip(dt_list, ix_list, strict=False))
        self._index_datetime_map = dict(zip(ix_list, dt_list, strict=False))

        # Clear data range cache
        self._clear_cache()

    def update_bar(self, bar: BarData) -> None:
        """
        更新 `bar` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `bar` (`BarData`)：K 线数据对象。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        dt: datetime = bar.datetime

        if dt not in self._datetime_index_map:
            ix: int = len(self._bars)
            self._datetime_index_map[dt] = ix
            self._index_datetime_map[ix] = dt

        self._bars[dt] = bar

        self._clear_cache()

    def get_count(self) -> int:
        """
        获取 `count` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `int`：返回该方法计算或查询得到的结果。
        """
        return len(self._bars)

    def get_index(self, dt: datetime) -> int | None:
        """
        获取 `index` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `dt` (`datetime`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `int | None`：返回该方法计算或查询得到的结果。
        """
        return self._datetime_index_map.get(dt, None)

    def get_datetime(self, ix: float) -> datetime | None:
        """
        获取 `datetime` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `ix` (`float`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `datetime | None`：返回该方法计算或查询得到的结果。
        """
        ix = to_int(ix)
        return self._index_datetime_map.get(ix, None)

    def get_bar(self, ix: float) -> BarData | None:
        """
        获取 `bar` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `ix` (`float`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `BarData | None`：返回该方法计算或查询得到的结果。
        """
        ix = to_int(ix)
        dt: datetime | None = self._index_datetime_map.get(ix, None)
        if not dt:
            return None

        return self._bars[dt]

    def get_all_bars(self) -> list[BarData]:
        """
        批量获取 `bars` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[BarData]`：返回按约定组织的数据列表。
        """
        return list(self._bars.values())

    def get_price_range(self, min_ix: float | None = None, max_ix: float | None = None) -> tuple[float, float]:
        """
        获取 `price_range` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `min_ix` (`float | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        2. `max_ix` (`float | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `tuple[float, float]`：返回多个值组成的结果元组。
        """
        if not self._bars:
            return 0, 1

        if min_ix is None or max_ix is None:
            min_ix = 0
            max_ix = len(self._bars) - 1
        else:
            min_ix = to_int(min_ix)
            max_ix = to_int(max_ix)
            max_ix = min(max_ix, self.get_count())

        buf: tuple[float, float] | None = self._price_ranges.get((min_ix, max_ix), None)
        if buf:
            return buf

        bar_list: list[BarData] = list(self._bars.values())[min_ix:max_ix + 1]
        first_bar: BarData = bar_list[0]
        max_price: float = first_bar.high_price
        min_price: float = first_bar.low_price

        for bar in bar_list[1:]:
            max_price = max(max_price, bar.high_price)
            min_price = min(min_price, bar.low_price)

        self._price_ranges[(min_ix, max_ix)] = (min_price, max_price)
        return min_price, max_price

    def get_volume_range(self, min_ix: float | None = None, max_ix: float | None = None) -> tuple[float, float]:
        """
        获取 `volume_range` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `min_ix` (`float | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        2. `max_ix` (`float | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `tuple[float, float]`：返回多个值组成的结果元组。
        """
        if not self._bars:
            return 0, 1

        if min_ix is None or max_ix is None:
            min_ix = 0
            max_ix = len(self._bars) - 1
        else:
            min_ix = to_int(min_ix)
            max_ix = to_int(max_ix)
            max_ix = min(max_ix, self.get_count())

        buf: tuple[float, float] | None = self._volume_ranges.get((min_ix, max_ix), None)
        if buf:
            return buf

        bar_list: list[BarData] = list(self._bars.values())[min_ix:max_ix + 1]

        first_bar: BarData = bar_list[0]
        max_volume = first_bar.volume
        min_volume = 0

        for bar in bar_list[1:]:
            max_volume = max(max_volume, bar.volume)

        self._volume_ranges[(min_ix, max_ix)] = (min_volume, max_volume)
        return min_volume, max_volume

    def _clear_cache(self) -> None:
        """
        执行 `_clear_cache` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self._price_ranges.clear()
        self._volume_ranges.clear()

    def clear_all(self) -> None:
        """
        执行 `clear_all` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self._bars.clear()
        self._datetime_index_map.clear()
        self._index_datetime_map.clear()

        self._clear_cache()
