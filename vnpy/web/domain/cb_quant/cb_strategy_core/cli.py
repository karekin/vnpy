"""策略核心的 CLI 兼容入口。

这个模块只保留研究/离线运行需要的命令行外壳。
当前主运行路径已经是 `vnpy cb-quant` 服务，不再依赖历史脚本工程。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from vnpy.web.domain.cb_quant.history_store import CbHistoryStore
from vnpy.web.domain.cb_quant.cb_strategy_core.backtest import run_backtest
from vnpy.web.domain.cb_quant.cb_strategy_core.candidates import build_strategy_config
from vnpy.web.domain.cb_quant.cb_strategy_core.normalizer import _safe_float

PROJECT_ROOT = Path(__file__).resolve().parents[5]
DATA_ROOT = PROJECT_ROOT / "out" / "cb_quant"
GLOBAL_TARGET = "return_drawdown_ratio"


def parse_args() -> argparse.Namespace:
    """解析策略优化 CLI 参数。"""
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
    parser.add_argument("--until-win", action="store_true")
    parser.add_argument("--max-hold-num", type=int, default=12)
    parser.add_argument("--price-start", type=float, default=106)
    parser.add_argument("--price-end", type=float, default=124)
    parser.add_argument("--price-step", type=float, default=2)
    parser.add_argument("--premium-start", type=float, default=16)
    parser.add_argument("--premium-end", type=float, default=34)
    parser.add_argument("--premium-step", type=float, default=2)
    parser.add_argument("--stock-ratio-start", type=float, default=0.20)
    parser.add_argument("--stock-ratio-end", type=float, default=0.35)
    parser.add_argument("--stock-ratio-step", type=float, default=0.05)
    parser.add_argument("--premium-ratio-start", type=float, default=0.15)
    parser.add_argument("--premium-ratio-end", type=float, default=0.35)
    parser.add_argument("--premium-ratio-step", type=float, default=0.05)
    parser.add_argument("--stdevry-start", type=float, default=20)
    parser.add_argument("--stdevry-end", type=float, default=35)
    parser.add_argument("--stdevry-step", type=float, default=5)
    parser.add_argument("--max-price-start", type=float, default=125)
    parser.add_argument("--max-price-end", type=float, default=140)
    parser.add_argument("--max-price-step", type=float, default=5)
    parser.add_argument("--head-count-start", type=float, default=8)
    parser.add_argument("--head-count-end", type=float, default=14)
    parser.add_argument("--head-count-step", type=float, default=2)
    parser.add_argument("--remain-ratio-start", type=float, default=0.10)
    parser.add_argument("--remain-ratio-end", type=float, default=0.20)
    parser.add_argument("--remain-ratio-step", type=float, default=0.05)
    return parser.parse_args()


def load_market_data(data_dir: Path) -> list[tuple[str, Any]]:
    """从 cb_snapshots.db 读取历史市场快照。"""
    root = Path(data_dir).resolve()
    db_path = root if root.is_file() else (root / "_cb_quant" / "cb_snapshots.db")
    store = CbHistoryStore(db_path)
    dataset = store.load_market_dataset()
    if not dataset:
        raise RuntimeError(f"No market snapshots available in {db_path}")
    return dataset


def evaluate_setting(setting: dict[str, Any]) -> dict[str, Any]:
    """供 vnpy 优化器调用的单组合评估函数。"""
    data_dir = Path(str(setting["data_dir"])).resolve()
    dataset = load_market_data(data_dir)
    cfg = build_strategy_config(setting)
    head_count = int(round(_safe_float(setting["head_count"], 10)))
    if head_count <= 0:
        head_count = 1

    max_hold_num = int(round(_safe_float(setting["max_hold_num"], 12)))
    until_win = bool(setting.get("until_win", False))
    stats = run_backtest(
        dataset=dataset,
        cfg=cfg,
        head_count=head_count,
        max_hold_num=max_hold_num,
        until_win=until_win,
    )
    return {
        **setting,
        "bond_ratio": round(1 - _safe_float(setting["stock_ratio"]), 2),
        "head_count": head_count,
        **stats,
    }


def key_func(result: dict[str, Any]) -> float:
    """根据全局目标字段提取排序值。"""
    value = result.get(GLOBAL_TARGET, 0.0)
    if value is None:
        return -math.inf
    return float(value)


def build_optimization_setting(args: argparse.Namespace, optimization_setting_class: type[Any]) -> Any:
    """构造 vnpy 优化器需要的 OptimizationSetting。"""
    opt = optimization_setting_class()
    opt.add_parameter("data_dir", str(Path(args.data_dir).resolve()))
    opt.add_parameter("max_hold_num", args.max_hold_num)
    opt.add_parameter("until_win", args.until_win)

    def add_param(name: str, start: float, end: float, step: float) -> None:
        if math.isclose(start, end):
            ok, msg = opt.add_parameter(name, start)
        else:
            ok, msg = opt.add_parameter(name, start, end, step)
        if not ok:
            raise ValueError(f"failed to add parameter {name}: {msg}")

    add_param("price_bemchmark", args.price_start, args.price_end, args.price_step)
    add_param("premium_bemchmark", args.premium_start, args.premium_end, args.premium_step)
    add_param("stock_ratio", args.stock_ratio_start, args.stock_ratio_end, args.stock_ratio_step)
    add_param("premium_ratio", args.premium_ratio_start, args.premium_ratio_end, args.premium_ratio_step)
    add_param("stock_stdevry_bemchmark", args.stdevry_start, args.stdevry_end, args.stdevry_step)
    add_param("max_price", args.max_price_start, args.max_price_end, args.max_price_step)
    add_param("head_count", args.head_count_start, args.head_count_end, args.head_count_step)
    add_param("remain_ratio", args.remain_ratio_start, args.remain_ratio_end, args.remain_ratio_step)
    opt.set_target(args.target)
    return opt


def save_results(output_dir: Path, top_results: list[dict[str, Any]], all_count: int, args: argparse.Namespace) -> None:
    """把优化结果保存为 JSON / CSV。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "run_at": timestamp,
        "target": args.target,
        "total_settings": all_count,
        "top_n": args.top_n,
        "max_workers": args.max_workers,
        "data_dir": str(Path(args.data_dir).resolve()),
        "until_win": args.until_win,
        "max_hold_num": args.max_hold_num,
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
    """CLI 入口：构造参数空间并执行暴力优化。"""
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
            f"head={item.get('head_count')} "
            f"price={item.get('price_bemchmark')} "
            f"premium={item.get('premium_bemchmark')}"
        )
