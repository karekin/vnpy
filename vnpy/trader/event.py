"""
交易域事件类型常量定义。

这些常量是 vn.py 事件总线里的“主题名”，
由网关/引擎发布，OMS、UI、策略等模块订阅。

约定：
1. 以点号结尾的事件（如 ``eTick.``）可拼接细粒度键：
   ``EVENT_TICK + vt_symbol``、``EVENT_ORDER + vt_orderid``。
2. 不带点号的事件（如 ``eLog``）通常只走全局通道。
"""

from vnpy.event import EVENT_TIMER  # noqa

# 行情 Tick 更新事件（全局 + 指定 vt_symbol 子通道）。
EVENT_TICK = "eTick."
# 成交回报事件（全局 + 指定 vt_symbol 子通道）。
EVENT_TRADE = "eTrade."
# 委托状态事件（全局 + 指定 vt_orderid 子通道）。
EVENT_ORDER = "eOrder."
# 持仓变化事件（全局 + 指定 vt_symbol 子通道）。
EVENT_POSITION = "ePosition."
# 账户资金事件（全局 + 指定 vt_accountid 子通道）。
EVENT_ACCOUNT = "eAccount."
# 双边报价事件（全局 + 指定 vt_symbol 子通道）。
EVENT_QUOTE = "eQuote."
# 合约元数据事件（通常用于合约信息初始化/刷新）。
EVENT_CONTRACT = "eContract."
# 日志事件（供日志引擎和日志面板消费）。
EVENT_LOG = "eLog"
