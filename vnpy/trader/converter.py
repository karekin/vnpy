from copy import copy
from typing import TYPE_CHECKING

from .object import (
    ContractData,
    OrderData,
    TradeData,
    PositionData,
    OrderRequest
)
from .constant import Direction, Offset, Exchange

if TYPE_CHECKING:
    from .engine import OmsEngine


class PositionHolding:
    """
    `PositionHolding` 维护单合约的持仓与冻结明细，是开平转换与可平计算的基础状态容器。
    
    职责：
    1. 汇总多空方向的今仓、昨仓、冻结和成交变化。
    2. 基于委托与成交持续更新可用仓位。
    3. 为不同交易所规则下的下单转换提供原始状态。
    
    协作：
    1. 与 `OmsEngine` 协作维护实时状态。
    2. 在下单前由主引擎调用，保障请求符合交易所规则。
    """

    def __init__(self, contract: ContractData) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `contract` (`ContractData`)：合约元数据对象。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.vt_symbol: str = contract.vt_symbol
        self.exchange: Exchange = contract.exchange

        self.active_orders: dict[str, OrderData] = {}

        self.long_pos: float = 0
        self.long_yd: float = 0
        self.long_td: float = 0

        self.short_pos: float = 0
        self.short_yd: float = 0
        self.short_td: float = 0

        self.long_pos_frozen: float = 0
        self.long_yd_frozen: float = 0
        self.long_td_frozen: float = 0

        self.short_pos_frozen: float = 0
        self.short_yd_frozen: float = 0
        self.short_td_frozen: float = 0

    def update_position(self, position: PositionData) -> None:
        """
        更新 `position` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `position` (`PositionData`)：持仓数据对象。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if position.direction == Direction.LONG:
            self.long_pos = position.volume
            self.long_yd = position.yd_volume
            self.long_td = self.long_pos - self.long_yd
        else:
            self.short_pos = position.volume
            self.short_yd = position.yd_volume
            self.short_td = self.short_pos - self.short_yd

    def update_order(self, order: OrderData) -> None:
        """
        更新 `order` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `order` (`OrderData`)：委托数据对象。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if order.is_active():
            self.active_orders[order.vt_orderid] = order
        else:
            if order.vt_orderid in self.active_orders:
                self.active_orders.pop(order.vt_orderid)

        self.calculate_frozen()

    def update_order_request(self, req: OrderRequest, vt_orderid: str) -> None:
        """
        更新 `order_request` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `req` (`OrderRequest`)：请求对象，封装本次操作所需参数。
        2. `vt_orderid` (`str`)：标准委托编号。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        gateway_name, orderid = vt_orderid.split(".")

        order: OrderData = req.create_order_data(orderid, gateway_name)
        self.update_order(order)

    def update_trade(self, trade: TradeData) -> None:
        """
        更新 `trade` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `trade` (`TradeData`)：成交数据对象。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if trade.direction == Direction.LONG:
            if trade.offset == Offset.OPEN:
                self.long_td += trade.volume
            elif trade.offset == Offset.CLOSETODAY:
                self.short_td -= trade.volume
            elif trade.offset == Offset.CLOSEYESTERDAY:
                self.short_yd -= trade.volume
            elif trade.offset == Offset.CLOSE:
                if trade.exchange in {Exchange.SHFE, Exchange.INE}:
                    self.short_yd -= trade.volume
                else:
                    self.short_td -= trade.volume

                    if self.short_td < 0:
                        self.short_yd += self.short_td
                        self.short_td = 0
        else:
            if trade.offset == Offset.OPEN:
                self.short_td += trade.volume
            elif trade.offset == Offset.CLOSETODAY:
                self.long_td -= trade.volume
            elif trade.offset == Offset.CLOSEYESTERDAY:
                self.long_yd -= trade.volume
            elif trade.offset == Offset.CLOSE:
                if trade.exchange in {Exchange.SHFE, Exchange.INE}:
                    self.long_yd -= trade.volume
                else:
                    self.long_td -= trade.volume

                    if self.long_td < 0:
                        self.long_yd += self.long_td
                        self.long_td = 0

        self.long_pos = self.long_td + self.long_yd
        self.short_pos = self.short_td + self.short_yd

        # Update frozen volume to ensure no more than total volume
        self.sum_pos_frozen()

    def calculate_frozen(self) -> None:
        """
        执行 `calculate_frozen` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.long_pos_frozen = 0
        self.long_yd_frozen = 0
        self.long_td_frozen = 0

        self.short_pos_frozen = 0
        self.short_yd_frozen = 0
        self.short_td_frozen = 0

        for order in self.active_orders.values():
            # Ignore position open orders
            if order.offset == Offset.OPEN:
                continue

            frozen: float = order.volume - order.traded

            if order.direction == Direction.LONG:
                if order.offset == Offset.CLOSETODAY:
                    self.short_td_frozen += frozen
                elif order.offset == Offset.CLOSEYESTERDAY:
                    self.short_yd_frozen += frozen
                elif order.offset == Offset.CLOSE:
                    self.short_td_frozen += frozen

                    if self.short_td_frozen > self.short_td:
                        self.short_yd_frozen += (self.short_td_frozen
                                                 - self.short_td)
                        self.short_td_frozen = self.short_td
            elif order.direction == Direction.SHORT:
                if order.offset == Offset.CLOSETODAY:
                    self.long_td_frozen += frozen
                elif order.offset == Offset.CLOSEYESTERDAY:
                    self.long_yd_frozen += frozen
                elif order.offset == Offset.CLOSE:
                    self.long_td_frozen += frozen

                    if self.long_td_frozen > self.long_td:
                        self.long_yd_frozen += (self.long_td_frozen
                                                - self.long_td)
                        self.long_td_frozen = self.long_td

        self.sum_pos_frozen()

    def sum_pos_frozen(self) -> None:
        """
        执行 `sum_pos_frozen` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        # Frozen volume should be no more than total volume
        self.long_td_frozen = min(self.long_td_frozen, self.long_td)
        self.long_yd_frozen = min(self.long_yd_frozen, self.long_yd)

        self.short_td_frozen = min(self.short_td_frozen, self.short_td)
        self.short_yd_frozen = min(self.short_yd_frozen, self.short_yd)

        self.long_pos_frozen = self.long_td_frozen + self.long_yd_frozen
        self.short_pos_frozen = self.short_td_frozen + self.short_yd_frozen

    def convert_order_request_shfe(self, req: OrderRequest) -> list[OrderRequest]:
        """
        执行 `convert_order_request_shfe` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `req` (`OrderRequest`)：请求对象，封装本次操作所需参数。
        
        返回：
        1. `list[OrderRequest]`：返回按约定组织的数据列表。
        """
        if req.offset == Offset.OPEN:
            return [req]

        if req.direction == Direction.LONG:
            pos_available: float = self.short_pos - self.short_pos_frozen
            td_available: float = self.short_td - self.short_td_frozen
        else:
            pos_available = self.long_pos - self.long_pos_frozen
            td_available = self.long_td - self.long_td_frozen

        if req.volume > pos_available:
            return []
        elif req.volume <= td_available:
            req_td: OrderRequest = copy(req)
            req_td.offset = Offset.CLOSETODAY
            return [req_td]
        else:
            req_list: list[OrderRequest] = []

            if td_available > 0:
                req_td = copy(req)
                req_td.offset = Offset.CLOSETODAY
                req_td.volume = td_available
                req_list.append(req_td)

            req_yd: OrderRequest = copy(req)
            req_yd.offset = Offset.CLOSEYESTERDAY
            req_yd.volume = req.volume - td_available
            req_list.append(req_yd)

            return req_list

    def convert_order_request_lock(self, req: OrderRequest) -> list[OrderRequest]:
        """
        执行 `convert_order_request_lock` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `req` (`OrderRequest`)：请求对象，封装本次操作所需参数。
        
        返回：
        1. `list[OrderRequest]`：返回按约定组织的数据列表。
        """
        if req.direction == Direction.LONG:
            td_volume: float = self.short_td
            yd_available: float = self.short_yd - self.short_yd_frozen
        else:
            td_volume = self.long_td
            yd_available = self.long_yd - self.long_yd_frozen

        close_yd_exchanges: set[Exchange] = {Exchange.SHFE, Exchange.INE}

        # If there is td_volume, we can only lock position
        if td_volume and self.exchange not in close_yd_exchanges:
            req_open: OrderRequest = copy(req)
            req_open.offset = Offset.OPEN
            return [req_open]
        # If no td_volume, we close opposite yd position first
        # then open new position
        else:
            close_volume: float = min(req.volume, yd_available)
            open_volume: float = max(0, req.volume - yd_available)
            req_list: list[OrderRequest] = []

            if yd_available:
                req_yd: OrderRequest = copy(req)
                if self.exchange in close_yd_exchanges:
                    req_yd.offset = Offset.CLOSEYESTERDAY
                else:
                    req_yd.offset = Offset.CLOSE
                req_yd.volume = close_volume
                req_list.append(req_yd)

            if open_volume:
                req_open = copy(req)
                req_open.offset = Offset.OPEN
                req_open.volume = open_volume
                req_list.append(req_open)

            return req_list

    def convert_order_request_net(self, req: OrderRequest) -> list[OrderRequest]:
        """
        执行 `convert_order_request_net` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `req` (`OrderRequest`)：请求对象，封装本次操作所需参数。
        
        返回：
        1. `list[OrderRequest]`：返回按约定组织的数据列表。
        """
        if req.direction == Direction.LONG:
            pos_available: float = self.short_pos - self.short_pos_frozen
            td_available: float = self.short_td - self.short_td_frozen
            yd_available: float = self.short_yd - self.short_yd_frozen
        else:
            pos_available = self.long_pos - self.long_pos_frozen
            td_available = self.long_td - self.long_td_frozen
            yd_available = self.long_yd - self.long_yd_frozen

        # Split close order to close today/yesterday for SHFE/INE exchange
        if req.exchange in {Exchange.SHFE, Exchange.INE}:
            reqs: list[OrderRequest] = []
            volume_left: float = req.volume

            if td_available:
                td_volume: float = min(td_available, volume_left)
                volume_left -= td_volume

                td_req: OrderRequest = copy(req)
                td_req.offset = Offset.CLOSETODAY
                td_req.volume = td_volume
                reqs.append(td_req)

            if volume_left and yd_available:
                yd_volume: float = min(yd_available, volume_left)
                volume_left -= yd_volume

                yd_req: OrderRequest = copy(req)
                yd_req.offset = Offset.CLOSEYESTERDAY
                yd_req.volume = yd_volume
                reqs.append(yd_req)

            if volume_left > 0:
                open_volume: float = volume_left

                open_req: OrderRequest = copy(req)
                open_req.offset = Offset.OPEN
                open_req.volume = open_volume
                reqs.append(open_req)

            return reqs
        # Just use close for other exchanges
        else:
            reqs = []
            volume_left = req.volume

            if pos_available:
                close_volume: float = min(pos_available, volume_left)
                volume_left -= pos_available

                close_req: OrderRequest = copy(req)
                close_req.offset = Offset.CLOSE
                close_req.volume = close_volume
                reqs.append(close_req)

            if volume_left > 0:
                open_volume = volume_left

                open_req = copy(req)
                open_req.offset = Offset.OPEN
                open_req.volume = open_volume
                reqs.append(open_req)

            return reqs


class OffsetConverter:
    """
    `OffsetConverter` 负责将标准下单请求转换为交易所可接受的开平组合（如平今/平昨拆分）。
    
    职责：
    1. 按网关和交易所规则转换 `OrderRequest` 的 offset 字段。
    2. 处理锁仓、净仓模式下的委托拆分与数量分配。
    3. 同步委托、成交、持仓事件以保持转换依据实时有效。
    
    协作：
    1. 与 `OmsEngine` 协作维护实时状态。
    2. 在下单前由主引擎调用，保障请求符合交易所规则。
    """

    def __init__(self, oms_engine: "OmsEngine") -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `oms_engine` (`'OmsEngine'`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.holdings: dict[str, PositionHolding] = {}

        self.get_contract = oms_engine.get_contract

    def update_position(self, position: PositionData) -> None:
        """
        更新 `position` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `position` (`PositionData`)：持仓数据对象。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if not self.is_convert_required(position.vt_symbol):
            return

        holding: PositionHolding | None = self.get_position_holding(position.vt_symbol)
        if holding:
            holding.update_position(position)

    def update_trade(self, trade: TradeData) -> None:
        """
        更新 `trade` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `trade` (`TradeData`)：成交数据对象。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if not self.is_convert_required(trade.vt_symbol):
            return

        holding: PositionHolding | None = self.get_position_holding(trade.vt_symbol)
        if holding:
            holding.update_trade(trade)

    def update_order(self, order: OrderData) -> None:
        """
        更新 `order` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `order` (`OrderData`)：委托数据对象。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if not self.is_convert_required(order.vt_symbol):
            return

        holding: PositionHolding | None = self.get_position_holding(order.vt_symbol)
        if holding:
            holding.update_order(order)

    def update_order_request(self, req: OrderRequest, vt_orderid: str) -> None:
        """
        更新 `order_request` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `req` (`OrderRequest`)：请求对象，封装本次操作所需参数。
        2. `vt_orderid` (`str`)：标准委托编号。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if not self.is_convert_required(req.vt_symbol):
            return

        holding: PositionHolding | None = self.get_position_holding(req.vt_symbol)
        if holding:
            holding.update_order_request(req, vt_orderid)

    def get_position_holding(self, vt_symbol: str) -> PositionHolding | None:
        """
        获取 `position_holding` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `vt_symbol` (`str`)：标准合约代码（交易所.代码）。
        
        返回：
        1. `PositionHolding | None`：返回该方法计算或查询得到的结果。
        """
        holding: PositionHolding | None = self.holdings.get(vt_symbol, None)

        if not holding:
            contract: ContractData | None = self.get_contract(vt_symbol)
            if contract:
                holding = PositionHolding(contract)
                self.holdings[vt_symbol] = holding

        return holding

    def convert_order_request(
        self,
        req: OrderRequest,
        lock: bool,
        net: bool = False
    ) -> list[OrderRequest]:
        """
        执行 `convert_order_request` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `req` (`OrderRequest`)：请求对象，封装本次操作所需参数。
        2. `lock` (`bool`)：输入参数，用于控制该方法的处理行为。
        3. `net` (`bool`)，默认值 `False`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `list[OrderRequest]`：返回按约定组织的数据列表。
        """
        if not self.is_convert_required(req.vt_symbol):
            return [req]

        holding: PositionHolding | None = self.get_position_holding(req.vt_symbol)

        if not holding:
            return [req]
        elif lock:
            return holding.convert_order_request_lock(req)
        elif net:
            return holding.convert_order_request_net(req)
        elif req.exchange in {Exchange.SHFE, Exchange.INE}:
            return holding.convert_order_request_shfe(req)
        else:
            return [req]

    def is_convert_required(self, vt_symbol: str) -> bool:
        """
        执行 `is_convert_required` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `vt_symbol` (`str`)：标准合约代码（交易所.代码）。
        
        返回：
        1. `bool`：表示操作是否成功或条件是否成立。
        """
        contract: ContractData | None = self.get_contract(vt_symbol)

        # Only contracts with long-short position mode requires convert
        if not contract:
            return False
        elif contract.net_position:
            return False
        else:
            return True
