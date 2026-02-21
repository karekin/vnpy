import smtplib
import os
import traceback
from abc import ABC, abstractmethod
from email.message import EmailMessage
from queue import Empty, Queue
from threading import Thread
from typing import TypeVar
from collections.abc import Callable

from vnpy.event import Event, EventEngine
from .app import BaseApp
from .event import (
    EVENT_TICK,
    EVENT_ORDER,
    EVENT_TRADE,
    EVENT_POSITION,
    EVENT_ACCOUNT,
    EVENT_CONTRACT,
    EVENT_LOG,
    EVENT_QUOTE
)
from .gateway import BaseGateway
from .object import (
    CancelRequest,
    LogData,
    OrderRequest,
    QuoteData,
    QuoteRequest,
    SubscribeRequest,
    HistoryRequest,
    OrderData,
    BarData,
    TickData,
    TradeData,
    PositionData,
    AccountData,
    ContractData,
    Exchange
)
from .setting import SETTINGS
from .utility import TRADER_DIR
from .converter import OffsetConverter
from .logger import logger, DEBUG, INFO, WARNING, ERROR, CRITICAL
from .locale import _


EngineType = TypeVar("EngineType", bound="BaseEngine")


class BaseEngine(ABC):
    """
    `BaseEngine` 是功能引擎抽象基类，定义了 vn.py 子引擎统一生命周期接口。
    
    职责：
    1. 统一持有 `main_engine` 与 `event_engine` 引用。
    2. 为各业务引擎提供统一命名和注册约定。
    3. 定义 `close()` 资源释放钩子，约束子类清理行为。
    
    协作：
    1. 与 `EventEngine` 协同处理异步事件。
    2. 与 `Gateway`、`AppEngine`、UI 模块共同构成交易运行时。
    """

    @abstractmethod
    def __init__(
        self,
        main_engine: "MainEngine",
        event_engine: EventEngine,
        engine_name: str,
    ) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        实现要求：
        1. 该方法为抽象接口，需由子类提供具体实现。
        2. 子类实现应遵循线程安全和非阻塞约束。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `main_engine` (`'MainEngine'`)：输入参数，用于控制该方法的处理行为。
        2. `event_engine` (`EventEngine`)：输入参数，用于控制该方法的处理行为。
        3. `engine_name` (`str`)：引擎名称，用于定位目标引擎实例。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.main_engine: MainEngine = main_engine
        self.event_engine: EventEngine = event_engine
        self.engine_name: str = engine_name

    def close(self) -> None:
        """
        关闭连接与资源，并执行必要清理。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        return


class MainEngine:
    """
    `MainEngine` 是交易内核入口，负责网关、应用、子引擎的装配与统一调度。
    
    职责：
    1. 管理网关连接、行情订阅、下单撤单等核心交易入口。
    2. 托管 OMS、日志、邮件等功能引擎并向外透传能力。
    3. 维护全局交易所列表和应用注册信息。
    
    协作：
    1. 与 `EventEngine` 协同处理异步事件。
    2. 与 `Gateway`、`AppEngine`、UI 模块共同构成交易运行时。
    """

    def __init__(self, event_engine: EventEngine | None = None) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `event_engine` (`EventEngine | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if event_engine:
            self.event_engine: EventEngine = event_engine
        else:
            self.event_engine = EventEngine()
        self.event_engine.start()

        # 维护系统内所有已注册对象的容器。
        self.gateways: dict[str, BaseGateway] = {}
        self.engines: dict[str, BaseEngine] = {}
        self.apps: dict[str, BaseApp] = {}
        self.exchanges: list[Exchange] = []

        os.chdir(TRADER_DIR)    # 切换到交易工作目录，统一相对路径行为。
        self.init_engines()     # 初始化内置引擎（日志、OMS、邮件）。

    def add_engine(self, engine_class: type[EngineType]) -> EngineType:
        """
        新增 `engine` 相关对象或配置项。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `engine_class` (`type[EngineType]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `EngineType`：返回该方法计算或查询得到的结果。
        """
        engine: EngineType = engine_class(self, self.event_engine)      # type: ignore
        self.engines[engine.engine_name] = engine
        return engine

    def add_gateway(self, gateway_class: type[BaseGateway], gateway_name: str = "") -> BaseGateway:
        """
        新增 `gateway` 相关对象或配置项。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `gateway_class` (`type[BaseGateway]`)：输入参数，用于控制该方法的处理行为。
        2. `gateway_name` (`str`)，默认值 `''`：网关名称，用于定位目标网关实例。
        
        返回：
        1. `BaseGateway`：返回该方法计算或查询得到的结果。
        """
        # 未传入网关名时使用网关类默认名称。
        if not gateway_name:
            gateway_name = gateway_class.default_name

        gateway: BaseGateway = gateway_class(self.event_engine, gateway_name)
        self.gateways[gateway_name] = gateway

        # 汇总该网关支持的交易所列表，供上层界面/策略查询。
        for exchange in gateway.exchanges:
            if exchange not in self.exchanges:
                self.exchanges.append(exchange)

        return gateway

    def add_app(self, app_class: type[BaseApp]) -> BaseEngine:
        """
        新增 `app` 相关对象或配置项。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `app_class` (`type[BaseApp]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `BaseEngine`：返回该方法计算或查询得到的结果。
        """
        app: BaseApp = app_class()
        self.apps[app.app_name] = app

        engine: BaseEngine = self.add_engine(app.engine_class)
        return engine

    def init_engines(self) -> None:
        """
        执行 `init_engines` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.add_engine(LogEngine)

        oms_engine: OmsEngine = self.add_engine(OmsEngine)
        # 将 OMS 查询与转换能力绑定到 MainEngine，形成统一调用入口。
        self.get_tick: Callable[[str], TickData | None] = oms_engine.get_tick
        self.get_order: Callable[[str], OrderData | None] = oms_engine.get_order
        self.get_trade: Callable[[str], TradeData | None] = oms_engine.get_trade
        self.get_position: Callable[[str], PositionData | None] = oms_engine.get_position
        self.get_account: Callable[[str], AccountData | None] = oms_engine.get_account
        self.get_contract: Callable[[str], ContractData | None] = oms_engine.get_contract
        self.get_quote: Callable[[str], QuoteData | None] = oms_engine.get_quote
        self.get_all_ticks: Callable[[], list[TickData]] = oms_engine.get_all_ticks
        self.get_all_orders: Callable[[], list[OrderData]] = oms_engine.get_all_orders
        self.get_all_trades: Callable[[], list[TradeData]] = oms_engine.get_all_trades
        self.get_all_positions: Callable[[], list[PositionData]] = oms_engine.get_all_positions
        self.get_all_accounts: Callable[[], list[AccountData]] = oms_engine.get_all_accounts
        self.get_all_contracts: Callable[[], list[ContractData]] = oms_engine.get_all_contracts
        self.get_all_quotes: Callable[[], list[QuoteData]] = oms_engine.get_all_quotes
        self.get_all_active_orders: Callable[[], list[OrderData]] = oms_engine.get_all_active_orders
        self.get_all_active_quotes: Callable[[], list[QuoteData]] = oms_engine.get_all_active_quotes
        self.update_order_request: Callable[[OrderRequest, str, str], None] = oms_engine.update_order_request
        self.convert_order_request: Callable[[OrderRequest, str, bool, bool], list[OrderRequest]] = oms_engine.convert_order_request
        self.get_converter: Callable[[str], OffsetConverter | None] = oms_engine.get_converter

        email_engine: EmailEngine = self.add_engine(EmailEngine)
        # 暴露邮件发送接口。
        self.send_email: Callable[[str, str, str | None], None] = email_engine.send_email

    def write_log(self, msg: str, source: str = "MainEngine") -> None:
        """
        执行 `write_log` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `msg` (`str`)：日志或提示消息文本。
        2. `source` (`str`)，默认值 `'MainEngine'`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        log: LogData = LogData(msg=msg, gateway_name=source)
        event: Event = Event(EVENT_LOG, log)
        self.event_engine.put(event)

    def get_gateway(self, gateway_name: str) -> BaseGateway | None:
        """
        获取 `gateway` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `BaseGateway | None`：返回该方法计算或查询得到的结果。
        """
        gateway: BaseGateway | None = self.gateways.get(gateway_name, None)
        if not gateway:
            self.write_log(_("找不到底层接口：{}").format(gateway_name))
        return gateway

    def get_engine(self, engine_name: str) -> BaseEngine | None:
        """
        获取 `engine` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `engine_name` (`str`)：引擎名称，用于定位目标引擎实例。
        
        返回：
        1. `BaseEngine | None`：返回该方法计算或查询得到的结果。
        """
        engine: BaseEngine | None = self.engines.get(engine_name, None)
        if not engine:
            self.write_log(_("找不到引擎：{}").format(engine_name))
        return engine

    def get_default_setting(self, gateway_name: str) -> dict[str, str | bool | int | float] | None:
        """
        获取 `default_setting` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `dict[str, str | bool | int | float] | None`：返回键值映射结果。
        """
        gateway: BaseGateway | None = self.get_gateway(gateway_name)
        if gateway:
            return gateway.get_default_setting()
        return None

    def get_all_gateway_names(self) -> list[str]:
        """
        批量获取 `gateway_names` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[str]`：返回按约定组织的数据列表。
        """
        return list(self.gateways.keys())

    def get_all_apps(self) -> list[BaseApp]:
        """
        批量获取 `apps` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[BaseApp]`：返回按约定组织的数据列表。
        """
        return list(self.apps.values())

    def get_all_exchanges(self) -> list[Exchange]:
        """
        批量获取 `exchanges` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[Exchange]`：返回按约定组织的数据列表。
        """
        return self.exchanges

    def connect(self, setting: dict, gateway_name: str) -> None:
        """
        建立与外部系统的连接并准备可用状态。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. `setting` (`dict`)：配置字典或配置对象。
        2. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        gateway: BaseGateway | None = self.get_gateway(gateway_name)
        if gateway:
            self.write_log(_("连接登录 -> {}").format(gateway_name))

            gateway.connect(setting)

    def subscribe(self, req: SubscribeRequest, gateway_name: str) -> None:
        """
        执行 `subscribe` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `req` (`SubscribeRequest`)：请求对象，封装本次操作所需参数。
        2. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        gateway: BaseGateway | None = self.get_gateway(gateway_name)
        if gateway:
            self.write_log(_("订阅行情 -> {}：{}").format(gateway_name, req))

            gateway.subscribe(req)

    def send_order(self, req: OrderRequest, gateway_name: str) -> str:
        """
        发送 `order` 请求并处理返回结果。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. `req` (`OrderRequest`)：请求对象，封装本次操作所需参数。
        2. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `str`：返回委托标识字符串。
        """
        gateway: BaseGateway | None = self.get_gateway(gateway_name)
        if gateway:
            self.write_log(_("委托下单 -> {}：{}").format(gateway_name, req))

            return gateway.send_order(req)
        else:
            return ""

    def cancel_order(self, req: CancelRequest, gateway_name: str) -> None:
        """
        执行 `order` 撤销或取消操作。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. `req` (`CancelRequest`)：请求对象，封装本次操作所需参数。
        2. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        gateway: BaseGateway | None = self.get_gateway(gateway_name)
        if gateway:
            self.write_log(_("委托撤单 -> {}：{}").format(gateway_name, req))

            gateway.cancel_order(req)

    def send_quote(self, req: QuoteRequest, gateway_name: str) -> str:
        """
        发送 `quote` 请求并处理返回结果。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. `req` (`QuoteRequest`)：请求对象，封装本次操作所需参数。
        2. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `str`：返回报价标识字符串。
        """
        gateway: BaseGateway | None = self.get_gateway(gateway_name)
        if gateway:
            self.write_log(_("报价下单 -> {}：{}").format(gateway_name, req))

            return gateway.send_quote(req)
        else:
            return ""

    def cancel_quote(self, req: CancelRequest, gateway_name: str) -> None:
        """
        执行 `quote` 撤销或取消操作。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. `req` (`CancelRequest`)：请求对象，封装本次操作所需参数。
        2. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        gateway: BaseGateway | None = self.get_gateway(gateway_name)
        if gateway:
            self.write_log(_("报价撤单 -> {}：{}").format(gateway_name, req))

            gateway.cancel_quote(req)

    def query_history(self, req: HistoryRequest, gateway_name: str) -> list[BarData]:
        """
        查询 `history` 相关信息。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `req` (`HistoryRequest`)：请求对象，封装本次操作所需参数。
        2. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `list[BarData]`：返回按约定组织的数据列表。
        """
        gateway: BaseGateway | None = self.get_gateway(gateway_name)
        if gateway:
            self.write_log(_("查询K线 -> {}：{}").format(gateway_name, req))

            return gateway.query_history(req)
        else:
            return []

    def close(self) -> None:
        """
        关闭连接与资源，并执行必要清理。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        # 先停止事件引擎，避免关闭过程中仍有事件进入。
        self.event_engine.stop()

        for engine in self.engines.values():
            engine.close()

        for gateway in self.gateways.values():
            gateway.close()


class LogEngine(BaseEngine):
    """
    `LogEngine` 是系统日志处理引擎，负责消费日志事件并输出到日志后端。
    
    职责：
    1. 监听 `EVENT_LOG` 事件并执行统一格式化输出。
    2. 根据配置控制日志开关与级别映射。
    3. 按网关来源绑定上下文，便于定位问题。
    
    协作：
    1. 与 `EventEngine` 协同处理异步事件。
    2. 与 `Gateway`、`AppEngine`、UI 模块共同构成交易运行时。
    """

    level_map: dict[int, str] = {
        DEBUG: "DEBUG",
        INFO: "INFO",
        WARNING: "WARNING",
        ERROR: "ERROR",
        CRITICAL: "CRITICAL",
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
        super().__init__(main_engine, event_engine, "log")

        # 读取日志开关配置，关闭时直接忽略日志事件。
        self.active = SETTINGS["log.active"]

        self.register_log(EVENT_LOG)

    def process_log_event(self, event: Event) -> None:
        """
        处理 `log_event` 相关业务逻辑。
        
        用途说明：
        1. 作为事件驱动入口，消费输入并执行核心处理。
        2. 按需更新缓存、发布事件或触发后续流程。
        
        参数：
        1. `event` (`Event`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if not self.active:
            return

        log: LogData = event.data
        level: str | int = self.level_map.get(log.level, log.level)
        logger.bind(gateway_name=log.gateway_name).log(level, log.msg)

    def register_log(self, event_type: str) -> None:
        """
        执行 `register_log` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `event_type` (`str`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.event_engine.register(event_type, self.process_log_event)


class OmsEngine(BaseEngine):
    """
    `OmsEngine` 是订单管理引擎，维护交易状态内存快照与活动订单集合。
    
    职责：
    1. 缓存 tick/order/trade/position/account/contract/quote 最新数据。
    2. 维护活动委托与活动报价集合，供 UI/策略快速查询。
    3. 管理 `OffsetConverter`，支持平今平昨与锁仓转换。
    
    协作：
    1. 与 `EventEngine` 协同处理异步事件。
    2. 与 `Gateway`、`AppEngine`、UI 模块共同构成交易运行时。
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
        super().__init__(main_engine, event_engine, "oms")

        # 全量最新快照：key 为各类对象的唯一 vt_* 标识。
        self.ticks: dict[str, TickData] = {}
        self.orders: dict[str, OrderData] = {}
        self.trades: dict[str, TradeData] = {}
        self.positions: dict[str, PositionData] = {}
        self.accounts: dict[str, AccountData] = {}
        self.contracts: dict[str, ContractData] = {}
        self.quotes: dict[str, QuoteData] = {}

        # 活动中的委托/报价子集，便于界面和策略快速获取。
        self.active_orders: dict[str, OrderData] = {}
        self.active_quotes: dict[str, QuoteData] = {}

        # 每个 gateway 各维护一个仓位转换器实例。
        self.offset_converters: dict[str, OffsetConverter] = {}

        self.register_event()

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
        self.event_engine.register(EVENT_TICK, self.process_tick_event)
        self.event_engine.register(EVENT_ORDER, self.process_order_event)
        self.event_engine.register(EVENT_TRADE, self.process_trade_event)
        self.event_engine.register(EVENT_POSITION, self.process_position_event)
        self.event_engine.register(EVENT_ACCOUNT, self.process_account_event)
        self.event_engine.register(EVENT_CONTRACT, self.process_contract_event)
        self.event_engine.register(EVENT_QUOTE, self.process_quote_event)

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
        self.ticks[tick.vt_symbol] = tick

    def process_order_event(self, event: Event) -> None:
        """
        处理 `order_event` 相关业务逻辑。
        
        用途说明：
        1. 作为事件驱动入口，消费输入并执行核心处理。
        2. 按需更新缓存、发布事件或触发后续流程。
        
        参数：
        1. `event` (`Event`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        order: OrderData = event.data
        self.orders[order.vt_orderid] = order

        # 若委托仍处于活动状态（未完全成交/撤销），放入活动委托集合。
        if order.is_active():
            self.active_orders[order.vt_orderid] = order
        # 否则从活动集合移除，保证集合只保留可操作委托。
        elif order.vt_orderid in self.active_orders:
            self.active_orders.pop(order.vt_orderid)

        # 同步到对应网关的转换器，用于后续开平计算。
        converter: OffsetConverter | None = self.offset_converters.get(order.gateway_name, None)
        if converter:
            converter.update_order(order)

    def process_trade_event(self, event: Event) -> None:
        """
        处理 `trade_event` 相关业务逻辑。
        
        用途说明：
        1. 作为事件驱动入口，消费输入并执行核心处理。
        2. 按需更新缓存、发布事件或触发后续流程。
        
        参数：
        1. `event` (`Event`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        trade: TradeData = event.data
        self.trades[trade.vt_tradeid] = trade

        # 成交会直接影响可平仓量，需实时更新转换器状态。
        converter: OffsetConverter | None = self.offset_converters.get(trade.gateway_name, None)
        if converter:
            converter.update_trade(trade)

    def process_position_event(self, event: Event) -> None:
        """
        处理 `position_event` 相关业务逻辑。
        
        用途说明：
        1. 作为事件驱动入口，消费输入并执行核心处理。
        2. 按需更新缓存、发布事件或触发后续流程。
        
        参数：
        1. `event` (`Event`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        position: PositionData = event.data
        self.positions[position.vt_positionid] = position

        # 持仓变化也会影响开平规则与冻结数量。
        converter: OffsetConverter | None = self.offset_converters.get(position.gateway_name, None)
        if converter:
            converter.update_position(position)

    def process_account_event(self, event: Event) -> None:
        """
        处理 `account_event` 相关业务逻辑。
        
        用途说明：
        1. 作为事件驱动入口，消费输入并执行核心处理。
        2. 按需更新缓存、发布事件或触发后续流程。
        
        参数：
        1. `event` (`Event`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        account: AccountData = event.data
        self.accounts[account.vt_accountid] = account

    def process_contract_event(self, event: Event) -> None:
        """
        处理 `contract_event` 相关业务逻辑。
        
        用途说明：
        1. 作为事件驱动入口，消费输入并执行核心处理。
        2. 按需更新缓存、发布事件或触发后续流程。
        
        参数：
        1. `event` (`Event`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        contract: ContractData = event.data
        self.contracts[contract.vt_symbol] = contract

        # 每个网关只初始化一次转换器实例。
        if contract.gateway_name not in self.offset_converters:
            self.offset_converters[contract.gateway_name] = OffsetConverter(self)

    def process_quote_event(self, event: Event) -> None:
        """
        处理 `quote_event` 相关业务逻辑。
        
        用途说明：
        1. 作为事件驱动入口，消费输入并执行核心处理。
        2. 按需更新缓存、发布事件或触发后续流程。
        
        参数：
        1. `event` (`Event`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        quote: QuoteData = event.data
        self.quotes[quote.vt_quoteid] = quote

        # 活动报价放入可跟踪集合，便于集中管理与撤销。
        if quote.is_active():
            self.active_quotes[quote.vt_quoteid] = quote
        # 非活动状态则从集合移除。
        elif quote.vt_quoteid in self.active_quotes:
            self.active_quotes.pop(quote.vt_quoteid)

    def get_tick(self, vt_symbol: str) -> TickData | None:
        """
        获取 `tick` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `vt_symbol` (`str`)：标准合约代码（交易所.代码）。
        
        返回：
        1. `TickData | None`：返回该方法计算或查询得到的结果。
        """
        return self.ticks.get(vt_symbol, None)

    def get_order(self, vt_orderid: str) -> OrderData | None:
        """
        获取 `order` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `vt_orderid` (`str`)：标准委托编号。
        
        返回：
        1. `OrderData | None`：返回该方法计算或查询得到的结果。
        """
        return self.orders.get(vt_orderid, None)

    def get_trade(self, vt_tradeid: str) -> TradeData | None:
        """
        获取 `trade` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `vt_tradeid` (`str`)：标准成交编号。
        
        返回：
        1. `TradeData | None`：返回该方法计算或查询得到的结果。
        """
        return self.trades.get(vt_tradeid, None)

    def get_position(self, vt_positionid: str) -> PositionData | None:
        """
        获取 `position` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `vt_positionid` (`str`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `PositionData | None`：返回该方法计算或查询得到的结果。
        """
        return self.positions.get(vt_positionid, None)

    def get_account(self, vt_accountid: str) -> AccountData | None:
        """
        获取 `account` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `vt_accountid` (`str`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `AccountData | None`：返回该方法计算或查询得到的结果。
        """
        return self.accounts.get(vt_accountid, None)

    def get_contract(self, vt_symbol: str) -> ContractData | None:
        """
        获取 `contract` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `vt_symbol` (`str`)：标准合约代码（交易所.代码）。
        
        返回：
        1. `ContractData | None`：返回该方法计算或查询得到的结果。
        """
        return self.contracts.get(vt_symbol, None)

    def get_quote(self, vt_quoteid: str) -> QuoteData | None:
        """
        获取 `quote` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `vt_quoteid` (`str`)：标准报价编号。
        
        返回：
        1. `QuoteData | None`：返回该方法计算或查询得到的结果。
        """
        return self.quotes.get(vt_quoteid, None)

    def get_all_ticks(self) -> list[TickData]:
        """
        批量获取 `ticks` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[TickData]`：返回按约定组织的数据列表。
        """
        return list(self.ticks.values())

    def get_all_orders(self) -> list[OrderData]:
        """
        批量获取 `orders` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[OrderData]`：返回按约定组织的数据列表。
        """
        return list(self.orders.values())

    def get_all_trades(self) -> list[TradeData]:
        """
        批量获取 `trades` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[TradeData]`：返回按约定组织的数据列表。
        """
        return list(self.trades.values())

    def get_all_positions(self) -> list[PositionData]:
        """
        批量获取 `positions` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[PositionData]`：返回按约定组织的数据列表。
        """
        return list(self.positions.values())

    def get_all_accounts(self) -> list[AccountData]:
        """
        批量获取 `accounts` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[AccountData]`：返回按约定组织的数据列表。
        """
        return list(self.accounts.values())

    def get_all_contracts(self) -> list[ContractData]:
        """
        批量获取 `contracts` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[ContractData]`：返回按约定组织的数据列表。
        """
        return list(self.contracts.values())

    def get_all_quotes(self) -> list[QuoteData]:
        """
        批量获取 `quotes` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[QuoteData]`：返回按约定组织的数据列表。
        """
        return list(self.quotes.values())

    def get_all_active_orders(self) -> list[OrderData]:
        """
        批量获取 `active_orders` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[OrderData]`：返回按约定组织的数据列表。
        """
        return list(self.active_orders.values())

    def get_all_active_quotes(self) -> list[QuoteData]:
        """
        批量获取 `active_quotes` 相关数据集合。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `list[QuoteData]`：返回按约定组织的数据列表。
        """
        return list(self.active_quotes.values())

    def update_order_request(self, req: OrderRequest, vt_orderid: str, gateway_name: str) -> None:
        """
        更新 `order_request` 相关状态与缓存。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `req` (`OrderRequest`)：请求对象，封装本次操作所需参数。
        2. `vt_orderid` (`str`)：标准委托编号。
        3. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        converter: OffsetConverter | None = self.offset_converters.get(gateway_name, None)
        if converter:
            converter.update_order_request(req, vt_orderid)

    def convert_order_request(
        self,
        req: OrderRequest,
        gateway_name: str,
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
        2. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        3. `lock` (`bool`)：输入参数，用于控制该方法的处理行为。
        4. `net` (`bool`)，默认值 `False`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `list[OrderRequest]`：返回按约定组织的数据列表。
        """
        converter: OffsetConverter | None = self.offset_converters.get(gateway_name, None)
        if not converter:
            return [req]

        reqs: list[OrderRequest] = converter.convert_order_request(req, lock, net)
        return reqs

    def get_converter(self, gateway_name: str) -> OffsetConverter | None:
        """
        获取 `converter` 相关对象或计算结果。
        
        用途说明：
        1. 从当前对象缓存或下游组件中读取目标数据。
        2. 默认应保持无副作用，便于上层安全重复调用。
        
        参数：
        1. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `OffsetConverter | None`：返回该方法计算或查询得到的结果。
        """
        return self.offset_converters.get(gateway_name, None)


class EmailEngine(BaseEngine):
    """
    `EmailEngine` 是异步通知引擎，用后台线程发送邮件告警。
    
    职责：
    1. 通过队列解耦邮件发送与主线程业务。
    2. 按配置建立 SMTP SSL 连接并发送消息。
    3. 捕获发送异常并回写系统日志。
    
    协作：
    1. 与 `EventEngine` 协同处理异步事件。
    2. 与 `Gateway`、`AppEngine`、UI 模块共同构成交易运行时。
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
        super().__init__(main_engine, event_engine, "email")

        # 后台线程循环读取队列中的 EmailMessage 并发送。
        self.thread: Thread = Thread(target=self.run)
        self.queue: Queue = Queue()
        self.active: bool = False

    def send_email(self, subject: str, content: str, receiver: str | None = None) -> None:
        """
        发送 `email` 请求并处理返回结果。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. `subject` (`str`)：邮件主题或通知标题。
        2. `content` (`str`)：正文内容。
        3. `receiver` (`str | None`)，默认值 `None`：接收方标识（如邮箱地址）。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        # 首次发送时启动邮件线程。
        if not self.active:
            self.start()

        # 未指定收件人时使用全局默认配置。
        if not receiver:
            receiver = SETTINGS["email.receiver"]

        msg: EmailMessage = EmailMessage()
        msg["From"] = SETTINGS["email.sender"]
        msg["To"] = receiver
        msg["Subject"] = subject
        msg.set_content(content)

        self.queue.put(msg)

    def run(self) -> None:
        """
        执行组件主循环或核心处理流程。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        server: str = SETTINGS["email.server"]
        port: int = SETTINGS["email.port"]
        username: str = SETTINGS["email.username"]
        password: str = SETTINGS["email.password"]

        while self.active:
            try:
                msg: EmailMessage = self.queue.get(block=True, timeout=1)

                try:
                    with smtplib.SMTP_SSL(server, port) as smtp:
                        smtp.login(username, password)
                        smtp.send_message(msg)
                        smtp.close()
                except Exception:
                    # 发送异常写入日志，不抛出以保证线程持续运行。
                    log_msg: str = _("邮件发送失败: {}").format(traceback.format_exc())
                    self.main_engine.write_log(log_msg, "EmailEngine")
            except Empty:
                # 队列暂时无数据属于正常情况。
                pass

    def start(self) -> None:
        """
        启动当前组件管理的流程、任务或后台线程。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.active = True
        self.thread.start()

    def close(self) -> None:
        """
        关闭连接与资源，并执行必要清理。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if not self.active:
            return

        self.active = False
        self.thread.join()
