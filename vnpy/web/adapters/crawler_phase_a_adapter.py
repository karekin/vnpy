from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from vnpy.web.domain.cb_quant.history_store import CbHistoryStore
from vnpy.web.domain.cb_quant import cb_strategy_core


class CrawlerPhaseABacktestAdapter:
    """可转债策略回测适配层。

    历史上这里曾通过外部脚本动态加载策略核心；现在运行时核心已经迁入 `vnpy`，
    这里保留适配层，
    主要负责：
    - 统一历史快照读取入口
    - 提供窗口切片能力
    - 让上层服务不必感知底层策略内核的位置变化
    """

    _FALLBACK_SETTING: dict[str, Any] = {
        "price_benchmark": 115.0,
        "premium_benchmark": 25.0,
        "stock_weight": 0.3,
        "premium_weight": 0.3,
        "volatility_benchmark": 30.0,
        "max_candidate_price": 130.0,
        "candidate_count": 12,
        "outstanding_amount_weight": 0.1,
        "max_hold_count": 12,
        "hold_until_profit": False,
    }

    def __init__(self, data_dir: Path | None = None) -> None:
        project_root: Path = Path(__file__).resolve().parents[3]
        self.data_dir: Path = data_dir or (project_root / "out" / "cb_quant")
        self._history_store: CbHistoryStore = CbHistoryStore(self.data_dir / "_cb_quant" / "cb_snapshots.db")

    def run_backtest(
        self,
        *,
        setting: dict[str, Any],
        window_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        module = self._load_module()
        dataset = self.load_market_data()
        sliced = self._slice_dataset(
            dataset=dataset,
            window_name=window_name,
            start_date=start_date,
            end_date=end_date,
        )
        fallback_used = False
        fallback_reason = ""

        if not sliced and (start_date or end_date):
            fallback_used = True
            sliced = self._slice_dataset(
                dataset=dataset,
                window_name=window_name,
                start_date=None,
                end_date=None,
            )
            if sliced:
                fallback_reason = (
                    f"requested range {start_date or '-'}~{end_date or '-'} unavailable; "
                    f"fallback to {sliced[0][0]}~{sliced[-1][0]}"
                )

        if not sliced:
            raise RuntimeError("No market snapshots available for selected backtest window")

        strategy_parameters = module.build_strategy_parameters(setting)
        runtime_config = module.build_runtime_config(setting)

        stats = module.run_backtest(
            dataset=sliced,
            strategy_parameters=strategy_parameters,
            runtime_config=runtime_config,
        )
        stats["sample_days"] = len(sliced)
        stats["window_name"] = window_name
        stats["fallback_used"] = fallback_used
        stats["fallback_reason"] = fallback_reason
        stats["used_range_start"] = sliced[0][0] if sliced else None
        stats["used_range_end"] = sliced[-1][0] if sliced else None
        return stats

    def load_market_data(self) -> list[tuple[str, Any]]:
        """优先从 cb_snapshots.db 加载历史快照。

        这里不再把 crawler 目录里的 Excel 作为运行时主数据源；
        如果快照库为空，就返回空数据集，由上层决定是否提示同步或做 bootstrap。
        """
        dataset = self._history_store.load_market_dataset()
        if dataset:
            module = self._load_module()
            normalized: list[tuple[str, Any]] = []
            normalizer = getattr(module, "normalize_market_frame", None)
            for trade_date, frame in dataset:
                if callable(normalizer):
                    normalized.append((trade_date, normalizer(frame)))
                else:
                    normalized.append((trade_date, frame))
            return normalized
        return []

    def default_setting(self) -> dict[str, Any]:
        try:
            module = self._load_module()
            base_cfg = dict(module.multiple_factors_config)
            return {
                "price_benchmark": float(base_cfg.get("price_benchmark", 115)),
                "premium_benchmark": float(base_cfg.get("premium_benchmark", 25)),
                "stock_weight": float(base_cfg.get("stock_weight", 0.3)),
                "premium_weight": float(base_cfg.get("premium_weight", 0.3)),
                "volatility_benchmark": float(base_cfg.get("volatility_benchmark", 30)),
                "max_candidate_price": float(base_cfg.get("max_candidate_price", 130)),
                "candidate_count": 12,
                "outstanding_amount_weight": float(base_cfg.get("outstanding_amount_weight", 0.1)),
                "max_hold_count": 12,
                "hold_until_profit": False,
            }
        except Exception:
            return dict(self._FALLBACK_SETTING)

    def _load_module(self):
        """返回已融合进 `vnpy` 的策略核心模块。"""
        return cb_strategy_core

    @staticmethod
    def _slice_dataset(
        *,
        dataset: list[tuple[str, Any]],
        window_name: str,
        start_date: date | None,
        end_date: date | None,
    ) -> list[tuple[str, Any]]:
        normalized: list[tuple[datetime, str, Any]] = []
        for ds, frame in dataset:
            try:
                dt = datetime.strptime(ds, "%Y-%m-%d")
            except ValueError:
                continue
            normalized.append((dt, ds, frame))

        normalized.sort(key=lambda item: item[0])
        if not normalized:
            return []

        # 窗口名和起止日期都可能存在。
        # 期望语义应为“先得到窗口自身覆盖范围，再与用户指定日期范围取交集”，
        # 而不是像旧逻辑那样只要传了 start/end 就把 1w/1y/3y 全部覆盖掉。
        dataset_begin = normalized[0][0]
        dataset_end = normalized[-1][0]
        begin = dataset_begin
        end = dataset_end
        if window_name == "3y":
            begin = CrawlerPhaseABacktestAdapter._minus_years(dataset_end, years=3)
        elif window_name == "1y":
            begin = CrawlerPhaseABacktestAdapter._minus_years(dataset_end, years=1)
        elif window_name == "1w":
            begin = dataset_end - timedelta(days=7)

        if start_date:
            begin = max(begin, datetime.combine(start_date, datetime.min.time()))
        if end_date:
            end = min(end, datetime.combine(end_date, datetime.max.time()))

        if begin > end:
            return []
        return [(ds, frame) for dt, ds, frame in normalized if begin <= dt <= end]

    @staticmethod
    def _minus_years(value: datetime, years: int) -> datetime:
        try:
            return value.replace(year=value.year - years)
        except ValueError:
            # Handle leap-day rollbacks like 2024-02-29 -> 2023-02-28.
            return value.replace(month=2, day=28, year=value.year - years)
