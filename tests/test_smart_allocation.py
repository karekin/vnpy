from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys

from vnpy.web.domain.smart_allocation.calculator import calculate_allocation_targets
from vnpy.web.domain.smart_allocation.call_spread import build_call_spread_daily_recommendation
from vnpy.web.domain.smart_allocation.classifier import snapshot_from_legacy_portfolio_status
from vnpy.web.domain.smart_allocation.guardrails import run_guardrail_checks
from vnpy.web.domain.smart_allocation.models import (
    AllocationProfile,
    AllocationSnapshot,
    CashflowEvent,
    IncomeStatus,
)
from vnpy.web.domain.smart_allocation.rebalance import generate_recommendations
from vnpy.web.domain.smart_allocation.waterfall import plan_waterfall_transfer
from vnpy.web.domain.smart_allocation.wheel import build_wheel_candidates
from vnpy.web.app import create_app
from vnpy.web.services.smart_allocation_service import SmartAllocationService
from vnpy.web.domain.smart_allocation.store import SmartAllocationStore


def test_calculate_allocation_targets_should_match_400k_reference_case() -> None:
    profile = AllocationProfile(age=38, income_status=IncomeStatus.STABLE)

    targets = calculate_allocation_targets(profile, Decimal("400000"))

    assert targets.dca_ratio == Decimal("0.58")
    assert targets.cash_ratio == Decimal("0.17")
    assert targets.options_ratio == Decimal("0.25")
    assert targets.dca_value == Decimal("232000.00")
    assert targets.cash_value == Decimal("68000.00")
    assert targets.options_value == Decimal("100000.00")
    assert targets.qqqm_value == Decimal("69600.00")
    assert targets.voo_value == Decimal("69600.00")
    assert targets.quality_stock_value == Decimal("92800.00")
    assert targets.single_stock_limit == Decimal("23200.00")
    assert targets.wheel_value == Decimal("60000.00")
    assert targets.leaps_value == Decimal("40000.00")
    assert targets.margin_limit == Decimal("100000.00")


def test_calculate_allocation_targets_should_cap_dca_and_raise_cash_without_income() -> None:
    retired = AllocationProfile(age=60, income_status=IncomeStatus.RETIRED)

    targets = calculate_allocation_targets(retired, Decimal("100000"))

    assert targets.dca_ratio == Decimal("0.70")
    assert targets.cash_ratio == Decimal("0.15")
    assert targets.options_ratio == Decimal("0.15")
    assert targets.dca_ratio + targets.cash_ratio + targets.options_ratio == Decimal("1.00")


def test_calculate_allocation_targets_should_cap_young_stable_options() -> None:
    profile = AllocationProfile(age=28, income_status=IncomeStatus.STABLE)

    targets = calculate_allocation_targets(profile, Decimal("100000"))

    assert targets.dca_ratio == Decimal("0.48")
    assert targets.cash_ratio == Decimal("0.27")
    assert targets.options_ratio == Decimal("0.25")
    assert targets.wheel_value == Decimal("15000.00")
    assert targets.leaps_value == Decimal("10000.00")


def test_guardrails_should_flag_concentration_margin_and_leaps_discipline() -> None:
    profile = AllocationProfile(age=38, income_status=IncomeStatus.STABLE)
    targets = calculate_allocation_targets(profile, Decimal("400000"))
    snapshot = AllocationSnapshot(
        total_equity=Decimal("400000"),
        cash_value=Decimal("12000"),
        dca_value=Decimal("260000"),
        options_value=Decimal("128000"),
        wheel_value=Decimal("110000"),
        leaps_value=Decimal("18000"),
        margin_used=Decimal("120000"),
        single_stock_values={"NVDA.US": Decimal("30000")},
        latest_rsi_by_symbol={"NVDA.US": Decimal("44")},
        open_leaps_symbols=["NVDA.US"],
    )

    violations = run_guardrail_checks(profile, snapshot, targets)
    codes = {item.rule_code for item in violations}

    assert "single_stock_limit" in codes
    assert "margin_limit" in codes
    assert "leaps_rsi_discipline" in codes
    assert any(item.blocking for item in violations if item.rule_code == "margin_limit")


def test_guardrails_should_not_flag_index_etf_concentration() -> None:
    profile = AllocationProfile(age=38, income_status=IncomeStatus.STABLE)
    targets = calculate_allocation_targets(profile, Decimal("100000"))
    snapshot = AllocationSnapshot(
        total_equity=Decimal("100000"),
        cash_value=Decimal("5000"),
        dca_value=Decimal("48000"),
        options_value=Decimal("47000"),
        single_stock_values={"VOO.US": Decimal("30000"), "QQQ.US": Decimal("20000")},
    )

    violations = run_guardrail_checks(profile, snapshot, targets)

    assert "single_stock_limit" not in {item.rule_code for item in violations}


def test_rebalance_should_trigger_when_deviation_reaches_threshold() -> None:
    profile = AllocationProfile(age=38, income_status=IncomeStatus.STABLE)
    targets = calculate_allocation_targets(profile, Decimal("400000"))
    snapshot = AllocationSnapshot(
        total_equity=Decimal("400000"),
        cash_value=Decimal("0"),
        dca_value=Decimal("250000"),
        options_value=Decimal("150000"),
    )

    recommendations = generate_recommendations(profile, snapshot, targets)

    assert any(item.recommendation_type == "top_up_cash" for item in recommendations)


def test_waterfall_should_top_up_cash_before_dca_injection() -> None:
    profile = AllocationProfile(age=38, income_status=IncomeStatus.STABLE)
    targets = calculate_allocation_targets(profile, Decimal("400000"))
    snapshot = AllocationSnapshot(
        total_equity=Decimal("400000"),
        cash_value=Decimal("18000"),
        dca_value=Decimal("232000"),
        options_value=Decimal("150000"),
    )
    event = CashflowEvent(event_type="leaps_profit_realized", amount=Decimal("10000"))

    transfers = plan_waterfall_transfer(profile, snapshot, targets, event)

    assert transfers[0].target_bucket == "cash"
    assert transfers[0].amount == Decimal("10000")
    assert sum(item.amount for item in transfers if item.target_bucket == "dca") == Decimal("0")


def test_smart_allocation_service_should_build_dashboard_from_manual_snapshot(tmp_path: Path) -> None:
    service = SmartAllocationService(store=SmartAllocationStore(tmp_path / "smart_allocation.db"))
    profile = service.create_profile(age=38, income_status="stable")
    dashboard = service.refresh_snapshot(
        profile.id,
        {
            "total_equity": 400000,
            "cash_value": 20000,
            "dca_value": 232000,
            "options_value": 148000,
            "wheel_value": 118400,
            "leaps_value": 29600,
            "source_inputs": {"hsbcTotalHkd": "144367.35", "schwabNetLiquidationUsd": "9027.61"},
        },
    )

    assert dashboard.targets.dca_value == 232000
    assert dashboard.targets.cash_value == 68000
    assert dashboard.snapshot.source_inputs["hsbcTotalHkd"] == "144367.35"
    assert dashboard.risk_level == "orange"
    events = service.list_cashflow_events(profile.id)
    assert events[0].event_type == "snapshot_waterfall_audit"
    assert events[0].source_bucket == "system"


def test_legacy_portfolio_status_should_convert_to_smart_allocation_snapshot() -> None:
    profile = AllocationProfile(
        age=38,
        income_status=IncomeStatus.STABLE,
        quality_stock_symbols=("NVDA.US",),
        wheel_symbols=("TSLA.US",),
        leaps_symbols=("AAPL.US",),
    )
    payload = {
        "total_capital": 400000,
        "available_cash": 20000,
        "positions": [
            {"symbol": "QQQM.US", "quantity": 10, "value": 69600},
            {"symbol": "VOO.US", "quantity": 10, "value": 69600},
            {"symbol": "NVDA.US", "quantity": 10, "value": 92800},
            {"symbol": "TSLA.US", "quantity": 1, "value": 118400},
            {"symbol": "AAPL.US", "quantity": 1, "value": 29600},
        ],
    }

    snapshot = snapshot_from_legacy_portfolio_status(profile, payload)

    assert snapshot.total_equity == Decimal("400000")
    assert snapshot.cash_value == Decimal("20000")
    assert snapshot.dca_value == Decimal("232000")
    assert snapshot.options_value == Decimal("148000")
    assert snapshot.wheel_value == Decimal("118400")
    assert snapshot.leaps_value == Decimal("29600")


def test_smart_allocation_routes_should_be_registered_on_vnpy_web_app() -> None:
    app = create_app()

    paths = {route.path for route in app.routes}

    assert "/api/v1/smart-allocation/dashboard" in paths
    assert "/api/v1/smart-allocation/profiles/{profile_id}" in paths
    assert "/api/v1/smart-allocation/profiles/{profile_id}/activate" in paths
    assert "/api/v1/smart-allocation/snapshots/import/legacy-position-manager" in paths
    assert "/api/v1/smart-allocation/guardrails/events" in paths
    assert "/api/v1/smart-allocation/cashflow/events" in paths
    assert "/api/v1/smart-allocation/recommendations/{recommendation_id}/ignore" in paths
    assert "/api/v1/smart-allocation/leaps/candidates/refresh" in paths
    assert "/api/v1/smart-allocation/wheel/candidates/refresh" in paths
    assert "/api/v1/smart-allocation/wheel/daily-recommendations/refresh" in paths
    assert "/api/v1/smart-allocation/call-spread/daily-recommendations/refresh" in paths


def test_smart_allocation_store_should_persist_profile_snapshot_and_cashflow(tmp_path: Path) -> None:
    store = SmartAllocationStore(tmp_path / "smart_allocation.db")
    first = SmartAllocationService(store=store)
    profile = first.create_profile(age=38, income_status="stable", quality_stock_symbols=["NVDA.US"])
    first.refresh_snapshot(
        profile.id,
        {
            "total_equity": 400000,
            "cash_value": 0,
            "dca_value": 232000,
            "options_value": 168000,
            "source_inputs": {"hkdUsdRate": "7.8352"},
        },
    )
    first.record_cashflow_event(profile.id, event_type="leaps_profit_realized", amount=10000)

    second = SmartAllocationService(store=SmartAllocationStore(tmp_path / "smart_allocation.db"))
    dashboard = second.get_dashboard(profile.id)
    events = second.list_cashflow_events(profile.id)

    assert dashboard.profile.id == profile.id
    assert dashboard.snapshot.cash_value == 10000
    assert dashboard.snapshot.source_inputs["hkdUsdRate"] == "7.8352"
    assert events[0].event_type == "leaps_profit_realized"
    assert any(item.event_type == "snapshot_waterfall_audit" for item in events)


def test_cashflow_event_should_move_snapshot_forward(tmp_path: Path) -> None:
    service = SmartAllocationService(store=SmartAllocationStore(tmp_path / "smart_allocation.db"))
    profile = service.create_profile(age=38, income_status="stable")
    service.refresh_snapshot(
        profile.id,
        {
            "total_equity": 400000,
            "cash_value": 10000,
            "dca_value": 232000,
            "options_value": 158000,
            "wheel_value": 128000,
            "leaps_value": 30000,
        },
    )

    transfers = service.record_cashflow_event(profile.id, event_type="wheel_premium_received", amount=5000)
    dashboard = service.get_dashboard(profile.id)

    assert transfers[0].target_bucket == "cash"
    assert dashboard.snapshot.cash_value == 15000
    assert dashboard.snapshot.total_equity == 405000
    assert dashboard.targets.cash_value == 68850


def test_recommendation_status_should_persist(tmp_path: Path) -> None:
    service = SmartAllocationService(store=SmartAllocationStore(tmp_path / "smart_allocation.db"))
    profile = service.create_profile(age=38, income_status="stable")
    service.refresh_snapshot(
        profile.id,
        {
            "total_equity": 400000,
            "cash_value": 0,
            "dca_value": 232000,
            "options_value": 168000,
        },
    )
    recommendations = service.list_recommendations(profile.id)

    updated = service.set_recommendation_status(
        profile.id,
        recommendations[0].id,
        status="ignored",
        user_note="手动延后",
    )

    assert updated[0].status == "ignored"
    restored = SmartAllocationService(store=SmartAllocationStore(tmp_path / "smart_allocation.db"))
    assert restored.list_recommendations(profile.id)[0].user_note == "手动延后"


def test_profile_update_and_activation_should_persist(tmp_path: Path) -> None:
    store = SmartAllocationStore(tmp_path / "smart_allocation.db")
    service = SmartAllocationService(store=store)
    first = service.create_profile(age=38, income_status="stable")
    second = service.create_profile(age=45, income_status="retired")

    service.update_profile(first.id, age=39, income_status="unstable", quality_stock_symbols=["MSFT.US"])
    activated = service.activate_profile(first.id)

    restored = SmartAllocationService(store=SmartAllocationStore(tmp_path / "smart_allocation.db"))
    dashboard = restored.get_dashboard()

    assert second.id != activated.id
    assert activated.id == first.id
    assert activated.age == 39
    assert dashboard.profile.id == first.id
    assert dashboard.profile.income_status == "unstable"
    assert dashboard.profile.quality_stock_symbols == ["MSFT.US"]


def test_default_profile_should_use_empty_account_onboarding_age(tmp_path: Path) -> None:
    service = SmartAllocationService(store=SmartAllocationStore(tmp_path / "smart_allocation.db"))

    dashboard = service.get_dashboard()

    assert dashboard.profile.age == 28


def test_smart_allocation_should_not_require_legacy_package(tmp_path: Path) -> None:
    sys.modules.pop("backend", None)
    service = SmartAllocationService(store=SmartAllocationStore(tmp_path / "smart_allocation.db"))

    dashboard = service.get_dashboard()

    assert dashboard.profile.age == 28
    assert dashboard.snapshot.total_equity == 0
    assert dashboard.targets.dca_value == 0
    assert "backend" not in sys.modules


def test_wheel_candidates_should_explain_source_and_blockers() -> None:
    profile = AllocationProfile(
        age=38,
        income_status=IncomeStatus.STABLE,
        quality_stock_symbols=("MSFT.US",),
        wheel_symbols=("AAPL.US",),
    )
    targets = calculate_allocation_targets(profile, Decimal("100000"))
    snapshot = AllocationSnapshot(
        total_equity=Decimal("100000"),
        cash_value=Decimal("5000"),
        dca_value=Decimal("58000"),
        options_value=Decimal("37000"),
        wheel_value=Decimal("28000"),
        single_stock_values={"NVDA.US": Decimal("30000")},
    )

    candidates = build_wheel_candidates(profile, snapshot, targets)
    by_symbol = {item.symbol: item for item in candidates}

    assert by_symbol["AAPL.US"].source == "手动 Wheel 候选池"
    assert by_symbol["AAPL.US"].estimated_cash_required == Decimal("20000")
    assert by_symbol["NVDA.US"].status == "blocked"
    assert by_symbol["NVDA.US"].blockers


def test_smart_allocation_service_should_list_wheel_candidates(tmp_path: Path) -> None:
    service = SmartAllocationService(store=SmartAllocationStore(tmp_path / "smart_allocation.db"))
    profile = service.create_profile(age=38, income_status="stable", wheel_symbols=["AAPL.US"])
    service.refresh_snapshot(
        profile.id,
        {
            "total_equity": 100000,
            "cash_value": 5000,
            "dca_value": 58000,
            "options_value": 37000,
            "wheel_value": 0,
        },
    )

    candidates = service.list_wheel_candidates(profile.id)

    assert candidates
    assert any(item.symbol == "AAPL.US" for item in candidates)
    assert candidates[0].score >= candidates[-1].score


def test_service_should_skip_reference_fixture_active_profile(tmp_path: Path) -> None:
    db_path = tmp_path / "smart_allocation.db"
    service = SmartAllocationService(store=SmartAllocationStore(db_path))
    real_profile = service.create_profile(age=28, income_status="stable")
    service.refresh_snapshot(
        real_profile.id,
        {
            "total_equity": 12550.56,
            "cash_value": 3045.87,
            "dca_value": 9504.69,
            "options_value": 0,
            "wheel_value": 0,
            "leaps_value": 0,
            "single_stock_values": {
                "NVDA.US": 1043.1,
                "DRAM.US": 111.9,
                "UCO.US": 427.9,
            },
        },
    )
    fixture_profile = service.create_profile(age=38, income_status="stable")
    service.refresh_snapshot(
        fixture_profile.id,
        {
            "total_equity": 400000,
            "cash_value": 20000,
            "dca_value": 232000,
            "options_value": 148000,
            "wheel_value": 118400,
            "leaps_value": 29600,
        },
    )

    restored = SmartAllocationService(store=SmartAllocationStore(db_path))
    dashboard = restored.get_dashboard()

    assert dashboard.profile.id == real_profile.id
    assert dashboard.profile.age == 28
    assert dashboard.snapshot.total_equity == 12550.56
    assert dashboard.snapshot_source == "persistent"
    assert dashboard.data_warnings == []


def test_daily_wheel_recommendation_should_hide_unaffordable_blocked_symbols(tmp_path: Path) -> None:
    service = SmartAllocationService(store=SmartAllocationStore(tmp_path / "smart_allocation.db"))
    profile = service.create_profile(age=28, income_status="stable")
    service.refresh_snapshot(
        profile.id,
        {
            "total_equity": 12550.56,
            "cash_value": 3045.87,
            "dca_value": 9504.69,
            "options_value": 0,
            "wheel_value": 0,
            "leaps_value": 0,
        },
    )

    recommendation = service.get_daily_wheel_recommendation(profile.id)
    all_candidates = service.list_wheel_candidates(profile.id)
    by_symbol = {item.symbol: item for item in all_candidates}

    assert recommendation.pool_sources
    assert any(source.name == "系统内置高流动性观察池" for source in recommendation.pool_sources)
    assert recommendation.candidates == []
    assert recommendation.candidate_count == 0
    assert recommendation.actionable_count == 0
    assert "MRVL.US" in by_symbol
    assert by_symbol["MRVL.US"].status == "blocked"
    assert by_symbol["MRVL.US"].estimated_cash_required == 15000
    assert by_symbol["MRVL.US"].blockers


def test_call_spread_recommendation_should_use_budget_and_option_chain() -> None:
    profile = AllocationProfile(
        age=28,
        income_status=IncomeStatus.STABLE,
        quality_stock_symbols=("PLTR.US",),
    )
    snapshot = AllocationSnapshot(
        total_equity=Decimal("12550.56"),
        cash_value=Decimal("4500"),
        dca_value=Decimal("8050.56"),
        options_value=Decimal("0"),
        wheel_value=Decimal("0"),
        leaps_value=Decimal("0"),
        single_stock_values={"NVDA.US": Decimal("1043.10")},
    )
    targets = calculate_allocation_targets(profile, snapshot.total_equity)
    expiration = (date.today() + timedelta(days=30)).isoformat()

    recommendation = build_call_spread_daily_recommendation(
        profile,
        snapshot,
        targets,
        option_summaries={
            "PLTR": {
                "underlying_price": Decimal("137.97"),
                "selection_score": Decimal("81.28"),
                "flow_sentiment": "bullish",
            }
        },
        option_chains={
            "PLTR": [
                {
                    "expiration_date": expiration,
                    "contract_symbol": "PLTR260515C00140000",
                    "strike": Decimal("140"),
                    "bid": Decimal("7.20"),
                    "ask": Decimal("7.40"),
                    "volume": 8000,
                    "open_interest": 12000,
                    "underlying_price": Decimal("137.97"),
                },
                {
                    "expiration_date": expiration,
                    "contract_symbol": "PLTR260515C00160000",
                    "strike": Decimal("160"),
                    "bid": Decimal("1.88"),
                    "ask": Decimal("2.00"),
                    "volume": 6000,
                    "open_interest": 20000,
                    "underlying_price": Decimal("137.97"),
                },
            ]
        },
    )
    by_symbol = {item.symbol: item for item in recommendation.candidates}

    assert recommendation.options_available > Decimal("0")
    assert recommendation.per_trade_limit == Decimal("555.68")
    assert by_symbol["PLTR.US"].status == "candidate"
    assert by_symbol["PLTR.US"].long_strike == Decimal("140")
    assert by_symbol["PLTR.US"].short_strike == Decimal("160")
    assert by_symbol["PLTR.US"].max_loss == Decimal("552.00")
    assert by_symbol["PLTR.US"].max_contracts == 1
