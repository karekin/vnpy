from datetime import datetime
from typing import Any

import pyqtgraph as pg      # type: ignore

from .manager import BarManager
from .base import AXIS_WIDTH, NORMAL_FONT, QtGui


class DatetimeAxis(pg.AxisItem):
    """
    `DatetimeAxis` 是图表时间轴组件，把内部时间索引转换为可读日期时间标签。
    
    职责：
    1. 根据 K 线索引动态格式化横轴文本。
    2. 配合缩放与拖拽保持时间刻度可读。
    3. 统一图表模块时间显示风格。
    
    协作：
    1. 挂载于 `ChartWidget`。
    2. 从 `BarManager` 读取索引到时间的映射关系。
    """

    def __init__(self, manager: BarManager, *args: Any, **kwargs: Any) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `manager` (`BarManager`)：输入参数，用于控制该方法的处理行为。
        2. `*args` (`Any`)：输入参数，用于控制该方法的处理行为。
        3. `**kwargs` (`Any`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(*args, **kwargs)

        self._manager: BarManager = manager

        self.setPen(width=AXIS_WIDTH)
        self.tickFont: QtGui.QFont = NORMAL_FONT

    def tickStrings(self, values: list[int], scale: float, spacing: int) -> list:
        """
        执行 `tickStrings` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `values` (`list[int]`)：输入参数，用于控制该方法的处理行为。
        2. `scale` (`float`)：输入参数，用于控制该方法的处理行为。
        3. `spacing` (`int`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `list`：返回按约定组织的数据列表。
        """
        # Show no axis string if spacing smaller than 1
        if spacing < 1:
            return ["" for i in values]

        strings: list = []

        for ix in values:
            dt: datetime | None = self._manager.get_datetime(ix)

            if not dt:
                s: str = ""
            elif dt.hour:
                s = dt.strftime("%Y-%m-%d\n%H:%M:%S")
            else:
                s = dt.strftime("%Y-%m-%d")

            strings.append(s)

        return strings
