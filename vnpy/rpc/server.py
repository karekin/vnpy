import threading
import traceback
from time import time
from collections.abc import Callable

import zmq

from .common import HEARTBEAT_TOPIC, HEARTBEAT_INTERVAL


class RpcServer:
    """
    vn.py 的远程服务端。

    业务上把“远程下发指令”和“服务端主动推送事件”拆成两条链路：
    1. `REP` 链路：客户端发送 `(函数名, args, kwargs)`，服务端执行本地函数后回包。
    2. `PUB` 链路：服务端向所有订阅端广播主题消息，常用于心跳、日志、行情转发。
    """

    def __init__(self) -> None:
        """
        准备 RPC 运行时状态。

        包括：
        1. 远程可调用函数表（供 `run` 按名称路由）
        2. REP/PUB 两个 ZeroMQ 套接字
        3. 工作线程状态与心跳调度时间
        """
        # 可远程调用函数表：key=函数名，value=可调用对象。
        self._functions: dict[str, Callable] = {}

        # ZeroMQ 上下文。
        self._context: zmq.Context = zmq.Context()

        # 请求-响应通道（客户端 RPC 调用）。
        self._socket_rep: zmq.Socket = self._context.socket(zmq.REP)

        # 发布-订阅通道（服务器主动广播）。
        self._socket_pub: zmq.Socket = self._context.socket(zmq.PUB)

        # 线程与运行状态。
        self._active: bool = False                          # 服务是否运行中
        self._thread: threading.Thread | None = None        # 服务线程
        self._lock: threading.Lock = threading.Lock()

        # 下一次心跳广播时间戳。
        self._heartbeat_at: float | None = None

    def is_active(self) -> bool:
        """
        查询服务是否在处理 RPC 请求。
        """
        return self._active

    def start(
        self,
        rep_address: str,
        pub_address: str,
    ) -> None:
        """
        启动服务监听。

        业务流程：
        1. 对外暴露 REP 地址（接收远程调用）和 PUB 地址（对外广播事件）
        2. 启动后台线程进入 `run` 主循环
        3. 设定下一次心跳发送时间，供订阅端做存活检测
        """
        if self._active:
            return

        # 绑定监听地址。
        self._socket_rep.bind(rep_address)
        self._socket_pub.bind(pub_address)

        # 切换到运行态。
        self._active = True

        # 启动服务线程。
        self._thread = threading.Thread(target=self.run)
        self._thread.start()

        # 安排第一次心跳时间。
        self._heartbeat_at = time() + HEARTBEAT_INTERVAL

    def stop(self) -> None:
        """
        标记服务停止。

        这里不强制中断 socket，依赖 `run` 循环自然退出并在退出阶段关闭资源。
        """
        if not self._active:
            return

        # 切换为停止态，run 循环会自然退出。
        self._active = False

    def join(self) -> None:
        """
        阻塞等待后台 RPC 线程结束，常用于应用关闭阶段。
        """
        if self._thread and self._thread.is_alive():
            self._thread.join()
        self._thread = None

    def run(self) -> None:
        """
        RPC 主循环，负责“收请求 -> 执行业务函数 -> 回结果”。

        协议约定：
        1. 请求体：`(name, args, kwargs)`
        2. 响应体：`[success, payload]`
           `success=True` 时 `payload` 为返回值；
           `success=False` 时 `payload` 为异常堆栈字符串。
        """
        while self._active:
            # 轮询等待请求；超时后也要继续执行心跳检查。
            n: int = self._socket_rep.poll(1000)
            self.check_heartbeat()

            if not n:
                continue

            # 客户端请求体：函数名 + 位置参数 + 关键字参数。
            req = self._socket_rep.recv_pyobj()

            name, args, kwargs = req

            # 执行业务函数。失败时不抛给通信层，统一封装为失败响应。
            try:
                func: Callable = self._functions[name]
                r: object = func(*args, **kwargs)
                rep: list = [True, r]
            except Exception as e:  # noqa
                rep = [False, traceback.format_exc()]

            # 统一响应格式，便于客户端做通用解包。
            self._socket_rep.send_pyobj(rep)

        # 停止后关闭通信资源，释放端口占用。
        self._socket_pub.close()
        self._socket_rep.close()

    def publish(self, topic: str, data: object) -> None:
        """
        向订阅端广播主题消息。

        `topic` 用于客户端侧分发（如心跳/日志/业务事件），
        锁用于避免多线程同时发送造成消息帧交叉。
        """
        with self._lock:
            self._socket_pub.send_pyobj([topic, data])

    def register(self, func: Callable) -> None:
        """
        注册远程可调用函数。

        客户端只能按函数名发起调用，因此以 `func.__name__` 作为路由键。
        """
        self._functions[func.__name__] = func

    def check_heartbeat(self) -> None:
        """
        到达心跳时间后广播当前时间戳。

        订阅端可据此判断：
        1. 服务端是否仍在线
        2. 通道是否出现明显延迟或阻塞
        """
        now: float = time()

        if self._heartbeat_at and now >= self._heartbeat_at:
            # 心跳载荷使用服务端当前时间。
            self.publish(HEARTBEAT_TOPIC, now)

            # 重新安排下一个心跳周期。
            self._heartbeat_at = now + HEARTBEAT_INTERVAL
