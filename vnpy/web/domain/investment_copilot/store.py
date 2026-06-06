from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from vnpy.web.base_store import PgStore, _jsonb
from vnpy.web.db import DbSettings
from vnpy.web.contracts.investment_copilot import (
    ActionStatus,
    InvestmentCopilotActionDecisionResponse,
    InvestmentCopilotInvestorPolicy,
    InvestmentLedgerAccountRequest,
    InvestmentLedgerAccountRow,
    InvestmentLedgerBootstrapRequest,
    InvestmentLedgerCashflowRequest,
    InvestmentLedgerCashflowRow,
    InvestmentLedgerHoldingRequest,
    InvestmentLedgerHoldingRow,
    InvestmentLedgerSummaryResponse,
    InvestmentLedgerTopPosition,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _loads(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    import json
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


class InvestmentCopilotStore(PgStore):
    def __init__(self, settings: DbSettings) -> None:
        super().__init__(settings)

    def load_policy(self) -> InvestmentCopilotInvestorPolicy:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload, updated_at FROM oltp.copilot_policy WHERE id = %s",
                ("default",),
            ).fetchone()

        if row is None:
            return InvestmentCopilotInvestorPolicy()

        payload = _loads(row["payload"])
        payload["updated_at"] = row["updated_at"]
        return InvestmentCopilotInvestorPolicy.model_validate(payload)

    def save_policy(self, policy: InvestmentCopilotInvestorPolicy) -> InvestmentCopilotInvestorPolicy:
        updated_at = _now()
        payload = policy.model_dump()
        payload["updated_at"] = updated_at
        normalized = InvestmentCopilotInvestorPolicy.model_validate(payload)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO oltp.copilot_policy (id, payload, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
                """,
                ("default", _jsonb(normalized.model_dump()), updated_at),
            )
        return normalized

    def load_action_decisions(self) -> dict[str, InvestmentCopilotActionDecisionResponse]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT action_id, status, user_note, decision_reason, updated_at FROM oltp.copilot_action_decision"
            ).fetchall()
        return {
            row["action_id"]: InvestmentCopilotActionDecisionResponse(
                action_id=row["action_id"],
                status=row["status"],
                user_note=row["user_note"],
                decision_reason=row["decision_reason"],
                updated_at=row["updated_at"],
            )
            for row in rows
        }

    def upsert_action_decision(
        self,
        *,
        action_id: str,
        status: ActionStatus,
        user_note: str = "",
        decision_reason: str = "",
        snapshot: dict[str, Any] | None = None,
    ) -> InvestmentCopilotActionDecisionResponse:
        updated_at = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO oltp.copilot_action_decision
                    (action_id, status, user_note, decision_reason, snapshot_json, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(action_id) DO UPDATE SET
                    status = excluded.status,
                    user_note = excluded.user_note,
                    decision_reason = excluded.decision_reason,
                    snapshot_json = excluded.snapshot_json,
                    updated_at = excluded.updated_at
                """,
                (
                    action_id,
                    status,
                    user_note,
                    decision_reason,
                    _jsonb(snapshot or {}),
                    updated_at,
                ),
            )
        return InvestmentCopilotActionDecisionResponse(
            action_id=action_id,
            status=status,
            user_note=user_note,
            decision_reason=decision_reason,
            updated_at=updated_at,
        )

    def upsert_account(self, request: InvestmentLedgerAccountRequest) -> InvestmentLedgerAccountRow:
        updated_at = _now()
        row = InvestmentLedgerAccountRow(**request.model_dump(), updated_at=updated_at)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO oltp.ledger_account (account_id, payload, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT(account_id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
                """,
                (row.account_id, _jsonb(row.model_dump()), updated_at),
            )
        return row

    def list_accounts(self) -> list[InvestmentLedgerAccountRow]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload, updated_at FROM oltp.ledger_account ORDER BY updated_at DESC, account_id"
            ).fetchall()
        accounts: list[InvestmentLedgerAccountRow] = []
        for row in rows:
            payload = _loads(row["payload"])
            payload["updated_at"] = row["updated_at"]
            accounts.append(InvestmentLedgerAccountRow.model_validate(payload))
        return accounts

    def upsert_holding(self, request: InvestmentLedgerHoldingRequest) -> InvestmentLedgerHoldingRow:
        updated_at = _now()
        row = InvestmentLedgerHoldingRow(**request.model_dump(), updated_at=updated_at)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO oltp.ledger_holding (account_id, symbol, asset_type, payload, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(account_id, symbol, asset_type) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    row.account_id,
                    row.symbol.upper(),
                    row.asset_type,
                    _jsonb(row.model_dump()),
                    updated_at,
                ),
            )
        return row

    def list_holdings(self, account_id: str | None = None) -> list[InvestmentLedgerHoldingRow]:
        with self._connect() as conn:
            if account_id:
                rows = conn.execute(
                    "SELECT payload, updated_at FROM oltp.ledger_holding WHERE account_id = %s ORDER BY updated_at DESC, symbol",
                    (account_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT payload, updated_at FROM oltp.ledger_holding ORDER BY updated_at DESC, symbol"
                ).fetchall()
        holdings: list[InvestmentLedgerHoldingRow] = []
        for row in rows:
            payload = _loads(row["payload"])
            payload["updated_at"] = row["updated_at"]
            holdings.append(InvestmentLedgerHoldingRow.model_validate(payload))
        return holdings

    def add_cashflow(self, request: InvestmentLedgerCashflowRequest) -> InvestmentLedgerCashflowRow:
        created_at = _now()
        event_id = f"ICF-{uuid4().hex[:12]}"
        event_date = request.event_date or created_at[:10]
        row = InvestmentLedgerCashflowRow(
            **{**request.model_dump(), "event_date": event_date},
            event_id=event_id,
            created_at=created_at,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO oltp.ledger_cashflow (event_id, account_id, event_date, payload, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (row.event_id, row.account_id, row.event_date, _jsonb(row.model_dump()), created_at),
            )
        return row

    def list_cashflows(self, account_id: str | None = None, *, limit: int = 100) -> list[InvestmentLedgerCashflowRow]:
        with self._connect() as conn:
            if account_id:
                rows = conn.execute(
                    "SELECT payload, created_at FROM oltp.ledger_cashflow WHERE account_id = %s ORDER BY event_date DESC, created_at DESC LIMIT %s",
                    (account_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT payload, created_at FROM oltp.ledger_cashflow ORDER BY event_date DESC, created_at DESC LIMIT %s",
                    (limit,),
                ).fetchall()
        cashflows: list[InvestmentLedgerCashflowRow] = []
        for row in rows:
            payload = _loads(row["payload"])
            payload["created_at"] = row["created_at"]
            cashflows.append(InvestmentLedgerCashflowRow.model_validate(payload))
        return cashflows

    def bootstrap_ledger(self, request: InvestmentLedgerBootstrapRequest) -> InvestmentLedgerSummaryResponse:
        for account in request.accounts:
            self.upsert_account(account)
        for holding in request.holdings:
            self.upsert_holding(holding)
        for cashflow in request.cashflows:
            self.add_cashflow(cashflow)
        return self.ledger_summary()

    def ledger_summary(self) -> InvestmentLedgerSummaryResponse:
        accounts = [account for account in self.list_accounts() if account.active]
        holdings = self.list_holdings()
        total_equity = sum(max(float(item.market_value), 0.0) for item in holdings)
        cash_value = sum(max(float(item.market_value), 0.0) for item in holdings if item.asset_type == "cash")
        options_value = sum(max(float(item.market_value), 0.0) for item in holdings if item.asset_type == "option")
        invested_value = max(total_equity - cash_value, 0.0)
        sorted_positions = sorted(
            [item for item in holdings if item.asset_type != "cash"],
            key=lambda item: float(item.market_value),
            reverse=True,
        )
        top_positions = [
            InvestmentLedgerTopPosition(
                symbol=item.symbol.upper(),
                asset_type=item.asset_type,
                market_value=float(item.market_value),
                weight=(float(item.market_value) / total_equity) if total_equity > 0 else 0.0,
                account_id=item.account_id,
            )
            for item in sorted_positions[:5]
        ]
        updated_candidates = [item.updated_at for item in holdings] + [item.updated_at for item in accounts]
        return InvestmentLedgerSummaryResponse(
            account_count=len(accounts),
            holding_count=len(holdings),
            total_equity=total_equity,
            cash_value=cash_value,
            invested_value=invested_value,
            options_value=options_value,
            largest_position_weight=top_positions[0].weight if top_positions else 0.0,
            base_currency=accounts[0].base_currency if accounts else "USD",
            top_positions=top_positions,
            updated_at=max(updated_candidates) if updated_candidates else None,
        )
