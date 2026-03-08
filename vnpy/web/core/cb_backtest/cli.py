"""策略核心的 CLI 兼容入口。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from vnpy.web.core.cb_backtest.portfolio_backtest import run_backtest
from vnpy.web.core.cb_backtest.strategy_config import build_runtime_config, build_strategy_parameters
from vnpy.web.domain.cb_quant.history_store import CbHistoryStore

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_ROOT = PROJECT_ROOT / "out" / "cb_quant"
GLOBAL_TARGET = "return_drawdown_ratio"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CB strategy parameter optimization for convertible bonds.")
    parser.add_argument("--data-dir", default=str(DATA_ROOT))
    parser.add_argument("--output-dir", default=str(DATA_ROOT / "phase_a"))
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument(
        "--target",
        default="return_drawdown_ratio",
        choices=["return_drawdown_ratio", "total_return_pct", "calmar_like"],
    )
    parser.add_argument("--hold-until-profit", action="store_true")
    parser.add_argument("--max-hold-count", type=int, default=12)
    parser.add_argument("--price-start", type=float, default=106)
    parser.add_argument("--price-end", type=float, default=124)
    parser.add_argument("--price-step", type=float, default=2)
    parser.add_argument("--premium-start", type=float, default=16)
    parser.add_argument("--premium-end", type=float, default=34)
    parser.add_argument("--premium-step", type=float, default=2)
    parser.add_argument("--stock-weight-start", type=float, default=0.20)
    parser.add_argument("--stock-weight-end", type=float, default=0.35)
    parser.add_argument("--stock-weight-step", type=float, default=0.05)
    parser.add_argument("--premium-weight-start", type=float, default=0.15)
    parser.add_argument("--premium-weight-end", type=float, default=0.35)
    parser.add_argument("--premium-weight-step", type=float, default=0.05)
    parser.add_argument("--volatility-start", type=float, default=20)
    parser.add_argument("--volatility-end", type=float, default=35)
    parser.add_argument("--volatility-step", type=float, default=5)
    parser.add_argument("--max-candidate-price-start", type=float, default=125)
    parser.add_argument("--max-candidate-price-end", type=float, default=140)
    parser.add_argument("--max-candidate-price-step", type=float, default=5)
    parser.add_argument("--candidate-count-start", type=float, default=8)
    parser.add_argument("--candidate-count-end", type=float, default=14)
    parser.add_argument("--candidate-count-step", type=float, default=2)
    parser.add_argument("--outstanding-weight-start", type=float, default=0.10)
    parser.add_argument("--outstanding-weight-end", type=float, default=0.20)
    parser.add_argument("--outstanding-weight-step", type=float, default=0.05)
    return parser.parse_args()


def load_market_data(data_dir: Path) -> list[tuple[str, Any]]:
    root = Path(data_dir).resolve()
    db_path = root if root.is_file() else (root / "_cb_quant" / "cb_snapshots.db")
    store = CbHistoryStore(db_path)
    dataset = store.load_market_dataset()
    if not dataset:
        raise RuntimeError(f"No market snapshots available in {db_path}")
    return dataset


def evaluate_setting(setting: dict[str, Any]) -> dict[str, Any]:
    data_dir = Path(str(setting["data_dir"])).resolve()
    dataset = load_market_data(data_dir)
    strategy_parameters = build_strategy_parameters(setting)
    runtime_config = build_runtime_config(setting)
    stats = run_backtest(
        dataset=dataset,
        strategy_parameters=strategy_parameters,
        runtime_config=runtime_config,
    )
    return {
        **setting,
        "bond_weight": strategy_parameters.bond_weight,
        "candidate_count": runtime_config.candidate_count,
        **stats,
    }


def key_func(result: dict[str, Any]) -> float:
    value = result.get(GLOBAL_TARGET, 0.0)
    if value is None:
        return -math.inf
    return float(value)


def build_optimization_setting(args: argparse.Namespace, optimization_setting_class: type[Any]) -> Any:
    opt = optimization_setting_class()
    opt.add_parameter("data_dir", str(Path(args.data_dir).resolve()))
    opt.add_parameter("max_hold_count", args.max_hold_count)
    opt.add_parameter("hold_until_profit", args.hold_until_profit)

    def add_param(name: str, start: float, end: float, step: float) -> None:
        if math.isclose(start, end):
            ok, msg = opt.add_parameter(name, start)
        else:
            ok, msg = opt.add_parameter(name, start, end, step)
        if not ok:
            raise ValueError(f"failed to add parameter {name}: {msg}")

    add_param("price_benchmark", args.price_start, args.price_end, args.price_step)
    add_param("premium_benchmark", args.premium_start, args.premium_end, args.premium_step)
    add_param("stock_weight", args.stock_weight_start, args.stock_weight_end, args.stock_weight_step)
    add_param("premium_weight", args.premium_weight_start, args.premium_weight_end, args.premium_weight_step)
    add_param("volatility_benchmark", args.volatility_start, args.volatility_end, args.volatility_step)
    add_param(
        "max_candidate_price",
        args.max_candidate_price_start,
        args.max_candidate_price_end,
        args.max_candidate_price_step,
    )
    add_param("candidate_count", args.candidate_count_start, args.candidate_count_end, args.candidate_count_step)
    add_param(
        "outstanding_amount_weight",
        args.outstanding_weight_start,
        args.outstanding_weight_end,
        args.outstanding_weight_step,
    )
    opt.set_target(args.target)
    return opt


def save_results(output_dir: Path, top_results: list[dict[str, Any]], all_count: int, args: argparse.Namespace) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "run_at": timestamp,
        "target": args.target,
        "total_settings": all_count,
        "top_n": args.top_n,
        "max_workers": args.max_workers,
        "data_dir": str(Path(args.data_dir).resolve()),
        "hold_until_profit": args.hold_until_profit,
        "max_hold_count": args.max_hold_count,
        "top_results": top_results,
    }

    json_path = output_dir / f"phase_a_top_{timestamp}.json"
    with json_path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)

    if top_results:
        csv_path = output_dir / f"phase_a_top_{timestamp}.csv"
        fieldnames = list(top_results[0].keys())
        with csv_path.open("w", encoding="utf-8", newline="") as file_obj:
            writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(top_results)

    print(f"[CB Strategy] saved json: {json_path}")
    if top_results:
        print(f"[CB Strategy] saved csv : {output_dir / f'phase_a_top_{timestamp}.csv'}")


def main() -> None:
    from vnpy.trader.optimize import OptimizationSetting, check_optimization_setting, run_bf_optimization

    args = parse_args()
    global GLOBAL_TARGET
    GLOBAL_TARGET = args.target

    data_dir = Path(args.data_dir).resolve()
    if not data_dir.exists():
        raise FileNotFoundError(f"data dir not found: {data_dir}")

    optimization_setting = build_optimization_setting(args, OptimizationSetting)
    if not check_optimization_setting(optimization_setting):
        raise RuntimeError("invalid optimization setting")

    settings_count = len(optimization_setting.generate_settings())
    print(f"[CB Strategy] target={args.target}, settings={settings_count}, workers={args.max_workers}")

    results = run_bf_optimization(
        evaluate_func=evaluate_setting,
        optimization_setting=optimization_setting,
        key_func=key_func,
        max_workers=args.max_workers,
        output=print,
    )
    top_results = results[: args.top_n]
    output_dir = Path(args.output_dir).resolve()
    save_results(output_dir, top_results, settings_count, args)

    print("[CB Strategy] top strategies preview:")
    for idx, item in enumerate(top_results[: min(10, len(top_results))], start=1):
        print(
            f"{idx:02d}. score={item.get(args.target)} "
            f"ret={item.get('total_return_pct')} "
            f"mdd={item.get('max_drawdown_pct')} "
            f"candidate={item.get('candidate_count')} "
            f"price={item.get('price_benchmark')} "
            f"premium={item.get('premium_benchmark')}"
        )
