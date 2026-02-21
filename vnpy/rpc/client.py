import threading
from time import time
from functools import lru_cache
from typing import Any

import zmq

from .common import HEARTBEAT_TOPIC, HEARTBEAT_TOLERANCE


class RemoteException(Exception):
    """
    RPC 调用失败时抛出的异常。

    触发场景：
    1. 服务端业务函数执行失败并回传异常堆栈。
    2. 客户端等待响应超时（网络中断或服务端阻塞）。
    """

    def __init__(self, value: Any) -> None:
        """
        保存远程错误内容，通常是超时信息或服务端 traceback 字符串。
        """
        self._value: Any = value

    def __str__(self) -> str:
        """
        返回可直接记录日志/展示给上层的错误文本。
        """
        return str(self._value)


class RpcClient:
    """
    vn.py RPC 客户端。

    同时维护两条链路：
    1. `REQ` 链路：同步远程调用，发送函数名和参数并等待结果。
    2. `SUB` 链路：异步接收服务端广播（心跳和业务推送）。
    """

    def __init__(self) -> None:
        """
        初始化通信资源和运行状态。

        包括：
        1. 创建 REQ/SUB 套接字
        2. 配置 TCP keepalive，降低静默断连不可感知的问题
        3. 准备接收线程、请求锁和最近心跳时间
        """
        # ZeroMQ 上下文与通信套接字。
        self._context: zmq.Context = zmq.Context()

        # REQ：远程调用请求-应答通道。
        self._socket_req: zmq.Socket = self._context.socket(zmq.REQ)

        # SUB：订阅服务端主动推送的数据。
        self._socket_sub: zmq.Socket = self._context.socket(zmq.SUB)

        # 启用 TCP keepalive，尽早发现半开连接。
        for socket in [self._socket_req, self._socket_sub]:
            socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
            socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 60)

        # 接收线程状态。
        self._active: bool = False
        self._thread: threading.Thread | None = None
        self._lock: threading.Lock = threading.Lock()

        # 最近一次收到服务端心跳的时间戳。
        self._last_received_ping: float = time()

    @lru_cache(100)  # noqa
    def __getattr__(self, name: str) -> Any:
        """
        按函数名动态生成 RPC 调用代理。

        例如访问 `client.query_history(...)` 时，
        实际会返回一个闭包，把 `query_history` 作为远程函数名发送给服务端。
        """
        # 构造一次远程调用。
        def dorpc(*args: Any, **kwargs: Any) -> Any:
            # 调用超时（毫秒），默认 30 秒。
            timeout: int = kwargs.pop("timeout", 30000)

            # 请求协议：[函数名, 位置参数, 关键字参数]。
            req: list = [name, args, kwargs]

            # REQ 套接字必须严格 send/recv 成对，使用锁避免多线程并发打乱顺序。
            with self._lock:
                self._socket_req.send_pyobj(req)

                # 超时未收到任何响应。
                n: int = self._socket_req.poll(timeout)
                if not n:
                    msg: str = f"Timeout of {timeout}ms reached for {req}"
                    raise RemoteException(msg)

                rep = self._socket_req.recv_pyobj()

            # 响应协议：[success, payload]。
            if rep[0]:
                return rep[1]
            else:
                raise RemoteException(rep[1])

        return dorpc

    def start(
        self,
        req_address: str,
        sub_address: str
    ) -> None:
        """
        建立到 RPC 服务端的连接并启动订阅处理线程。

        `req_address` 用于远程调用，`sub_address` 用于订阅广播事件。
        """
        if self._active:
            return

        # 连接服务端两个端口。
        self._socket_req.connect(req_address)
        self._socket_sub.connect(sub_address)

        # 切换到运行态并启动接收线程。
        self._active = True
        self._thread = threading.Thread(target=self.run)
        self._thread.start()

        # 重置最近心跳时间。
        self._last_received_ping = time()

    def stop(self) -> None:
        """
        请求停止客户端主循环。

        套接字关闭在 `run` 退出阶段执行。
        """
        if not self._active:
            return

        # 标记停止，通知 run 循环退出。
        self._active = False

    def join(self) -> None:
        """
        等待订阅处理线程结束，常用于应用退出前收尾。
        """
        if self._thread and self._thread.is_alive():
            self._thread.join()
        self._thread = None

    def run(self) -> None:
        """
        订阅链路主循环。

        处理顺序：
        1. 在心跳容忍时间内等待服务端推送
        2. 超时则触发断连处理
        3. 收到心跳则刷新最后心跳时间
        4. 收到业务主题则交给 `callback`
        """
        pull_tolerance: int = HEARTBEAT_TOLERANCE * 1000

        while self._active:
            if not self._socket_sub.poll(pull_tolerance):
                self.on_disconnected()
                continue

            # 推送消息格式：[topic, data]。
            topic, data = self._socket_sub.recv_pyobj(flags=zmq.NOBLOCK)

            if topic == HEARTBEAT_TOPIC:
                # 心跳只用于连接健康检查，不进入业务回调。
                self._last_received_ping = data
            else:
                # 业务消息由子类实现具体处理。
                self.callback(topic, data)

        # 退出时释放网络资源。
        self._socket_req.close()
        self._socket_sub.close()

    def callback(self, topic: str, data: Any) -> None:
        """
        业务回调扩展点。

        子类应按 `topic` 分发处理订阅消息，例如转事件引擎、刷新缓存或触发策略逻辑。
        """
        raise NotImplementedError

    def subscribe_topic(self, topic: str) -> None:
        """
        添加主题订阅。

        只有匹配该前缀的服务端推送才会送达 `run` 循环。
        """
        self._socket_sub.setsockopt_string(zmq.SUBSCRIBE, topic)

    def on_disconnected(self) -> None:
        """
        断连处理扩展点。

        默认只打印提示；生产环境通常会在子类里改为告警、重连或切换备份通道。
        """
        msg: str = f"RpcServer has no response over {HEARTBEAT_TOLERANCE} seconds, please check you connection."
        print(msg)
