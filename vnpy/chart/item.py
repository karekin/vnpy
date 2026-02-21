from abc import abstractmethod

import pyqtgraph as pg      # type: ignore

from vnpy.trader.ui import QtCore, QtGui, QtWidgets
from vnpy.trader.object import BarData

from .base import BLACK_COLOR, UP_COLOR, DOWN_COLOR, PEN_WIDTH, BAR_WIDTH
from .manager import BarManager


class ChartItem(pg.GraphicsObject):
    """
    `ChartItem` 是图表绘制项基类，定义缓存绘制与重绘协议。
    
    职责：
    1. 统一管理绘图缓存、可见区渲染和样式参数。
    2. 规范子类如何从 `BarManager` 读取数据并绘制。
    3. 降低大数据量场景下的重复绘制开销。
    
    协作：
    1. 依赖 `BarManager` 数据。
    2. 由 `ChartWidget` 统一调度刷新。
    """

    def __init__(self, manager: BarManager) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `manager` (`BarManager`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__()

        self._manager: BarManager = manager

        self._bar_picutures: dict[int, QtGui.QPicture | None] = {}
        self._item_picuture: QtGui.QPicture | None = None

        self._black_brush: QtGui.QBrush = pg.mkBrush(color=BLACK_COLOR)

        self._up_pen: QtGui.QPen = pg.mkPen(
            color=UP_COLOR, width=PEN_WIDTH
        )
        self._up_brush: QtGui.QBrush = pg.mkBrush(color=UP_COLOR)

        self._down_pen: QtGui.QPen = pg.mkPen(
            color=DOWN_COLOR, width=PEN_WIDTH
        )
        self._down_brush: QtGui.QBrush = pg.mkBrush(color=DOWN_COLOR)

        self._rect_area: tuple[float, float] | None = None

        # Very important! Only redraw the visible part and improve speed a lot.
        self.setFlag(self.GraphicsItemFlag.ItemUsesExtendedStyleOption)

        # Force update during the next paint
        self._to_update: bool = False

    @abstractmethod
    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """
        执行 `_draw_bar_picture` 相关业务逻辑。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `ix` (`int`)：输入参数，用于控制该方法的处理行为。
        2. `bar` (`BarData`)：K 线数据对象。
        
        返回：
        1. `QtGui.QPicture`：返回该方法计算或查询得到的结果。
        """
        pass

    @abstractmethod
    def boundingRect(self) -> QtCore.QRectF:
        """
        执行 `boundingRect` 相关业务逻辑。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `QtCore.QRectF`：返回该方法计算或查询得到的结果。
        """
        pass

    @abstractmethod
    def get_y_range(self, min_ix: int | None = None, max_ix: int | None = None) -> tuple[float, float]:
        """
        获取 `y_range` 相关对象或计算结果。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `min_ix` (`int | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        2. `max_ix` (`int | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `tuple[float, float]`：返回多个值组成的结果元组。
        """
        pass

    @abstractmethod
    def get_info_text(self, ix: int) -> str:
        """
        获取 `info_text` 相关对象或计算结果。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `ix` (`int`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `str`：返回字符串结果。
        """
        pass

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
        self._bar_picutures.clear()

        bars: list[BarData] = self._manager.get_all_bars()

        for ix, _ in enumerate(bars):
            self._bar_picutures[ix] = None

        self.update()

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
        ix: int | None = self._manager.get_index(bar.datetime)
        if ix is None:
            return

        self._bar_picutures[ix] = None

        self.update()

    def update(self) -> None:
        """
        执行 `update` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if self.scene():
            self._to_update = True
            self.scene().update()

    def paint(
        self,
        painter: QtGui.QPainter,
        opt: QtWidgets.QStyleOptionGraphicsItem,
        w: QtWidgets.QWidget
    ) -> None:
        """
        执行 `paint` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `painter` (`QtGui.QPainter`)：输入参数，用于控制该方法的处理行为。
        2. `opt` (`QtWidgets.QStyleOptionGraphicsItem`)：输入参数，用于控制该方法的处理行为。
        3. `w` (`QtWidgets.QWidget`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        rect: QtCore.QRectF = opt.exposedRect       # type: ignore

        min_ix: int = int(rect.left())
        max_ix: int = int(rect.right())
        max_ix = min(max_ix, len(self._bar_picutures))

        rect_area: tuple = (min_ix, max_ix)
        if (
            self._to_update
            or rect_area != self._rect_area
            or not self._item_picuture
        ):
            self._to_update = False
            self._rect_area = rect_area
            self._draw_item_picture(min_ix, max_ix)

        if self._item_picuture:
            self._item_picuture.play(painter)

    def _draw_item_picture(self, min_ix: int, max_ix: int) -> None:
        """
        执行 `_draw_item_picture` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `min_ix` (`int`)：输入参数，用于控制该方法的处理行为。
        2. `max_ix` (`int`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self._item_picuture = QtGui.QPicture()
        painter: QtGui.QPainter = QtGui.QPainter(self._item_picuture)

        for ix in range(min_ix, max_ix):
            bar_picture: QtGui.QPicture | None = self._bar_picutures[ix]

            if bar_picture is None:
                bar: BarData | None = self._manager.get_bar(ix)
                if bar is None:
                    continue

                bar_picture = self._draw_bar_picture(ix, bar)
                self._bar_picutures[ix] = bar_picture

            bar_picture.play(painter)

        painter.end()

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
        self._item_picuture = None
        self._bar_picutures.clear()
        self.update()


class CandleItem(ChartItem):
    """
    `CandleItem` 是蜡烛图绘制项，负责 OHLC K 线主体渲染。
    
    职责：
    1. 按涨跌颜色绘制开高低收实体与影线。
    2. 支持局部区域增量重绘。
    3. 为交易员提供主价格走势可视化。
    
    协作：
    1. 依赖 `BarManager` 数据。
    2. 由 `ChartWidget` 统一调度刷新。
    """

    def __init__(self, manager: BarManager) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `manager` (`BarManager`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(manager)

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """
        执行 `_draw_bar_picture` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `ix` (`int`)：输入参数，用于控制该方法的处理行为。
        2. `bar` (`BarData`)：K 线数据对象。
        
        返回：
        1. `QtGui.QPicture`：返回该方法计算或查询得到的结果。
        """
        # Create objects
        candle_picture: QtGui.QPicture = QtGui.QPicture()
        painter: QtGui.QPainter = QtGui.QPainter(candle_picture)

        # Set painter color
        if bar.close_price >= bar.open_price:
            painter.setPen(self._up_pen)
            painter.setBrush(self._black_brush)
        else:
            painter.setPen(self._down_pen)
            painter.setBrush(self._down_brush)

        # Draw candle shadow
        if bar.high_price > bar.low_price:
            painter.drawLine(
                QtCore.QPointF(ix, bar.high_price),
                QtCore.QPointF(ix, bar.low_price)
            )

        # Draw candle body
        if bar.open_price == bar.close_price:
            painter.drawLine(
                QtCore.QPointF(ix - BAR_WIDTH, bar.open_price),
                QtCore.QPointF(ix + BAR_WIDTH, bar.open_price),
            )
        else:
            rect: QtCore.QRectF = QtCore.QRectF(
                ix - BAR_WIDTH,
                bar.open_price,
                BAR_WIDTH * 2,
                bar.close_price - bar.open_price
            )
            painter.drawRect(rect)

        # Finish
        painter.end()
        return candle_picture

    def boundingRect(self) -> QtCore.QRectF:
        """
        执行 `boundingRect` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `QtCore.QRectF`：返回该方法计算或查询得到的结果。
        """
        min_price, max_price = self._manager.get_price_range()
        rect: QtCore.QRectF = QtCore.QRectF(
            0,
            min_price,
            len(self._bar_picutures),
            max_price - min_price
        )
        return rect

    def get_y_range(self, min_ix: int | None = None, max_ix: int | None = None) -> tuple[float, float]:
        """
        获取 `y_range` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `min_ix` (`int | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        2. `max_ix` (`int | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `tuple[float, float]`：返回多个值组成的结果元组。
        """
        min_price, max_price = self._manager.get_price_range(min_ix, max_ix)
        return min_price, max_price

    def get_info_text(self, ix: int) -> str:
        """
        获取 `info_text` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `ix` (`int`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `str`：返回字符串结果。
        """
        bar: BarData | None = self._manager.get_bar(ix)

        if bar:
            words: list = [
                "Date",
                bar.datetime.strftime("%Y-%m-%d"),
                "",
                "Time",
                bar.datetime.strftime("%H:%M"),
                "",
                "Open",
                str(bar.open_price),
                "",
                "High",
                str(bar.high_price),
                "",
                "Low",
                str(bar.low_price),
                "",
                "Close",
                str(bar.close_price)
            ]
            text: str = "\n".join(words)
        else:
            text = ""

        return text


class VolumeItem(ChartItem):
    """
    `VolumeItem` 是成交量柱状图绘制项，与蜡烛图时间轴对齐展示成交量变化。
    
    职责：
    1. 按涨跌方向渲染量柱颜色。
    2. 与主图时间轴同步滚动和缩放。
    3. 辅助判断量价关系。
    
    协作：
    1. 依赖 `BarManager` 数据。
    2. 由 `ChartWidget` 统一调度刷新。
    """

    def __init__(self, manager: BarManager) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `manager` (`BarManager`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(manager)

    def _draw_bar_picture(self, ix: int, bar: BarData) -> QtGui.QPicture:
        """
        执行 `_draw_bar_picture` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `ix` (`int`)：输入参数，用于控制该方法的处理行为。
        2. `bar` (`BarData`)：K 线数据对象。
        
        返回：
        1. `QtGui.QPicture`：返回该方法计算或查询得到的结果。
        """
        # Create objects
        volume_picture: QtGui.QPicture = QtGui.QPicture()
        painter: QtGui.QPainter = QtGui.QPainter(volume_picture)

        # Set painter color
        if bar.close_price >= bar.open_price:
            painter.setPen(self._up_pen)
            painter.setBrush(self._up_brush)
        else:
            painter.setPen(self._down_pen)
            painter.setBrush(self._down_brush)

        # Draw volume body
        rect: QtCore.QRectF = QtCore.QRectF(
            ix - BAR_WIDTH,
            0,
            BAR_WIDTH * 2,
            bar.volume
        )
        painter.drawRect(rect)

        # Finish
        painter.end()
        return volume_picture

    def boundingRect(self) -> QtCore.QRectF:
        """
        执行 `boundingRect` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `QtCore.QRectF`：返回该方法计算或查询得到的结果。
        """
        min_volume, max_volume = self._manager.get_volume_range()
        rect: QtCore.QRectF = QtCore.QRectF(
            0,
            min_volume,
            len(self._bar_picutures),
            max_volume - min_volume
        )
        return rect

    def get_y_range(self, min_ix: int | None = None, max_ix: int | None = None) -> tuple[float, float]:
        """
        获取 `y_range` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `min_ix` (`int | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        2. `max_ix` (`int | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `tuple[float, float]`：返回多个值组成的结果元组。
        """
        min_volume, max_volume = self._manager.get_volume_range(min_ix, max_ix)
        return min_volume, max_volume

    def get_info_text(self, ix: int) -> str:
        """
        获取 `info_text` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `ix` (`int`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `str`：返回字符串结果。
        """
        bar: BarData | None = self._manager.get_bar(ix)

        if bar:
            text: str = f"Volume {bar.volume}"
        else:
            text = ""

        return text
