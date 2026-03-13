from __future__ import annotations

import argparse
import cProfile
from datetime import date
from pathlib import Path
import pstats
from typing import Any

from vnpy.web.services.cb_quant_service import CbQuantService, _evaluate_combo_payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile CB Quant optimize hotspots.")
    parser.add_argument("--template-id", default="", help="Template id to profile. Defaults to first active template.")
    parser.add_argument("--window", default="1y", help="Backtest window, e.g. 1w/1y/3y/full.")
    parser.add_argument("--combo-limit", type=int, default=3, help="Number of combos to profile.")
    parser.add_argument("--day-limit", type=int, default=60, help="Only keep the latest N trade days.")
    parser.add_argument("--output", default="", help="Profile report output path.")
    parser.add_argument("--start-date", default="", help="Optional ISO start date.")
    parser.add_argument("--end-date", default="", help="Optional ISO end date.")
    return parser.parse_args()


def _pick_template_id(service: CbQuantService, template_id: str) -> str:
    if template_id:
        return template_id
    for row in service._templates:
        if row.status == "active":
            return row.id
    if not service._templates:
        raise RuntimeError("no templates available for profiling")
    return service._templates[0].id


def _build_settings(service: CbQuantService, *, template_id: str, combo_limit: int) -> list[tuple[str, dict[str, Any]]]:
    combos: list[tuple[str, dict[str, Any]]] = []
    for combo_id, setting in service._iter_template_settings(template_id=template_id, limit=max(1, combo_limit)):
        combos.append((combo_id, setting))
    if not combos:
        raise RuntimeError(f"template has no combos to profile: {template_id}")
    return combos


def _slice_latest_days(dataset: list[tuple[str, Any]], day_limit: int) -> list[tuple[str, Any]]:
    safe_limit = max(1, int(day_limit))
    if len(dataset) <= safe_limit:
        return dataset
    return dataset[-safe_limit:]


def _parse_iso_date(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    return date.fromisoformat(text)


def main() -> None:
    args = _parse_args()
    service = CbQuantService(recover_runtime_state=False)
    template_id = _pick_template_id(service, args.template_id)
    combos = _build_settings(service, template_id=template_id, combo_limit=args.combo_limit)

    dataset = service._backtest_service.load_market_data()
    dataset = _slice_latest_days(dataset, args.day_limit)
    start_date = _parse_iso_date(args.start_date)
    end_date = _parse_iso_date(args.end_date)
    window_dataset_map = service._prepare_window_dataset_map(
        dataset=dataset,
        windows=[args.window],
        start_date=start_date,
        end_date=end_date,
    )
    base_dataset = service._resolve_base_dataset_for_windows(
        dataset=dataset,
        windows=[args.window],
        window_dataset_map=window_dataset_map,
    )
    task_config = {
        "initial_capital_wan": 100.0,
        "benchmark_name": "转债等权",
        "rebalance_interval_type": "trade_day",
        "rebalance_interval_value": 1,
        "max_position_pct": 20.0,
        "max_hold_count": 12,
        "exclude_redeem_days_below": None,
        "take_profit_pct": None,
        "stop_loss_pct": None,
    }

    profiler = cProfile.Profile()
    profiler.enable()
    prepared_pool_map = service._prepare_candidate_pool_map(dataset=base_dataset)
    for combo_id, setting in combos:
        _evaluate_combo_payload(
            task_id="PROFILE",
            template_id=template_id,
            template_name=template_id,
            dataset=dataset,
            combo_id=combo_id,
            windows=[args.window],
            start_date=start_date,
            end_date=end_date,
            setting=setting,
            window_dataset_map=window_dataset_map,
            prepared_pool_map=prepared_pool_map,
            task_config=task_config,
        )
    profiler.disable()

    default_dir = Path(getattr(service, "_runtime_config").profiling.output_dir)
    output_path = Path(args.output).expanduser() if args.output else default_dir / "cbq_optimize_profile.txt"
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        stats = pstats.Stats(profiler, stream=handle).sort_stats("cumulative")
        stats.print_stats(80)

    print(f"profile written to {output_path}")
    print(f"template={template_id}, combos={len(combos)}, days={len(dataset)}, window={args.window}")


if __name__ == "__main__":
    main()
