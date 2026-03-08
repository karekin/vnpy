from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd

from vnpy.web import app as web_app
from vnpy.web.core import cb_backtest
from vnpy.web.core.cb_backtest import cli as phase_a_cli
from vnpy.web.core.cb_backtest import backtest as phase_a_backtest
from vnpy.web.services.cb_backtest_service import CbBacktestService
from vnpy.web.services.cb_history_service import CbHistoryService


def test_backtest_service_should_load_integrated_cb_backtest_core() -> None:
    backtest_service = CbBacktestService()
    module = backtest_service._load_module()

    assert module is cb_backtest
    assert hasattr(module, "build_candidates")
    assert hasattr(module, "run_backtest")


def test_cb_backtest_core_cli_should_load_snapshots_from_db(tmp_path: Path) -> None:
    data_root = tmp_path / "cb_quant"
    store_dir = data_root / "_cb_quant"
    store_dir.mkdir(parents=True, exist_ok=True)
    backtest_service = CbBacktestService(data_dir=data_root)
    history_store = backtest_service._history_store
    history_store.upsert_snapshot_rows(
        trade_date="2024-02-01",
        source="unit-test",
        rows=[
            {
                "bond_code": "110001",
                "bond_name": "CB-ONE",
                "close_price": 101.0,
                "conversion_premium_pct": 12.5,
                "bond_pure_value_ratio": 1.2,
                "is_listed": True,
                "was_listed_prev_day": True,
                "is_redeem_triggered": False,
                "put_status": "not_reached",
                "days_to_maturity": 200,
                "listing_date": "2024-01-01",
                "legacy_only_field": "should-be-dropped",
            }
        ],
    )

    dataset = phase_a_cli.load_market_data(data_root)
    assert len(dataset) == 1
    assert dataset[0][0] == "2024-02-01"
    frame = dataset[0][1]
    assert "data_source" in frame.columns
    assert "legacy_only_field" not in frame.columns


def test_cb_backtest_core_should_share_same_backtest_core_for_candidates(monkeypatch) -> None:
    dataset = [
        (
            "2024-02-01",
            pd.DataFrame(
                [
                    {"bond_code": "110001", "close_price": 100.0, "is_redeem_triggered": False},
                    {"bond_code": "110002", "close_price": 102.0, "is_redeem_triggered": False},
                ]
            ).set_index("bond_code", drop=False),
        ),
        (
            "2024-02-02",
            pd.DataFrame(
                [
                    {"bond_code": "110001", "close_price": 101.0, "is_redeem_triggered": False},
                    {"bond_code": "110002", "close_price": 103.0, "is_redeem_triggered": False},
                ]
            ).set_index("bond_code", drop=False),
        ),
    ]

    def fake_build_candidates(df_all, _trade_date, _strategy_parameters, _candidate_count):
        return df_all.reset_index(drop=True)[["bond_code", "close_price"]]

    monkeypatch.setattr(phase_a_backtest, "build_candidates", fake_build_candidates)

    candidate_map = {
        "2024-02-01": ["110001", "110002"],
        "2024-02-02": ["110001", "110002"],
    }
    setting = {"max_hold_count": 2, "rebalance_interval_type": "trade_day", "rebalance_interval_value": 1}

    cli_stats = phase_a_backtest.run_backtest(
        dataset=dataset,
        strategy_parameters=cb_backtest.build_strategy_parameters({}),
        runtime_config=cb_backtest.build_runtime_config({"candidate_count": 2, "max_hold_count": 2}),
    )
    optimize_stats = phase_a_backtest.run_backtest_from_candidates(
        dataset=dataset,
        candidate_code_map=candidate_map,
        runtime_config=cb_backtest.build_runtime_config(setting),
    )

    assert optimize_stats["total_return_pct"] == cli_stats["total_return_pct"]
    assert optimize_stats["max_drawdown_pct"] == cli_stats["max_drawdown_pct"]
    assert optimize_stats["trade_count"] == cli_stats["trade_count"]
    assert optimize_stats["win_rate_pct"] == cli_stats["win_rate_pct"]


def test_history_bootstrap_should_use_cb_backtest_core_loader(monkeypatch, tmp_path: Path) -> None:
    service = object.__new__(CbHistoryService)
    backtest_service = CbBacktestService(data_dir=tmp_path)
    service._store = backtest_service._history_store

    inserted = service.bootstrap_from_crawler_snapshots()

    assert inserted == 0
    latest_log = service._store.latest_sync_log()
    assert latest_log is not None
    assert latest_log.mode == "bootstrap"
    assert "legacy excel snapshots has been removed" in latest_log.message


def test_app_lifespan_should_not_call_legacy_bootstrap(monkeypatch) -> None:
    calls: list[str] = []

    class ImmediateThread:
        def __init__(self, *, target, name, daemon):
            self._target = target

        def start(self) -> None:
            self._target()

    monkeypatch.setattr(web_app, "Thread", ImmediateThread)
    monkeypatch.setattr(
        web_app.cb_history_service,
        "sync_today_from_market",
        lambda *, mode="manual": calls.append(f"sync:{mode}") or 0,
    )
    monkeypatch.setattr(
        web_app.cb_history_service,
        "start_scheduler",
        lambda: calls.append("start_scheduler"),
    )
    monkeypatch.setattr(
        web_app.cb_history_service,
        "stop_scheduler",
        lambda: calls.append("stop_scheduler"),
    )
    monkeypatch.setattr(
        web_app.cb_history_service,
        "bootstrap_from_crawler_snapshots",
        lambda: calls.append("bootstrap"),
    )

    async def run_lifespan() -> None:
        async with web_app._lifespan(None):
            assert "bootstrap" not in calls
            assert "sync:startup" in calls
            assert "start_scheduler" in calls

    asyncio.run(run_lifespan())
    assert "stop_scheduler" in calls
