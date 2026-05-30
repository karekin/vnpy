from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

from vnpy.web.contracts.investment_copilot import (
    InvestmentCopilotActionDecisionRequest,
    InvestmentCopilotActionPreflightRequest,
    InvestmentCopilotInvestorPolicy,
    InvestmentLedgerAccountRequest,
    InvestmentLedgerBootstrapRequest,
    InvestmentLedgerCashflowRequest,
    InvestmentLedgerCsvImportRequest,
    InvestmentLedgerHoldingRequest,
)
from vnpy.web.domain.investment_copilot.store import InvestmentCopilotStore
from vnpy.web.app import create_app
from vnpy.web.services.investment_copilot_service import InvestmentCopilotService


class _AllocationService:
    def get_dashboard(self):
        return SimpleNamespace(
            health_score=72,
            risk_level="orange",
            snapshot=SimpleNamespace(
                total_equity=100_000,
                cash_value=2_000,
                options_value=30_000,
                margin_used=12_000,
            ),
            targets=SimpleNamespace(
                cash_value=17_000,
                options_value=25_000,
                margin_limit=25_000,
            ),
            guardrails=[
                SimpleNamespace(message="现金仓位偏离目标超过阈值。", blocking=False),
            ],
        )


class _TenxService:
    def get_workspace_snapshot(self, market: str):
        assert market == "US"
        return SimpleNamespace(
            market="US",
            universe="US Growth Hunt",
            snapshot_at="2026-05-15 10:00 UTC",
            candidates=[
                SimpleNamespace(
                    symbol="NVDA",
                    name="NVIDIA",
                    score=91,
                    risk_level="medium",
                    thesis="AI infrastructure demand remains strong.",
                    next_event="earnings",
                    why_selected=SimpleNamespace(summary="AI infrastructure leader with fresh evidence."),
                )
            ],
            themes=[SimpleNamespace(name="AI Compute")],
            watchlist=[],
        )


class _QuantService:
    def get_history_data_summary(self):
        return SimpleNamespace(
            latest_trade_date="2026-05-15",
            latest_bond_count=520,
            snapshot_count=120_000,
        )

    def get_stats(self):
        return SimpleNamespace(
            running_jobs=1,
            queued_jobs=2,
            finished_jobs=5,
            failed_jobs=0,
        )

    def list_leaderboard(self, page: int, page_size: int):
        return SimpleNamespace(
            total=1,
            items=[
                SimpleNamespace(
                    template="低溢价动量",
                    cagr=18.5,
                    mdd=-7.2,
                )
            ],
        )

    def list_optimize_tasks(self, status: str, page: int, page_size: int):
        return SimpleNamespace(total=3, items=[])


def test_investment_copilot_routes_should_be_registered() -> None:
    app = create_app()

    paths = {route.path for route in app.routes}

    assert "/api/v1/investment-copilot/daily-brief" in paths
    assert "/api/v1/investment-copilot/agent-context" in paths
    assert "/api/v1/investment-copilot/policy" in paths
    assert "/api/v1/investment-copilot/actions/{action_id}/decision" in paths
    assert "/api/v1/investment-copilot/actions/{action_id}/preflight" in paths
    assert "/api/v1/investment-copilot/ledger/summary" in paths
    assert "/api/v1/investment-copilot/ledger/reconciliation" in paths
    assert "/api/v1/investment-copilot/ledger/bootstrap" in paths
    assert "/api/v1/investment-copilot/ledger/import-csv" in paths


def test_investment_copilot_daily_brief_should_aggregate_existing_domains(monkeypatch, tmp_path: Path) -> None:
    services = importlib.import_module("vnpy.web.services")
    monkeypatch.setattr(services, "allocation_service", _AllocationService(), raising=False)
    monkeypatch.setattr(services, "tenx_service", _TenxService(), raising=False)
    monkeypatch.setattr(services, "quant_service", _QuantService(), raising=False)

    service = InvestmentCopilotService(store=InvestmentCopilotStore(tmp_path / "investment_copilot.db"))
    brief = service.get_daily_brief(market="US")

    assert brief.portfolio.cash_gap == 15_000
    assert brief.research.top_candidates[0].symbol == "NVDA"
    assert brief.cb_quant.top_strategy == "低溢价动量"
    assert any(card.id == "portfolio:cash-gap" for card in brief.action_cards)
    assert any(card.id == "ledger:bootstrap" for card in brief.action_cards)
    assert any(item.source == "portfolio_ledger" and not item.ok for item in brief.source_health)
    assert all(item.ok for item in brief.source_health if item.source != "portfolio_ledger")
    assert brief.reconciliation.ok is False
    assert brief.investor_policy.require_human_confirmation is True


def test_investment_copilot_should_persist_policy_and_action_decision(monkeypatch, tmp_path: Path) -> None:
    services = importlib.import_module("vnpy.web.services")
    monkeypatch.setattr(services, "allocation_service", _AllocationService(), raising=False)
    monkeypatch.setattr(services, "tenx_service", _TenxService(), raising=False)
    monkeypatch.setattr(services, "quant_service", _QuantService(), raising=False)
    service = InvestmentCopilotService(store=InvestmentCopilotStore(tmp_path / "investment_copilot.db"))

    policy = service.update_investor_policy(
        InvestmentCopilotInvestorPolicy(
            profile_name="保守测试政策",
            allow_cb_quant=False,
            forbidden_symbols=["NVDA"],
        )
    )
    decision = service.record_action_decision(
        "portfolio:cash-gap",
        InvestmentCopilotActionDecisionRequest(
            status="accepted",
            user_note="先补现金。",
            decision_reason="现金缺口达到阈值。",
        ),
    )
    brief = service.get_daily_brief(market="US")
    cash_gap = next(card for card in brief.action_cards if card.id == "portfolio:cash-gap")
    research = next(card for card in brief.action_cards if card.id == "research:NVDA")

    assert policy.allow_cb_quant is False
    assert decision.status == "accepted"
    assert cash_gap.status == "accepted"
    assert cash_gap.user_note == "先补现金。"
    assert research.severity == "warning"
    assert any(card.id == "policy:cb-quant-disabled" for card in brief.action_cards)


def test_investment_copilot_ledger_should_persist_and_summarize(tmp_path: Path) -> None:
    service = InvestmentCopilotService(store=InvestmentCopilotStore(tmp_path / "investment_copilot.db"))

    response = service.bootstrap_ledger(
        InvestmentLedgerBootstrapRequest(
            accounts=[
                InvestmentLedgerAccountRequest(
                    account_id="schwab",
                    name="Schwab Brokerage",
                )
            ],
            holdings=[
                InvestmentLedgerHoldingRequest(
                    account_id="schwab",
                    symbol="USD",
                    asset_type="cash",
                    quantity=10_000,
                    market_value=10_000,
                ),
                InvestmentLedgerHoldingRequest(
                    account_id="schwab",
                    symbol="NVDA",
                    asset_type="equity",
                    quantity=3,
                    market_value=3_000,
                ),
                InvestmentLedgerHoldingRequest(
                    account_id="schwab",
                    symbol="AMD260116C200",
                    asset_type="option",
                    quantity=1,
                    market_value=500,
                ),
            ],
            cashflows=[
                InvestmentLedgerCashflowRequest(
                    account_id="schwab",
                    event_type="deposit",
                    amount=10_000,
                    note="initial cash",
                )
            ],
        )
    )

    summary = service.get_ledger_summary()
    holdings = service.list_ledger_holdings(account_id="schwab")
    cashflows = service.list_ledger_cashflows(account_id="schwab")

    assert response.account_count == 1
    assert summary.total_equity == 13_500
    assert summary.cash_value == 10_000
    assert summary.options_value == 500
    assert summary.top_positions[0].symbol == "NVDA"
    assert len(holdings) == 3
    assert cashflows[0].event_type == "deposit"


def test_investment_copilot_should_warn_when_ledger_and_snapshot_diverge(monkeypatch, tmp_path: Path) -> None:
    services = importlib.import_module("vnpy.web.services")
    monkeypatch.setattr(services, "allocation_service", _AllocationService(), raising=False)
    monkeypatch.setattr(services, "tenx_service", _TenxService(), raising=False)
    monkeypatch.setattr(services, "quant_service", _QuantService(), raising=False)
    service = InvestmentCopilotService(store=InvestmentCopilotStore(tmp_path / "investment_copilot.db"))

    service.bootstrap_ledger(
        InvestmentLedgerBootstrapRequest(
            accounts=[InvestmentLedgerAccountRequest(account_id="main", name="Main Brokerage")],
            holdings=[
                InvestmentLedgerHoldingRequest(
                    account_id="main",
                    symbol="USD",
                    asset_type="cash",
                    quantity=4_000,
                    market_value=4_000,
                ),
                InvestmentLedgerHoldingRequest(
                    account_id="main",
                    symbol="NVDA",
                    asset_type="equity",
                    quantity=10,
                    market_value=76_000,
                ),
            ],
        )
    )

    brief = service.get_daily_brief(market="US")
    agent_context = service.get_agent_context(market="US")

    assert brief.reconciliation.ok is False
    assert brief.reconciliation.total_equity_delta == -20_000
    assert any(card.id == "ledger:reconcile" for card in brief.action_cards)
    assert agent_context.daily_brief.generated_at
    assert agent_context.ledger_accounts[0].account_id == "main"


def test_investment_copilot_should_import_generic_ledger_csv(tmp_path: Path) -> None:
    service = InvestmentCopilotService(store=InvestmentCopilotStore(tmp_path / "investment_copilot.db"))

    response = service.import_ledger_csv(
        InvestmentLedgerCsvImportRequest(
            account=InvestmentLedgerAccountRequest(account_id="generic", name="Generic CSV"),
            raw_csv=(
                "symbol,asset_type,quantity,market_value,cost_basis\n"
                "USD,cash,10000,10000,\n"
                "NVDA,equity,3,3000,2500\n"
                "BAD,equity,1,not-a-number,\n"
            ),
        )
    )

    holdings = service.list_ledger_holdings(account_id="generic")

    assert response.imported_holding_count == 2
    assert response.rejected_row_count == 1
    assert response.summary.total_equity == 13_000
    assert {item.symbol for item in holdings} == {"USD", "NVDA"}
    assert response.errors[0].row_number == 4


def test_investment_copilot_should_import_schwab_like_positions_csv(tmp_path: Path) -> None:
    service = InvestmentCopilotService(store=InvestmentCopilotStore(tmp_path / "investment_copilot.db"))

    response = service.import_ledger_csv(
        InvestmentLedgerCsvImportRequest(
            account=InvestmentLedgerAccountRequest(account_id="schwab-csv", name="Schwab CSV"),
            format="schwab_positions",
            raw_csv=(
                "Symbol,Description,Quantity,Market Value,Security Type\n"
                ",Cash & Cash Investments,1500,\"$1,500.00\",Cash\n"
                "AAPL,Apple Inc,2,\"$400.00\",Equity\n"
                "AAPL260116C00200000,AAPL Call,1,\"$250.00\",Option\n"
                "Total,,,\"$2,150.00\",\n"
            ),
        )
    )

    holdings = service.list_ledger_holdings(account_id="schwab-csv")

    assert response.imported_holding_count == 3
    assert response.rejected_row_count == 0
    assert response.summary.cash_value == 1_500
    assert response.summary.options_value == 250
    assert {item.asset_type for item in holdings} == {"cash", "equity", "option"}


def test_investment_copilot_action_preflight_should_block_without_clean_data(monkeypatch, tmp_path: Path) -> None:
    services = importlib.import_module("vnpy.web.services")
    monkeypatch.setattr(services, "allocation_service", _AllocationService(), raising=False)
    monkeypatch.setattr(services, "tenx_service", _TenxService(), raising=False)
    monkeypatch.setattr(services, "quant_service", _QuantService(), raising=False)
    service = InvestmentCopilotService(store=InvestmentCopilotStore(tmp_path / "investment_copilot.db"))

    preflight = service.preflight_action(
        "portfolio:cash-gap",
        InvestmentCopilotActionPreflightRequest(
            market="US",
            intended_action="sell covered call to raise cash",
        ),
    )

    assert preflight.allowed is False
    assert preflight.requires_human_confirmation is True
    assert any("不可用数据源" in item for item in preflight.blockers)
    assert any("人工确认" in item for item in preflight.blockers)
    assert any("sell covered call" in item for item in preflight.checklist)


def test_investment_copilot_action_preflight_should_allow_data_quality_action(monkeypatch, tmp_path: Path) -> None:
    services = importlib.import_module("vnpy.web.services")
    monkeypatch.setattr(services, "allocation_service", _AllocationService(), raising=False)
    monkeypatch.setattr(services, "tenx_service", _TenxService(), raising=False)
    monkeypatch.setattr(services, "quant_service", _QuantService(), raising=False)
    service = InvestmentCopilotService(store=InvestmentCopilotStore(tmp_path / "investment_copilot.db"))

    preflight = service.preflight_action(
        "ledger:bootstrap",
        InvestmentCopilotActionPreflightRequest(
            market="US",
            acknowledged_human_confirmation=True,
        ),
    )

    assert preflight.allowed is True
    assert preflight.blockers == []
