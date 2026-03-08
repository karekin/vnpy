from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd

from vnpy.web import app as web_app
from vnpy.web.adapters.crawler_phase_a_adapter import CrawlerPhaseABacktestAdapter
from vnpy.web.domain.cb_quant import cb_strategy_core
from vnpy.web.domain.cb_quant.cb_strategy_core import cli as phase_a_cli
from vnpy.web.domain.cb_quant.cb_strategy_core import backtest as phase_a_backtest
from vnpy.web.services.cb_history_service import CbHistoryService


def test_adapter_should_load_integrated_cb_strategy_core() -> None:
    adapter = CrawlerPhaseABacktestAdapter()
    module = adapter._load_module()

    assert module is cb_strategy_core
    assert hasattr(module, "build_candidates")
    assert hasattr(module, "run_backtest")


def test_cb_strategy_core_cli_should_load_snapshots_from_db(tmp_path: Path) -> None:
    data_root = tmp_path / "cb_quant"
    store_dir = data_root / "_cb_quant"
    store_dir.mkdir(parents=True, exist_ok=True)
    adapter = CrawlerPhaseABacktestAdapter(data_dir=data_root)
    history_store = adapter._history_store
    history_store.upsert_snapshot_rows(
        trade_date="2024-02-01",
        source="unit-test",
        rows=[
            {
                "cb_code": "110001",
                "cb_name": "CB-ONE",
                "price": 101.0,
                "premium_rate": 12.5,
                "cb_to_pb": 1.2,
                "is_unlist": "N",
                "last_is_unlist": "N",
                "is_ransom_flag": "False",
                "date_return_distance": "未到",
                "date_remain_distance": "200天",
                "issue_date": "2024-01-01",
                "legacy_only_field": "should-be-dropped",
            }
        ],
    )

    dataset = phase_a_cli.load_market_data(data_root)
    assert len(dataset) == 1
    assert dataset[0][0] == "2024-02-01"
    frame = dataset[0][1]
    assert "market_source" in frame.columns
    assert "legacy_only_field" not in frame.columns


def test_cb_strategy_core_should_share_same_backtest_core_for_candidates(monkeypatch) -> None:
    dataset = [
        (
            "2024-02-01",
            pd.DataFrame(
                [
                    {"cb_code": "110001", "price": 100.0, "is_ransom_flag": "False"},
                    {"cb_code": "110002", "price": 102.0, "is_ransom_flag": "False"},
                ]
            ).set_index("cb_code", drop=False),
        ),
        (
            "2024-02-02",
            pd.DataFrame(
                [
                    {"cb_code": "110001", "price": 101.0, "is_ransom_flag": "False"},
                    {"cb_code": "110002", "price": 103.0, "is_ransom_flag": "False"},
                ]
            ).set_index("cb_code", drop=False),
        ),
    ]

    def fake_build_candidates(df_all, _trade_date, _cfg, _head_count):
        return df_all.reset_index(drop=True)[["cb_code", "price"]]

    monkeypatch.setattr(phase_a_backtest, "build_candidates", fake_build_candidates)

    candidate_map = {
        "2024-02-01": ["110001", "110002"],
        "2024-02-02": ["110001", "110002"],
    }
    setting = {"max_hold_num": 2, "rebalance_frequency_type": "trade_day", "rebalance_frequency_value": 1}

    cli_stats = phase_a_backtest.run_backtest(
        dataset=dataset,
        cfg={},
        head_count=2,
        max_hold_num=2,
        until_win=False,
    )
    optimize_stats = phase_a_backtest.run_backtest_from_candidates(
        dataset=dataset,
        candidate_code_map=candidate_map,
        setting=setting,
    )

    assert optimize_stats["total_return_pct"] == cli_stats["total_return_pct"]
    assert optimize_stats["max_drawdown_pct"] == cli_stats["max_drawdown_pct"]
    assert optimize_stats["trade_count"] == cli_stats["trade_count"]
    assert optimize_stats["win_rate_pct"] == cli_stats["win_rate_pct"]


def test_history_bootstrap_should_use_cb_strategy_core_loader(monkeypatch, tmp_path: Path) -> None:
    service = object.__new__(CbHistoryService)
    adapter = CrawlerPhaseABacktestAdapter(data_dir=tmp_path)
    service._adapter = adapter
    service._store = adapter._history_store

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
