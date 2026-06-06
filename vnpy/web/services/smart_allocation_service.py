from __future__ import annotations

from decimal import Decimal
from typing import Any

from vnpy.web.contracts.smart_allocation import (
    SmartAllocationCallSpreadCandidateResponse,
    SmartAllocationCallSpreadDailyRecommendationResponse,
    SmartAllocationDashboardResponse,
    SmartAllocationCashflowEventResponse,
    SmartAllocationGuardrailResponse,
    SmartAllocationLeapsCandidateResponse,
    SmartAllocationProfileResponse,
    SmartAllocationRecommendationResponse,
    SmartAllocationSnapshotResponse,
    SmartAllocationTargetsResponse,
    SmartAllocationWaterfallTransferResponse,
    SmartAllocationWheelCandidateResponse,
    SmartAllocationWheelCandidatePoolSourceResponse,
    SmartAllocationWheelDailyRecommendationResponse,
)
from vnpy.web.db import load_db_settings
from vnpy.web.domain.smart_allocation.calculator import calculate_allocation_targets, decimal_from
from vnpy.web.domain.smart_allocation.call_spread import (
    build_call_spread_daily_recommendation,
    list_call_spread_symbols,
)
from vnpy.web.domain.smart_allocation.classifier import snapshot_from_legacy_portfolio_status
from vnpy.web.domain.smart_allocation.guardrails import run_guardrail_checks
from vnpy.web.domain.smart_allocation.leaps import classify_leaps_candidate
from vnpy.web.domain.smart_allocation.models import (
    AllocationProfile,
    AllocationSnapshot,
    AllocationTargets,
    CashflowEvent,
    GuardrailViolation,
    IncomeStatus,
    RebalanceRecommendation,
)
from vnpy.web.domain.smart_allocation.rebalance import generate_recommendations
from vnpy.web.domain.smart_allocation.store import SmartAllocationStore
from vnpy.web.domain.smart_allocation.waterfall import plan_waterfall_transfer
from vnpy.web.domain.smart_allocation.wheel import build_daily_wheel_recommendation, build_wheel_candidates


def _float(value: Decimal) -> float:
    return float(value)


def _optional_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


class SmartAllocationService:
    def __init__(self, store: SmartAllocationStore | None = None) -> None:
        self._store = store or SmartAllocationStore(load_db_settings())
        profiles, active_profile_id = self._store.load_profiles()
        self._profiles: dict[str, AllocationProfile] = {profile.id: profile for profile in profiles}
        self._snapshots: dict[str, AllocationSnapshot] = {}
        for profile in profiles:
            snapshot = self._store.load_latest_snapshot(profile.id)
            if snapshot is not None:
                self._snapshots[profile.id] = snapshot
        self._data_warnings: list[str] = []
        self._active_profile_id = self._select_active_profile_id(profiles, active_profile_id)

    def create_profile(
        self,
        *,
        age: int,
        income_status: str,
        name: str = "智能仓位默认方案",
        rebalance_threshold: float = 0.05,
        allow_bull_market_leaps_relaxation: bool = False,
        quality_stock_symbols: list[str] | None = None,
        wheel_symbols: list[str] | None = None,
        leaps_symbols: list[str] | None = None,
    ) -> AllocationProfile:
        profile = AllocationProfile(
            age=age,
            income_status=IncomeStatus(income_status),
            name=name,
            rebalance_threshold=decimal_from(rebalance_threshold),
            allow_bull_market_leaps_relaxation=allow_bull_market_leaps_relaxation,
            quality_stock_symbols=tuple(quality_stock_symbols or ()),
            wheel_symbols=tuple(wheel_symbols or ()),
            leaps_symbols=tuple(leaps_symbols or ()),
        )
        self._profiles[profile.id] = profile
        self._active_profile_id = profile.id
        self._store.upsert_profile(profile, active=True)
        return profile

    def get_profile_response(self, profile_id: str) -> SmartAllocationProfileResponse:
        return self._profile_response(self._get_profile(profile_id))

    def update_profile(
        self,
        profile_id: str,
        *,
        age: int,
        income_status: str,
        name: str = "智能仓位默认方案",
        rebalance_threshold: float = 0.05,
        allow_bull_market_leaps_relaxation: bool = False,
        quality_stock_symbols: list[str] | None = None,
        wheel_symbols: list[str] | None = None,
        leaps_symbols: list[str] | None = None,
    ) -> AllocationProfile:
        self._get_profile(profile_id)
        profile = AllocationProfile(
            id=profile_id,
            age=age,
            income_status=IncomeStatus(income_status),
            name=name,
            rebalance_threshold=decimal_from(rebalance_threshold),
            allow_bull_market_leaps_relaxation=allow_bull_market_leaps_relaxation,
            quality_stock_symbols=tuple(quality_stock_symbols or ()),
            wheel_symbols=tuple(wheel_symbols or ()),
            leaps_symbols=tuple(leaps_symbols or ()),
        )
        was_active = self._active_profile_id == profile_id
        self._profiles[profile.id] = profile
        self._store.upsert_profile(profile, active=was_active)
        return profile

    def activate_profile(self, profile_id: str) -> SmartAllocationProfileResponse:
        profile = self._get_profile(profile_id)
        self._active_profile_id = profile.id
        self._store.upsert_profile(profile, active=True)
        return self._profile_response(profile)

    def list_profiles(self) -> list[SmartAllocationProfileResponse]:
        self._ensure_profile()
        return [self._profile_response(profile) for profile in self._profiles.values()]

    def get_dashboard(self, profile_id: str | None = None) -> SmartAllocationDashboardResponse:
        profile = self._get_profile(profile_id)
        snapshot = self._snapshots.get(profile.id) or self._default_snapshot()
        return self._build_dashboard(profile, snapshot)

    def refresh_snapshot(self, profile_id: str | None, payload: dict) -> SmartAllocationDashboardResponse:
        profile = self._get_profile(profile_id)
        snapshot = AllocationSnapshot(
            total_equity=decimal_from(payload.get("total_equity", 0)),
            cash_value=decimal_from(payload.get("cash_value", 0)),
            dca_value=decimal_from(payload.get("dca_value", 0)),
            options_value=decimal_from(payload.get("options_value", 0)),
            wheel_value=decimal_from(payload.get("wheel_value", 0)),
            leaps_value=decimal_from(payload.get("leaps_value", 0)),
            margin_used=decimal_from(payload.get("margin_used", 0)),
            unclassified_value=decimal_from(payload.get("unclassified_value", 0)),
            single_stock_values={key: decimal_from(value) for key, value in payload.get("single_stock_values", {}).items()},
            latest_rsi_by_symbol={key: decimal_from(value) for key, value in payload.get("latest_rsi_by_symbol", {}).items()},
            open_leaps_symbols=list(payload.get("open_leaps_symbols", [])),
            source_inputs={str(key): str(value) for key, value in payload.get("source_inputs", {}).items()},
        )
        self._snapshots[profile.id] = snapshot
        self._store.insert_snapshot(profile.id, snapshot)
        if snapshot.total_equity > 0:
            self._store.insert_cashflow_event(
                profile.id,
                CashflowEvent(
                    event_type="snapshot_waterfall_audit",
                    amount=snapshot.total_equity,
                    source_bucket="system",
                    target_bucket="waterfall",
                    note=(
                        "资金快照已刷新，系统自动重算现金流瀑布状态："
                        f"现金 {snapshot.cash_value}，定投 {snapshot.dca_value}，期权 {snapshot.options_value}。"
                    ),
                ),
            )
        return self._build_dashboard(profile, snapshot)

    def refresh_from_legacy_portfolio_status(
        self,
        profile_id: str | None,
        payload: dict,
    ) -> SmartAllocationDashboardResponse:
        profile = self._get_profile(profile_id)
        snapshot = snapshot_from_legacy_portfolio_status(profile, payload)
        self._snapshots[profile.id] = snapshot
        self._store.insert_snapshot(profile.id, snapshot)
        return self._build_dashboard(profile, snapshot)

    def record_cashflow_event(
        self,
        profile_id: str | None,
        *,
        event_type: str,
        amount: float,
        source_bucket: str = "options",
        target_bucket: str = "cash",
        symbol: str | None = None,
        note: str = "",
    ) -> list[SmartAllocationWaterfallTransferResponse]:
        profile = self._get_profile(profile_id)
        snapshot = self._snapshots.get(profile.id) or self._default_snapshot()
        targets = calculate_allocation_targets(profile, snapshot.total_equity)
        event = CashflowEvent(
            event_type=event_type,
            amount=decimal_from(amount),
            source_bucket=source_bucket,
            target_bucket=target_bucket,
            symbol=symbol,
            note=note,
        )
        self._store.insert_cashflow_event(profile.id, event)
        transfers = plan_waterfall_transfer(profile, snapshot, targets, event)
        updated_snapshot = self._apply_cashflow_event(snapshot, event)
        self._snapshots[profile.id] = updated_snapshot
        self._store.insert_snapshot(profile.id, updated_snapshot)
        return [
            SmartAllocationWaterfallTransferResponse(
                amount=_float(item.amount),
                source_bucket=item.source_bucket,
                target_bucket=item.target_bucket,
                target_sub_bucket=item.target_sub_bucket,
                reason=item.reason,
            )
            for item in transfers
        ]

    @staticmethod
    def _apply_cashflow_event(snapshot: AllocationSnapshot, event: CashflowEvent) -> AllocationSnapshot:
        amount = event.amount
        total_equity = snapshot.total_equity
        cash_value = snapshot.cash_value
        dca_value = snapshot.dca_value
        options_value = snapshot.options_value
        wheel_value = snapshot.wheel_value
        leaps_value = snapshot.leaps_value

        if event.event_type in {"wheel_premium_received", "leaps_profit_realized", "cash_bucket_topup", "manual_adjustment"}:
            cash_value += amount
            total_equity += amount
        elif event.event_type == "leaps_entry":
            cash_value = max(cash_value - amount, Decimal("0"))
            leaps_value += amount
            options_value += amount
        elif event.event_type == "leaps_exit":
            released = min(leaps_value, amount)
            cash_value += amount
            leaps_value -= released
            options_value = max(options_value - released, Decimal("0"))
        elif event.event_type == "dca_injection":
            cash_value = max(cash_value - amount, Decimal("0"))
            dca_value += amount

        return AllocationSnapshot(
            total_equity=total_equity,
            cash_value=cash_value,
            dca_value=dca_value,
            options_value=options_value,
            wheel_value=wheel_value,
            leaps_value=leaps_value,
            margin_used=snapshot.margin_used,
            unclassified_value=snapshot.unclassified_value,
            single_stock_values=snapshot.single_stock_values,
            latest_rsi_by_symbol=snapshot.latest_rsi_by_symbol,
            open_leaps_symbols=snapshot.open_leaps_symbols,
            source_inputs=snapshot.source_inputs,
        )

    def list_cashflow_events(self, profile_id: str | None = None) -> list[CashflowEvent]:
        profile = self._get_profile(profile_id)
        return self._store.list_cashflow_events(profile.id)

    def list_cashflow_event_responses(self, profile_id: str | None = None) -> list[SmartAllocationCashflowEventResponse]:
        return [
            SmartAllocationCashflowEventResponse(
                event_type=item.event_type,
                amount=_float(item.amount),
                source_bucket=item.source_bucket,
                target_bucket=item.target_bucket,
                symbol=item.symbol,
                note=item.note,
                created_at=item.created_at.isoformat(),
            )
            for item in self.list_cashflow_events(profile_id)
        ]

    def latest_snapshot_response(self, profile_id: str | None = None) -> SmartAllocationSnapshotResponse:
        profile = self._get_profile(profile_id)
        snapshot = self._snapshots.get(profile.id) or self._default_snapshot()
        return self._snapshot_response(snapshot)

    def list_recommendations(self, profile_id: str | None = None) -> list[SmartAllocationRecommendationResponse]:
        return self.get_dashboard(profile_id).recommendations

    def set_recommendation_status(
        self,
        profile_id: str | None,
        recommendation_id: str,
        *,
        status: str,
        user_note: str = "",
    ) -> list[SmartAllocationRecommendationResponse]:
        profile = self._get_profile(profile_id)
        self._store.set_recommendation_status(profile.id, recommendation_id, status=status, user_note=user_note)
        return self.list_recommendations(profile.id)

    def list_leaps_candidates(self, profile_id: str | None = None) -> list[SmartAllocationLeapsCandidateResponse]:
        profile = self._get_profile(profile_id)
        snapshot = self._snapshots.get(profile.id) or self._default_snapshot()
        symbols = set(profile.leaps_symbols) | set(snapshot.latest_rsi_by_symbol)
        candidates = [
            classify_leaps_candidate(profile, symbol, snapshot.latest_rsi_by_symbol.get(symbol, Decimal("99")))
            for symbol in sorted(symbols)
        ]
        return [
            SmartAllocationLeapsCandidateResponse(
                symbol=item.symbol,
                rsi=_float(item.rsi),
                status=item.status,
                reason=item.reason,
            )
            for item in candidates
        ]

    def list_wheel_candidates(self, profile_id: str | None = None) -> list[SmartAllocationWheelCandidateResponse]:
        profile = self._get_profile(profile_id)
        snapshot = self._snapshots.get(profile.id) or self._default_snapshot()
        targets = calculate_allocation_targets(profile, snapshot.total_equity)
        candidates = build_wheel_candidates(profile, snapshot, targets)
        return [
            SmartAllocationWheelCandidateResponse(
                symbol=item.symbol,
                source=item.source,
                score=item.score,
                status=item.status,
                estimated_cash_required=_float(item.estimated_cash_required),
                max_contracts=item.max_contracts,
                reason=item.reason,
                blockers=list(item.blockers),
            )
            for item in candidates
        ]

    def get_daily_wheel_recommendation(
        self,
        profile_id: str | None = None,
    ) -> SmartAllocationWheelDailyRecommendationResponse:
        profile = self._get_profile(profile_id)
        snapshot = self._snapshots.get(profile.id) or self._default_snapshot()
        targets = calculate_allocation_targets(profile, snapshot.total_equity)
        recommendation = build_daily_wheel_recommendation(profile, snapshot, targets)
        return SmartAllocationWheelDailyRecommendationResponse(
            scan_date=recommendation.scan_date,
            account_equity=_float(recommendation.account_equity),
            wheel_target=_float(recommendation.wheel_target),
            wheel_available=_float(recommendation.wheel_available),
            candidate_count=recommendation.candidate_count,
            actionable_count=recommendation.actionable_count,
            candidates=[
                SmartAllocationWheelCandidateResponse(
                    symbol=item.symbol,
                    source=item.source,
                    score=item.score,
                    status=item.status,
                    estimated_cash_required=_float(item.estimated_cash_required),
                    max_contracts=item.max_contracts,
                    reason=item.reason,
                    blockers=list(item.blockers),
                )
                for item in recommendation.candidates
            ],
            pool_sources=[
                SmartAllocationWheelCandidatePoolSourceResponse(
                    name=item.name,
                    count=item.count,
                    symbols=list(item.symbols),
                    rule=item.rule,
                )
                for item in recommendation.pool_sources
            ],
            methodology=list(recommendation.methodology),
        )

    def get_daily_call_spread_recommendation(
        self,
        profile_id: str | None = None,
    ) -> SmartAllocationCallSpreadDailyRecommendationResponse:
        profile = self._get_profile(profile_id)
        snapshot = self._snapshots.get(profile.id) or self._default_snapshot()
        targets = calculate_allocation_targets(profile, snapshot.total_equity)
        symbols = list_call_spread_symbols(profile, snapshot)
        option_chains, option_summaries = self._load_latest_call_option_context(symbols)
        recommendation = build_call_spread_daily_recommendation(
            profile,
            snapshot,
            targets,
            option_chains=option_chains,
            option_summaries=option_summaries,
        )
        return SmartAllocationCallSpreadDailyRecommendationResponse(
            scan_date=recommendation.scan_date,
            account_equity=_float(recommendation.account_equity),
            options_available=_float(recommendation.options_available),
            per_trade_limit=_float(recommendation.per_trade_limit),
            candidate_count=recommendation.candidate_count,
            actionable_count=recommendation.actionable_count,
            candidates=[
                SmartAllocationCallSpreadCandidateResponse(
                    symbol=item.symbol,
                    source=item.source,
                    score=item.score,
                    status=item.status,
                    expiration_date=item.expiration_date,
                    long_strike=_optional_float(item.long_strike),
                    short_strike=_optional_float(item.short_strike),
                    net_debit=_float(item.net_debit),
                    max_profit=_float(item.max_profit),
                    max_loss=_float(item.max_loss),
                    reward_risk=_float(item.reward_risk),
                    break_even=_optional_float(item.break_even),
                    max_contracts=item.max_contracts,
                    underlying_price=_optional_float(item.underlying_price),
                    reason=item.reason,
                    blockers=list(item.blockers),
                )
                for item in recommendation.candidates
            ],
            methodology=list(recommendation.methodology),
        )

    @staticmethod
    def _load_latest_call_option_context(
        symbols: list[str],
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
        normalized_symbols = sorted({symbol.strip().upper().replace(".US", "") for symbol in symbols if symbol.strip()})
        if not normalized_symbols:
            return {}, {}
        try:
            from vnpy.web.tenx_hunter.config import load_settings
            from vnpy.web.tenx_hunter.db import connect
        except ModuleNotFoundError:
            return {}, {}

        try:
            settings = load_settings()
            with connect(settings) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        WITH latest AS (
                            SELECT symbol, MAX(trade_date) AS trade_date
                            FROM ods.us_option_chain_raw
                            WHERE market = 'US' AND option_type = 'call' AND symbol = ANY(%s)
                            GROUP BY symbol
                        )
                        SELECT r.symbol, r.expiration_date, r.contract_symbol, r.strike, r.bid, r.ask,
                               r.volume, r.open_interest, r.underlying_price
                        FROM ods.us_option_chain_raw r
                        JOIN latest l ON l.symbol = r.symbol AND l.trade_date = r.trade_date
                        WHERE r.market = 'US' AND r.option_type = 'call'
                        ORDER BY r.symbol, r.expiration_date, r.strike
                        """,
                        (normalized_symbols,),
                    )
                    option_rows = cur.fetchall()
                    cur.execute(
                        """
                        WITH latest AS (
                            SELECT symbol, MAX(trade_date) AS trade_date
                            FROM dws.security_option_chain_summary_daily
                            WHERE market = 'US' AND symbol = ANY(%s)
                            GROUP BY symbol
                        )
                        SELECT s.symbol, s.underlying_price, s.selection_score, s.liquidity_score,
                               s.flow_sentiment, s.data_quality_flag, s.summary_json
                        FROM dws.security_option_chain_summary_daily s
                        JOIN latest l ON l.symbol = s.symbol AND l.trade_date = s.trade_date
                        WHERE s.market = 'US'
                        """,
                        (normalized_symbols,),
                    )
                    summary_rows = cur.fetchall()
        except Exception:
            return {}, {}

        chains: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in normalized_symbols}
        for row in option_rows:
            symbol = str(row.get("symbol", "")).upper()
            chains.setdefault(symbol, []).append(dict(row))

        summaries: dict[str, dict[str, Any]] = {}
        for row in summary_rows:
            symbol = str(row.get("symbol", "")).upper()
            summary = dict(row.get("summary_json") or {})
            summary.update({key: value for key, value in row.items() if key != "summary_json"})
            summaries[symbol] = summary
        return chains, summaries

    def _select_active_profile_id(
        self,
        profiles: list[AllocationProfile],
        active_profile_id: str | None,
    ) -> str | None:
        if not profiles:
            return None
        if active_profile_id:
            active_snapshot = self._snapshots.get(active_profile_id)
            if not self._is_reference_fixture_snapshot(active_snapshot):
                return active_profile_id
            for profile in profiles:
                snapshot = self._snapshots.get(profile.id)
                if not self._is_reference_fixture_snapshot(snapshot):
                    return profile.id
            return active_profile_id
        return profiles[0].id

    @staticmethod
    def _is_reference_fixture_snapshot(snapshot: AllocationSnapshot | None) -> bool:
        if snapshot is None:
            return False
        return (
            snapshot.total_equity == Decimal("400000")
            and snapshot.cash_value == Decimal("20000")
            and snapshot.dca_value == Decimal("232000")
            and snapshot.options_value == Decimal("148000")
            and snapshot.wheel_value == Decimal("118400")
            and snapshot.leaps_value == Decimal("29600")
            and snapshot.margin_used == Decimal("0")
            and not snapshot.single_stock_values
        )

    def _ensure_profile(self) -> AllocationProfile:
        if self._active_profile_id and self._active_profile_id in self._profiles:
            return self._profiles[self._active_profile_id]
        return self.create_profile(age=28, income_status=IncomeStatus.STABLE.value)

    def _get_profile(self, profile_id: str | None) -> AllocationProfile:
        if profile_id:
            return self._profiles[profile_id]
        return self._ensure_profile()

    @staticmethod
    def _default_snapshot() -> AllocationSnapshot:
        return AllocationSnapshot(
            total_equity=Decimal("0"),
            cash_value=Decimal("0"),
            dca_value=Decimal("0"),
            options_value=Decimal("0"),
            wheel_value=Decimal("0"),
            leaps_value=Decimal("0"),
        )

    def _build_dashboard(
        self,
        profile: AllocationProfile,
        snapshot: AllocationSnapshot,
    ) -> SmartAllocationDashboardResponse:
        targets = calculate_allocation_targets(profile, snapshot.total_equity)
        guardrails = run_guardrail_checks(profile, snapshot, targets)
        recommendations = self._apply_recommendation_statuses(
            profile.id,
            generate_recommendations(profile, snapshot, targets),
        )
        risk_level = self._dashboard_risk_level(guardrails)
        health_score = max(0, 100 - len(guardrails) * 15 - sum(20 for item in guardrails if item.blocking))
        return SmartAllocationDashboardResponse(
            profile=self._profile_response(profile),
            snapshot=self._snapshot_response(snapshot),
            targets=self._targets_response(targets),
            guardrails=[self._guardrail_response(item) for item in guardrails],
            recommendations=[self._recommendation_response(item) for item in recommendations],
            health_score=health_score,
            risk_level=risk_level,
            data_warnings=[],
            snapshot_source="reference_fixture" if self._is_reference_fixture_snapshot(snapshot) else "persistent",
        )

    def _apply_recommendation_statuses(
        self,
        profile_id: str,
        recommendations: list[RebalanceRecommendation],
    ) -> list[RebalanceRecommendation]:
        statuses = self._store.load_recommendation_statuses(profile_id)
        if not statuses:
            return recommendations
        updated: list[RebalanceRecommendation] = []
        for item in recommendations:
            state = statuses.get(item.id)
            if not state:
                updated.append(item)
                continue
            updated.append(
                RebalanceRecommendation(
                    id=item.id,
                    recommendation_type=item.recommendation_type,
                    priority=item.priority,
                    amount=item.amount,
                    reason=item.reason,
                    before_state=item.before_state,
                    after_state=item.after_state,
                    status=state["status"],
                    symbol=item.symbol,
                    user_note=state["user_note"],
                )
            )
        return updated

    @staticmethod
    def _dashboard_risk_level(guardrails: list[GuardrailViolation]) -> str:
        if any(item.risk_level.value == "red" for item in guardrails):
            return "red"
        if any(item.risk_level.value == "orange" for item in guardrails):
            return "orange"
        if guardrails:
            return "yellow"
        return "green"

    @staticmethod
    def _profile_response(profile: AllocationProfile) -> SmartAllocationProfileResponse:
        return SmartAllocationProfileResponse(
            id=profile.id,
            age=profile.age,
            income_status=profile.income_status.value,
            name=profile.name,
            rebalance_threshold=_float(profile.rebalance_threshold),
            allow_bull_market_leaps_relaxation=profile.allow_bull_market_leaps_relaxation,
            quality_stock_symbols=list(profile.quality_stock_symbols),
            wheel_symbols=list(profile.wheel_symbols),
            leaps_symbols=list(profile.leaps_symbols),
            qqqm_symbol=profile.qqqm_symbol,
            voo_symbol=profile.voo_symbol,
        )

    @staticmethod
    def _snapshot_response(snapshot: AllocationSnapshot) -> SmartAllocationSnapshotResponse:
        return SmartAllocationSnapshotResponse(
            total_equity=_float(snapshot.total_equity),
            cash_value=_float(snapshot.cash_value),
            dca_value=_float(snapshot.dca_value),
            options_value=_float(snapshot.options_value),
            wheel_value=_float(snapshot.wheel_value),
            leaps_value=_float(snapshot.leaps_value),
            margin_used=_float(snapshot.margin_used),
            unclassified_value=_float(snapshot.unclassified_value),
            single_stock_values={key: _float(value) for key, value in snapshot.single_stock_values.items()},
            latest_rsi_by_symbol={key: _float(value) for key, value in snapshot.latest_rsi_by_symbol.items()},
            open_leaps_symbols=snapshot.open_leaps_symbols,
            source_inputs=snapshot.source_inputs,
            snapshot_at=snapshot.snapshot_at.isoformat(),
        )

    @staticmethod
    def _targets_response(targets: AllocationTargets) -> SmartAllocationTargetsResponse:
        return SmartAllocationTargetsResponse(
            dca_ratio=_float(targets.dca_ratio),
            cash_ratio=_float(targets.cash_ratio),
            options_ratio=_float(targets.options_ratio),
            dca_value=_float(targets.dca_value),
            cash_value=_float(targets.cash_value),
            options_value=_float(targets.options_value),
            qqqm_value=_float(targets.qqqm_value),
            voo_value=_float(targets.voo_value),
            quality_stock_value=_float(targets.quality_stock_value),
            single_stock_limit=_float(targets.single_stock_limit),
            wheel_value=_float(targets.wheel_value),
            leaps_value=_float(targets.leaps_value),
            margin_limit=_float(targets.margin_limit),
        )

    @staticmethod
    def _guardrail_response(item: GuardrailViolation) -> SmartAllocationGuardrailResponse:
        return SmartAllocationGuardrailResponse(
            rule_code=item.rule_code,
            risk_level=item.risk_level.value,
            message=item.message,
            actual_value=_float(item.actual_value),
            limit_value=_float(item.limit_value),
            recommended_action=item.recommended_action,
            blocking=item.blocking,
        )

    @staticmethod
    def _recommendation_response(item: RebalanceRecommendation) -> SmartAllocationRecommendationResponse:
        return SmartAllocationRecommendationResponse(
            id=item.id,
            recommendation_type=item.recommendation_type,
            priority=item.priority,
            amount=_float(item.amount),
            reason=item.reason,
            before_state=item.before_state,
            after_state=item.after_state,
            status=item.status,
            symbol=item.symbol,
            user_note=item.user_note,
        )
