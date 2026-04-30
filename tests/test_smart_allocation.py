from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys

from vnpy.web.domain.smart_allocation.calculator import calculate_allocation_targets
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
    assert targets.cash_ratio == Decimal("0.05")
    assert targets.options_ratio == Decimal("0.37")
    assert targets.dca_value == Decimal("232000.00")
    assert targets.cash_value == Decimal("20000.00")
    assert targets.options_value == Decimal("148000.00")
    assert targets.qqqm_value == Decimal("69600.00")
    assert targets.voo_value == Decimal("69600.00")
    assert targets.quality_stock_value == Decimal("92800.00")
    assert targets.single_stock_limit == Decimal("23200.00")
    assert targets.wheel_value == Decimal("118400.00")
    assert targets.leaps_value == Decimal("29600.00")
    assert targets.margin_limit == Decimal("100000.00")


def test_calculate_allocation_targets_should_cap_dca_and_raise_cash_without_income() -> None:
    retired = AllocationProfile(age=60, income_status=IncomeStatus.RETIRED)

    targets = calculate_allocation_targets(retired, Decimal("100000"))

    assert targets.dca_ratio == Decimal("0.70")
    assert targets.cash_ratio == Decimal("0.10")
    assert targets.options_ratio == Decimal("0.20")
    assert targets.dca_ratio + targets.cash_ratio + targets.options_ratio == Decimal("1.00")


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
    assert transfers[0].amount == Decimal("2000.00")
    assert sum(item.amount for item in transfers if item.target_bucket == "dca") == Decimal("8000.00")


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
        },
    )

    assert dashboard.targets.dca_value == 232000
    assert dashboard.targets.cash_value == 20000
    assert dashboard.risk_level == "green"
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
        },
    )
    first.record_cashflow_event(profile.id, event_type="leaps_profit_realized", amount=10000)

    second = SmartAllocationService(store=SmartAllocationStore(tmp_path / "smart_allocation.db"))
    dashboard = second.get_dashboard(profile.id)
    events = second.list_cashflow_events(profile.id)

    assert dashboard.profile.id == profile.id
    assert dashboard.snapshot.cash_value == 10000
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
    assert dashboard.targets.cash_value == 20250


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


def test_daily_wheel_recommendation_should_include_pool_sources_and_mrvl(tmp_path: Path) -> None:
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
    by_symbol = {item.symbol: item for item in recommendation.candidates}

    assert recommendation.pool_sources
    assert any(source.name == "系统内置高流动性观察池" for source in recommendation.pool_sources)
    assert "MRVL.US" in by_symbol
    assert by_symbol["MRVL.US"].status == "blocked"
    assert by_symbol["MRVL.US"].estimated_cash_required == 15000
    assert by_symbol["MRVL.US"].blockers
