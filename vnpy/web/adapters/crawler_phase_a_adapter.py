from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from vnpy.web.domain.cb_quant.history_store import CbHistoryStore
from vnpy.web.domain.cb_quant import phase_a_core


class CrawlerPhaseABacktestAdapter:
    """Phase A 回测适配层。

    历史上这里曾通过外部脚本动态加载 Phase A 能力；现在运行时核心已经迁入 `vnpy`，
    这里保留适配层，
    主要负责：
    - 统一历史快照读取入口
    - 提供窗口切片能力
    - 让上层服务不必感知底层策略内核的位置变化
    """

    _FALLBACK_SETTING: dict[str, Any] = {
        "price_bemchmark": 115.0,
        "premium_bemchmark": 25.0,
        "stock_ratio": 0.3,
        "premium_ratio": 0.3,
        "stock_stdevry_bemchmark": 30.0,
        "max_price": 130.0,
        "head_count": 10,
        "remain_ratio": 0.1,
        "max_hold_num": 12,
        "until_win": False,
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

        cfg = module.build_strategy_config(setting)
        head_count = int(round(float(setting.get("head_count", 10))))
        head_count = max(head_count, 1)
        max_hold_num = int(round(float(setting.get("max_hold_num", 12))))
        max_hold_num = max(max_hold_num, 1)
        until_win = bool(setting.get("until_win", False))

        stats = module.run_backtest(
            dataset=sliced,
            cfg=cfg,
            head_count=head_count,
            max_hold_num=max_hold_num,
            until_win=until_win,
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
                "price_bemchmark": float(base_cfg.get("price_bemchmark", 115)),
                "premium_bemchmark": float(base_cfg.get("premium_bemchmark", 25)),
                "stock_ratio": float(base_cfg.get("stock_ratio", 0.3)),
                "premium_ratio": float(base_cfg.get("premium_ratio", 0.3)),
                "stock_stdevry_bemchmark": float(base_cfg.get("stock_stdevry_bemchmark", 30)),
                "max_price": float(base_cfg.get("max_price", 130)),
                "head_count": int(base_cfg.get("head_count", 10)),
                "remain_ratio": float(base_cfg.get("remain_ratio", 0.1)),
                "max_hold_num": 12,
                "until_win": False,
            }
        except Exception:
            return dict(self._FALLBACK_SETTING)

    def _load_module(self):
        """返回已融合进 `vnpy` 的 Phase A 核心模块。"""
        return phase_a_core

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

        if start_date or end_date:
            begin = datetime.combine(start_date, datetime.min.time()) if start_date else normalized[0][0]
            end = datetime.combine(end_date, datetime.max.time()) if end_date else normalized[-1][0]
            return [(ds, frame) for dt, ds, frame in normalized if begin <= dt <= end]

        end = normalized[-1][0]
        if window_name == "3y":
            begin = CrawlerPhaseABacktestAdapter._minus_years(end, years=3)
            return [(ds, frame) for dt, ds, frame in normalized if dt >= begin]
        if window_name == "1y":
            begin = CrawlerPhaseABacktestAdapter._minus_years(end, years=1)
            return [(ds, frame) for dt, ds, frame in normalized if dt >= begin]
        if window_name == "1w":
            begin = end - timedelta(days=7)
            return [(ds, frame) for dt, ds, frame in normalized if dt >= begin]
        return [(ds, frame) for _, ds, frame in normalized]

    @staticmethod
    def _minus_years(value: datetime, years: int) -> datetime:
        try:
            return value.replace(year=value.year - years)
        except ValueError:
            # Handle leap-day rollbacks like 2024-02-29 -> 2023-02-28.
            return value.replace(month=2, day=28, year=value.year - years)
