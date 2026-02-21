"""
vn.py 交易域核心数据对象定义。

这个文件里的 dataclass 是网关、主引擎、OMS、UI、回测之间的通用数据协议：
1. 网关把外部回报转换为这些对象并投递事件；
2. OMS 和界面直接消费这些对象更新状态；
3. 请求对象（*Request）用于统一封装下行调用参数。
"""

from dataclasses import dataclass, field
from datetime import datetime as Datetime

from .constant import Direction, Exchange, Interval, Offset, Status, Product, OptionType, OrderType


INFO: int = 20


ACTIVE_STATUSES = set([Status.SUBMITTING, Status.NOTTRADED, Status.PARTTRADED])


@dataclass
class BaseData:
    """
    所有交易数据对象的基类。

    `gateway_name` 标记数据来源（哪个网关实例），
    `extra` 预留给插件或网关扩展字段，避免改动核心结构。
    """

    gateway_name: str

    extra: dict | None = field(default=None, init=False)


@dataclass
class TickData(BaseData):
    """
    Tick 行情快照。

    对应实盘中的“最新一跳行情”，包含：
    1. 最新成交价/量
    2. 五档盘口
    3. 当日统计字段（成交量、持仓量、涨跌停等）
    """

    symbol: str
    exchange: Exchange
    datetime: Datetime

    name: str = ""
    volume: float = 0
    turnover: float = 0
    open_interest: float = 0
    last_price: float = 0
    last_volume: float = 0
    limit_up: float = 0
    limit_down: float = 0

    open_price: float = 0
    high_price: float = 0
    low_price: float = 0
    pre_close: float = 0

    bid_price_1: float = 0
    bid_price_2: float = 0
    bid_price_3: float = 0
    bid_price_4: float = 0
    bid_price_5: float = 0

    ask_price_1: float = 0
    ask_price_2: float = 0
    ask_price_3: float = 0
    ask_price_4: float = 0
    ask_price_5: float = 0

    bid_volume_1: float = 0
    bid_volume_2: float = 0
    bid_volume_3: float = 0
    bid_volume_4: float = 0
    bid_volume_5: float = 0

    ask_volume_1: float = 0
    ask_volume_2: float = 0
    ask_volume_3: float = 0
    ask_volume_4: float = 0
    ask_volume_5: float = 0

    localtime: Datetime | None = None

    def __post_init__(self) -> None:
        """
        生成全局唯一合约键 `vt_symbol`（`symbol.exchange`）。
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"


@dataclass
class BarData(BaseData):
    """
    K 线数据（按固定周期聚合）。

    常用于：
    1. 回测驱动
    2. 指标计算
    3. 图表展示
    """

    symbol: str
    exchange: Exchange
    datetime: Datetime

    interval: Interval | None = None
    volume: float = 0
    turnover: float = 0
    open_interest: float = 0
    open_price: float = 0
    high_price: float = 0
    low_price: float = 0
    close_price: float = 0

    def __post_init__(self) -> None:
        """
        生成 `vt_symbol`，便于跨模块统一索引。
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"


@dataclass
class OrderData(BaseData):
    """
    委托状态快照。

    这是 OMS 最核心的对象之一，用于跟踪订单完整生命周期：
    SUBMITTING -> NOTTRADED/PARTTRADED -> ALLTRADED/CANCELLED/REJECTED。
    """

    symbol: str
    exchange: Exchange
    orderid: str

    type: OrderType = OrderType.LIMIT
    direction: Direction | None = None
    offset: Offset = Offset.NONE
    price: float = 0
    volume: float = 0
    traded: float = 0
    status: Status = Status.SUBMITTING
    datetime: Datetime | None = None
    reference: str = ""

    def __post_init__(self) -> None:
        """
        生成委托相关全局键：
        1. `vt_symbol`
        2. `vt_orderid`（`gateway_name.orderid`）
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"
        self.vt_orderid: str = f"{self.gateway_name}.{self.orderid}"

    def is_active(self) -> bool:
        """
        判断委托当前是否仍可成交/可撤。
        """
        return self.status in ACTIVE_STATUSES

    def create_cancel_request(self) -> "CancelRequest":
        """
        从当前委托生成对应的撤单请求对象。

        用于 UI/策略拿到 `OrderData` 后直接发起撤单。
        """
        req: CancelRequest = CancelRequest(
            orderid=self.orderid, symbol=self.symbol, exchange=self.exchange
        )
        return req


@dataclass
class TradeData(BaseData):
    """
    成交回报。

    一笔委托可对应多笔成交；该对象用于：
    1. 持仓更新
    2. 成本和盈亏计算
    3. 成交明细展示
    """

    symbol: str
    exchange: Exchange
    orderid: str
    tradeid: str
    direction: Direction | None = None

    offset: Offset = Offset.NONE
    price: float = 0
    volume: float = 0
    datetime: Datetime | None = None

    def __post_init__(self) -> None:
        """
        生成成交相关全局键：
        1. `vt_symbol`
        2. `vt_orderid`
        3. `vt_tradeid`
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"
        self.vt_orderid: str = f"{self.gateway_name}.{self.orderid}"
        self.vt_tradeid: str = f"{self.gateway_name}.{self.tradeid}"


@dataclass
class PositionData(BaseData):
    """
    单合约单方向持仓快照。

    包含可用量、冻结量、持仓成本、浮动盈亏等信息，
    是风控和开平转换（平今/平昨）计算的输入。
    """

    symbol: str
    exchange: Exchange
    direction: Direction

    volume: float = 0
    frozen: float = 0
    price: float = 0
    pnl: float = 0
    yd_volume: float = 0

    def __post_init__(self) -> None:
        """
        生成持仓唯一键 `vt_positionid`：
        `gateway_name.vt_symbol.direction`。
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"
        self.vt_positionid: str = f"{self.gateway_name}.{self.vt_symbol}.{self.direction.value}"


@dataclass
class AccountData(BaseData):
    """
    账户资金快照。

    重点字段：
    1. `balance`：账户总权益
    2. `frozen`：冻结资金
    3. `available`：可用资金（由两者计算）
    """

    accountid: str

    balance: float = 0
    frozen: float = 0

    def __post_init__(self) -> None:
        """
        计算可用资金并生成全局账户键 `vt_accountid`。
        """
        self.available: float = self.balance - self.frozen
        self.vt_accountid: str = f"{self.gateway_name}.{self.accountid}"


@dataclass
class LogData(BaseData):
    """
    日志事件载体。

    统一承载日志内容和级别，供日志引擎、日志面板和文件落盘复用。
    """

    msg: str
    level: int = INFO

    def __post_init__(self) -> None:
        """
        记录日志生成时间。
        """
        self.time: Datetime = Datetime.now()


@dataclass
class ContractData(BaseData):
    """
    合约静态信息。

    用于下单前校验与参数规范化，例如：
    1. 最小价格跳动（`pricetick`）
    2. 合约乘数（`size`）
    3. 最小/最大下单量
    4. 是否支持历史数据、止损单等能力标志
    """

    symbol: str
    exchange: Exchange
    name: str
    product: Product
    size: float
    pricetick: float

    min_volume: float = 1                   # minimum order volume
    max_volume: float | None = None         # maximum order volume
    stop_supported: bool = False            # whether server supports stop order
    net_position: bool = False              # whether gateway uses net position volume
    history_data: bool = False              # whether gateway provides bar history data

    option_strike: float | None = None
    option_underlying: str | None = None     # vt_symbol of underlying contract
    option_type: OptionType | None = None
    option_listed: Datetime | None = None
    option_expiry: Datetime | None = None
    option_portfolio: str | None = None
    option_index: str | None = None          # for identifying options with same strike price

    def __post_init__(self) -> None:
        """
        生成合约全局键 `vt_symbol`。
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"


@dataclass
class QuoteData(BaseData):
    """
    双边报价状态快照（做市场景）。

    同时包含 bid/ask 价格和数量，以及报价状态。
    """

    symbol: str
    exchange: Exchange
    quoteid: str

    bid_price: float = 0.0
    bid_volume: int = 0
    ask_price: float = 0.0
    ask_volume: int = 0
    bid_offset: Offset = Offset.NONE
    ask_offset: Offset = Offset.NONE
    status: Status = Status.SUBMITTING
    datetime: Datetime | None = None
    reference: str = ""

    def __post_init__(self) -> None:
        """
        生成报价相关全局键：
        1. `vt_symbol`
        2. `vt_quoteid`
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"
        self.vt_quoteid: str = f"{self.gateway_name}.{self.quoteid}"

    def is_active(self) -> bool:
        """
        判断报价是否仍处于活动状态。
        """
        return self.status in ACTIVE_STATUSES

    def create_cancel_request(self) -> "CancelRequest":
        """
        从当前报价生成撤销请求对象。
        """
        req: CancelRequest = CancelRequest(
            orderid=self.quoteid, symbol=self.symbol, exchange=self.exchange
        )
        return req


@dataclass
class SubscribeRequest:
    """
    行情订阅请求。

    用于告诉网关“订阅哪个合约的实时行情”。
    """

    symbol: str
    exchange: Exchange

    def __post_init__(self) -> None:
        """
        生成订阅目标键 `vt_symbol`。
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"


@dataclass
class OrderRequest:
    """
    标准化下单请求。

    这是策略/UI 下行调用网关的统一输入结构，
    屏蔽不同柜台接口在字段命名上的差异。
    """

    symbol: str
    exchange: Exchange
    direction: Direction
    type: OrderType
    volume: float
    price: float = 0
    offset: Offset = Offset.NONE
    reference: str = ""

    def __post_init__(self) -> None:
        """
        生成目标合约键 `vt_symbol`。
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"

    def create_order_data(self, orderid: str, gateway_name: str) -> OrderData:
        """
        把请求对象扩展成可流转的 `OrderData`。

        网关通常在分配本地 orderid 后调用该方法，生成首笔委托快照。
        """
        order: OrderData = OrderData(
            symbol=self.symbol,
            exchange=self.exchange,
            orderid=orderid,
            type=self.type,
            direction=self.direction,
            offset=self.offset,
            price=self.price,
            volume=self.volume,
            reference=self.reference,
            gateway_name=gateway_name,
        )
        return order


@dataclass
class CancelRequest:
    """
    撤单请求。

    关键是精确定位要撤的委托：`orderid + symbol + exchange`。
    """

    orderid: str
    symbol: str
    exchange: Exchange

    def __post_init__(self) -> None:
        """
        生成目标合约键 `vt_symbol`。
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"


@dataclass
class HistoryRequest:
    """
    历史数据查询请求。

    同时用于：
    1. 网关侧历史查询
    2. 数据库侧历史读取
    保证回测与图表模块的请求结构一致。
    """

    symbol: str
    exchange: Exchange
    start: Datetime
    end: Datetime | None = None
    interval: Interval | None = None

    def __post_init__(self) -> None:
        """
        生成查询目标键 `vt_symbol`。
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"


@dataclass
class QuoteRequest:
    """
    双边报价请求（做市）。

    同时携带 bid/ask 两侧参数，供支持 quote 的网关一次性下发。
    """

    symbol: str
    exchange: Exchange
    bid_price: float
    bid_volume: int
    ask_price: float
    ask_volume: int
    bid_offset: Offset = Offset.NONE
    ask_offset: Offset = Offset.NONE
    reference: str = ""

    def __post_init__(self) -> None:
        """
        生成目标合约键 `vt_symbol`。
        """
        self.vt_symbol: str = f"{self.symbol}.{self.exchange.value}"

    def create_quote_data(self, quoteid: str, gateway_name: str) -> QuoteData:
        """
        把报价请求扩展成 `QuoteData` 快照对象。

        网关在拿到本地 quoteid 后调用该方法，生成可投递的报价状态对象。
        """
        quote: QuoteData = QuoteData(
            symbol=self.symbol,
            exchange=self.exchange,
            quoteid=quoteid,
            bid_price=self.bid_price,
            bid_volume=self.bid_volume,
            ask_price=self.ask_price,
            ask_volume=self.ask_volume,
            bid_offset=self.bid_offset,
            ask_offset=self.ask_offset,
            reference=self.reference,
            gateway_name=gateway_name,
        )
        return quote
