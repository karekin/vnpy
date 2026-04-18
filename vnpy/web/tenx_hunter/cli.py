from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import load_settings
from .pipeline import bootstrap_real_data, bootstrap_sample_data, ensure_schema, fetch_ads_preview, reset_all, run_all


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TenX Hunter ODS→ADS pipeline CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("help", help="Show this help message")
    subparsers.add_parser("bootstrap", help="Load bundled sample ODS/DIM data")
    subparsers.add_parser("bootstrap-real", help="Fetch live SEC + Polygon/yfinance data into ODS/DIM")
    subparsers.add_parser("run-all", help="Build DWD -> DWS -> ADS from current ODS data")
    subparsers.add_parser("demo", help="bootstrap sample + run-all + show-ads")
    subparsers.add_parser("demo-real", help="bootstrap real sources + run-all + show-ads")
    subparsers.add_parser("show-ads", help="Print ADS preview as JSON")
    subparsers.add_parser("reset", help="Truncate all schemas in the demo database")
    subparsers.add_parser("migrate-ods", help="Sync existing PostgreSQL ODS schema to the latest design")
    subparsers.add_parser("test", help="Run unit tests inside the container")
    return parser


def _print_runtime_settings() -> None:
    settings = load_settings()
    selected_universe = settings.market_universes[settings.default_market]
    payload = {
        "default_market": settings.default_market,
        "universe_name": selected_universe.name,
        "universe_strategy": selected_universe.strategy,
        "universe_bucket_labels": [bucket.label for bucket in selected_universe.buckets],
        "real_symbols_source": settings.real_symbols_source,
        "real_symbols": selected_universe.symbols,
        "price_provider": settings.price_provider,
        "price_start_date": settings.price_start_date,
        "price_end_date": settings.price_end_date,
        "sec_user_agent": settings.sec_user_agent,
        "include_yfinance_supplement": settings.include_yfinance_supplement,
        "polygon_api_key_present": bool(settings.polygon_api_key),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _show_ads() -> None:
    settings = load_settings()
    preview = fetch_ads_preview(settings)
    print(json.dumps(preview, ensure_ascii=False, indent=2, default=str))


def _bootstrap_sample() -> None:
    settings = load_settings()
    bootstrap_sample_data(settings, reset=True)
    print("bootstrap complete")


def _bootstrap_real() -> None:
    settings = load_settings()
    _print_runtime_settings()
    bootstrap_real_data(settings, reset=True, market=settings.default_market)
    print("bootstrap-real complete")


def _run_all() -> None:
    settings = load_settings()
    run_all(settings)
    print("run-all complete")


def _demo_sample() -> None:
    settings = load_settings()
    bootstrap_sample_data(settings, reset=True)
    run_all(settings)
    preview = fetch_ads_preview(settings)
    print(json.dumps(preview, ensure_ascii=False, indent=2, default=str))


def _demo_real() -> None:
    settings = load_settings()
    _print_runtime_settings()
    bootstrap_real_data(settings, reset=True, market=settings.default_market)
    run_all(settings)
    preview = fetch_ads_preview(settings)
    print(json.dumps(preview, ensure_ascii=False, indent=2, default=str))


def _reset() -> None:
    settings = load_settings()
    reset_all(settings)
    print("reset complete")


def _migrate_ods() -> None:
    settings = load_settings()
    ensure_schema(settings)
    print("migrate-ods complete")


def _test() -> None:
    import unittest

    suite = unittest.defaultTestLoader.discover(str(_repo_root() / "tests"), pattern="test_tenx*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    command = args.command or "help"

    if command == "help":
        parser.print_help()
        return 0
    if command == "bootstrap":
        _bootstrap_sample()
        return 0
    if command == "bootstrap-real":
        _bootstrap_real()
        return 0
    if command == "run-all":
        _run_all()
        return 0
    if command == "demo":
        _demo_sample()
        return 0
    if command == "demo-real":
        _demo_real()
        return 0
    if command == "show-ads":
        _show_ads()
        return 0
    if command == "reset":
        _reset()
        return 0
    if command == "migrate-ods":
        _migrate_ods()
        return 0
    if command == "test":
        _test()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
