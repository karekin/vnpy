"""
vn.py 事件驱动框架核心模块。

提供统一事件对象与事件引擎，实现模块间解耦通信和定时事件驱动。
"""

from collections import defaultdict
from collections.abc import Callable
from queue import Empty, Queue
from threading import Thread
from time import sleep
from typing import Any


EVENT_TIMER = "eTimer"


class Event:
    """
    事件对象，封装“事件类型 + 业务数据”。

    在 vn.py 中，网关、引擎、策略、UI 都通过它交换消息：
    1. `type` 决定路由目标（例如行情、委托、成交、定时器事件）。
    2. `data` 承载对应业务载荷，避免模块之间直接耦合调用。
    """

    def __init__(self, type: str, data: Any = None) -> None:
        """
        构造事件包。

        业务约定：
        1. `type` 用于事件引擎路由。
        2. `data` 可为任意业务对象，按 `type` 解释。
        """
        self.type: str = type
        self.data: Any = data


# Defines handler function to be used in event engine.
HandlerType = Callable[[Event], None]


class EventEngine:
    """
    vn.py 的事件总线核心实现。

    业务角色：
    1. 把各模块产生的事件放入同一队列，统一串行分发，降低并发读写冲突。
    2. 按 `event.type` 分发给精准处理器，并可额外分发给“全量监听”处理器。
    3. 定期推送 `EVENT_TIMER`，驱动策略轮询、定时检查等周期任务。
    """

    def __init__(self, interval: int = 1) -> None:
        """
        初始化事件引擎运行时状态。

        `interval` 控制定时器线程发送 `EVENT_TIMER` 的秒级周期。
        """
        self._interval: int = interval
        self._queue: Queue = Queue()
        self._active: bool = False
        self._thread: Thread = Thread(target=self._run)
        self._timer: Thread = Thread(target=self._run_timer)
        self._handlers: defaultdict = defaultdict(list)
        self._general_handlers: list = []

    def _run(self) -> None:
        """
        事件消费主循环。

        逻辑：
        1. 从队列阻塞获取事件。
        2. 获取成功后交给 `_process` 分发。
        3. 超时无事件时继续下一轮等待。
        """
        while self._active:
            try:
                event: Event = self._queue.get(block=True, timeout=1)
                self._process(event)
            except Empty:
                pass

    def _process(self, event: Event) -> None:
        """
        执行一次事件分发。

        分发顺序：
        1. 先执行该 `event.type` 的专用处理器。
        2. 再执行所有通用处理器（用于日志、监控、调试等全量订阅场景）。
        """
        if event.type in self._handlers:
            [handler(event) for handler in self._handlers[event.type]]

        if self._general_handlers:
            [handler(event) for handler in self._general_handlers]

    def _run_timer(self) -> None:
        """
        定时器线程。

        每隔 `_interval` 秒生成一个 `EVENT_TIMER` 并入队，
        让上层用事件方式实现周期任务，而不是自己管理线程/睡眠。
        """
        while self._active:
            sleep(self._interval)
            event: Event = Event(EVENT_TIMER)
            self.put(event)

    def start(self) -> None:
        """
        启动事件引擎。

        同时启动：
        1. 事件消费线程 `_run`
        2. 定时器线程 `_run_timer`
        """
        self._active = True
        self._thread.start()
        self._timer.start()

    def stop(self) -> None:
        """
        停止事件引擎并等待线程退出。

        先置 `_active=False`，再 `join` 两个线程，确保不再有新事件被处理。
        """
        self._active = False
        self._timer.join()
        self._thread.join()

    def put(self, event: Event) -> None:
        """
        将事件放入队列，等待异步分发。

        各业务模块统一通过此入口投递事件，避免模块间直接互调。
        """
        self._queue.put(event)

    def register(self, type: str, handler: HandlerType) -> None:
        """
        为指定事件类型注册处理器。

        同一处理器不会重复注册，避免一次事件被同一函数重复执行。
        """
        handler_list: list = self._handlers[type]
        if handler not in handler_list:
            handler_list.append(handler)

    def unregister(self, type: str, handler: HandlerType) -> None:
        """
        取消指定事件类型的处理器注册。

        若该事件类型已无处理器，会清理映射项，减少无效键占用。
        """
        handler_list: list = self._handlers[type]

        if handler in handler_list:
            handler_list.remove(handler)

        if not handler_list:
            self._handlers.pop(type)

    def register_general(self, handler: HandlerType) -> None:
        """
        注册通用处理器。

        通用处理器会收到所有事件，适合做统一日志、统计、链路观测。
        """
        if handler not in self._general_handlers:
            self._general_handlers.append(handler)

    def unregister_general(self, handler: HandlerType) -> None:
        """
        取消通用处理器注册。
        """
        if handler in self._general_handlers:
            self._general_handlers.remove(handler)
