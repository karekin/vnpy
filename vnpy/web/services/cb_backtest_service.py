from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

from vnpy.web.core import cb_backtest
from vnpy.web.db import load_db_settings
from vnpy.web.domain.cb_quant.history_store import CbHistoryStore


class CbBacktestService:
    """可转债回测基础服务。

    负责共享的回测基础能力：
    - 历史快照读取
    - 数据标准化
    - 窗口切片
    - 默认回测参数
    - 单次回测执行
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """初始化服务并绑定历史数据存储。"""

        # 以当前文件为锚点回溯到项目根目录，避免受运行目录影响。
        project_root: Path = Path(__file__).resolve().parents[3]
        # 若调用方未显式传入数据目录，则使用项目内约定的输出目录。
        self.data_dir: Path = data_dir or (project_root / "out" / "cb_quant")
        # 历史快照统一从 PostgreSQL 中读取。
        self._history_store: CbHistoryStore = CbHistoryStore(load_db_settings())
        # 历史数据按进程做缓存，避免同一个 worker 内重复全量反序列化 SQLite 快照。
        self._market_data_lock: Lock = Lock()
        self._market_data_cache: list[tuple[str, Any]] | None = None
        self._market_data_cache_mtime: float | None = None

    def run_backtest(
        self,
        *,
        setting: dict[str, Any],
        window_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """执行一次回测，并在结果中补充窗口信息。"""

        # 回测逻辑放在核心模块中，这里只负责组织输入输出。
        module = self._load_module()
        # 先读取并标准化全量市场快照。
        dataset = self.load_market_data()
        # 按窗口类型和用户传入日期裁剪数据。
        sliced = self.slice_dataset(
            dataset=dataset,
            window_name=window_name,
            start_date=start_date,
            end_date=end_date,
        )
        if not sliced:
            # 量化回测不应静默改用其他区间；数据不满足时直接报错。
            if start_date or end_date:
                raise RuntimeError(
                    f"No market snapshots available for requested range: "
                    f"{start_date or '-'}~{end_date or '-'}"
                )
            raise RuntimeError("No market snapshots available for selected backtest window")

        # 将外部 setting 转换成核心回测模块要求的策略参数。
        strategy_parameters = module.build_strategy_parameters(setting)
        # 构造回测运行期配置，例如仓位、持仓数等约束。
        runtime_config = module.build_runtime_config(setting)

        # 调用核心模块执行实际回测。
        stats = module.run_backtest(
            dataset=sliced,
            strategy_parameters=strategy_parameters,
            runtime_config=runtime_config,
        )
        # 补充服务层统一维护的元信息，方便 API 直接返回。
        stats["sample_days"] = len(sliced)
        stats["window_name"] = window_name
        # 为兼容现有响应结构，保留字段但固定表示“未使用回退”。
        stats["fallback_used"] = False
        stats["fallback_reason"] = None
        # 记录本次实际使用的数据起止日期，便于排查窗口裁剪结果。
        stats["used_range_start"] = sliced[0][0]
        stats["used_range_end"] = sliced[-1][0]
        return stats

    def load_market_data(self) -> list[tuple[str, Any]]:
        """读取市场快照，并在需要时调用核心模块做标准化处理。"""

        db_path = self._history_store.db_path
        cache_mtime = db_path.stat().st_mtime if db_path.exists() else None
        with self._market_data_lock:
            if self._market_data_cache is not None and self._market_data_cache_mtime == cache_mtime:
                return self._market_data_cache

        # 从历史存储中读取原始数据集，返回格式通常为 [(交易日字符串, 数据框), ...]。
        dataset = self._history_store.load_market_dataset()
        if dataset:
            module = self._load_module()
            # 标准化后的数据仍保持相同的二元组结构。
            normalized: list[tuple[str, Any]] = []
            # `normalize_market_frame` 不是强制接口，因此先动态探测。
            normalizer = getattr(module, "normalize_market_frame", None)
            for trade_date, frame in dataset:
                # 如果核心模块提供了标准化函数，则逐日处理数据框。
                if callable(normalizer):
                    normalized.append((trade_date, normalizer(frame)))
                else:
                    # 否则直接保留原始 frame，保证服务层兼容旧实现。
                    normalized.append((trade_date, frame))
            with self._market_data_lock:
                self._market_data_cache = normalized
                self._market_data_cache_mtime = cache_mtime
            return normalized
        # 没有任何历史数据时，返回空列表而不是抛异常，交给上层统一处理。
        with self._market_data_lock:
            self._market_data_cache = []
            self._market_data_cache_mtime = cache_mtime
        return []

    def default_setting(self) -> dict[str, Any]:
        """返回回测默认参数；配置异常时直接报错。"""

        module = self._load_module()
        # 将模块中的配置对象转成普通 dict，避免后续读取时依赖其具体类型。
        base_cfg = dict(module.multiple_factors_config)
        required_keys = [
            "price_benchmark",
            "premium_benchmark",
            "stock_weight",
            "premium_weight",
            "volatility_benchmark",
            "max_candidate_price",
            "outstanding_amount_weight",
        ]
        missing_keys = [key for key in required_keys if key not in base_cfg]
        if missing_keys:
            raise RuntimeError(f"cb_backtest.multiple_factors_config missing keys: {', '.join(missing_keys)}")
        return {
            # 这些字段必须来自核心模块配置；缺失说明配置本身已损坏。
            "price_benchmark": float(base_cfg["price_benchmark"]),
            "premium_benchmark": float(base_cfg["premium_benchmark"]),
            "stock_weight": float(base_cfg["stock_weight"]),
            "premium_weight": float(base_cfg["premium_weight"]),
            "volatility_benchmark": float(base_cfg["volatility_benchmark"]),
            "max_candidate_price": float(base_cfg["max_candidate_price"]),
            # 当前服务层将候选数固定为 12，未从模块配置透传。
            "candidate_count": 12,
            "outstanding_amount_weight": float(base_cfg["outstanding_amount_weight"]),
            # 最大持仓数同样固定为 12。
            "max_hold_count": 12,
            # 默认不启用“盈利前持有不卖出”策略。
            "hold_until_profit": False,
        }

    def _load_module(self):
        """返回实际承载回测实现的模块，便于后续替换或测试注入。"""

        return cb_backtest

    @staticmethod
    def slice_dataset(
        *,
        dataset: list[tuple[str, Any]],
        window_name: str,
        start_date: date | None,
        end_date: date | None,
    ) -> list[tuple[str, Any]]:
        """按窗口和自定义日期区间裁剪数据集。"""

        # 中间结构额外保留解析后的 datetime，便于排序和范围比较。
        normalized: list[tuple[datetime, str, Any]] = []
        for ds, frame in dataset:
            try:
                # 历史数据中的日期以 `YYYY-MM-DD` 字符串保存，这里统一解析。
                dt = datetime.strptime(ds, "%Y-%m-%d")
            except ValueError:
                # 非法日期直接忽略，避免坏数据影响整体回测。
                continue
            normalized.append((dt, ds, frame))

        # 先按时间正序排列，确保后续窗口裁剪和起止日期计算可靠。
        normalized.sort(key=lambda item: item[0])
        if not normalized:
            return []

        # 数据集天然的最早/最晚日期，用作默认窗口边界。
        dataset_begin = normalized[0][0]
        dataset_end = normalized[-1][0]
        # 默认使用全量数据范围。
        begin = dataset_begin
        end = dataset_end
        # 根据预设窗口名称收缩起始时间。
        if window_name == "3y":
            begin = CbBacktestService._minus_years(dataset_end, years=3)
        elif window_name == "1y":
            begin = CbBacktestService._minus_years(dataset_end, years=1)
        elif window_name == "1w":
            # 一周窗口按最近 7 天回溯。
            begin = dataset_end - timedelta(days=7)

        # 若调用方传入自定义开始日期，则以更晚者为准，避免超出数据边界。
        if start_date:
            begin = max(begin, datetime.combine(start_date, datetime.min.time()))
        # 若调用方传入自定义结束日期，则以更早者为准。
        if end_date:
            end = min(end, datetime.combine(end_date, datetime.max.time()))

        # 起始时间晚于结束时间时，说明没有交集。
        if begin > end:
            return []
        # 返回原始日期字符串和对应 frame，保持调用方接口稳定。
        return [(ds, frame) for dt, ds, frame in normalized if begin <= dt <= end]

    @staticmethod
    def _minus_years(value: datetime, years: int) -> datetime:
        """将时间回退指定年数，并兼容闰年日期。"""

        try:
            # 常规日期可以直接替换年份。
            return value.replace(year=value.year - years)
        except ValueError:
            # 例如 2 月 29 日回退到平年时，会降级为 2 月 28 日。
            return value.replace(month=2, day=28, year=value.year - years)
