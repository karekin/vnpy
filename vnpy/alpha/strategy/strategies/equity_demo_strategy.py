from collections import defaultdict

import polars as pl

from vnpy.trader.object import BarData, TradeData
from vnpy.trader.constant import Direction
from vnpy.trader.utility import round_to

from vnpy.alpha import AlphaStrategy


class EquityDemoStrategy(AlphaStrategy):
    """
    股票横截面轮动示例策略。

    调仓思想：
    1. 每期优先持有信号排名前 `top_k` 的股票。
    2. 先卖出不在成分池/信号靠后的持仓，再买入高分未持仓股票。
    3. 受最小持有天数、资金使用比例和最小交易单位约束。
    """

    top_k: int = 50                 # 目标持仓股票数上限
    n_drop: int = 5                 # 每次调仓最多淘汰的低分持仓数量
    min_days: int = 3               # 最短持有天数，未到期不卖
    cash_ratio: float = 0.95        # 可用资金中用于建仓的比例
    min_volume: int = 100           # 最小交易单位（A股常见为100股）
    open_rate: float = 0.0005       # 买入费率估计
    close_rate: float = 0.0015      # 卖出费率估计
    min_commission: int = 5         # 单笔最小手续费
    price_add: float = 0.05         # 发单价格相对收盘价的偏移比例

    def on_init(self) -> None:
        """
        初始化持仓天数跟踪表。

        `holding_days` 用于控制最小持有期，避免策略过度换手。
        """
        # 记录每个持仓标的已持有的交易日数。
        self.holding_days: defaultdict = defaultdict(int)

        self.write_log("Strategy initialized")

    def on_trade(self, trade: TradeData) -> None:
        """
        成交后维护持仓天数字典。

        卖出成交后移除对应标的的持有记录，后续若再次买入将重新计天数。
        """
        # 卖出后删除持有天数记录。
        if trade.direction == Direction.SHORT:
            self.holding_days.pop(trade.vt_symbol, None)

    def on_bars(self, bars: dict[str, BarData]) -> None:
        """
        基于当期信号执行一次调仓决策。

        决策流程：
        1. 读取并按分数降序排序当期信号。
        2. 更新当前持仓的持有天数。
        3. 生成卖出列表：剔除非成分股 + 淘汰低分持仓。
        4. 生成买入列表：从未持仓高分标的中补足目标持仓数。
        5. 先按卖出后现金估算可买金额，再等权设置买入目标仓位。
        6. 调用 `execute_trading` 把目标仓位转换成具体委托。
        """
        # 读取当期信号并按分数从高到低排序。
        last_signal: pl.DataFrame = self.get_signal()
        last_signal = last_signal.sort("signal", descending=True)

        # 当前持仓标的列表，并累计持有天数。
        pos_symbols: list[str] = [vt_symbol for vt_symbol, pos in self.pos_data.items() if pos]

        for vt_symbol in pos_symbols:
            self.holding_days[vt_symbol] += 1

        # 生成待卖列表。
        active_symbols: set[str] = set(last_signal["vt_symbol"][:self.top_k])                         # 候选池：高分股票
        active_symbols.update(pos_symbols)                                                            # 并入当前持仓，避免全量突变
        active_df: pl.DataFrame = last_signal.filter(pl.col("vt_symbol").is_in(active_symbols))       # 活跃池信号表

        component_symbols: set[str] = set(last_signal["vt_symbol"])                 # 当前可交易成分池
        sell_symbols: set[str] = set(pos_symbols).difference(component_symbols)     # 持仓中不在成分池的先卖出

        for vt_symbol in active_df["vt_symbol"][-self.n_drop:]:                     # 活跃池中低分尾部
            if vt_symbol in pos_symbols:                                            # 仅淘汰已有持仓
                sell_symbols.add(vt_symbol)

        # 生成待买列表：从未持仓高分股票中补齐目标持仓数量。
        buyable_df: pl.DataFrame = last_signal.filter(~pl.col("vt_symbol").is_in(pos_symbols))
        buy_quantity: int = len(sell_symbols) + self.top_k - len(pos_symbols)
        buy_symbols: list = list(buyable_df[:buy_quantity]["vt_symbol"])

        # 卖出侧调仓：先估算卖出后可用现金。
        cash: float = self.get_cash_available()                     # 昨日结算后可用现金

        for vt_symbol in sell_symbols:
            if self.holding_days[vt_symbol] < self.min_days:        # 不满足最短持有期则跳过
                continue

            bar: BarData | None = bars.get(vt_symbol)               # 当前行情
            if not bar:
                continue
            sell_price: float = bar.close_price

            sell_volume: float = self.get_pos(vt_symbol)            # 当前持仓数量

            self.set_target(vt_symbol, target=0)                    # 目标仓位归零

            turnover: float = sell_price * sell_volume
            cost: float = max(turnover * self.close_rate, self.min_commission)
            cash += turnover - cost

        # 买入侧调仓：按资金等额分配到待买标的。
        if buy_symbols:
            buy_value: float = cash * self.cash_ratio / len(buy_symbols)

            for vt_symbol in buy_symbols:
                buy_price: float = bars[vt_symbol].close_price
                if not buy_price:
                    continue

                buy_volume: float = round_to(buy_value / buy_price, self.min_volume)

                self.set_target(vt_symbol, buy_volume)

        # 将目标仓位差转换为具体委托。
        self.execute_trading(bars, price_add=self.price_add)
