from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO
import re

from vnpy.web.contracts.investment_copilot import (
    InvestmentCopilotAgentContextResponse,
    InvestmentCopilotActionCard,
    InvestmentCopilotActionDecisionRequest,
    InvestmentCopilotActionDecisionResponse,
    InvestmentCopilotActionPreflightRequest,
    InvestmentCopilotActionPreflightResponse,
    InvestmentCopilotCbQuantBrief,
    InvestmentCopilotDailyBriefResponse,
    InvestmentCopilotDecisionPolicy,
    InvestmentCopilotInvestorPolicy,
    InvestmentCopilotPortfolioBrief,
    InvestmentCopilotResearchBrief,
    InvestmentCopilotResearchCandidate,
    InvestmentCopilotSourceHealth,
    InvestmentLedgerAccountRequest,
    InvestmentLedgerAccountRow,
    InvestmentLedgerBootstrapRequest,
    InvestmentLedgerBootstrapResponse,
    InvestmentLedgerCashflowRequest,
    InvestmentLedgerCashflowRow,
    InvestmentLedgerCsvImportError,
    InvestmentLedgerCsvImportRequest,
    InvestmentLedgerCsvImportResponse,
    InvestmentLedgerHoldingRequest,
    InvestmentLedgerHoldingRow,
    InvestmentLedgerReconciliationResponse,
    InvestmentLedgerSummaryResponse,
)
from vnpy.web.db import load_db_settings
from vnpy.web.domain.investment_copilot.store import InvestmentCopilotStore


class InvestmentCopilotService:
    """Aggregation and decision-memory layer for the AI-native investment cockpit."""

    def __init__(self, store: InvestmentCopilotStore | None = None) -> None:
        self._store = store or InvestmentCopilotStore(load_db_settings())

    def get_daily_brief(self, market: str = "US") -> InvestmentCopilotDailyBriefResponse:
        source_health: list[InvestmentCopilotSourceHealth] = []
        investor_policy = self.get_investor_policy()
        portfolio = self._build_portfolio_brief(source_health)
        ledger = self._build_ledger_brief(source_health)
        reconciliation = self._build_reconciliation(portfolio, ledger)
        research = self._build_research_brief(market, source_health)
        cb_quant = self._build_cb_quant_brief(source_health)
        action_cards = self._apply_action_decisions(
            self._build_action_cards(portfolio, ledger, reconciliation, research, cb_quant, source_health, investor_policy),
            investor_policy,
        )

        headline = self._headline(portfolio, research, cb_quant, source_health)
        return InvestmentCopilotDailyBriefResponse(
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            headline=headline,
            portfolio=portfolio,
            ledger=ledger,
            reconciliation=reconciliation,
            research=research,
            cb_quant=cb_quant,
            source_health=source_health,
            action_cards=sorted(action_cards, key=lambda item: item.priority),
            decision_policy=self._decision_policy(portfolio, investor_policy),
            investor_policy=investor_policy,
        )

    def get_investor_policy(self) -> InvestmentCopilotInvestorPolicy:
        return self._store.load_policy()

    def update_investor_policy(self, policy: InvestmentCopilotInvestorPolicy) -> InvestmentCopilotInvestorPolicy:
        return self._store.save_policy(policy)

    def list_action_decisions(self) -> list[InvestmentCopilotActionDecisionResponse]:
        return sorted(self._store.load_action_decisions().values(), key=lambda item: item.updated_at, reverse=True)

    def get_agent_context(self, market: str = "US") -> InvestmentCopilotAgentContextResponse:
        return InvestmentCopilotAgentContextResponse(
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            daily_brief=self.get_daily_brief(market=market),
            action_decisions=self.list_action_decisions(),
            ledger_accounts=self.list_ledger_accounts(),
            ledger_holdings=self.list_ledger_holdings(),
            ledger_cashflows=self.list_ledger_cashflows(),
        )

    def upsert_ledger_account(self, request: InvestmentLedgerAccountRequest) -> InvestmentLedgerAccountRow:
        return self._store.upsert_account(request)

    def list_ledger_accounts(self) -> list[InvestmentLedgerAccountRow]:
        return self._store.list_accounts()

    def upsert_ledger_holding(self, request: InvestmentLedgerHoldingRequest) -> InvestmentLedgerHoldingRow:
        return self._store.upsert_holding(request)

    def list_ledger_holdings(self, account_id: str | None = None) -> list[InvestmentLedgerHoldingRow]:
        return self._store.list_holdings(account_id=account_id)

    def add_ledger_cashflow(self, request: InvestmentLedgerCashflowRequest) -> InvestmentLedgerCashflowRow:
        return self._store.add_cashflow(request)

    def list_ledger_cashflows(self, account_id: str | None = None) -> list[InvestmentLedgerCashflowRow]:
        return self._store.list_cashflows(account_id=account_id)

    def get_ledger_summary(self) -> InvestmentLedgerSummaryResponse:
        return self._store.ledger_summary()

    def get_ledger_reconciliation(self) -> InvestmentLedgerReconciliationResponse:
        return self._build_reconciliation(
            self._build_portfolio_brief([]),
            self.get_ledger_summary(),
        )

    def bootstrap_ledger(self, request: InvestmentLedgerBootstrapRequest) -> InvestmentLedgerBootstrapResponse:
        summary = self._store.bootstrap_ledger(request)
        return InvestmentLedgerBootstrapResponse(
            account_count=len(request.accounts),
            holding_count=len(request.holdings),
            cashflow_count=len(request.cashflows),
            summary=summary,
        )

    def import_ledger_csv(self, request: InvestmentLedgerCsvImportRequest) -> InvestmentLedgerCsvImportResponse:
        account = self._store.upsert_account(request.account)
        holdings, errors = self._parse_ledger_csv(request)
        for holding in holdings:
            self._store.upsert_holding(holding)
        return InvestmentLedgerCsvImportResponse(
            account=account,
            imported_holding_count=len(holdings),
            rejected_row_count=len(errors),
            summary=self._store.ledger_summary(),
            errors=errors,
        )

    def record_action_decision(
        self,
        action_id: str,
        request: InvestmentCopilotActionDecisionRequest,
        *,
        market: str = "US",
    ) -> InvestmentCopilotActionDecisionResponse:
        brief = self.get_daily_brief(market=market)
        action = next((item for item in brief.action_cards if item.id == action_id), None)
        snapshot = action.model_dump() if action is not None else {"action_id": action_id}
        return self._store.upsert_action_decision(
            action_id=action_id,
            status=request.status,
            user_note=request.user_note,
            decision_reason=request.decision_reason,
            snapshot=snapshot,
        )

    def preflight_action(
        self,
        action_id: str,
        request: InvestmentCopilotActionPreflightRequest,
    ) -> InvestmentCopilotActionPreflightResponse:
        brief = self.get_daily_brief(market=request.market)
        action = next((item for item in brief.action_cards if item.id == action_id), None)
        blockers: list[str] = []
        warnings: list[str] = []
        checklist = [
            *brief.decision_policy.hard_rules,
            *brief.decision_policy.review_questions,
        ]

        if action is None:
            blockers.append("行动卡片不存在或已经不在当前 Daily Brief 中。")
        else:
            checklist.append(action.suggested_action)
            if action.status == "executed":
                warnings.append("该行动已经标记为已执行，本次预检应只用于复盘或补充记录。")
            failed_sources = [item for item in brief.source_health if not item.ok]
            if action.source != "data_quality" and failed_sources:
                blockers.append("存在不可用数据源，非数据修复类行动不得推进。")
            if action.source != "data_quality" and not brief.reconciliation.ok:
                blockers.append("Portfolio Ledger 与账户快照未完成对账，非数据修复类行动不得推进。")
            if action.requires_confirmation and not request.acknowledged_human_confirmation:
                blockers.append("该行动需要人工确认后才能进入执行。")
            if action.severity in {"critical", "warning"}:
                warnings.append(f"行动等级为 {action.severity}，执行前需要记录反方假设。")
            if request.intended_action:
                checklist.append(f"用户计划动作：{request.intended_action}")

        return InvestmentCopilotActionPreflightResponse(
            action_id=action_id,
            allowed=not blockers,
            requires_human_confirmation=bool(action.requires_confirmation if action else True),
            blockers=blockers,
            warnings=warnings,
            checklist=checklist[:12],
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )

    @classmethod
    def _parse_ledger_csv(
        cls,
        request: InvestmentLedgerCsvImportRequest,
    ) -> tuple[list[InvestmentLedgerHoldingRequest], list[InvestmentLedgerCsvImportError]]:
        reader = csv.DictReader(StringIO(request.raw_csv.strip()))
        if not reader.fieldnames:
            return [], [InvestmentLedgerCsvImportError(row_number=1, message="CSV 缺少表头。")]

        holdings: list[InvestmentLedgerHoldingRequest] = []
        errors: list[InvestmentLedgerCsvImportError] = []
        for row_number, raw_row in enumerate(reader, start=2):
            normalized = {cls._normalize_csv_key(key): (value or "").strip() for key, value in raw_row.items() if key is not None}
            if not any(normalized.values()):
                continue
            try:
                holding = cls._csv_row_to_holding(request, normalized)
            except ValueError as exc:
                errors.append(
                    InvestmentLedgerCsvImportError(
                        row_number=row_number,
                        message=str(exc),
                        raw={key: value for key, value in raw_row.items() if key is not None and value is not None},
                    )
                )
                continue
            if holding is not None:
                holdings.append(holding)
        return holdings, errors

    @classmethod
    def _csv_row_to_holding(
        cls,
        request: InvestmentLedgerCsvImportRequest,
        row: dict[str, str],
    ) -> InvestmentLedgerHoldingRequest | None:
        symbol = cls._pick(row, "symbol", "ticker", "tickersymbol", "instrument", "underlyingsymbol")
        description = cls._pick(row, "description", "name", "securitydescription", "assetdescription")
        asset_hint = cls._pick(row, "assettype", "assetclass", "securitytype", "type", "producttype")

        if cls._is_total_or_header_row(symbol, description):
            return None
        if not symbol and cls._looks_like_cash(description or asset_hint):
            symbol = request.default_currency.upper()
        if not symbol:
            raise ValueError("缺少 symbol/ticker。")

        asset_type = cls._normalize_asset_type(symbol=symbol, asset_hint=asset_hint, description=description)
        quantity_raw = cls._pick(row, "quantity", "qty", "shares", "position", "positions", "amount")
        market_value_raw = cls._pick(row, "marketvalue", "value", "currentvalue", "positionvalue", "marketval", "netliq", "cashvalue")
        if not market_value_raw and asset_type == "cash":
            market_value_raw = quantity_raw
        if not market_value_raw:
            raise ValueError("缺少 market value/value。")

        market_value = cls._parse_money(market_value_raw)
        if market_value <= 0:
            return None

        quantity = cls._parse_money(quantity_raw) if quantity_raw else market_value if asset_type == "cash" else 0.0
        cost_basis_raw = cls._pick(row, "costbasis", "cost", "bookcost")
        cost_basis = cls._parse_money(cost_basis_raw) if cost_basis_raw else None
        currency = (cls._pick(row, "currency", "ccy") or request.default_currency).upper()
        return InvestmentLedgerHoldingRequest(
            account_id=request.account.account_id,
            symbol=symbol.strip().upper(),
            asset_type=asset_type,
            quantity=quantity,
            market_value=market_value,
            currency=currency,
            cost_basis=cost_basis,
            as_of_date=request.as_of_date,
        )

    @staticmethod
    def _normalize_csv_key(key: str) -> str:
        return re.sub(r"[^a-z0-9]", "", key.lower())

    @staticmethod
    def _pick(row: dict[str, str], *keys: str) -> str:
        for key in keys:
            value = row.get(key)
            if value:
                return value
        return ""

    @staticmethod
    def _parse_money(raw: str) -> float:
        value = raw.strip()
        if not value or value in {"-", "--", "N/A"}:
            return 0.0
        negative = value.startswith("(") and value.endswith(")")
        cleaned = value.strip("()").replace("$", "").replace(",", "").replace("%", "").strip()
        try:
            parsed = float(cleaned)
        except ValueError as exc:
            raise ValueError(f"无法解析金额：{raw}") from exc
        return -parsed if negative else parsed

    @staticmethod
    def _is_total_or_header_row(symbol: str, description: str) -> bool:
        combined = f"{symbol} {description}".strip().lower()
        return combined in {"total", "totals", "account total"} or combined.startswith("total ")

    @staticmethod
    def _looks_like_cash(value: str) -> bool:
        normalized = value.lower()
        return "cash" in normalized or "money market" in normalized or "sweep" in normalized

    @classmethod
    def _normalize_asset_type(cls, *, symbol: str, asset_hint: str, description: str) -> str:
        combined = f"{symbol} {asset_hint} {description}".lower()
        if cls._looks_like_cash(combined) or symbol.upper() in {"USD", "CASH"}:
            return "cash"
        if "option" in combined or re.search(r"\d{6}[cp]\d+", combined):
            return "option"
        if "etf" in combined:
            return "etf"
        if "bond" in combined and ("convertible" in combined or "cb" in combined):
            return "convertible_bond"
        if "bond" in combined or "fixed income" in combined:
            return "bond"
        if "fund" in combined or "mutual" in combined:
            return "fund"
        if "crypto" in combined or "bitcoin" in combined or "ethereum" in combined:
            return "crypto"
        if "stock" in combined or "equity" in combined or "common" in combined:
            return "equity"
        return "equity"

    @staticmethod
    def _health(source_health: list[InvestmentCopilotSourceHealth], source: str, ok: bool, summary: str, detail: str = "") -> None:
        source_health.append(
            InvestmentCopilotSourceHealth(
                source=source,
                ok=ok,
                summary=summary,
                detail=detail[:500],
            )
        )

    def _build_portfolio_brief(self, source_health: list[InvestmentCopilotSourceHealth]) -> InvestmentCopilotPortfolioBrief:
        import vnpy.web.services as services

        try:
            dashboard = services.allocation_service.get_dashboard()
            snapshot = dashboard.snapshot
            targets = dashboard.targets
            guardrails = dashboard.guardrails
            blocking_count = sum(1 for item in guardrails if item.blocking)
            self._health(
                source_health,
                "smart_allocation",
                True,
                f"账户快照已读取，风险等级 {dashboard.risk_level}。",
            )
            return InvestmentCopilotPortfolioBrief(
                total_equity=float(snapshot.total_equity),
                health_score=int(dashboard.health_score),
                risk_level=str(dashboard.risk_level),
                cash_value=float(snapshot.cash_value),
                options_value=float(snapshot.options_value),
                cash_gap=max(float(targets.cash_value) - float(snapshot.cash_value), 0.0),
                options_excess=max(float(snapshot.options_value) - float(targets.options_value), 0.0),
                margin_used=float(snapshot.margin_used),
                margin_limit=float(targets.margin_limit),
                guardrail_count=len(guardrails),
                blocking_guardrail_count=blocking_count,
                top_guardrails=[item.message for item in guardrails[:4]],
            )
        except Exception as exc:
            self._health(source_health, "smart_allocation", False, "账户结构暂不可用。", str(exc))
            return InvestmentCopilotPortfolioBrief(
                total_equity=0.0,
                health_score=0,
                risk_level="unknown",
                cash_gap=0.0,
                options_excess=0.0,
                margin_used=0.0,
                margin_limit=0.0,
                guardrail_count=0,
                blocking_guardrail_count=0,
            )

    def _build_research_brief(self, market: str, source_health: list[InvestmentCopilotSourceHealth]) -> InvestmentCopilotResearchBrief:
        import vnpy.web.services as services

        normalized_market = "US" if market.upper() == "US" else "CN"
        try:
            snapshot = services.tenx_service.get_workspace_snapshot(normalized_market)
            candidates = [
                InvestmentCopilotResearchCandidate(
                    symbol=item.symbol,
                    name=item.name,
                    score=int(item.score),
                    risk_level=item.risk_level,
                    thesis=item.why_selected.summary or item.thesis,
                    next_event=item.next_event,
                )
                for item in snapshot.candidates[:3]
            ]
            self._health(
                source_health,
                "tenx_hunter",
                True,
                f"{snapshot.market} 研究工作台已读取，候选 {len(snapshot.candidates)} 个。",
            )
            return InvestmentCopilotResearchBrief(
                market=snapshot.market,
                universe=snapshot.universe,
                snapshot_at=snapshot.snapshot_at,
                candidate_count=len(snapshot.candidates),
                theme_count=len(snapshot.themes),
                watchlist_count=len(snapshot.watchlist),
                top_candidates=candidates,
                hot_themes=[item.name for item in snapshot.themes[:3]],
            )
        except Exception as exc:
            self._health(source_health, "tenx_hunter", False, f"{normalized_market} 研究工作台暂不可用。", str(exc))
            return InvestmentCopilotResearchBrief(
                market=normalized_market,
                universe="",
                snapshot_at="",
                candidate_count=0,
                theme_count=0,
                watchlist_count=0,
            )

    def _build_cb_quant_brief(self, source_health: list[InvestmentCopilotSourceHealth]) -> InvestmentCopilotCbQuantBrief:
        import vnpy.web.services as services

        try:
            history = services.quant_service.get_history_data_summary()
            stats = services.quant_service.get_stats()
            leaderboard = services.quant_service.list_leaderboard(page=1, page_size=1)
            active_tasks = services.quant_service.list_optimize_tasks(status="active", page=1, page_size=3)
            top = leaderboard.items[0] if leaderboard.items else None
            self._health(
                source_health,
                "cb_quant",
                True,
                f"可转债快照最新交易日 {history.latest_trade_date or 'N/A'}，榜单 {leaderboard.total} 条。",
            )
            return InvestmentCopilotCbQuantBrief(
                latest_trade_date=history.latest_trade_date,
                latest_bond_count=int(history.latest_bond_count),
                snapshot_count=int(history.snapshot_count),
                running_jobs=int(stats.running_jobs),
                queued_jobs=int(stats.queued_jobs),
                finished_jobs=int(stats.finished_jobs),
                failed_jobs=int(stats.failed_jobs),
                active_optimize_tasks=int(active_tasks.total),
                top_strategy=top.template if top else "",
                top_cagr=float(top.cagr) if top else None,
                top_drawdown=float(top.mdd) if top else None,
            )
        except Exception as exc:
            self._health(source_health, "cb_quant", False, "可转债策略状态暂不可用。", str(exc))
            return InvestmentCopilotCbQuantBrief()

    def _build_ledger_brief(self, source_health: list[InvestmentCopilotSourceHealth]) -> InvestmentLedgerSummaryResponse:
        try:
            summary = self._store.ledger_summary()
            if summary.account_count and summary.holding_count:
                self._health(
                    source_health,
                    "portfolio_ledger",
                    True,
                    f"统一账本已读取，账户 {summary.account_count} 个，持仓 {summary.holding_count} 条。",
                )
            else:
                self._health(
                    source_health,
                    "portfolio_ledger",
                    False,
                    "统一账本尚未初始化，仍需依赖 Smart Allocation 快照。",
                    "No active ledger accounts or holdings.",
                )
            return summary
        except Exception as exc:
            self._health(source_health, "portfolio_ledger", False, "统一账本暂不可用。", str(exc))
            return InvestmentLedgerSummaryResponse()

    @staticmethod
    def _build_reconciliation(
        portfolio: InvestmentCopilotPortfolioBrief,
        ledger: InvestmentLedgerSummaryResponse,
    ) -> InvestmentLedgerReconciliationResponse:
        if ledger.account_count == 0 or ledger.holding_count == 0:
            return InvestmentLedgerReconciliationResponse(
                ok=False,
                summary="Portfolio Ledger 尚未初始化，无法与 Smart Allocation 对账。",
            )
        if portfolio.total_equity <= 0:
            return InvestmentLedgerReconciliationResponse(
                ok=False,
                summary="Smart Allocation 快照不可用，无法完成账本对账。",
            )

        total_equity_delta = ledger.total_equity - portfolio.total_equity
        cash_delta = ledger.cash_value - portfolio.cash_value
        options_delta = ledger.options_value - portfolio.options_value
        delta_ratio = abs(total_equity_delta) / portfolio.total_equity if portfolio.total_equity > 0 else 0.0
        tolerance_ratio = 0.02
        ok = delta_ratio <= tolerance_ratio
        return InvestmentLedgerReconciliationResponse(
            ok=ok,
            summary="账本与 Smart Allocation 权益差异在容忍范围内。" if ok else "账本与 Smart Allocation 权益差异超过容忍范围，需要复核同步口径。",
            total_equity_delta=total_equity_delta,
            cash_delta=cash_delta,
            options_delta=options_delta,
            delta_ratio=delta_ratio,
            tolerance_ratio=tolerance_ratio,
        )

    def _build_action_cards(
        self,
        portfolio: InvestmentCopilotPortfolioBrief,
        ledger: InvestmentLedgerSummaryResponse,
        reconciliation: InvestmentLedgerReconciliationResponse,
        research: InvestmentCopilotResearchBrief,
        cb_quant: InvestmentCopilotCbQuantBrief,
        source_health: list[InvestmentCopilotSourceHealth],
        investor_policy: InvestmentCopilotInvestorPolicy,
    ) -> list[InvestmentCopilotActionCard]:
        cards: list[InvestmentCopilotActionCard] = []

        if any(not item.ok for item in source_health):
            failed = [item.source for item in source_health if not item.ok]
            cards.append(
                InvestmentCopilotActionCard(
                    id="data-quality:repair",
                    source="data_quality",
                    severity="warning",
                    priority=5,
                    title="先修复不可用数据源",
                    rationale="投资建议需要账户、研究和策略数据同时可追溯；当前有数据源不可用。",
                    suggested_action=f"检查 {'、'.join(failed)} 的服务、数据库和同步任务。",
                    evidence=[item.summary for item in source_health if not item.ok],
                    href="/dashboard",
                    requires_confirmation=False,
                )
            )

        if ledger.account_count == 0 or ledger.holding_count == 0:
            cards.append(
                InvestmentCopilotActionCard(
                    id="ledger:bootstrap",
                    source="data_quality",
                    severity="warning",
                    priority=8,
                    title="建立统一 Portfolio Ledger",
                    rationale="当前驾驶舱仍主要依赖 Smart Allocation 快照；成熟产品需要唯一资产事实源。",
                    suggested_action="先录入至少一个账户和当前持仓快照，后续再接 CSV/券商导入。",
                    evidence=["Portfolio Ledger empty", "Smart Allocation snapshot fallback"],
                    href="/investment-copilot",
                    requires_confirmation=False,
                )
            )
        elif not reconciliation.ok:
            cards.append(
                InvestmentCopilotActionCard(
                    id="ledger:reconcile",
                    source="data_quality",
                    severity="warning",
                    priority=9,
                    title="账本与账户快照需要对账",
                    rationale="Portfolio Ledger 是长期事实源，Smart Allocation 是当前风控快照；两者偏差过大时，AI 建议必须先降级。",
                    suggested_action="检查最近一次持仓导入、现金调整和 Smart Allocation 快照时间。",
                    evidence=[
                        reconciliation.summary,
                        f"equity delta {reconciliation.total_equity_delta:,.0f}",
                        f"delta ratio {reconciliation.delta_ratio:.1%}",
                    ],
                    href="/investment-copilot",
                    requires_confirmation=False,
                )
            )
        elif ledger.largest_position_weight > investor_policy.max_single_stock_ratio:
            top = ledger.top_positions[0] if ledger.top_positions else None
            cards.append(
                InvestmentCopilotActionCard(
                    id="ledger:concentration",
                    source="portfolio",
                    severity="warning",
                    priority=12,
                    title="统一账本检测到集中度超限",
                    rationale="Portfolio Ledger 的最大持仓权重超过投资政策单股上限。",
                    suggested_action="复核该持仓是否需要停止新增或降集中度。",
                    evidence=[
                        f"{top.symbol} {top.weight:.1%}" if top else "largest position unknown",
                        f"limit {investor_policy.max_single_stock_ratio:.1%}",
                    ],
                    href="/investment-copilot",
                )
            )

        if portfolio.blocking_guardrail_count:
            cards.append(
                InvestmentCopilotActionCard(
                    id="portfolio:blocking-guardrails",
                    source="portfolio",
                    severity="critical",
                    priority=10,
                    title="先处理阻断级风控",
                    rationale="存在 blocking guardrail 时，不应该继续新增风险敞口。",
                    suggested_action="进入 Risk Guardrails，优先降低保证金、单股集中度或不合纪律的期权仓位。",
                    evidence=portfolio.top_guardrails,
                    href="/smart-allocation/guardrails",
                )
            )
        elif portfolio.cash_gap > 0:
            cards.append(
                InvestmentCopilotActionCard(
                    id="portfolio:cash-gap",
                    source="portfolio",
                    severity="warning",
                    priority=20,
                    title="现金仓位低于目标",
                    rationale="现金不足会降低后续调仓和防守能力。",
                    suggested_action=f"优先规划补足现金仓位，缺口约 {portfolio.cash_gap:,.0f}。",
                    evidence=portfolio.top_guardrails,
                    href="/smart-allocation/waterfall",
                )
            )

        if portfolio.options_excess > 0:
            cards.append(
                InvestmentCopilotActionCard(
                    id="portfolio:options-excess",
                    source="portfolio",
                    severity="warning",
                    priority=25,
                    title="期权仓位高于目标",
                    rationale="期权池超配时，新增 Wheel/LEAPS 应该收紧。",
                    suggested_action=f"暂停新增高风险期权仓位，并规划把约 {portfolio.options_excess:,.0f} 的超配部分流出期权池。",
                    href="/smart-allocation/rebalance",
                )
            )

        if not investor_policy.allow_leaps:
            cards.append(
                InvestmentCopilotActionCard(
                    id="policy:leaps-disabled",
                    source="portfolio",
                    severity="info",
                    priority=30,
                    title="LEAPS 已被投资政策关闭",
                    rationale="当前投资政策不允许新增 LEAPS，相关研究只能进入观察。",
                    suggested_action="保留现有风险复核，不生成新增 LEAPS 行动。",
                    href="/investment-copilot",
                    requires_confirmation=False,
                )
            )

        if research.top_candidates:
            top = research.top_candidates[0]
            forbidden = top.symbol.upper() in {symbol.upper() for symbol in investor_policy.forbidden_symbols}
            cards.append(
                InvestmentCopilotActionCard(
                    id=f"research:{top.symbol}",
                    source="research",
                    severity="warning" if forbidden else "watch",
                    priority=40,
                    title=f"研究候选：{top.symbol}",
                    rationale="该标的在禁买清单中，只能观察。" if forbidden else top.thesis,
                    suggested_action="记录为禁买观察，不进入交易计划。" if forbidden else "打开研究卡片，先验证证据链、反方风险和下一事件，不直接下单。",
                    evidence=[f"TenX score {top.score}", f"risk={top.risk_level}", top.next_event],
                    href=f"/tenx-hunter/{research.market.lower()}/research/{top.symbol}",
                    requires_confirmation=False,
                )
            )

        if cb_quant.top_strategy and investor_policy.allow_cb_quant:
            cards.append(
                InvestmentCopilotActionCard(
                    id="cb-quant:leaderboard",
                    source="cb_quant",
                    severity="info",
                    priority=55,
                    title="复核可转债榜首策略",
                    rationale="榜首策略只代表历史回测表现，仍需要检查回撤、换手和数据窗口稳定性。",
                    suggested_action="进入 Backtest Evaluation，对榜首策略做参数稳健性和最近窗口复核。",
                    evidence=[
                        cb_quant.top_strategy,
                        f"CAGR {cb_quant.top_cagr:.2f}%" if cb_quant.top_cagr is not None else "CAGR N/A",
                        f"MDD {cb_quant.top_drawdown:.2f}%" if cb_quant.top_drawdown is not None else "MDD N/A",
                    ],
                    href="/cb-quant/backtest-evaluation",
                    requires_confirmation=False,
                )
            )
        elif cb_quant.top_strategy and not investor_policy.allow_cb_quant:
            cards.append(
                InvestmentCopilotActionCard(
                    id="policy:cb-quant-disabled",
                    source="cb_quant",
                    severity="info",
                    priority=56,
                    title="可转债策略执行已被投资政策关闭",
                    rationale="当前仍可复核回测结果，但不会生成执行建议。",
                    suggested_action="只查看榜单和数据质量，不进入交易计划。",
                    evidence=[cb_quant.top_strategy],
                    href="/cb-quant/backtest-evaluation",
                    requires_confirmation=False,
                )
            )

        if not cards:
            cards.append(
                InvestmentCopilotActionCard(
                    id="review:daily",
                    source="portfolio",
                    severity="info",
                    priority=100,
                    title="今天以复盘和观察为主",
                    rationale="没有检测到明确阻断级风险或高优先级调仓动作。",
                    suggested_action="复核观察池和账户快照，记录今天不行动的理由。",
                    href="/smart-allocation/review",
                    requires_confirmation=False,
                )
            )

        return cards

    def _apply_action_decisions(
        self,
        cards: list[InvestmentCopilotActionCard],
        investor_policy: InvestmentCopilotInvestorPolicy,
    ) -> list[InvestmentCopilotActionCard]:
        decisions = self._store.load_action_decisions()
        updated: list[InvestmentCopilotActionCard] = []
        for card in cards:
            decision = decisions.get(card.id)
            payload = card.model_dump()
            payload["requires_confirmation"] = bool(card.requires_confirmation or investor_policy.require_human_confirmation)
            if decision is not None:
                payload["status"] = decision.status
                payload["user_note"] = decision.user_note
                payload["decision_reason"] = decision.decision_reason
                payload["decided_at"] = decision.updated_at
            updated.append(InvestmentCopilotActionCard.model_validate(payload))
        return updated

    @staticmethod
    def _headline(
        portfolio: InvestmentCopilotPortfolioBrief,
        research: InvestmentCopilotResearchBrief,
        cb_quant: InvestmentCopilotCbQuantBrief,
        source_health: list[InvestmentCopilotSourceHealth],
    ) -> str:
        if any(not item.ok for item in source_health):
            return "先修数据源，再做投资判断。"
        if portfolio.blocking_guardrail_count:
            return "今日优先降风险，暂缓新增风险敞口。"
        if portfolio.cash_gap > 0:
            return "今日优先补现金，再看研究候选。"
        if research.candidate_count:
            return "账户无阻断风险，可以进入研究验证。"
        if cb_quant.active_optimize_tasks:
            return "策略任务仍在运行，等待回测完成后再决策。"
        return "今天适合低动作复盘。"

    @staticmethod
    def _decision_policy(
        portfolio: InvestmentCopilotPortfolioBrief,
        investor_policy: InvestmentCopilotInvestorPolicy,
    ) -> InvestmentCopilotDecisionPolicy:
        hard_rules = [
            "任何交易建议必须先通过账户风控检查。",
            "数据源不可用或数据过期时，建议只能进入观察，不进入执行。",
            "默认输出行动建议单，不自动下单。",
            f"现金底线不低于账户权益 {investor_policy.cash_floor_ratio:.0%}。",
            f"单股上限不超过账户权益 {investor_policy.max_single_stock_ratio:.0%}。",
            f"期权仓位不超过账户权益 {investor_policy.max_options_ratio:.0%}。",
        ]
        if portfolio.blocking_guardrail_count:
            hard_rules.append("存在阻断级风控时，禁止新增期权和单股风险敞口。")
        if investor_policy.forbidden_symbols:
            hard_rules.append(f"禁买清单：{', '.join(investor_policy.forbidden_symbols)}。")

        return InvestmentCopilotDecisionPolicy(
            stance=investor_policy.stance,
            hard_rules=hard_rules,
            review_questions=[
                "这条建议是否改善了整体资产结构？",
                "如果判断错了，最大亏损和退出条件是什么？",
                "有没有更简单的不行动方案？",
            ],
        )
