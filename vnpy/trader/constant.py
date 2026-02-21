"""
General constant enums used in the trading platform.
"""

from enum import Enum

from .locale import _


class Direction(Enum):
    """
    交易方向枚举，表达买入/卖出、做多/做空等方向语义。
    
    职责：
    1. 避免在系统中散落魔法字符串，提升代码可读性与可维护性。
    2. 为对象序列化、UI 展示、策略判断提供统一常量来源。
    3. 约束参数输入范围，减少跨模块对接歧义。
    
    协作：
    1. 广泛用于 `OrderData/ContractData/Request` 等业务对象字段。
    2. 被网关适配层用于本地常量与交易柜台协议之间的映射。
    """
    LONG = _("多")
    SHORT = _("空")
    NET = _("净")


class Offset(Enum):
    """
    开平枚举，表达开仓、平仓、平今、平昨等交易意图。
    
    职责：
    1. 避免在系统中散落魔法字符串，提升代码可读性与可维护性。
    2. 为对象序列化、UI 展示、策略判断提供统一常量来源。
    3. 约束参数输入范围，减少跨模块对接歧义。
    
    协作：
    1. 广泛用于 `OrderData/ContractData/Request` 等业务对象字段。
    2. 被网关适配层用于本地常量与交易柜台协议之间的映射。
    """
    NONE = ""
    OPEN = _("开")
    CLOSE = _("平")
    CLOSETODAY = _("平今")
    CLOSEYESTERDAY = _("平昨")


class Status(Enum):
    """
    委托状态枚举，描述订单从提交到成交/撤销/拒绝的生命周期。
    
    职责：
    1. 避免在系统中散落魔法字符串，提升代码可读性与可维护性。
    2. 为对象序列化、UI 展示、策略判断提供统一常量来源。
    3. 约束参数输入范围，减少跨模块对接歧义。
    
    协作：
    1. 广泛用于 `OrderData/ContractData/Request` 等业务对象字段。
    2. 被网关适配层用于本地常量与交易柜台协议之间的映射。
    """
    SUBMITTING = _("提交中")
    NOTTRADED = _("未成交")
    PARTTRADED = _("部分成交")
    ALLTRADED = _("全部成交")
    CANCELLED = _("已撤销")
    REJECTED = _("拒单")


class Product(Enum):
    """
    合约品种枚举，用于区分股票、期货、期权、基金、数字货币等资产类型。
    
    职责：
    1. 避免在系统中散落魔法字符串，提升代码可读性与可维护性。
    2. 为对象序列化、UI 展示、策略判断提供统一常量来源。
    3. 约束参数输入范围，减少跨模块对接歧义。
    
    协作：
    1. 广泛用于 `OrderData/ContractData/Request` 等业务对象字段。
    2. 被网关适配层用于本地常量与交易柜台协议之间的映射。
    """
    EQUITY = _("股票")
    FUTURES = _("期货")
    OPTION = _("期权")
    INDEX = _("指数")
    FOREX = _("外汇")
    SPOT = _("现货")
    ETF = "ETF"
    BOND = _("债券")
    WARRANT = _("权证")
    SPREAD = _("价差")
    FUND = _("基金")
    CFD = "CFD"
    SWAP = _("互换")


class OrderType(Enum):
    """
    委托类型枚举，描述限价、市价、FAK/FOK 等撮合方式。
    
    职责：
    1. 避免在系统中散落魔法字符串，提升代码可读性与可维护性。
    2. 为对象序列化、UI 展示、策略判断提供统一常量来源。
    3. 约束参数输入范围，减少跨模块对接歧义。
    
    协作：
    1. 广泛用于 `OrderData/ContractData/Request` 等业务对象字段。
    2. 被网关适配层用于本地常量与交易柜台协议之间的映射。
    """
    LIMIT = _("限价")
    MARKET = _("市价")
    STOP = "STOP"
    FAK = "FAK"
    FOK = "FOK"
    RFQ = _("询价")
    ETF = "ETF"


class OptionType(Enum):
    """
    期权类型枚举，区分看涨期权与看跌期权。
    
    职责：
    1. 避免在系统中散落魔法字符串，提升代码可读性与可维护性。
    2. 为对象序列化、UI 展示、策略判断提供统一常量来源。
    3. 约束参数输入范围，减少跨模块对接歧义。
    
    协作：
    1. 广泛用于 `OrderData/ContractData/Request` 等业务对象字段。
    2. 被网关适配层用于本地常量与交易柜台协议之间的映射。
    """
    CALL = _("看涨期权")
    PUT = _("看跌期权")


class Exchange(Enum):
    """
    交易所枚举，统一系统内部对各交易所代码的表达。
    
    职责：
    1. 避免在系统中散落魔法字符串，提升代码可读性与可维护性。
    2. 为对象序列化、UI 展示、策略判断提供统一常量来源。
    3. 约束参数输入范围，减少跨模块对接歧义。
    
    协作：
    1. 广泛用于 `OrderData/ContractData/Request` 等业务对象字段。
    2. 被网关适配层用于本地常量与交易柜台协议之间的映射。
    """
    # Chinese
    CFFEX = "CFFEX"         # China Financial Futures Exchange
    SHFE = "SHFE"           # Shanghai Futures Exchange
    CZCE = "CZCE"           # Zhengzhou Commodity Exchange
    DCE = "DCE"             # Dalian Commodity Exchange
    INE = "INE"             # Shanghai International Energy Exchange
    GFEX = "GFEX"           # Guangzhou Futures Exchange
    SSE = "SSE"             # Shanghai Stock Exchange
    SZSE = "SZSE"           # Shenzhen Stock Exchange
    BSE = "BSE"             # Beijing Stock Exchange
    SHHK = "SHHK"           # Shanghai-HK Stock Connect
    SZHK = "SZHK"           # Shenzhen-HK Stock Connect
    SGE = "SGE"             # Shanghai Gold Exchange
    WXE = "WXE"             # Wuxi Steel Exchange
    CFETS = "CFETS"         # CFETS Bond Market Maker Trading System
    XBOND = "XBOND"         # CFETS X-Bond Anonymous Trading System

    # Global
    SMART = "SMART"         # Smart Router for US stocks
    NYSE = "NYSE"           # New York Stock Exchnage
    NASDAQ = "NASDAQ"       # Nasdaq Exchange
    ARCA = "ARCA"           # ARCA Exchange
    EDGEA = "EDGEA"         # Direct Edge Exchange
    ISLAND = "ISLAND"       # Nasdaq Island ECN
    BATS = "BATS"           # Bats Global Markets
    IEX = "IEX"             # The Investors Exchange
    AMEX = "AMEX"           # American Stock Exchange
    TSE = "TSE"             # Toronto Stock Exchange
    NYMEX = "NYMEX"         # New York Mercantile Exchange
    COMEX = "COMEX"         # COMEX of CME
    GLOBEX = "GLOBEX"       # Globex of CME
    IDEALPRO = "IDEALPRO"   # Forex ECN of Interactive Brokers
    CME = "CME"             # Chicago Mercantile Exchange
    ICE = "ICE"             # Intercontinental Exchange
    SEHK = "SEHK"           # Stock Exchange of Hong Kong
    HKFE = "HKFE"           # Hong Kong Futures Exchange
    SGX = "SGX"             # Singapore Global Exchange
    CBOT = "CBOT"           # Chicago Board of Trade
    CBOE = "CBOE"           # Chicago Board Options Exchange
    CFE = "CFE"             # CBOE Futures Exchange
    DME = "DME"             # Dubai Mercantile Exchange
    EUREX = "EUX"           # Eurex Exchange
    APEX = "APEX"           # Asia Pacific Exchange
    LME = "LME"             # London Metal Exchange
    BMD = "BMD"             # Bursa Malaysia Derivatives
    TOCOM = "TOCOM"         # Tokyo Commodity Exchange
    EUNX = "EUNX"           # Euronext Exchange
    KRX = "KRX"             # Korean Exchange
    OTC = "OTC"             # OTC Product (Forex/CFD/Pink Sheet Equity)
    IBKRATS = "IBKRATS"     # Paper Trading Exchange of IB

    # Special Function
    LOCAL = "LOCAL"         # For local generated data
    GLOBAL = "GLOBAL"       # For those exchanges not supported yet


class Currency(Enum):
    """
    币种枚举，标识账户与交易使用的结算货币。
    
    职责：
    1. 避免在系统中散落魔法字符串，提升代码可读性与可维护性。
    2. 为对象序列化、UI 展示、策略判断提供统一常量来源。
    3. 约束参数输入范围，减少跨模块对接歧义。
    
    协作：
    1. 广泛用于 `OrderData/ContractData/Request` 等业务对象字段。
    2. 被网关适配层用于本地常量与交易柜台协议之间的映射。
    """
    USD = "USD"
    HKD = "HKD"
    CNY = "CNY"
    CAD = "CAD"


class Interval(Enum):
    """
    K 线周期枚举，统一分钟、小时、日线等时间粒度。
    
    职责：
    1. 避免在系统中散落魔法字符串，提升代码可读性与可维护性。
    2. 为对象序列化、UI 展示、策略判断提供统一常量来源。
    3. 约束参数输入范围，减少跨模块对接歧义。
    
    协作：
    1. 广泛用于 `OrderData/ContractData/Request` 等业务对象字段。
    2. 被网关适配层用于本地常量与交易柜台协议之间的映射。
    """
    MINUTE = "1m"
    HOUR = "1h"
    DAILY = "d"
    WEEKLY = "w"
    TICK = "tick"
