from types import ModuleType
from collections.abc import Callable
from importlib import import_module

from .object import HistoryRequest, TickData, BarData
from .setting import SETTINGS
from .locale import _


class BaseDatafeed:
    """
    历史数据服务接口基类。

    业务上，策略回测和手动补历史数据都需要“统一的数据入口”，
    不同供应商（聚宽、米筐、自建服务）的调用方式不同，
    所以 vn.py 通过这个基类约束三个动作：
    1. 初始化数据服务连接（`init`）
    2. 查询 K 线历史（`query_bar_history`）
    3. 查询 Tick 历史（`query_tick_history`）

    默认实现全部返回失败或空列表，作用是“兜底”，
    防止用户没安装数据服务插件时程序直接报错退出。
    """

    def init(self, output: Callable = print) -> bool:
        """
        初始化数据服务。

        典型实现会在这里完成认证、连接检查、可用性探测等动作。
        返回值约定：
        1. `True`：数据服务可用，可执行历史查询
        2. `False`：初始化失败，上层应提示用户并停止依赖该数据源

        `output` 用来输出初始化过程日志（默认直接打印）。
        """
        return False

    def query_bar_history(self, req: HistoryRequest, output: Callable = print) -> list[BarData]:
        """
        查询 K 线历史数据。

        `req` 给出合约、周期、起止时间；实现类应返回标准 `BarData` 列表。
        业务约定：
        1. 查询成功返回按时间顺序排列的数据
        2. 查询失败返回空列表，并通过 `output` 给出失败原因
        """
        output(_("查询K线数据失败：没有正确配置数据服务"))
        return []

    def query_tick_history(self, req: HistoryRequest, output: Callable = print) -> list[TickData]:
        """
        查询 Tick 历史数据。

        与 `query_bar_history` 一样，失败时不抛异常中断流程，
        而是返回空列表并输出可读错误信息，方便上层决定重试或降级。
        """
        output(_("查询Tick数据失败：没有正确配置数据服务"))
        return []


datafeed: BaseDatafeed | None = None


def get_datafeed() -> BaseDatafeed:
    """
    按全局配置加载并返回数据服务实例（单例）。

    加载流程：
    1. 如果已初始化过，直接复用已有实例
    2. 读取 `SETTINGS["datafeed.name"]`
    3. 有配置则尝试导入 `vnpy_{name}` 并实例化其 `Datafeed` 类
    4. 导入失败或未配置时退回 `BaseDatafeed` 兜底实现
    """
    # 已初始化则直接返回，避免重复导入/重复创建实例。
    global datafeed
    if datafeed:
        return datafeed

    # 从全局配置读取要使用的数据服务名称。
    datafeed_name: str = SETTINGS["datafeed.name"]

    if not datafeed_name:
        datafeed = BaseDatafeed()

        print(_("没有配置要使用的数据服务，请修改全局配置中的datafeed相关内容"))
    else:
        module_name: str = f"vnpy_{datafeed_name}"

        # 尝试动态导入第三方数据服务插件模块。
        try:
            module: ModuleType = import_module(module_name)

            # 约定插件模块暴露 Datafeed 类作为入口。
            datafeed = module.Datafeed()
        # 插件不可用时降级到基础实现，保证程序可继续运行。
        except ModuleNotFoundError:
            datafeed = BaseDatafeed()

            print(_("无法加载数据服务模块，请运行 pip install {} 尝试安装").format(module_name))

    return datafeed
