from __future__ import annotations

from fastapi import APIRouter, Query

from vnpy.web.contracts.investment_copilot import (
    InvestmentCopilotAgentContextResponse,
    InvestmentCopilotActionDecisionRequest,
    InvestmentCopilotActionDecisionResponse,
    InvestmentCopilotActionPreflightRequest,
    InvestmentCopilotActionPreflightResponse,
    InvestmentCopilotDailyBriefResponse,
    InvestmentCopilotInvestorPolicy,
    InvestmentLedgerAccountRequest,
    InvestmentLedgerAccountRow,
    InvestmentLedgerBootstrapRequest,
    InvestmentLedgerBootstrapResponse,
    InvestmentLedgerCashflowRequest,
    InvestmentLedgerCashflowRow,
    InvestmentLedgerCsvImportRequest,
    InvestmentLedgerCsvImportResponse,
    InvestmentLedgerHoldingRequest,
    InvestmentLedgerHoldingRow,
    InvestmentLedgerReconciliationResponse,
    InvestmentLedgerSummaryResponse,
)
import vnpy.web.services as services

router = APIRouter(prefix="/investment-copilot", tags=["investment-copilot"])


def _service():
    return services.__getattr__("investment_copilot_service")


@router.get("/daily-brief", response_model=InvestmentCopilotDailyBriefResponse)
def get_daily_brief(market: str = Query("US")) -> InvestmentCopilotDailyBriefResponse:
    return _service().get_daily_brief(market=market)


@router.get("/agent-context", response_model=InvestmentCopilotAgentContextResponse)
def get_agent_context(market: str = Query("US")) -> InvestmentCopilotAgentContextResponse:
    return _service().get_agent_context(market=market)


@router.get("/policy", response_model=InvestmentCopilotInvestorPolicy)
def get_investor_policy() -> InvestmentCopilotInvestorPolicy:
    return _service().get_investor_policy()


@router.put("/policy", response_model=InvestmentCopilotInvestorPolicy)
def update_investor_policy(policy: InvestmentCopilotInvestorPolicy) -> InvestmentCopilotInvestorPolicy:
    return _service().update_investor_policy(policy)


@router.get("/actions/decisions", response_model=list[InvestmentCopilotActionDecisionResponse])
def list_action_decisions() -> list[InvestmentCopilotActionDecisionResponse]:
    return _service().list_action_decisions()


@router.post("/actions/{action_id}/decision", response_model=InvestmentCopilotActionDecisionResponse)
def record_action_decision(
    action_id: str,
    request: InvestmentCopilotActionDecisionRequest,
    market: str = Query("US"),
) -> InvestmentCopilotActionDecisionResponse:
    return _service().record_action_decision(
        action_id,
        request,
        market=market,
    )


@router.post("/actions/{action_id}/preflight", response_model=InvestmentCopilotActionPreflightResponse)
def preflight_action(
    action_id: str,
    request: InvestmentCopilotActionPreflightRequest,
) -> InvestmentCopilotActionPreflightResponse:
    return _service().preflight_action(action_id, request)


@router.get("/ledger/summary", response_model=InvestmentLedgerSummaryResponse)
def get_ledger_summary() -> InvestmentLedgerSummaryResponse:
    return _service().get_ledger_summary()


@router.get("/ledger/reconciliation", response_model=InvestmentLedgerReconciliationResponse)
def get_ledger_reconciliation() -> InvestmentLedgerReconciliationResponse:
    return _service().get_ledger_reconciliation()


@router.post("/ledger/bootstrap", response_model=InvestmentLedgerBootstrapResponse)
def bootstrap_ledger(request: InvestmentLedgerBootstrapRequest) -> InvestmentLedgerBootstrapResponse:
    return _service().bootstrap_ledger(request)


@router.post("/ledger/import-csv", response_model=InvestmentLedgerCsvImportResponse)
def import_ledger_csv(request: InvestmentLedgerCsvImportRequest) -> InvestmentLedgerCsvImportResponse:
    return _service().import_ledger_csv(request)


@router.get("/ledger/accounts", response_model=list[InvestmentLedgerAccountRow])
def list_ledger_accounts() -> list[InvestmentLedgerAccountRow]:
    return _service().list_ledger_accounts()


@router.post("/ledger/accounts", response_model=InvestmentLedgerAccountRow)
def upsert_ledger_account(request: InvestmentLedgerAccountRequest) -> InvestmentLedgerAccountRow:
    return _service().upsert_ledger_account(request)


@router.get("/ledger/holdings", response_model=list[InvestmentLedgerHoldingRow])
def list_ledger_holdings(account_id: str | None = Query(None)) -> list[InvestmentLedgerHoldingRow]:
    return _service().list_ledger_holdings(account_id=account_id)


@router.post("/ledger/holdings", response_model=InvestmentLedgerHoldingRow)
def upsert_ledger_holding(request: InvestmentLedgerHoldingRequest) -> InvestmentLedgerHoldingRow:
    return _service().upsert_ledger_holding(request)


@router.get("/ledger/cashflows", response_model=list[InvestmentLedgerCashflowRow])
def list_ledger_cashflows(account_id: str | None = Query(None)) -> list[InvestmentLedgerCashflowRow]:
    return _service().list_ledger_cashflows(account_id=account_id)


@router.post("/ledger/cashflows", response_model=InvestmentLedgerCashflowRow)
def add_ledger_cashflow(request: InvestmentLedgerCashflowRequest) -> InvestmentLedgerCashflowRow:
    return _service().add_ledger_cashflow(request)
