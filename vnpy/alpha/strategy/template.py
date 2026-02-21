from abc import ABCMeta, abstractmethod
from collections import defaultdict
from typing import TYPE_CHECKING

import polars as pl

from vnpy.trader.object import BarData, TradeData, OrderData
from vnpy.trader.constant import Offset, Direction


if TYPE_CHECKING:
    from vnpy.alpha.strategy.backtesting import BacktestingEngine


class AlphaStrategy(metaclass=ABCMeta):
    """
    Alpha 策略基类，定义“信号 -> 目标仓位 -> 委托执行”的标准接口。

    该模板把策略和回测引擎的职责分开：
    1. 子类负责生成目标仓位和交易时机。
    2. 引擎负责撮合、资金与持仓记账、订单生命周期管理。
    """

    def __init__(
        self,
        strategy_engine: "BacktestingEngine",
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict
    ) -> None:
        """
        初始化策略运行上下文。

        初始化内容：
        1. 引擎引用与策略标识。
        2. 实际仓位 `pos_data` 与目标仓位 `target_data`。
        3. 订单缓存与活动委托集合，用于撤单与状态跟踪。
        4. 读取 `setting` 中与类属性同名的参数作为策略配置。
        """
        self.strategy_engine: BacktestingEngine = strategy_engine
        self.strategy_name: str = strategy_name
        self.vt_symbols: list[str] = vt_symbols

        # 仓位状态：当前已成交仓位 vs 策略目标仓位。
        self.pos_data: dict[str, float] = defaultdict(float)
        self.target_data: dict[str, float] = defaultdict(float)

        # 委托状态缓存。
        self.orders: dict[str, OrderData] = {}
        self.active_orderids: set[str] = set()

        # 加载策略参数。
        for k, v in setting.items():
            if hasattr(self, k):
                setattr(self, k, v)

    @abstractmethod
    def on_init(self) -> None:
        """
        策略初始化回调。

        子类通常在这里完成历史数据预热、模型加载、初始目标仓位设置等准备动作。
        """
        pass

    @abstractmethod
    def on_bars(self, bars: dict[str, BarData]) -> None:
        """
        K 线驱动回调。

        子类应在这里基于最新截面数据更新信号与目标仓位，
        必要时调用 `execute_trading` 发起调仓。
        """
        pass

    @abstractmethod
    def on_trade(self, trade: TradeData) -> None:
        """
        成交回调。

        子类可在这里做成交后处理，例如记录换手、更新风控状态或触发再平衡逻辑。
        """
        pass

    def update_trade(self, trade: TradeData) -> None:
        """
        根据成交更新策略仓位，并转发给 `on_trade`。

        约定：`LONG` 成交增加仓位，`SHORT` 成交减少仓位。
        """
        if trade.direction == Direction.LONG:
            self.pos_data[trade.vt_symbol] += trade.volume
        else:
            self.pos_data[trade.vt_symbol] -= trade.volume

        self.on_trade(trade)

    def update_order(self, order: OrderData) -> None:
        """
        更新委托缓存和活动委托集合。

        当委托变为非活动状态（成交完/撤单/拒单）时，从活动集合移除。
        """
        self.orders[order.vt_orderid] = order

        if not order.is_active() and order.vt_orderid in self.active_orderids:
            self.active_orderids.remove(order.vt_orderid)

    def get_signal(self) -> pl.DataFrame:
        """
        获取当前时点的截面信号表。

        具体信号数据由回测引擎维护，策略可直接读取用于调仓决策。
        """
        return self.strategy_engine.get_signal()

    def buy(self, vt_symbol: str, price: float, volume: float) -> list[str]:
        """
        开多委托快捷方法（`LONG + OPEN`）。
        """
        return self.send_order(vt_symbol, Direction.LONG, Offset.OPEN, price, volume)

    def sell(self, vt_symbol: str, price: float, volume: float) -> list[str]:
        """
        平多委托快捷方法（`SHORT + CLOSE`）。
        """
        return self.send_order(vt_symbol, Direction.SHORT, Offset.CLOSE, price, volume)

    def short(self, vt_symbol: str, price: float, volume: float) -> list[str]:
        """
        开空委托快捷方法（`SHORT + OPEN`）。
        """
        return self.send_order(vt_symbol, Direction.SHORT, Offset.OPEN, price, volume)

    def cover(self, vt_symbol: str, price: float, volume: float) -> list[str]:
        """
        平空委托快捷方法（`LONG + CLOSE`）。
        """
        return self.send_order(vt_symbol, Direction.LONG, Offset.CLOSE, price, volume)

    def send_order(
        self,
        vt_symbol: str,
        direction: Direction,
        offset: Offset,
        price: float,
        volume: float
    ) -> list[str]:
        """
        通过引擎发单，并记录返回的活动委托号。

        返回值是本次发单对应的 `vt_orderid` 列表，用于后续跟踪和撤单。
        """
        vt_orderids: list = self.strategy_engine.send_order(
            self, vt_symbol, direction, offset, price, volume
        )

        for vt_orderid in vt_orderids:
            self.active_orderids.add(vt_orderid)

        return vt_orderids

    def cancel_order(self, vt_orderid: str) -> None:
        """
        撤销指定活动委托。
        """
        self.strategy_engine.cancel_order(self, vt_orderid)

    def cancel_all(self) -> None:
        """
        撤销当前策略全部活动委托。

        常用于重平衡前先清理旧挂单，避免旧目标与新目标冲突。
        """
        for vt_orderid in list(self.active_orderids):
            self.cancel_order(vt_orderid)

    def get_pos(self, vt_symbol: str) -> float:
        """
        查询指定合约当前持仓。
        """
        return self.pos_data[vt_symbol]

    def get_target(self, vt_symbol: str) -> float:
        """
        查询指定合约目标仓位。
        """
        return self.target_data[vt_symbol]

    def set_target(self, vt_symbol: str, target: float) -> None:
        """
        设置指定合约目标仓位。

        该值由策略信号决定，实际成交后会逐步收敛到目标值。
        """
        self.target_data[vt_symbol] = target

    def execute_trading(self, bars: dict[str, BarData], price_add: float) -> None:
        """
        按“目标仓位 - 当前仓位”执行调仓。

        执行规则：
        1. 先撤掉旧挂单，避免重复成交。
        2. `diff > 0` 表示净增多头，优先平空(`cover`)再开多(`buy`)。
        3. `diff < 0` 表示净增空头，优先平多(`sell`)再开空(`short`)。
        4. 下单价基于收盘价加减 `price_add`，用于模拟冲击成本/滑点缓冲。
        """
        self.cancel_all()

        # 仅对当前有行情的合约发单。
        for vt_symbol, bar in bars.items():
            # 目标仓位与实际仓位差值。
            target: float = self.get_target(vt_symbol)
            pos: float = self.get_pos(vt_symbol)
            diff: float = target - pos

            # 需要增加净多头敞口。
            if diff > 0:
                # 买入侧价格上浮。
                order_price: float = bar.close_price * (1 + price_add)

                # 先平空、后开多，避免方向冲突。
                cover_volume: float = 0
                buy_volume: float = 0

                if pos < 0:
                    cover_volume = min(diff, abs(pos))
                    buy_volume = diff - cover_volume
                else:
                    buy_volume = diff

                # 分别提交平空和开多委托。
                if cover_volume:
                    self.cover(vt_symbol, order_price, cover_volume)

                if buy_volume:
                    self.buy(vt_symbol, order_price, buy_volume)
            # 需要增加净空头敞口。
            elif diff < 0:
                # 卖出侧价格下浮。
                order_price = bar.close_price * (1 - price_add)

                # 先平多、后开空，避免方向冲突。
                sell_volume: float = 0
                short_volume: float = 0

                if pos > 0:
                    sell_volume = min(abs(diff), pos)
                    short_volume = abs(diff) - sell_volume
                else:
                    short_volume = abs(diff)

                # 分别提交平多和开空委托。
                if sell_volume:
                    self.sell(vt_symbol, order_price, sell_volume)

                if short_volume:
                    self.short(vt_symbol, order_price, short_volume)

    def write_log(self, msg: str) -> None:
        """
        通过引擎记录策略日志。
        """
        self.strategy_engine.write_log(msg, self)

    def get_cash_available(self) -> float:
        """
        获取当前可用现金。

        该值一般已扣除冻结保证金/占用资金，由回测引擎维护。
        """
        return self.strategy_engine.get_cash_available()

    def get_holding_value(self) -> float:
        """
        获取持仓市值。
        """
        return self.strategy_engine.get_holding_value()

    def get_portfolio_value(self) -> float:
        """
        获取组合总权益（可用现金 + 持仓市值）。
        """
        return self.get_cash_available() + self.get_holding_value()

    def get_cash(self) -> float:
        """
        `get_cash_available` 的别名接口。
        """
        return self.get_cash_available()
