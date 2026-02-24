from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from vnpy.web.domain.cb_quant.history_store import CbHistoryStore


class CrawlerPhaseABacktestAdapter:
    """Adapter to run real backtest logic from convertible-bond-crawler Phase A script."""

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
        self.script_path: Path = project_root / "convertible-bond-crawler" / "scripts" / "phase_a_optimize.py"
        self.data_dir: Path = data_dir or (project_root / "convertible-bond-crawler" / "out")
        self._module: ModuleType | None = None
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
        dataset = self._history_store.load_market_dataset()
        if dataset:
            return dataset
        module = self._load_module()
        return module.load_market_data(self.data_dir)

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

    def _load_module(self) -> ModuleType:
        if self._module:
            return self._module

        if not self.script_path.exists():
            raise FileNotFoundError(f"crawler phase-a script not found: {self.script_path}")

        spec = importlib.util.spec_from_file_location("cb_phase_a_optimize", str(self.script_path))
        if spec is None or spec.loader is None:
            raise RuntimeError(f"unable to load module spec from {self.script_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self._module = module
        return module

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
        return [(ds, frame) for _, ds, frame in normalized]

    @staticmethod
    def _minus_years(value: datetime, years: int) -> datetime:
        try:
            return value.replace(year=value.year - years)
        except ValueError:
            # Handle leap-day rollbacks like 2024-02-29 -> 2023-02-28.
            return value.replace(month=2, day=28, year=value.year - years)
