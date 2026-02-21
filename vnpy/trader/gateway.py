from abc import ABC, abstractmethod

from vnpy.event import Event, EventEngine
from .event import (
    EVENT_TICK,
    EVENT_ORDER,
    EVENT_TRADE,
    EVENT_POSITION,
    EVENT_ACCOUNT,
    EVENT_CONTRACT,
    EVENT_LOG,
    EVENT_QUOTE,
)
from .object import (
    TickData,
    OrderData,
    TradeData,
    PositionData,
    AccountData,
    ContractData,
    LogData,
    QuoteData,
    OrderRequest,
    CancelRequest,
    SubscribeRequest,
    HistoryRequest,
    QuoteRequest,
    Exchange,
    BarData
)


class BaseGateway(ABC):
    """
    交易网关抽象基类。

    网关是“交易系统协议”与“vn.py统一接口”之间的适配层：
    1. 上游接收 MainEngine 的连接、订阅、下单、撤单请求。
    2. 下游对接券商/交易所 API，并把回报转换成标准数据对象。
    3. 通过 on_xxx 回调把结果发布到事件总线，供 OMS、UI、策略消费。

    设计约束：
    1. 方法应尽量非阻塞，避免卡住事件线程和界面线程。
    2. 回调出去的数据对象应视为只读快照，后续不要原地修改。
    """

    # 网关默认名称（未显式指定时使用）。
    default_name: str = ""

    # connect() 所需的默认配置字段。
    default_setting: dict[str, str | int | float | bool] = {}

    # 当前网关支持的交易所列表。
    exchanges: list[Exchange] = []

    def __init__(self, event_engine: EventEngine, gateway_name: str) -> None:
        """
        保存事件引擎和网关实例名。

        同一网关类可开多个实例（例如不同账号），用 gateway_name 区分。
        """
        self.event_engine: EventEngine = event_engine
        self.gateway_name: str = gateway_name

    def on_event(self, type: str, data: object = None) -> None:
        """
        向事件引擎推送事件。

        网关所有业务回报最终都走这条通道进入系统。
        """
        event: Event = Event(type, data)
        self.event_engine.put(event)

    def on_tick(self, tick: TickData) -> None:
        """
        推送 Tick 行情回报。

        同时推送：
        1. 全局通道 `EVENT_TICK`（全市场监听）
        2. 合约通道 `EVENT_TICK + vt_symbol`（单合约监听）
        """
        # 广播给所有 Tick 监听者。
        self.on_event(EVENT_TICK, tick)
        # 精确推送给只关注某个 vt_symbol 的监听者。
        self.on_event(EVENT_TICK + tick.vt_symbol, tick)

    def on_trade(self, trade: TradeData) -> None:
        """
        推送成交回报。

        同时推送全局成交和按合约分组的成交事件。
        """
        self.on_event(EVENT_TRADE, trade)
        self.on_event(EVENT_TRADE + trade.vt_symbol, trade)

    def on_order(self, order: OrderData) -> None:
        """
        推送委托状态回报。

        订单更新是 OMS 的核心输入，因此除了全局通道，还要按 vt_orderid 分发。
        """
        self.on_event(EVENT_ORDER, order)
        self.on_event(EVENT_ORDER + order.vt_orderid, order)

    def on_position(self, position: PositionData) -> None:
        """
        推送持仓回报。

        用于驱动持仓监控、开平转换器和风控状态更新。
        """
        self.on_event(EVENT_POSITION, position)
        self.on_event(EVENT_POSITION + position.vt_symbol, position)

    def on_account(self, account: AccountData) -> None:
        """
        推送账户资金回报。

        同时推送全局账户通道和账户号通道，方便多账户场景分开监听。
        """
        self.on_event(EVENT_ACCOUNT, account)
        self.on_event(EVENT_ACCOUNT + account.vt_accountid, account)

    def on_quote(self, quote: QuoteData) -> None:
        """
        推送做市报价回报（可选能力）。
        """
        self.on_event(EVENT_QUOTE, quote)
        self.on_event(EVENT_QUOTE + quote.vt_symbol, quote)

    def on_log(self, log: LogData) -> None:
        """
        推送网关日志事件。

        用于连接状态提示、报错上报和运维排查。
        """
        self.on_event(EVENT_LOG, log)

    def on_contract(self, contract: ContractData) -> None:
        """
        推送合约基础信息。

        一般在连接后批量回报，供系统构建合约字典。
        """
        self.on_event(EVENT_CONTRACT, contract)

    def write_log(self, msg: str) -> None:
        """
        生成 LogData 并发送到日志事件通道。
        """
        log: LogData = LogData(msg=msg, gateway_name=self.gateway_name)
        self.on_log(log)

    @abstractmethod
    def connect(self, setting: dict) -> None:
        """
        建立连接并完成登录初始化。

        约定的业务动作：
        1. 建立交易/行情连接并鉴权。
        2. 连接成功后回补初始化数据（合约、资金、持仓、当日委托/成交）。
        3. 通过 on_xxx 把初始化结果推到系统，而不是只保存在网关内部。
        4. 初始化失败应写日志，便于用户判断是配置问题还是柜台问题。
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        关闭连接并释放后台资源（线程、会话、订阅）。
        """
        pass

    @abstractmethod
    def subscribe(self, req: SubscribeRequest) -> None:
        """
        订阅行情。

        收到订阅请求后，网关应尽快把后续行情通过 on_tick 持续推送。
        """
        pass

    @abstractmethod
    def send_order(self, req: OrderRequest) -> str:
        """
        发送新委托。

        约定：
        1. 本地先生成唯一 orderid，并构造 OrderData。
        2. 下单请求发送成功时，先推一笔 SUBMITTING 状态；失败则推 REJECTED。
        3. 返回 vt_orderid，供上层后续撤单/跟踪使用。
        """
        pass

    @abstractmethod
    def cancel_order(self, req: CancelRequest) -> None:
        """
        发送撤单请求。

        是否撤单成功由后续委托状态回报决定，不应在此直接假定成功。
        """
        pass

    def send_quote(self, req: QuoteRequest) -> str:
        """
        发送双边报价请求（可选能力，默认空实现）。

        语义与 send_order 类似：返回 vt_quoteid，并通过 on_quote 回报状态。
        不支持报价的网关可保持默认实现。
        """
        return ""

    def cancel_quote(self, req: CancelRequest) -> None:
        """
        发送报价撤销请求（可选能力）。
        """
        return

    @abstractmethod
    def query_account(self) -> None:
        """
        主动查询账户资金并通过 on_account 回报。
        """
        pass

    @abstractmethod
    def query_position(self) -> None:
        """
        主动查询持仓并通过 on_position 回报。
        """
        pass

    def query_history(self, req: HistoryRequest) -> list[BarData]:
        """
        查询历史K线（可选能力）。

        不支持历史查询的网关返回空列表。
        """
        return []

    def get_default_setting(self) -> dict[str, str | int | float | bool]:
        """
        返回连接参数模板，用于前端生成连接配置表单。
        """
        return self.default_setting
