"""
Basic widgets for UI.
"""

import csv
import platform
from enum import Enum
from typing import cast, Any
from copy import copy
from tzlocal import get_localzone_name
from datetime import datetime
from importlib import metadata

from .qt import QtCore, QtGui, QtWidgets, Qt
from ..constant import Direction, Exchange, Offset, OrderType
from ..engine import MainEngine, Event, EventEngine
from ..event import (
    EVENT_QUOTE,
    EVENT_TICK,
    EVENT_TRADE,
    EVENT_ORDER,
    EVENT_POSITION,
    EVENT_ACCOUNT,
    EVENT_LOG
)
from ..object import (
    OrderRequest,
    SubscribeRequest,
    CancelRequest,
    ContractData,
    PositionData,
    OrderData,
    QuoteData,
    TickData
)
from ..utility import load_json, save_json, get_digits, ZoneInfo
from ..setting import SETTING_FILENAME, SETTINGS
from ..locale import _


COLOR_LONG = QtGui.QColor("red")
COLOR_SHORT = QtGui.QColor("green")
COLOR_BID = QtGui.QColor(255, 174, 201)
COLOR_ASK = QtGui.QColor(160, 255, 160)
COLOR_BLACK = QtGui.QColor("black")


class BaseCell(QtWidgets.QTableWidgetItem):
    """
    表格基础单元格，封装字段取值、排序值和基础展示逻辑。
    
    职责：
    1. 将原始字段值转换为适合交易界面的展示格式。
    2. 根据业务语义设置颜色、对齐和排序行为。
    3. 提升高频刷新场景下的信息可读性。
    
    协作：
    1. 由各类 `Monitor` 在填充表格行时创建与更新。
    2. 和事件驱动更新机制配合进行增量刷新。
    """

    def __init__(self, content: Any, data: Any) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `content` (`Any`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__()

        self._text: str = ""
        self._data: Any = None

        self.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.set_content(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """
        设置 `content` 相关配置或运行参数。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `content` (`Any`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self._text = str(content)
        self._data = data

        self.setText(self._text)

    def get_data(self) -> Any:
        """
        获取 `data` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `Any`：返回该方法计算或查询得到的结果。
        """
        return self._data

    def __lt__(self, other: "BaseCell") -> bool:        # type: ignore
        """
        执行 `__lt__` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `other` (`'BaseCell'`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `bool`：表示操作是否成功或条件是否成立。
        """
        result: bool = self._text < other._text
        return result


class EnumCell(BaseCell):
    """
    枚举值单元格，把枚举对象显示为可读文本。
    
    职责：
    1. 将原始字段值转换为适合交易界面的展示格式。
    2. 根据业务语义设置颜色、对齐和排序行为。
    3. 提升高频刷新场景下的信息可读性。
    
    协作：
    1. 由各类 `Monitor` 在填充表格行时创建与更新。
    2. 和事件驱动更新机制配合进行增量刷新。
    """

    def __init__(self, content: Enum, data: Any) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `content` (`Enum`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """
        设置 `content` 相关配置或运行参数。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `content` (`Any`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if content:
            super().set_content(content.value, data)


class DirectionCell(EnumCell):
    """
    方向单元格，按多空方向设置文本颜色与显示样式。
    
    职责：
    1. 将原始字段值转换为适合交易界面的展示格式。
    2. 根据业务语义设置颜色、对齐和排序行为。
    3. 提升高频刷新场景下的信息可读性。
    
    协作：
    1. 由各类 `Monitor` 在填充表格行时创建与更新。
    2. 和事件驱动更新机制配合进行增量刷新。
    """

    def __init__(self, content: Enum, data: Any) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `content` (`Enum`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """
        设置 `content` 相关配置或运行参数。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `content` (`Any`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().set_content(content, data)

        if content is Direction.SHORT:
            self.setForeground(COLOR_SHORT)
        else:
            self.setForeground(COLOR_LONG)


class BidCell(BaseCell):
    """
    买价单元格，突出买盘报价信息。
    
    职责：
    1. 将原始字段值转换为适合交易界面的展示格式。
    2. 根据业务语义设置颜色、对齐和排序行为。
    3. 提升高频刷新场景下的信息可读性。
    
    协作：
    1. 由各类 `Monitor` 在填充表格行时创建与更新。
    2. 和事件驱动更新机制配合进行增量刷新。
    """

    def __init__(self, content: Any, data: Any) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `content` (`Any`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(content, data)

        self.setForeground(COLOR_BID)


class AskCell(BaseCell):
    """
    卖价单元格，突出卖盘报价信息。
    
    职责：
    1. 将原始字段值转换为适合交易界面的展示格式。
    2. 根据业务语义设置颜色、对齐和排序行为。
    3. 提升高频刷新场景下的信息可读性。
    
    协作：
    1. 由各类 `Monitor` 在填充表格行时创建与更新。
    2. 和事件驱动更新机制配合进行增量刷新。
    """

    def __init__(self, content: Any, data: Any) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `content` (`Any`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(content, data)

        self.setForeground(COLOR_ASK)


class PnlCell(BaseCell):
    """
    盈亏单元格，按正负收益着色显示。
    
    职责：
    1. 将原始字段值转换为适合交易界面的展示格式。
    2. 根据业务语义设置颜色、对齐和排序行为。
    3. 提升高频刷新场景下的信息可读性。
    
    协作：
    1. 由各类 `Monitor` 在填充表格行时创建与更新。
    2. 和事件驱动更新机制配合进行增量刷新。
    """

    def __init__(self, content: Any, data: Any) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `content` (`Any`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """
        设置 `content` 相关配置或运行参数。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `content` (`Any`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().set_content(content, data)

        if str(content).startswith("-"):
            self.setForeground(COLOR_SHORT)
        else:
            self.setForeground(COLOR_LONG)


class TimeCell(BaseCell):
    """
    时间单元格，格式化时分秒显示。
    
    职责：
    1. 将原始字段值转换为适合交易界面的展示格式。
    2. 根据业务语义设置颜色、对齐和排序行为。
    3. 提升高频刷新场景下的信息可读性。
    
    协作：
    1. 由各类 `Monitor` 在填充表格行时创建与更新。
    2. 和事件驱动更新机制配合进行增量刷新。
    """

    local_tz = ZoneInfo(get_localzone_name())

    def __init__(self, content: Any, data: Any) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `content` (`Any`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(content, data)

    def set_content(self, content: datetime | None, data: Any) -> None:
        """
        设置 `content` 相关配置或运行参数。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `content` (`datetime | None`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if content is None:
            return

        content = content.astimezone(self.local_tz)
        timestamp: str = content.strftime("%H:%M:%S")

        millisecond: int = int(content.microsecond / 1000)
        if millisecond:
            timestamp = f"{timestamp}.{millisecond}"
        else:
            timestamp = f"{timestamp}.000"

        self.setText(timestamp)
        self._data = data


class DateCell(BaseCell):
    """
    日期单元格，格式化日期显示。
    
    职责：
    1. 将原始字段值转换为适合交易界面的展示格式。
    2. 根据业务语义设置颜色、对齐和排序行为。
    3. 提升高频刷新场景下的信息可读性。
    
    协作：
    1. 由各类 `Monitor` 在填充表格行时创建与更新。
    2. 和事件驱动更新机制配合进行增量刷新。
    """

    def __init__(self, content: Any, data: Any) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `content` (`Any`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(content, data)

    def set_content(self, content: Any, data: Any) -> None:
        """
        设置 `content` 相关配置或运行参数。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `content` (`Any`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if content is None:
            return

        self.setText(content.strftime("%Y-%m-%d"))
        self._data = data


class MsgCell(BaseCell):
    """
    消息单元格，用于日志或提示文本展示。
    
    职责：
    1. 将原始字段值转换为适合交易界面的展示格式。
    2. 根据业务语义设置颜色、对齐和排序行为。
    3. 提升高频刷新场景下的信息可读性。
    
    协作：
    1. 由各类 `Monitor` 在填充表格行时创建与更新。
    2. 和事件驱动更新机制配合进行增量刷新。
    """

    def __init__(self, content: str, data: Any) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `content` (`str`)：正文内容。
        2. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(content, data)
        self.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)


class BaseMonitor(QtWidgets.QTableWidget):
    """
    监控表格基类，封装事件订阅、表格列定义和行更新机制。
    
    职责：
    1. 订阅对应事件并把数据对象映射为表格行。
    2. 在高频更新场景下执行增量刷新，避免全表重绘。
    3. 为人工交易提供实时可视化状态视图。
    
    协作：
    1. 与 `EventEngine` 事件流直接连接。
    2. 与 `MainEngine/OmsEngine` 提供的数据对象协同。
    """

    event_type: str = ""
    data_key: str = ""
    sorting: bool = False
    headers: dict = {}

    signal: QtCore.Signal = QtCore.Signal(Event)

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `main_engine` (`MainEngine`)：输入参数，用于控制该方法的处理行为。
        2. `event_engine` (`EventEngine`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__()

        self.main_engine: MainEngine = main_engine
        self.event_engine: EventEngine = event_engine
        self.cells: dict[str, dict] = {}

        self.init_ui()
        self.load_setting()
        self.register_event()

    def init_ui(self) -> None:
        """
        执行 `init_ui` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.init_table()
        self.init_menu()

    def init_table(self) -> None:
        """
        执行 `init_table` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.setColumnCount(len(self.headers))

        labels: list = [d["display"] for d in self.headers.values()]
        self.setHorizontalHeaderLabels(labels)

        self.verticalHeader().setVisible(False)
        self.setEditTriggers(self.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(self.sorting)

    def init_menu(self) -> None:
        """
        执行 `init_menu` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.menu: QtWidgets.QMenu = QtWidgets.QMenu(self)

        resize_action: QtGui.QAction = QtGui.QAction(_("调整列宽"), self)
        resize_action.triggered.connect(self.resize_columns)
        self.menu.addAction(resize_action)

        save_action: QtGui.QAction = QtGui.QAction(_("保存数据"), self)
        save_action.triggered.connect(self.save_csv)
        self.menu.addAction(save_action)

    def register_event(self) -> None:
        """
        执行 `register_event` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if self.event_type:
            self.signal.connect(self.process_event)
            self.event_engine.register(self.event_type, self.signal.emit)

    def process_event(self, event: Event) -> None:
        """
        处理 `event` 相关业务逻辑。
        
        用途说明：
        1. 作为事件驱动入口，消费输入并执行核心处理。
        2. 按需更新缓存、发布事件或触发后续流程。
        
        参数：
        1. `event` (`Event`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        # Disable sorting to prevent unwanted error.
        if self.sorting:
            self.setSortingEnabled(False)

        # Update data into table.
        data = event.data

        if not self.data_key:
            self.insert_new_row(data)
        else:
            key: str = data.__getattribute__(self.data_key)

            if key in self.cells:
                self.update_old_row(data)
            else:
                self.insert_new_row(data)

        # Enable sorting
        if self.sorting:
            self.setSortingEnabled(True)

    def insert_new_row(self, data: Any) -> None:
        """
        执行 `insert_new_row` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.insertRow(0)

        row_cells: dict = {}
        for column, header in enumerate(self.headers.keys()):
            setting: dict = self.headers[header]

            content = data.__getattribute__(header)
            cell: QtWidgets.QTableWidgetItem = setting["cell"](content, data)
            self.setItem(0, column, cell)

            if setting["update"]:
                row_cells[header] = cell

        if self.data_key:
            key: str = data.__getattribute__(self.data_key)
            self.cells[key] = row_cells

    def update_old_row(self, data: Any) -> None:
        """
        更新 `old_row` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `data` (`Any`)：待处理的原始或结构化数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        key: str = data.__getattribute__(self.data_key)
        row_cells = self.cells[key]

        for header, cell in row_cells.items():
            content = data.__getattribute__(header)
            cell.set_content(content, data)

    def resize_columns(self) -> None:
        """
        执行 `resize_columns` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.horizontalHeader().resizeSections(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

    def save_csv(self) -> None:
        """
        保存 `csv` 相关内容。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        path, __ = QtWidgets.QFileDialog.getSaveFileName(
            self, _("保存数据"), "", "CSV(*.csv)")

        if not path:
            return

        with open(path, "w") as f:
            writer = csv.writer(f, lineterminator="\n")

            headers: list = [d["display"] for d in self.headers.values()]
            writer.writerow(headers)

            for row in range(self.rowCount()):
                if self.isRowHidden(row):
                    continue

                row_data: list = []
                for column in range(self.columnCount()):
                    item: QtWidgets.QTableWidgetItem | None = self.item(row, column)
                    if item:
                        row_data.append(str(item.text()))
                    else:
                        row_data.append("")
                writer.writerow(row_data)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        """
        执行 `contextMenuEvent` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `event` (`QtGui.QContextMenuEvent`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.menu.popup(QtGui.QCursor.pos())

    def save_setting(self) -> None:
        """
        保存 `setting` 相关内容。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        settings: QtCore.QSettings = QtCore.QSettings(self.__class__.__name__, "custom")
        settings.setValue("column_state", self.horizontalHeader().saveState())

    def load_setting(self) -> None:
        """
        加载 `setting` 相关资源。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        settings: QtCore.QSettings = QtCore.QSettings(self.__class__.__name__, "custom")
        column_state = settings.value("column_state")

        if isinstance(column_state, QtCore.QByteArray):
            self.horizontalHeader().restoreState(column_state)
            self.horizontalHeader().setSortIndicator(-1, QtCore.Qt.SortOrder.AscendingOrder)


class TickMonitor(BaseMonitor):
    """
    行情监控面板，实时展示最新 Tick 数据。
    
    职责：
    1. 订阅对应事件并把数据对象映射为表格行。
    2. 在高频更新场景下执行增量刷新，避免全表重绘。
    3. 为人工交易提供实时可视化状态视图。
    
    协作：
    1. 与 `EventEngine` 事件流直接连接。
    2. 与 `MainEngine/OmsEngine` 提供的数据对象协同。
    """

    event_type: str = EVENT_TICK
    data_key: str = "vt_symbol"
    sorting: bool = True

    headers: dict = {
        "symbol": {"display": _("代码"), "cell": BaseCell, "update": False},
        "exchange": {"display": _("交易所"), "cell": EnumCell, "update": False},
        "name": {"display": _("名称"), "cell": BaseCell, "update": True},
        "last_price": {"display": _("最新价"), "cell": BaseCell, "update": True},
        "volume": {"display": _("成交量"), "cell": BaseCell, "update": True},
        "open_price": {"display": _("开盘价"), "cell": BaseCell, "update": True},
        "high_price": {"display": _("最高价"), "cell": BaseCell, "update": True},
        "low_price": {"display": _("最低价"), "cell": BaseCell, "update": True},
        "bid_price_1": {"display": _("买1价"), "cell": BidCell, "update": True},
        "bid_volume_1": {"display": _("买1量"), "cell": BidCell, "update": True},
        "ask_price_1": {"display": _("卖1价"), "cell": AskCell, "update": True},
        "ask_volume_1": {"display": _("卖1量"), "cell": AskCell, "update": True},
        "datetime": {"display": _("时间"), "cell": TimeCell, "update": True},
        "gateway_name": {"display": _("接口"), "cell": BaseCell, "update": False},
    }


class LogMonitor(BaseMonitor):
    """
    日志监控面板，展示系统与网关日志流。
    
    职责：
    1. 订阅对应事件并把数据对象映射为表格行。
    2. 在高频更新场景下执行增量刷新，避免全表重绘。
    3. 为人工交易提供实时可视化状态视图。
    
    协作：
    1. 与 `EventEngine` 事件流直接连接。
    2. 与 `MainEngine/OmsEngine` 提供的数据对象协同。
    """

    event_type: str = EVENT_LOG
    data_key: str = ""
    sorting: bool = False

    headers: dict = {
        "time": {"display": _("时间"), "cell": TimeCell, "update": False},
        "msg": {"display": _("信息"), "cell": MsgCell, "update": False},
        "gateway_name": {"display": _("接口"), "cell": BaseCell, "update": False},
    }


class TradeMonitor(BaseMonitor):
    """
    成交监控面板，展示每笔成交回报。
    
    职责：
    1. 订阅对应事件并把数据对象映射为表格行。
    2. 在高频更新场景下执行增量刷新，避免全表重绘。
    3. 为人工交易提供实时可视化状态视图。
    
    协作：
    1. 与 `EventEngine` 事件流直接连接。
    2. 与 `MainEngine/OmsEngine` 提供的数据对象协同。
    """

    event_type: str = EVENT_TRADE
    data_key: str = ""
    sorting: bool = True

    headers: dict = {
        "tradeid": {"display": _("成交号"), "cell": BaseCell, "update": False},
        "orderid": {"display": _("委托号"), "cell": BaseCell, "update": False},
        "symbol": {"display": _("代码"), "cell": BaseCell, "update": False},
        "exchange": {"display": _("交易所"), "cell": EnumCell, "update": False},
        "direction": {"display": _("方向"), "cell": DirectionCell, "update": False},
        "offset": {"display": _("开平"), "cell": EnumCell, "update": False},
        "price": {"display": _("价格"), "cell": BaseCell, "update": False},
        "volume": {"display": _("数量"), "cell": BaseCell, "update": False},
        "datetime": {"display": _("时间"), "cell": TimeCell, "update": False},
        "gateway_name": {"display": _("接口"), "cell": BaseCell, "update": False},
    }


class OrderMonitor(BaseMonitor):
    """
    委托监控面板，展示订单状态变化并支持操作。
    
    职责：
    1. 订阅对应事件并把数据对象映射为表格行。
    2. 在高频更新场景下执行增量刷新，避免全表重绘。
    3. 为人工交易提供实时可视化状态视图。
    
    协作：
    1. 与 `EventEngine` 事件流直接连接。
    2. 与 `MainEngine/OmsEngine` 提供的数据对象协同。
    """

    event_type: str = EVENT_ORDER
    data_key: str = "vt_orderid"
    sorting: bool = True

    headers: dict = {
        "orderid": {"display": _("委托号"), "cell": BaseCell, "update": False},
        "reference": {"display": _("来源"), "cell": BaseCell, "update": False},
        "symbol": {"display": _("代码"), "cell": BaseCell, "update": False},
        "exchange": {"display": _("交易所"), "cell": EnumCell, "update": False},
        "type": {"display": _("类型"), "cell": EnumCell, "update": False},
        "direction": {"display": _("方向"), "cell": DirectionCell, "update": False},
        "offset": {"display": _("开平"), "cell": EnumCell, "update": False},
        "price": {"display": _("价格"), "cell": BaseCell, "update": False},
        "volume": {"display": _("总数量"), "cell": BaseCell, "update": True},
        "traded": {"display": _("已成交"), "cell": BaseCell, "update": True},
        "status": {"display": _("状态"), "cell": EnumCell, "update": True},
        "datetime": {"display": _("时间"), "cell": TimeCell, "update": True},
        "gateway_name": {"display": _("接口"), "cell": BaseCell, "update": False},
    }

    def init_ui(self) -> None:
        """
        执行 `init_ui` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().init_ui()

        self.setToolTip(_("双击单元格撤单"))
        self.itemDoubleClicked.connect(self.cancel_order)

    def cancel_order(self, cell: BaseCell) -> None:
        """
        执行 `order` 撤销或取消操作。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. `cell` (`BaseCell`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        order: OrderData = cell.get_data()
        req: CancelRequest = order.create_cancel_request()
        self.main_engine.cancel_order(req, order.gateway_name)


class PositionMonitor(BaseMonitor):
    """
    持仓监控面板，展示账户持仓明细。
    
    职责：
    1. 订阅对应事件并把数据对象映射为表格行。
    2. 在高频更新场景下执行增量刷新，避免全表重绘。
    3. 为人工交易提供实时可视化状态视图。
    
    协作：
    1. 与 `EventEngine` 事件流直接连接。
    2. 与 `MainEngine/OmsEngine` 提供的数据对象协同。
    """

    event_type: str = EVENT_POSITION
    data_key: str = "vt_positionid"
    sorting: bool = True

    headers: dict = {
        "symbol": {"display": _("代码"), "cell": BaseCell, "update": False},
        "exchange": {"display": _("交易所"), "cell": EnumCell, "update": False},
        "direction": {"display": _("方向"), "cell": DirectionCell, "update": False},
        "volume": {"display": _("数量"), "cell": BaseCell, "update": True},
        "yd_volume": {"display": _("昨仓"), "cell": BaseCell, "update": True},
        "frozen": {"display": _("冻结"), "cell": BaseCell, "update": True},
        "price": {"display": _("均价"), "cell": BaseCell, "update": True},
        "pnl": {"display": _("盈亏"), "cell": PnlCell, "update": True},
        "gateway_name": {"display": _("接口"), "cell": BaseCell, "update": False},
    }


class AccountMonitor(BaseMonitor):
    """
    账户监控面板，展示资金权益和可用余额。
    
    职责：
    1. 订阅对应事件并把数据对象映射为表格行。
    2. 在高频更新场景下执行增量刷新，避免全表重绘。
    3. 为人工交易提供实时可视化状态视图。
    
    协作：
    1. 与 `EventEngine` 事件流直接连接。
    2. 与 `MainEngine/OmsEngine` 提供的数据对象协同。
    """

    event_type: str = EVENT_ACCOUNT
    data_key: str = "vt_accountid"
    sorting: bool = True

    headers: dict = {
        "accountid": {"display": _("账号"), "cell": BaseCell, "update": False},
        "balance": {"display": _("余额"), "cell": BaseCell, "update": True},
        "frozen": {"display": _("冻结"), "cell": BaseCell, "update": True},
        "available": {"display": _("可用"), "cell": BaseCell, "update": True},
        "gateway_name": {"display": _("接口"), "cell": BaseCell, "update": False},
    }


class QuoteMonitor(BaseMonitor):
    """
    报价监控面板，展示双边报价状态。
    
    职责：
    1. 订阅对应事件并把数据对象映射为表格行。
    2. 在高频更新场景下执行增量刷新，避免全表重绘。
    3. 为人工交易提供实时可视化状态视图。
    
    协作：
    1. 与 `EventEngine` 事件流直接连接。
    2. 与 `MainEngine/OmsEngine` 提供的数据对象协同。
    """

    event_type: str = EVENT_QUOTE
    data_key: str = "vt_quoteid"
    sorting: bool = True

    headers: dict = {
        "quoteid": {"display": _("报价号"), "cell": BaseCell, "update": False},
        "reference": {"display": _("来源"), "cell": BaseCell, "update": False},
        "symbol": {"display": _("代码"), "cell": BaseCell, "update": False},
        "exchange": {"display": _("交易所"), "cell": EnumCell, "update": False},
        "bid_offset": {"display": _("买开平"), "cell": EnumCell, "update": False},
        "bid_volume": {"display": _("买量"), "cell": BidCell, "update": False},
        "bid_price": {"display": _("买价"), "cell": BidCell, "update": False},
        "ask_price": {"display": _("卖价"), "cell": AskCell, "update": False},
        "ask_volume": {"display": _("卖量"), "cell": AskCell, "update": False},
        "ask_offset": {"display": _("卖开平"), "cell": EnumCell, "update": False},
        "status": {"display": _("状态"), "cell": EnumCell, "update": True},
        "datetime": {"display": _("时间"), "cell": TimeCell, "update": True},
        "gateway_name": {"display": _("接口"), "cell": BaseCell, "update": False},
    }

    def init_ui(self) -> None:
        """
        执行 `init_ui` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().init_ui()

        self.setToolTip(_("双击单元格撤销报价"))
        self.itemDoubleClicked.connect(self.cancel_quote)

    def cancel_quote(self, cell: BaseCell) -> None:
        """
        执行 `quote` 撤销或取消操作。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. `cell` (`BaseCell`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        quote: QuoteData = cell.get_data()
        req: CancelRequest = quote.create_cancel_request()
        self.main_engine.cancel_quote(req, quote.gateway_name)


class ConnectDialog(QtWidgets.QDialog):
    """
    `ConnectDialog` 是网关连接配置弹窗，用于输入并提交网关登录参数。
    
    职责：
    1. 动态生成配置表单并收集用户输入。
    2. 调用主引擎触发目标网关连接。
    3. 对连接参数进行基础校验和持久化。
    
    协作：
    1. 由 `MainWindow` 统一创建与管理。
    2. 与 `MainEngine` 交互执行真实业务动作。
    """

    def __init__(self, main_engine: MainEngine, gateway_name: str) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `main_engine` (`MainEngine`)：输入参数，用于控制该方法的处理行为。
        2. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__()

        self.main_engine: MainEngine = main_engine
        self.gateway_name: str = gateway_name
        self.filename: str = f"connect_{gateway_name.lower()}.json"

        self.widgets: dict[str, tuple[QtWidgets.QWidget, type]] = {}

        self.init_ui()

    def init_ui(self) -> None:
        """
        执行 `init_ui` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.setWindowTitle(_("连接{}").format(self.gateway_name))

        # Default setting provides field name, field data type and field default value.
        default_setting: dict | None = self.main_engine.get_default_setting(self.gateway_name)

        # Saved setting provides field data used last time.
        loaded_setting: dict = load_json(self.filename)

        # Initialize line edits and form layout based on setting.
        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()

        if default_setting:
            for field_name, field_value in default_setting.items():
                field_type: type = type(field_value)

                if field_type is list:
                    combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
                    combo.addItems(field_value)

                    if field_name in loaded_setting:
                        saved_value = loaded_setting[field_name]
                        ix: int = combo.findText(saved_value)
                        combo.setCurrentIndex(ix)

                    form.addRow(f"{field_name} <{field_type.__name__}>", combo)
                    self.widgets[field_name] = (combo, field_type)
                else:
                    line: QtWidgets.QLineEdit = QtWidgets.QLineEdit(str(field_value))

                    if field_name in loaded_setting:
                        saved_value = loaded_setting[field_name]
                        line.setText(str(saved_value))

                    if _("密码") in field_name:
                        line.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)

                    if field_type is int:
                        validator: QtGui.QIntValidator = QtGui.QIntValidator()
                        line.setValidator(validator)

                    form.addRow(f"{field_name} <{field_type.__name__}>", line)
                    self.widgets[field_name] = (line, field_type)

        button: QtWidgets.QPushButton = QtWidgets.QPushButton(_("连接"))
        button.clicked.connect(self.connect_gateway)
        form.addRow(button)

        self.setLayout(form)

    def connect_gateway(self) -> None:
        """
        执行 `connect_gateway` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        setting: dict = {}

        for field_name, tp in self.widgets.items():
            widget, field_type = tp
            if field_type is list:
                combo: QtWidgets.QComboBox = cast(QtWidgets.QComboBox, widget)
                field_value = str(combo.currentText())
            else:
                line: QtWidgets.QLineEdit = cast(QtWidgets.QLineEdit, widget)
                try:
                    field_value = field_type(line.text())
                except ValueError:
                    field_value = field_type()
            setting[field_name] = field_value

        save_json(self.filename, setting)

        self.main_engine.connect(setting, self.gateway_name)
        self.accept()


class TradingWidget(QtWidgets.QWidget):
    """
    `TradingWidget` 是手工交易面板，提供合约选择、下单、撤单与报价操作。
    
    职责：
    1. 提供统一的手工交易操作入口。
    2. 把用户输入转换为标准请求对象并调用主引擎。
    3. 联动行情和委托状态反馈交易结果。
    
    协作：
    1. 由 `MainWindow` 统一创建与管理。
    2. 与 `MainEngine` 交互执行真实业务动作。
    """

    signal_tick: QtCore.Signal = QtCore.Signal(Event)

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `main_engine` (`MainEngine`)：输入参数，用于控制该方法的处理行为。
        2. `event_engine` (`EventEngine`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__()

        self.main_engine: MainEngine = main_engine
        self.event_engine: EventEngine = event_engine

        self.vt_symbol: str = ""
        self.price_digits: int = 0

        self.init_ui()
        self.register_event()

    def init_ui(self) -> None:
        """
        执行 `init_ui` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.setFixedWidth(300)

        # Trading function area
        exchanges: list[Exchange] = self.main_engine.get_all_exchanges()
        self.exchange_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        self.exchange_combo.addItems([exchange.value for exchange in exchanges])

        self.symbol_line: QtWidgets.QLineEdit = QtWidgets.QLineEdit()
        self.symbol_line.returnPressed.connect(self.set_vt_symbol)

        self.name_line: QtWidgets.QLineEdit = QtWidgets.QLineEdit()
        self.name_line.setReadOnly(True)

        self.direction_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        self.direction_combo.addItems(
            [Direction.LONG.value, Direction.SHORT.value])

        self.offset_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        self.offset_combo.addItems([offset.value for offset in Offset])

        self.order_type_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        self.order_type_combo.addItems(
            [order_type.value for order_type in OrderType])

        double_validator: QtGui.QDoubleValidator = QtGui.QDoubleValidator()
        double_validator.setBottom(0)

        self.price_line: QtWidgets.QLineEdit = QtWidgets.QLineEdit()
        self.price_line.setValidator(double_validator)

        self.volume_line: QtWidgets.QLineEdit = QtWidgets.QLineEdit()
        self.volume_line.setValidator(double_validator)

        self.gateway_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        self.gateway_combo.addItems(self.main_engine.get_all_gateway_names())

        self.price_check: QtWidgets.QCheckBox = QtWidgets.QCheckBox()
        self.price_check.setToolTip(_("设置价格随行情更新"))

        send_button: QtWidgets.QPushButton = QtWidgets.QPushButton(_("委托"))
        send_button.clicked.connect(self.send_order)

        cancel_button: QtWidgets.QPushButton = QtWidgets.QPushButton(_("全撤"))
        cancel_button.clicked.connect(self.cancel_all)

        grid: QtWidgets.QGridLayout = QtWidgets.QGridLayout()
        grid.addWidget(QtWidgets.QLabel(_("交易所")), 0, 0)
        grid.addWidget(QtWidgets.QLabel(_("代码")), 1, 0)
        grid.addWidget(QtWidgets.QLabel(_("名称")), 2, 0)
        grid.addWidget(QtWidgets.QLabel(_("方向")), 3, 0)
        grid.addWidget(QtWidgets.QLabel(_("开平")), 4, 0)
        grid.addWidget(QtWidgets.QLabel(_("类型")), 5, 0)
        grid.addWidget(QtWidgets.QLabel(_("价格")), 6, 0)
        grid.addWidget(QtWidgets.QLabel(_("数量")), 7, 0)
        grid.addWidget(QtWidgets.QLabel(_("接口")), 8, 0)
        grid.addWidget(self.exchange_combo, 0, 1, 1, 2)
        grid.addWidget(self.symbol_line, 1, 1, 1, 2)
        grid.addWidget(self.name_line, 2, 1, 1, 2)
        grid.addWidget(self.direction_combo, 3, 1, 1, 2)
        grid.addWidget(self.offset_combo, 4, 1, 1, 2)
        grid.addWidget(self.order_type_combo, 5, 1, 1, 2)
        grid.addWidget(self.price_line, 6, 1, 1, 1)
        grid.addWidget(self.price_check, 6, 2, 1, 1)
        grid.addWidget(self.volume_line, 7, 1, 1, 2)
        grid.addWidget(self.gateway_combo, 8, 1, 1, 2)
        grid.addWidget(send_button, 9, 0, 1, 3)
        grid.addWidget(cancel_button, 10, 0, 1, 3)

        # Market depth display area
        bid_color: str = "rgb(255,174,201)"
        ask_color: str = "rgb(160,255,160)"

        self.bp1_label: QtWidgets.QLabel = self.create_label(bid_color)
        self.bp2_label: QtWidgets.QLabel = self.create_label(bid_color)
        self.bp3_label: QtWidgets.QLabel = self.create_label(bid_color)
        self.bp4_label: QtWidgets.QLabel = self.create_label(bid_color)
        self.bp5_label: QtWidgets.QLabel = self.create_label(bid_color)

        self.bv1_label: QtWidgets.QLabel = self.create_label(
            bid_color, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.bv2_label: QtWidgets.QLabel = self.create_label(
            bid_color, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.bv3_label: QtWidgets.QLabel = self.create_label(
            bid_color, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.bv4_label: QtWidgets.QLabel = self.create_label(
            bid_color, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.bv5_label: QtWidgets.QLabel = self.create_label(
            bid_color, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        self.ap1_label: QtWidgets.QLabel = self.create_label(ask_color)
        self.ap2_label: QtWidgets.QLabel = self.create_label(ask_color)
        self.ap3_label: QtWidgets.QLabel = self.create_label(ask_color)
        self.ap4_label: QtWidgets.QLabel = self.create_label(ask_color)
        self.ap5_label: QtWidgets.QLabel = self.create_label(ask_color)

        self.av1_label: QtWidgets.QLabel = self.create_label(
            ask_color, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.av2_label: QtWidgets.QLabel = self.create_label(
            ask_color, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.av3_label: QtWidgets.QLabel = self.create_label(
            ask_color, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.av4_label: QtWidgets.QLabel = self.create_label(
            ask_color, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.av5_label: QtWidgets.QLabel = self.create_label(
            ask_color, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        self.lp_label: QtWidgets.QLabel = self.create_label()
        self.return_label: QtWidgets.QLabel = self.create_label(alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()
        form.addRow(self.ap5_label, self.av5_label)
        form.addRow(self.ap4_label, self.av4_label)
        form.addRow(self.ap3_label, self.av3_label)
        form.addRow(self.ap2_label, self.av2_label)
        form.addRow(self.ap1_label, self.av1_label)
        form.addRow(self.lp_label, self.return_label)
        form.addRow(self.bp1_label, self.bv1_label)
        form.addRow(self.bp2_label, self.bv2_label)
        form.addRow(self.bp3_label, self.bv3_label)
        form.addRow(self.bp4_label, self.bv4_label)
        form.addRow(self.bp5_label, self.bv5_label)

        # Overall layout
        vbox: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout()
        vbox.addLayout(grid)
        vbox.addLayout(form)
        self.setLayout(vbox)

    def create_label(
        self,
        color: str = "",
        alignment: int = QtCore.Qt.AlignmentFlag.AlignLeft
    ) -> QtWidgets.QLabel:
        """
        执行 `create_label` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `color` (`str`)，默认值 `''`：输入参数，用于控制该方法的处理行为。
        2. `alignment` (`int`)，默认值 `QtCore.Qt.AlignmentFlag.AlignLeft`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `QtWidgets.QLabel`：返回该方法计算或查询得到的结果。
        """
        label: QtWidgets.QLabel = QtWidgets.QLabel()
        if color:
            label.setStyleSheet(f"color:{color}")
        label.setAlignment(Qt.AlignmentFlag(alignment))
        return label

    def register_event(self) -> None:
        """
        执行 `register_event` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.signal_tick.connect(self.process_tick_event)
        self.event_engine.register(EVENT_TICK, self.signal_tick.emit)

    def process_tick_event(self, event: Event) -> None:
        """
        处理 `tick_event` 相关业务逻辑。
        
        用途说明：
        1. 作为事件驱动入口，消费输入并执行核心处理。
        2. 按需更新缓存、发布事件或触发后续流程。
        
        参数：
        1. `event` (`Event`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        tick: TickData = event.data
        if tick.vt_symbol != self.vt_symbol:
            return

        price_digits: int = self.price_digits

        self.lp_label.setText(f"{tick.last_price:.{price_digits}f}")
        self.bp1_label.setText(f"{tick.bid_price_1:.{price_digits}f}")
        self.bv1_label.setText(str(tick.bid_volume_1))
        self.ap1_label.setText(f"{tick.ask_price_1:.{price_digits}f}")
        self.av1_label.setText(str(tick.ask_volume_1))

        if tick.pre_close:
            r: float = (tick.last_price / tick.pre_close - 1) * 100
            self.return_label.setText(f"{r:.2f}%")

        if tick.bid_price_2:
            self.bp2_label.setText(f"{tick.bid_price_2:.{price_digits}f}")
            self.bv2_label.setText(str(tick.bid_volume_2))
            self.ap2_label.setText(f"{tick.ask_price_2:.{price_digits}f}")
            self.av2_label.setText(str(tick.ask_volume_2))

            self.bp3_label.setText(f"{tick.bid_price_3:.{price_digits}f}")
            self.bv3_label.setText(str(tick.bid_volume_3))
            self.ap3_label.setText(f"{tick.ask_price_3:.{price_digits}f}")
            self.av3_label.setText(str(tick.ask_volume_3))

            self.bp4_label.setText(f"{tick.bid_price_4:.{price_digits}f}")
            self.bv4_label.setText(str(tick.bid_volume_4))
            self.ap4_label.setText(f"{tick.ask_price_4:.{price_digits}f}")
            self.av4_label.setText(str(tick.ask_volume_4))

            self.bp5_label.setText(f"{tick.bid_price_5:.{price_digits}f}")
            self.bv5_label.setText(str(tick.bid_volume_5))
            self.ap5_label.setText(f"{tick.ask_price_5:.{price_digits}f}")
            self.av5_label.setText(str(tick.ask_volume_5))

        if self.price_check.isChecked():
            self.price_line.setText(f"{tick.last_price:.{price_digits}f}")

    def set_vt_symbol(self) -> None:
        """
        设置 `vt_symbol` 相关配置或运行参数。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        symbol: str = str(self.symbol_line.text())
        if not symbol:
            return

        # Generate vt_symbol from symbol and exchange
        exchange_value: str = str(self.exchange_combo.currentText())
        vt_symbol: str = f"{symbol}.{exchange_value}"

        if vt_symbol == self.vt_symbol:
            return
        self.vt_symbol = vt_symbol

        # Update name line widget and clear all labels
        contract: ContractData | None = self.main_engine.get_contract(vt_symbol)
        if not contract:
            self.name_line.setText("")
            gateway_name: str = self.gateway_combo.currentText()
        else:
            self.name_line.setText(contract.name)
            gateway_name = contract.gateway_name

            # Update gateway combo box.
            ix: int = self.gateway_combo.findText(gateway_name)
            self.gateway_combo.setCurrentIndex(ix)

            # Update price digits
            self.price_digits = get_digits(contract.pricetick)

        self.clear_label_text()
        self.volume_line.setText("")
        self.price_line.setText("")

        # Subscribe tick data
        req: SubscribeRequest = SubscribeRequest(
            symbol=symbol, exchange=Exchange(exchange_value)
        )

        self.main_engine.subscribe(req, gateway_name)

    def clear_label_text(self) -> None:
        """
        执行 `clear_label_text` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.lp_label.setText("")
        self.return_label.setText("")

        self.bv1_label.setText("")
        self.bv2_label.setText("")
        self.bv3_label.setText("")
        self.bv4_label.setText("")
        self.bv5_label.setText("")

        self.av1_label.setText("")
        self.av2_label.setText("")
        self.av3_label.setText("")
        self.av4_label.setText("")
        self.av5_label.setText("")

        self.bp1_label.setText("")
        self.bp2_label.setText("")
        self.bp3_label.setText("")
        self.bp4_label.setText("")
        self.bp5_label.setText("")

        self.ap1_label.setText("")
        self.ap2_label.setText("")
        self.ap3_label.setText("")
        self.ap4_label.setText("")
        self.ap5_label.setText("")

    def send_order(self) -> None:
        """
        发送 `order` 请求并处理返回结果。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        symbol: str = str(self.symbol_line.text())
        if not symbol:
            QtWidgets.QMessageBox.critical(self, _("委托失败"), _("请输入合约代码"))
            return

        volume_text: str = str(self.volume_line.text())
        if not volume_text:
            QtWidgets.QMessageBox.critical(self, _("委托失败"), _("请输入委托数量"))
            return
        volume: float = float(volume_text)

        price_text: str = str(self.price_line.text())
        if not price_text:
            price: float = 0
        else:
            price = float(price_text)

        req: OrderRequest = OrderRequest(
            symbol=symbol,
            exchange=Exchange(str(self.exchange_combo.currentText())),
            direction=Direction(str(self.direction_combo.currentText())),
            type=OrderType(str(self.order_type_combo.currentText())),
            volume=volume,
            price=price,
            offset=Offset(str(self.offset_combo.currentText())),
            reference="ManualTrading"
        )

        gateway_name: str = str(self.gateway_combo.currentText())

        self.main_engine.send_order(req, gateway_name)

    def cancel_all(self) -> None:
        """
        执行 `all` 撤销或取消操作。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        order_list: list[OrderData] = self.main_engine.get_all_active_orders()
        for order in order_list:
            req: CancelRequest = order.create_cancel_request()
            self.main_engine.cancel_order(req, order.gateway_name)

    def update_with_cell(self, cell: BaseCell) -> None:
        """
        更新 `with_cell` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `cell` (`BaseCell`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        data = cell.get_data()

        self.symbol_line.setText(data.symbol)
        self.exchange_combo.setCurrentIndex(
            self.exchange_combo.findText(data.exchange.value)
        )

        self.set_vt_symbol()

        if isinstance(data, PositionData):
            if data.direction == Direction.SHORT:
                direction: Direction = Direction.LONG
            elif data.direction == Direction.LONG:
                direction = Direction.SHORT
            else:       # Net position mode
                if data.volume > 0:
                    direction = Direction.SHORT
                else:
                    direction = Direction.LONG

            self.direction_combo.setCurrentIndex(
                self.direction_combo.findText(direction.value)
            )
            self.offset_combo.setCurrentIndex(
                self.offset_combo.findText(Offset.CLOSE.value)
            )
            self.volume_line.setText(str(abs(data.volume)))


class ActiveOrderMonitor(OrderMonitor):
    """
    活动委托监控面板，仅展示仍可撤销/可成交的委托。
    
    职责：
    1. 订阅对应事件并把数据对象映射为表格行。
    2. 在高频更新场景下执行增量刷新，避免全表重绘。
    3. 为人工交易提供实时可视化状态视图。
    
    协作：
    1. 与 `EventEngine` 事件流直接连接。
    2. 与 `MainEngine/OmsEngine` 提供的数据对象协同。
    """

    def process_event(self, event: Event) -> None:
        """
        处理 `event` 相关业务逻辑。
        
        用途说明：
        1. 作为事件驱动入口，消费输入并执行核心处理。
        2. 按需更新缓存、发布事件或触发后续流程。
        
        参数：
        1. `event` (`Event`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().process_event(event)

        order: OrderData = event.data
        row_cells: dict = self.cells[order.vt_orderid]
        row: int = self.row(row_cells["volume"])

        if order.is_active():
            self.showRow(row)
        else:
            self.hideRow(row)


class ContractManager(QtWidgets.QWidget):
    """
    `ContractManager` 是合约查询管理面板，用于检索和浏览合约元数据。
    
    职责：
    1. 支持按代码、交易所等条件检索合约。
    2. 展示合约交易规则和静态属性。
    3. 为手工交易与策略配置提供查阅入口。
    
    协作：
    1. 由 `MainWindow` 统一创建与管理。
    2. 与 `MainEngine` 交互执行真实业务动作。
    """

    headers: dict[str, str] = {
        "vt_symbol": _("本地代码"),
        "symbol": _("代码"),
        "exchange": _("交易所"),
        "name": _("名称"),
        "product": _("合约分类"),
        "size": _("合约乘数"),
        "pricetick": _("价格跳动"),
        "min_volume": _("最小委托量"),
        "option_portfolio": _("期权产品"),
        "option_expiry": _("期权到期日"),
        "option_strike": _("期权行权价"),
        "option_type": _("期权类型"),
        "gateway_name": _("交易接口"),
    }

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `main_engine` (`MainEngine`)：输入参数，用于控制该方法的处理行为。
        2. `event_engine` (`EventEngine`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__()

        self.main_engine: MainEngine = main_engine
        self.event_engine: EventEngine = event_engine

        self.init_ui()

    def init_ui(self) -> None:
        """
        执行 `init_ui` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.setWindowTitle(_("合约查询"))
        self.resize(1000, 600)

        self.filter_line: QtWidgets.QLineEdit = QtWidgets.QLineEdit()
        self.filter_line.setPlaceholderText(_("输入合约代码或者交易所，留空则查询所有合约"))

        self.button_show: QtWidgets.QPushButton = QtWidgets.QPushButton(_("查询"))
        self.button_show.clicked.connect(self.show_contracts)

        labels: list = []
        for name, display in self.headers.items():
            label: str = f"{display}\n{name}"
            labels.append(label)

        self.contract_table: QtWidgets.QTableWidget = QtWidgets.QTableWidget()
        self.contract_table.setColumnCount(len(self.headers))
        self.contract_table.setHorizontalHeaderLabels(labels)
        self.contract_table.verticalHeader().setVisible(False)
        self.contract_table.setEditTriggers(self.contract_table.EditTrigger.NoEditTriggers)
        self.contract_table.setAlternatingRowColors(True)

        hbox: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.filter_line)
        hbox.addWidget(self.button_show)

        vbox: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout()
        vbox.addLayout(hbox)
        vbox.addWidget(self.contract_table)

        self.setLayout(vbox)

    def show_contracts(self) -> None:
        """
        执行 `show_contracts` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        flt: str = str(self.filter_line.text())

        all_contracts: list[ContractData] = self.main_engine.get_all_contracts()
        if flt:
            contracts: list[ContractData] = [
                contract for contract in all_contracts if flt in contract.vt_symbol
            ]
        else:
            contracts = all_contracts

        self.contract_table.clearContents()
        self.contract_table.setRowCount(len(contracts))

        for row, contract in enumerate(contracts):
            for column, name in enumerate(self.headers.keys()):
                value: Any = getattr(contract, name)

                if value in {None, 0}:
                    value = ""

                cell: BaseCell
                if isinstance(value, Enum):
                    cell = EnumCell(value, contract)
                elif isinstance(value, datetime):
                    cell = DateCell(value, contract)
                else:
                    cell = BaseCell(value, contract)
                self.contract_table.setItem(row, column, cell)

        self.contract_table.resizeColumnsToContents()


class AboutDialog(QtWidgets.QDialog):
    """
    `AboutDialog` 是关于弹窗，展示版本与项目信息。
    
    职责：
    1. 展示版本、作者和项目链接等说明信息。
    2. 提供运行环境与版权信息查看入口。
    3. 作为帮助入口提升可运维性。
    
    协作：
    1. 由 `MainWindow` 统一创建与管理。
    2. 与 `MainEngine` 交互执行真实业务动作。
    """

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `main_engine` (`MainEngine`)：输入参数，用于控制该方法的处理行为。
        2. `event_engine` (`EventEngine`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__()

        self.main_engine: MainEngine = main_engine
        self.event_engine: EventEngine = event_engine

        self.init_ui()

    def init_ui(self) -> None:
        """
        执行 `init_ui` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.setWindowTitle(_("关于VeighNa Trader"))

        from ... import __version__ as vnpy_version

        text: str = f"""
            By Traders, For Traders.

            Created by VeighNa Technology


            License：MIT
            Website：www.vnpy.com
            Github：www.github.com/vnpy/vnpy


            VeighNa - {vnpy_version}
            Python - {platform.python_version()}
            PySide6 - {metadata.version("pyside6")}
            NumPy - {metadata.version("numpy")}
            pandas - {metadata.version("pandas")}
            """

        label: QtWidgets.QLabel = QtWidgets.QLabel()
        label.setText(text)
        label.setMinimumWidth(500)

        vbox: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout()
        vbox.addWidget(label)
        self.setLayout(vbox)


class GlobalDialog(QtWidgets.QDialog):
    """
    `GlobalDialog` 是全局配置弹窗，用于修改系统级参数设置。
    
    职责：
    1. 展示并编辑全局配置项。
    2. 将修改结果写回配置并通知相关模块。
    3. 为日志、邮件、界面等公共行为提供统一配置入口。
    
    协作：
    1. 由 `MainWindow` 统一创建与管理。
    2. 与 `MainEngine` 交互执行真实业务动作。
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
        super().__init__()

        self.widgets: dict[str, tuple[QtWidgets.QLineEdit, type]] = {}

        self.init_ui()

    def init_ui(self) -> None:
        """
        执行 `init_ui` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.setWindowTitle(_("全局配置"))
        self.setMinimumWidth(800)

        settings: dict = copy(SETTINGS)
        settings.update(load_json(SETTING_FILENAME))

        # Initialize line edits and form layout based on setting.
        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()

        for field_name, field_value in settings.items():
            field_type: type = type(field_value)
            widget: QtWidgets.QLineEdit = QtWidgets.QLineEdit(str(field_value))

            form.addRow(f"{field_name} <{field_type.__name__}>", widget)
            self.widgets[field_name] = (widget, field_type)

        button: QtWidgets.QPushButton = QtWidgets.QPushButton(_("确定"))
        button.clicked.connect(self.update_setting)
        form.addRow(button)

        scroll_widget: QtWidgets.QWidget = QtWidgets.QWidget()
        scroll_widget.setLayout(form)

        scroll_area: QtWidgets.QScrollArea = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_widget)

        vbox: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout()
        vbox.addWidget(scroll_area)
        self.setLayout(vbox)

    def update_setting(self) -> None:
        """
        更新 `setting` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        settings: dict = {}
        for field_name, tp in self.widgets.items():
            widget, field_type = tp
            value_text: str = widget.text()

            if field_type is bool:
                if value_text == "True":
                    field_value: bool = True
                else:
                    field_value = False
            else:
                field_value = field_type(value_text)

            settings[field_name] = field_value

        QtWidgets.QMessageBox.information(
            self,
            _("注意"),
            _("全局配置的修改需要重启后才会生效！"),
            QtWidgets.QMessageBox.StandardButton.Ok
        )

        save_json(SETTING_FILENAME, settings)
        self.accept()
