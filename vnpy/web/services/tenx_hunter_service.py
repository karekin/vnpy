from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from vnpy.web.contracts.tenx_hunter import (
    TenxActionRow,
    TenxAlertCenterResponse,
    TenxAlertCreateRequest,
    TenxAlertItemRow,
    TenxCandidateRow,
    TenxDiscoverCandidateCreateRequest,
    TenxEarningsDeskEventRow,
    TenxEarningsDeskMetrics,
    TenxEarningsDeskResponse,
    TenxEarningsLensResponse,
    TenxEarningsOptionRow,
    TenxEarningsShortlineRow,
    TenxEvidenceItemRow,
    TenxEventMonitorEventRow,
    TenxEventMonitorResponse,
    TenxEventMonitorRuleRow,
    TenxEventMonitorSourceRow,
    TenxFreshnessRow,
    TenxLifecycleStageRow,
    TenxMutationResponse,
    TenxPriceMapHitReviewRow,
    TenxPriceMapResponse,
    TenxPriceSnapshotRow,
    TenxPromotionCheckRow,
    TenxResearchCardResponse,
    TenxResearchReportResponse,
    TenxResearchReportUploadResponse,
    TenxRiskItemRow,
    TenxScoreBreakdownRow,
    TenxThemeRow,
    TenxTimelineEventRow,
    TenxUniverseBucketRow,
    TenxWatchlistItemRow,
    TenxWatchlistMutationRequest,
    TenxWatchlistUpdateRequest,
    TenxWhySelectedRow,
    TenxWorkspaceSnapshotResponse,
)
from vnpy.web.services.political_signal_service import PoliticalSignalService
from vnpy.web.tenx_hunter.config import Settings, load_settings
from vnpy.web.tenx_hunter.db import connect
from vnpy.web.tenx_hunter.event_monitor import (
    EventMonitorEvent,
    EventMonitorSnapshot,
    build_event_monitor_snapshot,
    event_digest,
    format_utc_label,
    utc_now,
)
from vnpy.web.tenx_hunter.scoring import (
    CN_SCORE_PROFILE,
    US_SCORE_PROFILE,
    CandidateExplanation,
    ScoreComponents,
    build_candidate_explanation,
)


DEFAULT_USER_ID = "local-default-user"


class TenxHunterService:
    def __init__(self) -> None:
        self._settings = load_settings()
        self._bootstrap_schema()

    def _bootstrap_schema(self) -> None:
        """Create oltp/olap/dim schemas and tables on first use."""
        from vnpy.web.base_store import PgStore
        PgStore.ensure_full_schema(self._settings)

    @staticmethod
    def _canonical_stage(stage: str | None) -> str:
        normalized = (stage or "discovery").strip().lower()
        return {
            "early": "discovery",
        }.get(normalized, normalized)

    @staticmethod
    def _normalize_market(market: str | None, settings: Settings) -> str:
        value = (market or settings.default_market or "CN").strip().upper()
        return value if value in {"CN", "US"} else settings.default_market

    def _universe(self, market: str) -> tuple[str, str, str, list[TenxUniverseBucketRow]]:
        universe = self._settings.market_universes[market]
        return (
            universe.name,
            universe.strategy,
            universe.description,
            [
                TenxUniverseBucketRow(
                    slug=bucket.slug.replace("_", "-"),
                    label=bucket.label,
                    rationale=bucket.rationale,
                    symbol_count=len(bucket.symbols),
                    sample_symbols=bucket.symbols[:4],
                )
                for bucket in universe.buckets
            ],
        )

    @staticmethod
    def _format_date(value: date | datetime | str | None) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _format_timestamp(value: datetime | str | None) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return str(value)

    @staticmethod
    def _market_cap_label(market_cap: float | None, *, market: str) -> str:
        if market_cap is None:
            return "N/A"
        currency = "¥" if market == "CN" else "$"
        if market_cap >= 1_000_000_000_000:
            return f"{currency}{market_cap / 1_000_000_000_000:.1f}T"
        if market_cap >= 1_000_000_000:
            return f"{currency}{market_cap / 1_000_000_000:.0f}B"
        if market_cap >= 1_000_000:
            return f"{currency}{market_cap / 1_000_000:.0f}M"
        return f"{currency}{market_cap:.0f}"

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if value in (None, ""):
            return []
        return [value]

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @classmethod
    def _rule_payload_list(cls, payload: dict[str, Any], key: str) -> list[str]:
        value = payload.get(key)
        return [str(item).strip() for item in cls._as_list(value) if str(item).strip()]

    @staticmethod
    def _rule_payload_text(payload: dict[str, Any], key: str, default: str = "") -> str:
        value = payload.get(key)
        if value is None:
            return default
        return str(value).strip() or default

    @staticmethod
    def _risk_level(risk_tags: list[Any], negative_event_count: int) -> str:
        total_risk = len(risk_tags) + negative_event_count
        if total_risk >= 3:
            return "high"
        if total_risk >= 1:
            return "medium"
        return "low"

    @staticmethod
    def _momentum_from_return(return_5d: float | None) -> str:
        value = return_5d or 0.0
        if value >= 0.05:
            return "strengthening"
        if value <= -0.05:
            return "cooling"
        return "stable"

    @staticmethod
    def _watchlist_status(risk_level: str, score: int, alert_type: str) -> str:
        if risk_level == "high":
            return "at-risk"
        if alert_type == "candidate_upgrade" or score >= 85:
            return "strengthening"
        return "needs-review"

    @staticmethod
    def _flow_status_label(status: str) -> str:
        return {
            "hot-lead": "热度线索",
            "candidate": "候选验证",
            "watch-ready": "可晋级观察",
            "watching": "观察池",
            "alerting": "事件提醒中",
            "blocked": "暂不晋级",
        }.get(status, status)

    @staticmethod
    def _promotion_checks(stage: str, evidence_count: int, risk_level: str, momentum: str) -> list[TenxPromotionCheckRow]:
        return [
            TenxPromotionCheckRow(
                key="stage",
                label="阶段",
                passed=stage in {"validation", "acceleration"},
                detail="需要进入 validation/acceleration，不能只停留在早期发现。",
            ),
            TenxPromotionCheckRow(
                key="evidence",
                label="证据",
                passed=evidence_count >= 2,
                detail=f"当前 {evidence_count} 条，观察池要求至少 2 条可复核证据。",
            ),
            TenxPromotionCheckRow(
                key="risk",
                label="风险",
                passed=risk_level != "high",
                detail=f"当前风险等级 {risk_level}，高风险先补反证和无效条件。",
            ),
            TenxPromotionCheckRow(
                key="momentum",
                label="动量",
                passed=momentum != "cooling",
                detail=f"当前动量 {momentum}，降温标的先回到候选池复核。",
            ),
        ]

    @classmethod
    def _candidate_flow(
        cls,
        *,
        symbol: str,
        stage: str,
        evidence_count: int,
        risk_level: str,
        momentum: str,
        watch_symbols: set[str],
        alert_symbols: set[str],
    ) -> tuple[str, str, list[TenxPromotionCheckRow]]:
        checks = cls._promotion_checks(stage, evidence_count, risk_level, momentum)
        if symbol in alert_symbols:
            status = "alerting"
            summary = "已在观察池并存在事件/价格提醒，后续由 Alerts 打断注意力。"
        elif symbol in watch_symbols:
            status = "watching"
            summary = "已确认进入观察池，继续跟踪事件、价格结构和反证。"
        elif stage in {"crowded", "falsified"} or risk_level == "high":
            status = "blocked"
            summary = "拥挤、证伪或高风险状态，暂不自动晋级观察池。"
        elif all(item.passed for item in checks):
            status = "watch-ready"
            summary = "满足观察池晋级条件，可以由人工确认后进入事件追踪。"
        else:
            status = "candidate"
            summary = "仍在候选验证，需要补足阶段、证据、风险或动量条件。"
        return status, summary, checks

    @staticmethod
    def _theme_trend(status: str) -> str:
        if status == "上升":
            return "rising"
        if status == "转弱":
            return "weakening"
        return "stable"

    @staticmethod
    def _timeline_type(event_type: str, source_kind: str) -> str:
        lowered = (event_type or source_kind or "").lower()
        if "earn" in lowered:
            return "earnings"
        if "filing" in lowered or "10-" in lowered or "13f" in lowered or "holding" in lowered or source_kind == "institutional" or "公告" in lowered:
            return "filing"
        if "risk" in lowered:
            return "risk"
        if "supply" in lowered:
            return "supply-chain"
        return "price" if source_kind == "news" else "capex"

    @staticmethod
    def _stage_label(stage: str) -> str:
        return {
            "discovery": "早期发现",
            "validation": "逻辑验证",
            "acceleration": "业绩加速",
            "crowded": "机构拥挤",
            "falsified": "逻辑证伪",
        }.get(stage, stage)

    def _freshness(self, updated_at: str, market: str) -> TenxFreshnessRow:
        source = "Tushare 股票链路 + TenX 聚合" if market == "CN" else "SEC / Polygon / Yahoo + TenX 聚合"
        coverage = "候选池、研究卡、观察池、提醒中心"
        return TenxFreshnessRow(
            updated_at=updated_at,
            data_complete=bool(updated_at),
            source_summary=source,
            coverage=coverage,
        )

    @staticmethod
    def _format_percent_value(value: float | None) -> str:
        if value is None:
            return "N/A"
        scaled = value * 100 if -1 <= value <= 1 else value
        return f"{scaled:.1f}%"

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_int(value: Any) -> int:
        if value is None or value == "":
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _available_actions(symbol: str | None = None) -> list[TenxActionRow]:
        actions = [
            TenxActionRow(id="add-watchlist", label="加入观察池", kind="watchlist"),
            TenxActionRow(id="create-alert", label="创建提醒", kind="alert"),
        ]
        if symbol:
            actions.append(TenxActionRow(id="export-summary", label="导出摘要", kind="export"))
        return actions

    @staticmethod
    def _price_target_value(payload: Any, key: str) -> float | None:
        if not isinstance(payload, dict):
            return None
        value = payload.get(key)
        return float(value) if value is not None else None

    def _price_snapshot_from_row(self, row: Any | None) -> TenxPriceSnapshotRow | None:
        if row is None:
            return None
        base = row["base_target"] or {}
        bull = row["bull_target"] or {}
        bear = row["bear_zone"] or {}
        return TenxPriceSnapshotRow(
            as_of_date=self._format_date(row["as_of_date"]),
            current_price=float(row["current_price"]) if row["current_price"] is not None else None,
            posture=row["posture"],
            posture_label=row["posture_label"],
            confidence=row["confidence"],
            base_target_low=self._price_target_value(base, "low"),
            base_target_high=self._price_target_value(base, "high"),
            bull_target_low=self._price_target_value(bull, "low"),
            bull_target_high=self._price_target_value(bull, "high"),
            bear_zone_low=self._price_target_value(bear, "low"),
            bear_zone_high=self._price_target_value(bear, "high"),
            upside_pct_mid=self._price_target_value(base, "upside_pct_mid"),
            downside_pct_mid=self._price_target_value(bear, "upside_pct_mid"),
        )

    def _price_map_from_row(self, row: Any | None, hit_reviews: list[Any] | None = None) -> TenxPriceMapResponse | None:
        if row is None:
            return None
        return TenxPriceMapResponse(
            market=row["market"],
            symbol=row["symbol"],
            as_of_date=self._format_date(row["as_of_date"]),
            current_price=float(row["current_price"]) if row["current_price"] is not None else None,
            posture=row["posture"],
            posture_label=row["posture_label"],
            confidence=row["confidence"],
            base_target=row["base_target"],
            bull_target=row["bull_target"],
            bear_zone=row["bear_zone"],
            key_levels=row["key_levels"] or [],
            scenario_paths=row["scenario_paths"] or [],
            invalidation_rules=row["invalidation_rules"] or [],
            evidence_refs=row["evidence_refs"] or [],
            explanation=row["explanation"] or {},
            hit_reviews=[
                TenxPriceMapHitReviewRow(
                    snapshot_date=self._format_date(review["snapshot_date"]),
                    review_date=self._format_date(review["review_date"]),
                    horizon_days=int(review["horizon_days"] or 0),
                    base_hit=review["base_hit"],
                    bull_hit=review["bull_hit"],
                    bear_breached=review["bear_breached"],
                    max_close=float(review["max_close"]) if review["max_close"] is not None else None,
                    min_close=float(review["min_close"]) if review["min_close"] is not None else None,
                    hit_summary=review["hit_summary"],
                )
                for review in (hit_reviews or [])
            ],
        )

    def _fetch_price_map(self, conn: Any, market: str, symbol: str) -> TenxPriceMapResponse | None:
        row = conn.execute(
            """
            SELECT market, symbol, as_of_date, current_price, posture, posture_label, confidence,
                   base_target, bull_target, bear_zone, key_levels, scenario_paths,
                   invalidation_rules, evidence_refs, explanation
            FROM olap.price_map_current
            WHERE market = %s AND symbol = %s
            """,
            (market, symbol.upper()),
        ).fetchone()
        reviews = conn.execute(
            """
            SELECT snapshot_date, review_date, horizon_days, base_hit, bull_hit,
                   bear_breached, max_close, min_close, hit_summary
            FROM olap.price_map_hit_review_daily
            WHERE market = %s AND symbol = %s
            ORDER BY snapshot_date DESC, review_date DESC
            LIMIT 6
            """,
            (market, symbol.upper()),
        ).fetchall()
        return self._price_map_from_row(row, reviews)

    def _score_components_from_row(self, row: Any, market: str) -> ScoreComponents:
        return ScoreComponents(
            growth=float(row["growth_score"] or 0.0),
            quality=float(row["quality_score"] or 0.0),
            momentum=float(row["momentum_score"] or 0.0),
            valuation=float(row["valuation_score"] or 0.0),
            size=float(row["size_score"] or 0.0),
            evidence=float(row["evidence_score"] or 0.0),
            theme=float(row["theme_score"] or 0.0),
            risk=float(row["risk_score"] or 0.0),
            industry_prosperity=float(row["industry_prosperity_score"] or 0.0),
            leader_position=float(row["leader_position_score"] or 0.0),
            financial_acceleration=float(row["financial_acceleration_score"] or 0.0),
            cashflow_quality=float(row["cashflow_quality_score"] or 0.0),
            moat=float(row["moat_score"] or 0.0),
            valuation_chip=float(row["valuation_chip_score"] or 0.0),
            profile=CN_SCORE_PROFILE if market == "CN" else US_SCORE_PROFILE,
        )

    def _candidate_explanation(self, row: Any, market: str) -> CandidateExplanation:
        components = self._score_components_from_row(row, market)
        return build_candidate_explanation(
            self._canonical_stage(row["stage"]),
            components,
            market=market,
            ps_ttm=float(row["ps_ttm"] or 0.0) if row["ps_ttm"] is not None else None,
            pe_ttm=float(row["pe_ttm"] or 0.0) if row.get("pe_ttm") is not None else None,
            pb=float(row["pb"] or 0.0) if row.get("pb") is not None else None,
            market_cap=float(row["market_cap"] or 0.0) if row["market_cap"] is not None else None,
            return_5d=float(row["return_5d"] or 0.0) if row["return_5d"] is not None else None,
            distance_from_high=float(row["distance_from_recent_high"] or 0.0) if row["distance_from_recent_high"] is not None else None,
        )

    def _score_breakdown(self, row: Any, market: str) -> list[TenxScoreBreakdownRow]:
        if market == "CN":
            entries = [
                ("industry_prosperity", "行业景气", float(row["industry_prosperity_score"] or 0.0), 25, "赛道是不是长坡厚雪"),
                ("leader_position", "龙头位置", float(row["leader_position_score"] or 0.0), 20, "公司是否站在关键位置"),
                ("financial_acceleration", "财务加速", float(row["financial_acceleration_score"] or 0.0), 25, "收入利润是否加速"),
                ("cashflow_quality", "现金流质量", float(row["cashflow_quality_score"] or 0.0), 15, "增长质量是否可靠"),
                ("moat", "研发与护城河", float(row["moat_score"] or 0.0), 10, "下一轮增长有没有支撑"),
                ("valuation_chip", "估值与筹码", float(row["valuation_chip_score"] or 0.0), 5, "当前赔率是否拥挤"),
            ]
        else:
            entries = [
                ("growth", "增长", float(row["growth_score"] or 0.0), 22, "收入扩张是否兑现"),
                ("quality", "质量", float(row["quality_score"] or 0.0), 16, "利润率与现金流是否稳定"),
                ("valuation", "估值", float(row["valuation_score"] or 0.0), 14, "赔率是否仍可接受"),
                ("size", "市值弹性", float(row["size_score"] or 0.0), 12, "体量是否仍有赔率"),
                ("evidence", "证据", float(row["evidence_score"] or 0.0), 12, "验证信号是否持续"),
                ("theme", "主题", float(row["theme_score"] or 0.0), 6, "与主线的相关性"),
                ("momentum", "动量", float(row["momentum_score"] or 0.0), 8, "短期走势是否拥挤"),
                ("risk", "风险", float(row["risk_score"] or 0.0), 10, "风险是否仍可控"),
            ]
        return [
            TenxScoreBreakdownRow(
                key=key,
                label=label,
                score=round(score, 2),
                weight=weight,
                summary=summary,
                positive_notes=[f"{label}得分 {score:.1f}"],
                negative_notes=[] if score >= 50 else [f"{label}仍需补充更多验证"],
            )
            for key, label, score, weight, summary in entries
        ]

    def _lifecycle_stage(self, stage: str) -> TenxLifecycleStageRow:
        stage = self._canonical_stage(stage)
        return TenxLifecycleStageRow(
            key=stage,
            label=self._stage_label(stage),
            summary={
                "discovery": "赛道成立，但仍需要更多证据确认。",
                "validation": "逻辑开始兑现，指标进入重点跟踪区。",
                "acceleration": "财务与主题共振，是最值得深挖的窗口。",
                "crowded": "市场预期充分，赔率开始下降。",
                "falsified": "关键假设受损，需要优先复核。",
            }[stage],
        )

    @staticmethod
    def _ensure_discover_candidate_table(conn: Any) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oltp.user_discover_candidate_current (
                user_id TEXT NOT NULL,
                security_id INTEGER NOT NULL,
                market TEXT NOT NULL DEFAULT 'US',
                symbol TEXT NOT NULL,
                company_name TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual',
                stage TEXT NOT NULL DEFAULT 'discovery',
                theme TEXT NOT NULL DEFAULT 'Manual',
                thesis TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                score NUMERIC(10,2) NOT NULL DEFAULT 55,
                status TEXT NOT NULL DEFAULT 'active',
                source_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (user_id, market, symbol)
            )
            """
        )

    @staticmethod
    def _next_security_id(conn: Any) -> int:
        row = conn.execute("SELECT COALESCE(MAX(security_id), 0) + 1 AS next_id FROM dim.security").fetchone()
        return int(row["next_id"])

    def _ensure_security(
        self,
        conn: Any,
        *,
        market: str,
        symbol: str,
        name: str | None = None,
    ) -> Any:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol is required")

        row = conn.execute(
            """
            SELECT security_id, market, symbol, company_name, sector, industry
            FROM dim.security
            WHERE symbol = %s
            """,
            (normalized_symbol,),
        ).fetchone()
        if row is not None:
            if name and row["company_name"] in {normalized_symbol, "Unknown", "Unknown Company"}:
                conn.execute(
                    "UPDATE dim.security SET company_name = %s WHERE security_id = %s",
                    (name.strip(), row["security_id"]),
                )
                row = {**dict(row), "company_name": name.strip()}
            return row

        security_id = self._next_security_id(conn)
        company_name = (name or normalized_symbol).strip()
        conn.execute(
            """
            INSERT INTO dim.security (
                security_id, market, symbol, company_name, exchange_name, currency,
                listing_status, sector, industry
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                security_id,
                market,
                normalized_symbol,
                company_name,
                None,
                "USD" if market == "US" else "CNY",
                "active",
                "Unknown",
                "Unknown",
            ),
        )
        return {
            "security_id": security_id,
            "market": market,
            "symbol": normalized_symbol,
            "company_name": company_name,
            "sector": "Unknown",
            "industry": "Unknown",
        }

    def get_workspace_snapshot(self, market: str | None = None) -> TenxWorkspaceSnapshotResponse:
        market = self._normalize_market(market, self._settings)
        universe_name, universe_strategy, universe_description, universe_buckets = self._universe(market)
        with connect(self._settings) as conn:
            self._ensure_discover_candidate_table(conn)
            snapshot_row = conn.execute(
                "SELECT MAX(trade_date) AS trade_date FROM olap.candidate_pool_daily WHERE market = %s",
                (market,),
            ).fetchone()
            latest_trade_date = snapshot_row["trade_date"] if snapshot_row else None
            if latest_trade_date is None:
                latest_trade_date = date.today()

            watch_state_rows = conn.execute(
                """
                SELECT symbol
                FROM oltp.user_watchlist_state_current
                WHERE user_id = %s
                  AND market = %s
                  AND state = 'watching'
                """,
                (DEFAULT_USER_ID, market),
            ).fetchall()
            watch_symbols = {str(row["symbol"]) for row in watch_state_rows}

            alert_count_rows = conn.execute(
                """
                SELECT symbol, COUNT(*) AS alert_count
                FROM (
                    SELECT symbol
                    FROM olap.watchlist_alert_daily
                    WHERE user_id = %s
                      AND market = %s
                    UNION ALL
                    SELECT symbol
                    FROM oltp.user_alert_rule_current
                    WHERE user_id = %s
                      AND market = %s
                      AND status <> 'archived'
                ) alerts
                GROUP BY symbol
                """,
                (DEFAULT_USER_ID, market, DEFAULT_USER_ID, market),
            ).fetchall()
            alert_counts = {str(row["symbol"]): int(row["alert_count"] or 0) for row in alert_count_rows}
            alert_symbols = {symbol for symbol, count in alert_counts.items() if count > 0}
            alert_due_rows = conn.execute(
                """
                SELECT DISTINCT ON (symbol)
                    symbol,
                    rule_payload->>'due_at' AS due_at
                FROM oltp.user_alert_rule_current
                WHERE user_id = %s
                  AND market = %s
                  AND status <> 'archived'
                  AND COALESCE(rule_payload->>'due_at', '') <> ''
                ORDER BY symbol, updated_at DESC
                """,
                (DEFAULT_USER_ID, market),
            ).fetchall()
            alert_due_by_symbol = {str(row["symbol"]): str(row["due_at"]) for row in alert_due_rows if row["due_at"]}

            candidate_rows = conn.execute(
                """
                WITH evidence AS (
                    SELECT security_id, COUNT(*) AS evidence_count
                    FROM olap.security_document_signal
                    WHERE market = %s
                    GROUP BY security_id
                ),
                latest_event AS (
                    SELECT DISTINCT ON (security_id)
                        security_id,
                        title,
                        event_time
                    FROM olap.security_event_timeline
                    WHERE market = %s
                    ORDER BY security_id, event_time DESC
                ),
                theme_pick AS (
                    SELECT
                        st.security_id,
                        MIN(t.theme_name) AS theme_name
                    FROM dim.security_theme st
                    JOIN dim.theme t ON t.theme_id = st.theme_id
                    JOIN dim.security s ON s.security_id = st.security_id
                    WHERE s.market = %s
                    GROUP BY st.security_id
                )
                SELECT
                    c.market,
                    c.security_id,
                    c.symbol,
                    d.company_name,
                    COALESCE(d.sector, d.industry, 'Unknown') AS sector,
                    COALESCE(tp.theme_name, 'Growth') AS theme_name,
                    c.total_score,
                    c.stage,
                    c.reason_summary,
                    c.risk_tags,
                    m.close,
                    m.return_1d,
                    m.return_5d,
                    m.distance_from_recent_high,
                    m.market_cap,
                    m.ps_ttm,
                    m.pe_ttm,
                    m.pb,
                    rc.thesis,
                    COALESCE(e.evidence_count, 0) AS evidence_count,
                    le.title AS next_event,
                    sc.growth_score,
                    sc.quality_score,
                    sc.momentum_score,
                    sc.valuation_score,
                    sc.size_score,
                    sc.evidence_score,
                    sc.risk_score,
                    sc.theme_score,
                    sc.industry_prosperity_score,
                    sc.leader_position_score,
                    sc.financial_acceleration_score,
                    sc.cashflow_quality_score,
                    sc.moat_score,
                    sc.valuation_chip_score
                FROM olap.candidate_pool_daily c
                JOIN dim.security d ON d.security_id = c.security_id
                LEFT JOIN olap.security_market_daily m
                  ON m.security_id = c.security_id AND m.trade_date = c.trade_date
                LEFT JOIN olap.research_card_current rc ON rc.security_id = c.security_id
                LEFT JOIN olap.security_score_component_daily sc
                  ON sc.security_id = c.security_id AND sc.trade_date = c.trade_date
                LEFT JOIN evidence e ON e.security_id = c.security_id
                LEFT JOIN latest_event le ON le.security_id = c.security_id
                LEFT JOIN theme_pick tp ON tp.security_id = c.security_id
                WHERE c.market = %s AND c.trade_date = %s
                ORDER BY c.rank_no
                LIMIT 20
                """,
                (market, market, market, market, latest_trade_date),
            ).fetchall()

            candidates: list[TenxCandidateRow] = []
            freshness = self._freshness(self._format_date(latest_trade_date), market)
            existing_candidate_symbols: set[str] = set()
            for row in candidate_rows:
                explanation = self._candidate_explanation(row, market)
                stage = self._canonical_stage(row["stage"])
                evidence_count = int(row["evidence_count"] or 0)
                risk_level = self._risk_level(self._as_list(row["risk_tags"]), 0)
                momentum = self._momentum_from_return(float(row["return_5d"] or 0.0))
                existing_candidate_symbols.add(str(row["symbol"]))
                flow_status, promotion_summary, promotion_checks = self._candidate_flow(
                    symbol=row["symbol"],
                    stage=stage,
                    evidence_count=evidence_count,
                    risk_level=risk_level,
                    momentum=momentum,
                    watch_symbols=watch_symbols,
                    alert_symbols=alert_symbols,
                )
                candidates.append(
                    TenxCandidateRow(
                        market=market,
                        symbol=row["symbol"],
                        name=row["company_name"],
                        sector=row["sector"],
                        theme=row["theme_name"],
                        stage=stage,
                        lifecycle_stage=self._lifecycle_stage(stage),
                        score=int(round(float(row["total_score"] or 0.0))),
                        score_change=round(float(row["return_5d"] or 0.0) * 100, 1),
                        price=float(row["close"] or 0.0),
                        price_change_pct=round(float(row["return_1d"] or 0.0) * 100, 1),
                        market_cap_label=self._market_cap_label(float(row["market_cap"]), market=market) if row["market_cap"] is not None else "N/A",
                        evidence_count=evidence_count,
                        risk_level=risk_level,
                        momentum=momentum,
                        next_event=row["next_event"] or "等待下一事件更新",
                        thesis=row["thesis"] or row["reason_summary"],
                        key_signal=row["reason_summary"],
                        selection_reason=explanation.selection_reason,
                        stage_reason=explanation.stage_reason,
                        crowding_note=explanation.crowding_note,
                        score_drivers=explanation.score_drivers,
                        why_selected=TenxWhySelectedRow(summary=explanation.selection_reason, bullets=explanation.score_drivers),
                        score_breakdown=self._score_breakdown(row, market),
                        flow_status=flow_status,
                        flow_status_label=self._flow_status_label(flow_status),
                        promotion_summary=promotion_summary,
                        promotion_checks=promotion_checks,
                        freshness=freshness,
                        available_actions=self._available_actions(row["symbol"]),
                    )
                )

            manual_rows = conn.execute(
                """
                WITH evidence AS (
                    SELECT security_id, COUNT(*) AS evidence_count
                    FROM olap.security_document_signal
                    WHERE market = %s
                    GROUP BY security_id
                ),
                latest_event AS (
                    SELECT DISTINCT ON (security_id)
                        security_id,
                        title,
                        event_time
                    FROM olap.security_event_timeline
                    WHERE market = %s
                    ORDER BY security_id, event_time DESC
                )
                SELECT
                    md.market,
                    md.security_id,
                    md.symbol,
                    COALESCE(NULLIF(md.company_name, ''), d.company_name, md.symbol) AS company_name,
                    COALESCE(d.sector, d.industry, 'Unknown') AS sector,
                    COALESCE(NULLIF(md.theme, ''), 'Manual') AS theme_name,
                    md.score AS total_score,
                    md.stage,
                    CASE
                        WHEN COALESCE(NULLIF(md.note, ''), '') <> ''
                            THEN md.thesis || ' · ' || md.note
                        ELSE md.thesis
                    END AS reason_summary,
                    '[]'::jsonb AS risk_tags,
                    jsonb_build_array(COALESCE(NULLIF(md.theme, ''), 'Manual')) AS theme_tags,
                    m.close,
                    m.return_1d,
                    m.return_5d,
                    m.distance_from_recent_high,
                    m.market_cap,
                    m.ps_ttm,
                    m.pe_ttm,
                    m.pb,
                    COALESCE(rc.thesis, md.thesis) AS thesis,
                    COALESCE(e.evidence_count, 0) AS evidence_count,
                    COALESCE(le.title, '等待下一次事件验证') AS next_event,
                    sc.growth_score,
                    sc.quality_score,
                    sc.momentum_score,
                    sc.valuation_score,
                    sc.size_score,
                    sc.evidence_score,
                    sc.risk_score,
                    sc.theme_score,
                    sc.industry_prosperity_score,
                    sc.leader_position_score,
                    sc.financial_acceleration_score,
                    sc.cashflow_quality_score,
                    sc.moat_score,
                    sc.valuation_chip_score
                FROM oltp.user_discover_candidate_current md
                LEFT JOIN dim.security d ON d.security_id = md.security_id
                LEFT JOIN LATERAL (
                    SELECT *
                    FROM olap.security_market_daily m
                    WHERE m.security_id = md.security_id
                    ORDER BY m.trade_date DESC
                    LIMIT 1
                ) m ON TRUE
                LEFT JOIN LATERAL (
                    SELECT *
                    FROM olap.security_score_component_daily sc
                    WHERE sc.security_id = md.security_id
                    ORDER BY sc.trade_date DESC
                    LIMIT 1
                ) sc ON TRUE
                LEFT JOIN olap.research_card_current rc ON rc.security_id = md.security_id
                LEFT JOIN evidence e ON e.security_id = md.security_id
                LEFT JOIN latest_event le ON le.security_id = md.security_id
                WHERE md.user_id = %s
                  AND md.market = %s
                  AND md.status = 'active'
                ORDER BY md.updated_at DESC
                """,
                (market, market, DEFAULT_USER_ID, market),
            ).fetchall()

            manual_candidates: list[TenxCandidateRow] = []
            for row in manual_rows:
                if str(row["symbol"]) in existing_candidate_symbols:
                    continue
                explanation = self._candidate_explanation(row, market)
                stage = self._canonical_stage(row["stage"])
                evidence_count = int(row["evidence_count"] or 0)
                risk_level = self._risk_level(self._as_list(row["risk_tags"]), 0)
                momentum = self._momentum_from_return(float(row["return_5d"] or 0.0))
                flow_status, promotion_summary, promotion_checks = self._candidate_flow(
                    symbol=row["symbol"],
                    stage=stage,
                    evidence_count=evidence_count,
                    risk_level=risk_level,
                    momentum=momentum,
                    watch_symbols=watch_symbols,
                    alert_symbols=alert_symbols,
                )
                manual_candidates.append(
                    TenxCandidateRow(
                        market=market,
                        symbol=row["symbol"],
                        name=row["company_name"],
                        sector=row["sector"],
                        theme=row["theme_name"],
                        stage=stage,
                        lifecycle_stage=self._lifecycle_stage(stage),
                        score=int(round(float(row["total_score"] or 0.0))),
                        score_change=round(float(row["return_5d"] or 0.0) * 100, 1),
                        price=float(row["close"] or 0.0),
                        price_change_pct=round(float(row["return_1d"] or 0.0) * 100, 1),
                        market_cap_label=self._market_cap_label(float(row["market_cap"]), market=market) if row["market_cap"] is not None else "N/A",
                        evidence_count=evidence_count,
                        risk_level=risk_level,
                        momentum=momentum,
                        next_event=row["next_event"] or "等待下一事件更新",
                        thesis=row["thesis"] or row["reason_summary"],
                        key_signal=row["reason_summary"],
                        selection_reason=explanation.selection_reason,
                        stage_reason=explanation.stage_reason,
                        crowding_note=explanation.crowding_note,
                        score_drivers=explanation.score_drivers,
                        why_selected=TenxWhySelectedRow(summary=explanation.selection_reason, bullets=explanation.score_drivers),
                        score_breakdown=self._score_breakdown(row, market),
                        flow_status=flow_status,
                        flow_status_label=self._flow_status_label(flow_status),
                        promotion_summary=promotion_summary,
                        promotion_checks=promotion_checks,
                        freshness=freshness,
                        available_actions=self._available_actions(row["symbol"]),
                    )
                )
            if manual_candidates:
                candidates = manual_candidates + candidates

            theme_rows = conn.execute(
                """
                SELECT market, theme_id, theme_name, heat_score, status, key_drivers, representative_symbols
                FROM olap.theme_radar_daily
                WHERE market = %s AND trade_date = %s
                ORDER BY heat_score DESC
                """,
                (market, latest_trade_date),
            ).fetchall()
            themes = [
                TenxThemeRow(
                    market=market,
                    slug=str(row["theme_id"]).replace("_", "-"),
                    name=row["theme_name"],
                    heat=int(round(float(row["heat_score"] or 0.0))),
                    trend=self._theme_trend(row["status"]),
                    driver=(self._as_list(row["key_drivers"]) or [row["theme_name"]])[0],
                    evidence=[str(item) for item in self._as_list(row["key_drivers"])],
                    related_symbols=[str(item) for item in self._as_list(row["representative_symbols"])],
                    freshness=freshness,
                )
                for row in theme_rows
            ]

            watchlist_rows = conn.execute(
                """
                SELECT
                    w.market,
                    w.symbol,
                    d.company_name,
                    COALESCE(a.alert_type, 'watch') AS alert_type,
                    COALESCE(a.severity, 'medium') AS severity,
                    COALESCE(a.alert_message, '等待下一次事件验证') AS alert_message,
                    COALESCE(c.total_score, 0) AS total_score,
                    COALESCE(c.risk_tags, '[]'::jsonb) AS risk_tags,
                    pm.as_of_date AS price_as_of_date,
                    pm.current_price AS price_current_price,
                    pm.posture AS price_posture,
                    pm.posture_label AS price_posture_label,
                    pm.confidence AS price_confidence,
                    pm.base_target AS price_base_target,
                    pm.bull_target AS price_bull_target,
                    pm.bear_zone AS price_bear_zone
                FROM oltp.user_watchlist_state_current w
                JOIN dim.security d ON d.security_id = w.security_id
                LEFT JOIN LATERAL (
                    SELECT alert_type, severity, alert_message
                    FROM olap.watchlist_alert_daily a
                    WHERE a.user_id = w.user_id
                      AND a.market = w.market
                      AND a.symbol = w.symbol
                    ORDER BY a.created_at DESC
                    LIMIT 1
                ) a ON TRUE
                LEFT JOIN olap.candidate_pool_daily c
                  ON c.security_id = w.security_id AND c.trade_date = %s AND c.market = w.market
                LEFT JOIN olap.price_map_current pm ON pm.security_id = w.security_id AND pm.market = w.market
                WHERE w.user_id = %s
                  AND w.market = %s
                  AND w.state = 'watching'
                ORDER BY c.total_score DESC NULLS LAST, w.symbol
                """,
                (latest_trade_date, DEFAULT_USER_ID, market),
            ).fetchall()
            watchlist: list[TenxWatchlistItemRow] = []
            for row in watchlist_rows:
                risk_level = self._risk_level(self._as_list(row["risk_tags"]), 1 if row["severity"] == "high" else 0)
                score = int(round(float(row["total_score"] or 0.0)))
                watchlist.append(
                    TenxWatchlistItemRow(
                        market=market,
                        symbol=row["symbol"],
                        name=row["company_name"],
                        thesis_status=self._watchlist_status(risk_level, score, row["alert_type"]),
                        alert_type=row["alert_type"],
                        last_event=row["alert_message"],
                        next_check="刷新最新数据后复核",
                        risk_level=risk_level,
                        score=score,
                        price_snapshot=self._price_snapshot_from_row(
                            {
                                "as_of_date": row["price_as_of_date"],
                                "current_price": row["price_current_price"],
                                "posture": row["price_posture"],
                                "posture_label": row["price_posture_label"],
                                "confidence": row["price_confidence"],
                                "base_target": row["price_base_target"],
                                "bull_target": row["price_bull_target"],
                                "bear_zone": row["price_bear_zone"],
                            }
                        )
                        if row["price_posture"] is not None
                        else None,
                        tracking_status="事件提醒中" if alert_counts.get(row["symbol"], 0) else "事件追踪中",
                        active_alert_count=alert_counts.get(row["symbol"], 0),
                        next_alert_due=alert_due_by_symbol.get(row["symbol"]),
                        available_actions=self._available_actions(row["symbol"]),
                    )
                )

            timeline_rows = conn.execute(
                """
                SELECT e.event_id, e.market, e.symbol, e.event_time, e.title, e.event_type, e.source_kind,
                       COALESCE(s.summary, e.title) AS summary
                FROM olap.security_event_timeline e
                LEFT JOIN olap.security_document_signal s ON s.event_id = e.event_id
                WHERE e.market = %s
                ORDER BY e.event_time DESC
                LIMIT 20
                """,
                (market,),
            ).fetchall()
            timeline = [
                TenxTimelineEventRow(
                    id=row["event_id"],
                    market=market,
                    symbol=row["symbol"],
                    date=self._format_date(row["event_time"]),
                    title=row["title"],
                    type=self._timeline_type(row["event_type"], row["source_kind"]),
                    summary=row["summary"],
                )
                for row in timeline_rows
            ]

            prompts = [
                "今天最值得先看哪 3 只候选？",
                "哪些提醒是真正会改变逻辑判断的？",
                "如果只保留一个主题，当前该保留谁？",
            ]

            return TenxWorkspaceSnapshotResponse(
                market=market,
                universe=universe_name,
                universe_strategy=universe_strategy,
                universe_description=universe_description,
                universe_buckets=universe_buckets,
                snapshot_at=self._format_date(latest_trade_date),
                freshness=freshness,
                available_actions=self._available_actions(),
                candidates=candidates,
                themes=themes,
                watchlist=watchlist,
                timeline=timeline,
                copilot_prompts=prompts,
            )

    def get_earnings_lens(self, market: str | None = None) -> TenxEarningsLensResponse:
        market = self._normalize_market(market, self._settings)
        snapshot = self.get_workspace_snapshot(market)
        notes: list[str] = []

        symbol_rows: dict[str, dict[str, Any]] = {}
        for candidate in snapshot.candidates:
            symbol_rows[candidate.symbol.upper()] = {
                "symbol": candidate.symbol,
                "name": candidate.name,
                "theme": candidate.theme,
                "stage": candidate.stage,
                "flow_status": candidate.flow_status,
                "flow_status_label": candidate.flow_status_label,
                "score": candidate.score,
                "score_change": candidate.score_change,
                "risk_level": candidate.risk_level,
                "momentum": candidate.momentum,
                "next_event": candidate.next_event,
            }

        for item in snapshot.watchlist:
            symbol_rows.setdefault(
                item.symbol.upper(),
                {
                    "symbol": item.symbol,
                    "name": item.name,
                    "theme": "Watchlist",
                    "stage": "validation",
                    "flow_status": "alerting" if item.active_alert_count > 0 else "watching",
                    "flow_status_label": "事件提醒中" if item.active_alert_count > 0 else "观察池",
                    "score": item.score,
                    "score_change": 0.0,
                    "risk_level": item.risk_level,
                    "momentum": "stable",
                    "next_event": item.next_check or item.last_event,
                },
            )

        symbols = sorted(symbol_rows)
        earnings_by_symbol: dict[str, dict[str, Any]] = {}
        options_by_symbol: dict[str, dict[str, Any]] = {}

        if symbols:
            with connect(self._settings) as conn:
                earnings_table = conn.execute(
                    "SELECT to_regclass('olap.security_earnings_calendar_current') AS table_name",
                ).fetchone()
                if earnings_table and earnings_table["table_name"]:
                    earnings_rows = conn.execute(
                        """
                        SELECT
                            symbol,
                            next_earnings_date,
                            days_to_earnings,
                            fiscal_period,
                            time_of_day,
                            eps_estimate,
                            revenue_estimate,
                            currency,
                            data_quality_flag,
                            source_vendor
                        FROM olap.security_earnings_calendar_current
                        WHERE market = %s
                          AND symbol = ANY(%s)
                        """,
                        (market, symbols),
                    ).fetchall()
                    earnings_by_symbol = {str(row["symbol"]).upper(): dict(row) for row in earnings_rows}
                else:
                    notes.append("财报日历表尚未初始化，短线窗口只显示候选池内已有事件。")

                option_table = conn.execute(
                    "SELECT to_regclass('olap.security_option_chain_summary_daily') AS table_name",
                ).fetchone()
                if market == "US" and option_table and option_table["table_name"]:
                    option_rows = conn.execute(
                        """
                        WITH latest AS (
                            SELECT symbol, MAX(trade_date) AS trade_date
                            FROM olap.security_option_chain_summary_daily
                            WHERE market = %s
                              AND symbol = ANY(%s)
                            GROUP BY symbol
                        )
                        SELECT
                            s.symbol,
                            s.underlying_price,
                            s.nearest_expiration,
                            s.expiration_count,
                            s.contract_count,
                            s.total_call_volume,
                            s.total_put_volume,
                            s.call_put_volume_ratio,
                            s.total_call_open_interest,
                            s.total_put_open_interest,
                            s.call_put_open_interest_ratio,
                            s.avg_implied_volatility,
                            s.max_pain_strike,
                            s.liquidity_score,
                            s.flow_score,
                            s.selection_score,
                            s.flow_sentiment,
                            s.data_quality_flag,
                            s.updated_at
                        FROM olap.security_option_chain_summary_daily s
                        JOIN latest l
                          ON l.symbol = s.symbol
                         AND l.trade_date = s.trade_date
                        WHERE s.market = %s
                        """,
                        (market, symbols, market),
                    ).fetchall()
                    options_by_symbol = {str(row["symbol"]).upper(): dict(row) for row in option_rows}
                elif market == "US":
                    notes.append("期权链摘要表尚未初始化，请先运行 TenX refresh-options 后查看财报期权。")
                else:
                    notes.append("财报期权当前只对 US 市场展示。")
        else:
            notes.append("当前候选池和观察池为空，暂无财报窗口可展示。")

        shortline = [
            self._earnings_shortline_row(market, item, earnings_by_symbol.get(symbol))
            for symbol, item in symbol_rows.items()
        ]
        shortline.sort(
            key=lambda item: (
                item.days_to_earnings is None,
                item.days_to_earnings if item.days_to_earnings is not None else 9999,
                -item.score,
                item.symbol,
            )
        )

        option_items = [
            self._earnings_option_row(market, item, earnings_by_symbol.get(symbol), options_by_symbol.get(symbol))
            for symbol, item in symbol_rows.items()
        ]
        option_items.sort(
            key=lambda item: (
                item.data_quality_flag != "ok",
                -(item.option_selection_score or -1),
                item.days_to_earnings if item.days_to_earnings is not None else 9999,
                item.symbol,
            )
        )

        return TenxEarningsLensResponse(
            market=market,
            snapshot_at=snapshot.snapshot_at,
            freshness=snapshot.freshness,
            shortline=shortline,
            options=option_items,
            notes=notes,
        )

    # ── Earnings Event Desk（市场维度全量，不依赖用户持仓） ────────────

    def get_earnings_desk(self, market: str | None = None, horizon_days: int = 45) -> TenxEarningsDeskResponse:
        """ADS 层：聚合全市场即将到来的财报事件，LEFT JOIN 期权摘要。"""
        market = self._normalize_market(market, self._settings)
        settings = self._settings
        notes: list[str] = []

        if market != "US":
            notes.append("财报事件看板当前仅支持 US 市场。")
            freshness = self._build_freshness(market, settings)
            return TenxEarningsDeskResponse(
                market="US" if market == "US" else "CN",
                snapshot_at=datetime.now(timezone.utc).isoformat(),
                freshness=freshness,
                metrics=TenxEarningsDeskMetrics(),
                events=[],
                notes=notes,
            )

        today = date.today()
        horizon = today + timedelta(days=horizon_days)
        snapshot_at = datetime.now(timezone.utc).isoformat()
        freshness = self._build_freshness(market, settings)

        with connect(settings) as conn:
            # 检查表是否存在
            earnings_check = conn.execute(
                "SELECT to_regclass('olap.security_earnings_calendar_current') AS t"
            ).fetchone()
            if not earnings_check or not earnings_check["t"]:
                notes.append("财报日历表尚未初始化，请先运行 pipeline bootstrap。")
                return TenxEarningsDeskResponse(
                    market="US", snapshot_at=snapshot_at, freshness=freshness,
                    metrics=TenxEarningsDeskMetrics(), events=[], notes=notes,
                )

            # 查询全市场财报事件 + LEFT JOIN dim.security + 期权摘要
            rows = conn.execute(
                """
                SELECT
                    e.market,
                    e.symbol,
                    e.next_earnings_date,
                    e.days_to_earnings,
                    e.fiscal_period,
                    e.time_of_day,
                    e.eps_estimate,
                    e.revenue_estimate,
                    COALESCE(e.currency, 'USD') AS currency,
                    e.data_quality_flag,
                    e.source_vendor,
                    s.company_name,
                    s.sector,
                    o.avg_implied_volatility,
                    o.max_pain_strike,
                    o.liquidity_score,
                    o.flow_score,
                    o.selection_score,
                    o.flow_sentiment,
                    o.data_quality_flag AS option_quality
                FROM olap.security_earnings_calendar_current e
                LEFT JOIN dim.security s
                  ON s.symbol = e.symbol AND s.market = e.market
                LEFT JOIN LATERAL (
                    SELECT
                        s2.avg_implied_volatility,
                        s2.max_pain_strike,
                        s2.liquidity_score,
                        s2.flow_score,
                        s2.selection_score,
                        s2.flow_sentiment,
                        s2.data_quality_flag
                    FROM olap.security_option_chain_summary_daily s2
                    WHERE s2.symbol = e.symbol AND s2.market = e.market
                    ORDER BY s2.trade_date DESC
                    LIMIT 1
                ) o ON TRUE
                WHERE e.market = %s
                  AND e.next_earnings_date >= %s
                  AND e.next_earnings_date <= %s
                  AND e.data_quality_flag IN ('ok', 'partial')
                ORDER BY e.days_to_earnings ASC, e.symbol
                """,
                (market, today, horizon),
            ).fetchall()

        events: list[TenxEarningsDeskEventRow] = []
        for row in rows:
            days_to = self._as_int(row.get("days_to_earnings"))
            priority: str = "P1" if days_to is not None and days_to <= 3 else "P2"
            option_signal, action = self._earnings_desk_option_signal(row)
            events.append(TenxEarningsDeskEventRow(
                market="US",
                symbol=str(row["symbol"]),
                name=str(row.get("company_name") or ""),
                sector=str(row.get("sector") or ""),
                next_earnings_date=self._format_date(row.get("next_earnings_date")) or None,
                days_to_earnings=days_to,
                fiscal_period=str(row.get("fiscal_period") or ""),
                time_of_day=str(row.get("time_of_day") or ""),
                eps_estimate=self._as_float(row.get("eps_estimate")),
                revenue_estimate=self._as_float(row.get("revenue_estimate")),
                currency=str(row.get("currency") or "USD"),
                data_quality_flag=str(row.get("data_quality_flag") or "unavailable"),
                source_vendor=str(row.get("source_vendor") or ""),
                avg_implied_volatility=self._as_float(row.get("avg_implied_volatility")),
                max_pain_strike=self._as_float(row.get("max_pain_strike")),
                liquidity_score=self._as_float(row.get("liquidity_score")),
                flow_score=self._as_float(row.get("flow_score")),
                option_selection_score=self._as_float(row.get("selection_score")),
                flow_sentiment=str(row.get("flow_sentiment") or "unknown"),
                option_signal=option_signal,
                priority=priority,
                action_label=action,
            ))

        # 统计指标
        p1_count = sum(1 for ev in events if ev.priority == "P1")
        option_readable = sum(1 for ev in events if ev.avg_implied_volatility is not None)
        ivs = [ev.avg_implied_volatility for ev in events if ev.avg_implied_volatility is not None]
        avg_move: float | None = None
        if ivs:
            avg_move = sum(ivs) / len(ivs)

        metrics = TenxEarningsDeskMetrics(
            total_events=len(events),
            p1_count=p1_count,
            option_readable_count=option_readable,
            avg_expected_move=avg_move,
        )

        return TenxEarningsDeskResponse(
            market="US",
            snapshot_at=snapshot_at,
            freshness=freshness,
            metrics=metrics,
            events=events,
            notes=notes,
        )

    @staticmethod
    def _earnings_desk_option_signal(row: dict[str, Any]) -> tuple[str, str]:
        """根据期权数据生成信号和行动标签。"""
        sel = row.get("selection_score")
        flow = row.get("flow_sentiment")
        quality = row.get("option_quality")

        if quality != "ok" or sel is None:
            return "期权数据缺失", "补期权链"

        sel_val = float(sel)
        if flow == "bullish":
            signal = "偏多，资金流看涨"
            action = "关注看涨价差"
        elif flow == "bearish":
            signal = "偏空，资金流看跌"
            action = "关注看跌价差"
        else:
            signal = "波动预期，方向不明"
            action = "关注跨式/宽跨式"

        if sel_val >= 80:
            action = f"高分 {action}"
        elif sel_val < 50:
            signal += "，期权分偏低"

        return signal, action

    def _earnings_shortline_row(
        self,
        market: str,
        item: dict[str, Any],
        earnings: dict[str, Any] | None,
    ) -> TenxEarningsShortlineRow:
        earnings = earnings or {}
        days_to = self._as_int(earnings.get("days_to_earnings")) if earnings.get("days_to_earnings") is not None else None
        quality = str(earnings.get("data_quality_flag") or "unavailable")
        signal, action = self._earnings_shortline_signal(score=int(item["score"]), days_to=days_to, quality=quality)
        return TenxEarningsShortlineRow(
            market="US" if market == "US" else "CN",
            symbol=str(item["symbol"]),
            name=str(item["name"]),
            theme=str(item["theme"]),
            stage=item["stage"],
            flow_status=item["flow_status"],
            flow_status_label=str(item["flow_status_label"]),
            score=int(item["score"]),
            score_change=float(item["score_change"]),
            risk_level=item["risk_level"],
            momentum=item["momentum"],
            next_event=str(item["next_event"]),
            next_earnings_date=self._format_date(earnings.get("next_earnings_date")) or None,
            days_to_earnings=days_to,
            fiscal_period=str(earnings.get("fiscal_period") or ""),
            time_of_day=str(earnings.get("time_of_day") or ""),
            eps_estimate=self._as_float(earnings.get("eps_estimate")),
            revenue_estimate=self._as_float(earnings.get("revenue_estimate")),
            currency=str(earnings.get("currency") or ("USD" if market == "US" else "CNY")),
            earnings_quality=quality,
            source_vendor=str(earnings.get("source_vendor") or ""),
            shortline_signal=signal,
            action_label=action,
        )

    @staticmethod
    def _earnings_shortline_signal(*, score: int, days_to: int | None, quality: str) -> tuple[str, str]:
        if days_to is None:
            return "缺少下一次财报日，先补日历数据。", "补财报日历"
        if days_to < 0:
            return "财报窗口已过，等待价格和业绩复盘。", "复盘"
        if quality not in {"ok", "partial"}:
            return "财报日历质量不足，不进入短线优先队列。", "刷新日历"
        if days_to <= 3 and score >= 80:
            return "高分标的临近财报，优先复核预期差和风险。", "优先复核"
        if days_to <= 10 and score >= 70:
            return "进入财报准备窗口，检查估值、预期和反证。", "准备清单"
        if days_to <= 21:
            return "财报窗口可见，保持观察并等待更多催化。", "观察"
        return "距离财报仍远，维持候选跟踪。", "低频跟踪"

    def _earnings_option_row(
        self,
        market: str,
        item: dict[str, Any],
        earnings: dict[str, Any] | None,
        option: dict[str, Any] | None,
    ) -> TenxEarningsOptionRow:
        earnings = earnings or {}
        option = option or {}
        quality = str(option.get("data_quality_flag") or "unavailable")
        selection_score = self._as_float(option.get("selection_score"))
        liquidity_score = self._as_float(option.get("liquidity_score"))
        signal, action = self._earnings_option_signal(
            quality=quality,
            selection_score=selection_score,
            liquidity_score=liquidity_score,
            flow_sentiment=str(option.get("flow_sentiment") or "unknown"),
        )
        return TenxEarningsOptionRow(
            market="US" if market == "US" else "CN",
            symbol=str(item["symbol"]),
            name=str(item["name"]),
            next_earnings_date=self._format_date(earnings.get("next_earnings_date")) or None,
            days_to_earnings=self._as_int(earnings.get("days_to_earnings")) if earnings.get("days_to_earnings") is not None else None,
            score=int(item["score"]),
            underlying_price=self._as_float(option.get("underlying_price")),
            nearest_expiration=self._format_date(option.get("nearest_expiration")) or None,
            expiration_count=self._as_int(option.get("expiration_count")),
            contract_count=self._as_int(option.get("contract_count")),
            total_call_volume=self._as_int(option.get("total_call_volume")),
            total_put_volume=self._as_int(option.get("total_put_volume")),
            call_put_volume_ratio=self._as_float(option.get("call_put_volume_ratio")),
            total_call_open_interest=self._as_int(option.get("total_call_open_interest")),
            total_put_open_interest=self._as_int(option.get("total_put_open_interest")),
            call_put_open_interest_ratio=self._as_float(option.get("call_put_open_interest_ratio")),
            avg_implied_volatility=self._as_float(option.get("avg_implied_volatility")),
            max_pain_strike=self._as_float(option.get("max_pain_strike")),
            liquidity_score=liquidity_score,
            flow_score=self._as_float(option.get("flow_score")),
            option_selection_score=selection_score,
            flow_sentiment=str(option.get("flow_sentiment") or "unknown"),
            data_quality_flag=quality,
            updated_at=self._format_timestamp(option.get("updated_at")),
            option_signal=signal,
            action_label=action,
        )

    @staticmethod
    def _earnings_option_signal(
        *,
        quality: str,
        selection_score: float | None,
        liquidity_score: float | None,
        flow_sentiment: str,
    ) -> tuple[str, str]:
        if quality != "ok":
            return "暂无可用期权链摘要，不生成期权表达。", "刷新期权链"
        if selection_score is not None and selection_score >= 70 and (liquidity_score or 0) >= 60:
            return "期权流动性和评分可复核，可进入结构筛选。", "结构筛选"
        if flow_sentiment in {"bullish", "bearish"}:
            return f"期权流向偏 {flow_sentiment}，先校验 IV 与最大亏损。", "校验风险"
        return "期权链可读，但只适合做波动率观察。", "观察 IV"

    def get_research_card(self, market: str | None, symbol: str) -> TenxResearchCardResponse | None:
        market = self._normalize_market(market, self._settings)
        with connect(self._settings) as conn:
            row = conn.execute(
                """
                SELECT
                    rc.market,
                    rc.symbol,
                    d.company_name,
                    COALESCE(d.sector, d.industry, 'Unknown') AS sector,
                    COALESCE(MIN(t.theme_name), 'Growth') AS theme_name,
                    rc.thesis,
                    rc.key_points,
                    rc.risk_points,
                    rc.next_watch_items,
                    rc.stage,
                    rc.total_score,
                    f.revenue_yoy,
                    f.netprofit_yoy,
                    f.op_margin,
                    f.fcf_margin,
                    f.cfo_to_np,
                    f.rd_ratio_ttm,
                    m.close,
                    m.return_1d,
                    m.return_5d,
                    m.distance_from_recent_high,
                    m.market_cap,
                    m.ps_ttm,
                    m.pe_ttm,
                    m.pb,
                    sc.growth_score,
                    sc.quality_score,
                    sc.momentum_score,
                    sc.valuation_score,
                    sc.size_score,
                    sc.evidence_score,
                    sc.risk_score,
                    sc.theme_score,
                    sc.industry_prosperity_score,
                    sc.leader_position_score,
                    sc.financial_acceleration_score,
                    sc.cashflow_quality_score,
                    sc.moat_score,
                    sc.valuation_chip_score
                FROM olap.research_card_current rc
                JOIN dim.security d ON d.security_id = rc.security_id
                LEFT JOIN dim.security_theme st ON st.security_id = rc.security_id
                LEFT JOIN dim.theme t ON t.theme_id = st.theme_id
                LEFT JOIN olap.security_financial_quarterly f
                  ON f.security_id = rc.security_id
                 AND f.report_period = (
                    SELECT MAX(report_period) FROM olap.security_financial_quarterly WHERE security_id = rc.security_id
                 )
                LEFT JOIN olap.security_market_daily m
                  ON m.security_id = rc.security_id
                 AND m.trade_date = (
                    SELECT MAX(trade_date) FROM olap.security_market_daily WHERE security_id = rc.security_id
                 )
                LEFT JOIN olap.security_score_component_daily sc
                  ON sc.security_id = rc.security_id
                 AND sc.trade_date = (
                    SELECT MAX(trade_date) FROM olap.security_score_component_daily WHERE security_id = rc.security_id
                 )
                WHERE rc.market = %s AND rc.symbol = %s
                GROUP BY
                    rc.market, rc.symbol, d.company_name, d.sector, d.industry, rc.thesis,
                    rc.key_points, rc.risk_points, rc.next_watch_items, rc.stage, rc.total_score,
                    f.revenue_yoy, f.netprofit_yoy, f.op_margin, f.fcf_margin, f.cfo_to_np, f.rd_ratio_ttm,
                    m.close, m.return_1d, m.return_5d, m.distance_from_recent_high, m.market_cap, m.ps_ttm, m.pe_ttm, m.pb,
                    sc.growth_score, sc.quality_score, sc.momentum_score, sc.valuation_score,
                    sc.size_score, sc.evidence_score, sc.risk_score, sc.theme_score,
                    sc.industry_prosperity_score, sc.leader_position_score, sc.financial_acceleration_score,
                    sc.cashflow_quality_score, sc.moat_score, sc.valuation_chip_score
                """,
                (market, symbol.upper()),
            ).fetchone()
            if row is None:
                return None

            evidence_rows = conn.execute(
                """
                SELECT e.event_id, e.source_kind, e.event_time, e.title, COALESCE(s.summary, e.title) AS summary
                FROM olap.security_event_timeline e
                LEFT JOIN olap.security_document_signal s ON s.event_id = e.event_id
                WHERE e.market = %s AND e.symbol = %s
                ORDER BY e.event_time DESC
                LIMIT 6
                """,
                (market, symbol.upper()),
            ).fetchall()
            evidence = [
                TenxEvidenceItemRow(
                    id=str(item["event_id"]),
                    source=str(item["source_kind"]).upper(),
                    published_at=self._format_timestamp(item["event_time"]),
                    title=item["title"],
                    note=item["summary"],
                    linked_to=["evidence"],
                )
                for item in evidence_rows
            ]

            facts = [
                f"最新价格 {float(row['close'] or 0.0):.2f}{'元' if market == 'CN' else '美元'}" if row["close"] is not None else "价格快照暂缺",
                f"最近 5 日变化 {self._format_percent_value(float(row['return_5d'] or 0.0))}" if row["return_5d"] is not None else "5 日走势暂缺",
                f"营收同比 {self._format_percent_value(float(row['revenue_yoy'] or 0.0))}" if row["revenue_yoy"] is not None else "营收同比暂缺",
                f"净利同比 {self._format_percent_value(float(row['netprofit_yoy'] or 0.0))}" if row.get("netprofit_yoy") is not None else "净利同比暂缺",
            ]
            explanation = self._candidate_explanation(row, market)
            freshness = self._freshness(self._format_date(datetime.now(timezone.utc)), market)
            price_map = self._fetch_price_map(conn, market, symbol)
            risk_items = [
                TenxRiskItemRow(
                    title=str(item),
                    severity="medium",
                    trigger="需要人工复核",
                    note=str(item),
                )
                for item in (self._as_list(row["risk_points"]) or ["暂无显著负面事件"])
            ]
            return TenxResearchCardResponse(
                market=market,
                symbol=row["symbol"],
                name=row["company_name"],
                sector=row["sector"],
                theme=row["theme_name"],
                stage=self._canonical_stage(row["stage"]),
                lifecycle_stage=self._lifecycle_stage(row["stage"]),
                score=int(round(float(row["total_score"] or 0.0))),
                thesis_summary=row["thesis"],
                selection_reason=explanation.selection_reason,
                stage_reason=explanation.stage_reason,
                crowding_note=explanation.crowding_note,
                score_drivers=explanation.score_drivers,
                why_selected=TenxWhySelectedRow(summary=explanation.selection_reason, bullets=explanation.score_drivers),
                score_breakdown=self._score_breakdown(row, market),
                facts=facts,
                thesis_points=[str(item) for item in self._as_list(row["key_points"])],
                evidence_items=evidence,
                risk_items=risk_items,
                next_watch_points=[str(item) for item in self._as_list(row["next_watch_items"])],
                price_map=price_map,
                freshness=freshness,
                available_actions=self._available_actions(row["symbol"]),
            )

    @staticmethod
    def _ensure_research_report_table(conn: Any) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oltp.user_research_report_current (
                report_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                market TEXT NOT NULL DEFAULT 'US',
                symbol TEXT NOT NULL,
                title TEXT NOT NULL,
                source_filename TEXT NOT NULL,
                content_markdown TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(user_id, market, symbol)
            )
            """
        )

    @staticmethod
    def _markdown_title(symbol: str, markdown: str) -> str:
        for line in markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if title:
                    return title[:120]
        return f"{symbol.upper()} 投研报告"

    @staticmethod
    def _markdown_word_count(markdown: str) -> int:
        return len([char for char in markdown if not char.isspace()])

    def _research_report_from_row(self, row: Any) -> TenxResearchReportResponse:
        markdown = row["content_markdown"]
        return TenxResearchReportResponse(
            report_id=str(row["report_id"]),
            market=row["market"],
            symbol=row["symbol"],
            title=row["title"],
            source_filename=row["source_filename"],
            content_markdown=markdown,
            word_count=self._markdown_word_count(markdown),
            status=row["status"],
            created_at=self._format_timestamp(row["created_at"]),
            updated_at=self._format_timestamp(row["updated_at"]),
        )

    def get_research_report(self, market: str | None, symbol: str) -> TenxResearchReportResponse | None:
        market = self._normalize_market(market, self._settings)
        with connect(self._settings) as conn:
            self._ensure_research_report_table(conn)
            row = conn.execute(
                """
                SELECT report_id, market, symbol, title, source_filename, content_markdown,
                       status, created_at, updated_at
                FROM oltp.user_research_report_current
                WHERE user_id = %s
                  AND market = %s
                  AND symbol = %s
                  AND status = 'active'
                """,
                (DEFAULT_USER_ID, market, symbol.upper()),
            ).fetchone()
            return self._research_report_from_row(row) if row else None

    def save_research_report(
        self,
        market: str | None,
        symbol: str,
        filename: str,
        content: bytes,
    ) -> TenxResearchReportUploadResponse:
        market = self._normalize_market(market, self._settings)
        if len(content) > 2_000_000:
            raise ValueError("research report markdown is too large; please keep it under 2 MB")
        try:
            markdown = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("research report must be UTF-8 markdown") from exc
        if not markdown.strip():
            raise ValueError("research report markdown is empty")
        if not filename.lower().endswith((".md", ".markdown", ".txt")):
            raise ValueError("research report must be a markdown file")

        normalized_symbol = symbol.upper()
        title = self._markdown_title(normalized_symbol, markdown)
        content_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)
        with connect(self._settings) as conn:
            self._ensure_research_report_table(conn)
            security = conn.execute(
                "SELECT security_id FROM dim.security WHERE market = %s AND symbol = %s",
                (market, normalized_symbol),
            ).fetchone()
            if security is None:
                raise ValueError(f"unknown symbol: {market}:{normalized_symbol}")
            row = conn.execute(
                """
                INSERT INTO oltp.user_research_report_current (
                    report_id, user_id, market, symbol, title, source_filename,
                    content_markdown, content_hash, status, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s)
                ON CONFLICT (user_id, market, symbol) DO UPDATE SET
                    title = EXCLUDED.title,
                    source_filename = EXCLUDED.source_filename,
                    content_markdown = EXCLUDED.content_markdown,
                    content_hash = EXCLUDED.content_hash,
                    status = 'active',
                    updated_at = EXCLUDED.updated_at
                RETURNING report_id, market, symbol, title, source_filename, content_markdown,
                          status, created_at, updated_at
                """,
                (
                    str(uuid4()),
                    DEFAULT_USER_ID,
                    market,
                    normalized_symbol,
                    title,
                    filename,
                    markdown,
                    content_hash,
                    now,
                    now,
                ),
            ).fetchone()
        return TenxResearchReportUploadResponse(
            message=f"{normalized_symbol} 投研报告已保存到知识库。",
            report=self._research_report_from_row(row),
        )

    def create_discover_candidate(self, payload: TenxDiscoverCandidateCreateRequest) -> TenxMutationResponse:
        market = self._normalize_market(payload.market, self._settings)
        normalized_symbol = payload.symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol is required")

        stage = self._canonical_stage(payload.stage)
        theme = (payload.theme or "Manual").strip() or "Manual"
        source = (payload.source or "manual").strip() or "manual"
        company_name = payload.name.strip() if payload.name else None
        thesis = (payload.thesis or payload.note or f"{normalized_symbol} 已由人工从热点线索纳入发现池，等待补充投研报告和可复核证据。").strip()
        note = (payload.note or "").strip()
        score = 58 if source == "hot-monitor" else 55

        with connect(self._settings) as conn:
            self._ensure_discover_candidate_table(conn)
            security = self._ensure_security(conn, market=market, symbol=normalized_symbol, name=company_name)
            company_name = company_name or security["company_name"] or normalized_symbol
            conn.execute(
                """
                INSERT INTO oltp.user_discover_candidate_current (
                    user_id, security_id, market, symbol, company_name, source,
                    stage, theme, thesis, note, score, status, source_payload,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, NOW(), NOW())
                ON CONFLICT (user_id, market, symbol) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    source = EXCLUDED.source,
                    stage = EXCLUDED.stage,
                    theme = EXCLUDED.theme,
                    thesis = EXCLUDED.thesis,
                    note = EXCLUDED.note,
                    score = GREATEST(oltp.user_discover_candidate_current.score, EXCLUDED.score),
                    status = 'active',
                    source_payload = EXCLUDED.source_payload,
                    updated_at = NOW()
                """,
                (
                    DEFAULT_USER_ID,
                    security["security_id"],
                    market,
                    normalized_symbol,
                    company_name,
                    source,
                    stage,
                    theme,
                    thesis,
                    note,
                    score,
                    Jsonb(
                        {
                            **payload.source_payload,
                            "trigger_scene": payload.trigger_scene,
                        }
                    ),
                ),
            )

        return TenxMutationResponse(
            ok=True,
            message=f"{normalized_symbol} 已加入发现池；下一步补投研报告、事件证据和晋级条件。",
        )

    def get_price_map(self, market: str | None, symbol: str) -> TenxPriceMapResponse | None:
        market = self._normalize_market(market, self._settings)
        with connect(self._settings) as conn:
            return self._fetch_price_map(conn, market, symbol)

    @staticmethod
    def _ensure_event_monitor_table(conn: Any) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oltp.user_event_monitor_event_current (
                monitor_event_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                market TEXT NOT NULL DEFAULT 'US',
                symbol TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                event_time TIMESTAMPTZ NOT NULL,
                due_at DATE,
                priority TEXT NOT NULL,
                evidence_grade TEXT NOT NULL,
                confidence TEXT NOT NULL,
                source TEXT NOT NULL,
                source_url TEXT NOT NULL,
                status TEXT NOT NULL,
                matched_rule TEXT NOT NULL,
                asset_relevance TEXT NOT NULL,
                event_layer JSONB NOT NULL DEFAULT '[]'::jsonb,
                structure_layer JSONB NOT NULL DEFAULT '[]'::jsonb,
                execution_layer JSONB NOT NULL DEFAULT '[]'::jsonb,
                invalidation_signals JSONB NOT NULL DEFAULT '[]'::jsonb,
                raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_event_monitor_market_time
            ON oltp.user_event_monitor_event_current (user_id, market, event_time)
            """
        )

    def _event_monitor_watchlist_symbols(self, conn: Any, market: str) -> set[str]:
        rows = conn.execute(
            """
            SELECT symbol
            FROM oltp.user_watchlist_state_current
            WHERE user_id = %s
              AND market = %s
              AND state = 'watching'
            ORDER BY symbol
            """,
            (DEFAULT_USER_ID, market),
        ).fetchall()
        return {str(row["symbol"]).upper() for row in rows}

    def _event_monitor_earnings_rows(self, conn: Any, market: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT
                e.security_id,
                e.market,
                e.symbol,
                COALESCE(s.company_name, e.symbol) AS company_name,
                e.snapshot_date,
                e.next_earnings_date,
                e.days_to_earnings,
                e.fiscal_period,
                e.time_of_day,
                e.eps_estimate,
                e.revenue_estimate,
                e.currency,
                e.data_quality_flag,
                e.source_vendor,
                e.raw_payload
            FROM olap.security_earnings_calendar_current e
            JOIN oltp.user_watchlist_state_current w
              ON w.user_id = %s
             AND w.market = e.market
             AND w.symbol = e.symbol
             AND w.state = 'watching'
            LEFT JOIN dim.security s
              ON s.security_id = e.security_id
            WHERE e.market = %s
            ORDER BY e.next_earnings_date NULLS LAST, e.symbol
            """,
            (DEFAULT_USER_ID, market),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _event_monitor_row_from_event(event: EventMonitorEvent) -> TenxEventMonitorEventRow:
        return TenxEventMonitorEventRow(
            event_id=event.event_id,
            market="US" if event.market == "US" else "CN",
            symbol=event.symbol,
            event_type=event.event_type,
            title=event.title,
            summary=event.summary,
            event_time=format_utc_label(event.event_time),
            due_at=event.due_at.isoformat() if event.due_at else None,
            priority=event.priority,
            evidence_grade=event.evidence_grade,
            confidence=event.confidence,
            source=event.source,
            source_url=event.source_url,
            status=event.status,
            matched_rule=event.matched_rule,
            asset_relevance=event.asset_relevance,
        )

    @staticmethod
    def _event_monitor_response(
        *,
        market: str,
        watchlist_symbols: set[str],
        snapshot: EventMonitorSnapshot,
    ) -> TenxEventMonitorResponse:
        return TenxEventMonitorResponse(
            market="US" if market == "US" else "CN",
            snapshot_at=format_utc_label(snapshot.snapshot_at),
            freshness=TenxFreshnessRow(
                updated_at=format_utc_label(snapshot.snapshot_at),
                data_complete=all(source.status == "ok" for source in snapshot.source_status),
                source_summary="FOMC + earnings calendar + political signal queue + public executive news",
                coverage="资产相关事件监听、提醒规则重建、Alerts 详情复核",
            ),
            watchlist_symbols=sorted(watchlist_symbols),
            generated_alerts=len(snapshot.events),
            source_status=[
                TenxEventMonitorSourceRow(
                    key=source.key,
                    label=source.label,
                    source=source.source,
                    source_url=source.source_url,
                    status=source.status if source.status in {"ok", "degraded", "unavailable"} else "degraded",
                    detail=source.detail,
                    updated_at=source.updated_at,
                )
                for source in snapshot.source_status
            ],
            rules=[
                TenxEventMonitorRuleRow(
                    key=rule.key,
                    label=rule.label,
                    event_type=rule.event_type,
                    priority=rule.priority,
                    scope=rule.scope,
                    cadence=rule.cadence,
                    enabled=rule.enabled,
                    source=rule.source,
                    source_url=rule.source_url,
                )
                for rule in snapshot.rules
            ],
            events=[TenxHunterService._event_monitor_row_from_event(event) for event in snapshot.events],
            notes=snapshot.notes,
        )

    @staticmethod
    def _event_monitor_alert_payload(event: EventMonitorEvent) -> dict[str, Any]:
        return {
            "status": event.status,
            "evidence_grade": event.evidence_grade,
            "confidence": event.confidence,
            "due_at": event.due_at.isoformat() if event.due_at else "",
            "next_action": "按事件层、结构层、执行层完成复核；只有预期差和价格结构同时成立才升级交易表达。",
            "source_label": "event-monitor",
            "source_note": f"{event.source}: {event.asset_relevance}",
            "source_url": event.source_url,
            "event_monitor_id": event.event_id,
            "matched_rule": event.matched_rule,
            "event_layer": event.event_layer,
            "structure_layer": event.structure_layer,
            "execution_layer": event.execution_layer,
            "invalidation_signals": event.invalidation_signals,
        }

    def _upsert_event_monitor_event(self, conn: Any, event: EventMonitorEvent, action_time: datetime) -> str:
        monitor_event_id = f"monitor::{event_digest(event.event_id)}"
        conn.execute(
            """
            INSERT INTO oltp.user_event_monitor_event_current (
                monitor_event_id, user_id, market, symbol, event_type, title, summary,
                event_time, due_at, priority, evidence_grade, confidence, source, source_url,
                status, matched_rule, asset_relevance, event_layer, structure_layer,
                execution_layer, invalidation_signals, raw_payload, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (monitor_event_id) DO UPDATE SET
                market = EXCLUDED.market,
                symbol = EXCLUDED.symbol,
                event_type = EXCLUDED.event_type,
                title = EXCLUDED.title,
                summary = EXCLUDED.summary,
                event_time = EXCLUDED.event_time,
                due_at = EXCLUDED.due_at,
                priority = EXCLUDED.priority,
                evidence_grade = EXCLUDED.evidence_grade,
                confidence = EXCLUDED.confidence,
                source = EXCLUDED.source,
                source_url = EXCLUDED.source_url,
                status = EXCLUDED.status,
                matched_rule = EXCLUDED.matched_rule,
                asset_relevance = EXCLUDED.asset_relevance,
                event_layer = EXCLUDED.event_layer,
                structure_layer = EXCLUDED.structure_layer,
                execution_layer = EXCLUDED.execution_layer,
                invalidation_signals = EXCLUDED.invalidation_signals,
                raw_payload = EXCLUDED.raw_payload,
                updated_at = EXCLUDED.updated_at
            """,
            (
                monitor_event_id,
                DEFAULT_USER_ID,
                event.market,
                event.symbol,
                event.event_type,
                event.title,
                event.summary,
                event.event_time,
                event.due_at,
                event.priority,
                event.evidence_grade,
                event.confidence,
                event.source,
                event.source_url,
                event.status,
                event.matched_rule,
                event.asset_relevance,
                Jsonb(event.event_layer),
                Jsonb(event.structure_layer),
                Jsonb(event.execution_layer),
                Jsonb(event.invalidation_signals),
                Jsonb(event.raw_payload),
                action_time,
                action_time,
            ),
        )
        return monitor_event_id

    def _upsert_event_monitor_alert_rule(
        self,
        conn: Any,
        event: EventMonitorEvent,
        monitor_event_id: str,
        action_time: datetime,
    ) -> None:
        rule_id = f"event-monitor::{event_digest(monitor_event_id, event.event_id)}"
        payload = {
            **self._event_monitor_alert_payload(event),
            "monitor_event_row_id": monitor_event_id,
        }
        conn.execute(
            """
            INSERT INTO oltp.user_alert_rule_current (
                rule_id, user_id, market, symbol, rule_type, severity, title,
                note, status, rule_payload, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (rule_id) DO UPDATE SET
                market = EXCLUDED.market,
                symbol = EXCLUDED.symbol,
                rule_type = EXCLUDED.rule_type,
                severity = EXCLUDED.severity,
                title = EXCLUDED.title,
                note = EXCLUDED.note,
                status = EXCLUDED.status,
                rule_payload = EXCLUDED.rule_payload,
                updated_at = EXCLUDED.updated_at
            """,
            (
                rule_id,
                DEFAULT_USER_ID,
                event.market,
                event.symbol,
                event.event_type,
                event.priority,
                event.title,
                event.summary,
                "active",
                Jsonb(payload),
                action_time,
                action_time,
            ),
        )

    def refresh_event_monitor(self, market: str | None = None, *, fetch_remote: bool = True) -> TenxEventMonitorResponse:
        market = self._normalize_market(market, self._settings)
        with connect(self._settings) as conn:
            self._ensure_event_monitor_table(conn)
            watchlist_symbols = self._event_monitor_watchlist_symbols(conn, market)
            earnings_rows = self._event_monitor_earnings_rows(conn, market)
            snapshot = build_event_monitor_snapshot(
                market=market,
                watchlist_symbols=watchlist_symbols,
                earnings_rows=earnings_rows,
                political_mentions=PoliticalSignalService()._mention_rows(),
                fetch_remote=fetch_remote,
            )
            action_time = utc_now()
            for event in snapshot.events:
                monitor_event_id = self._upsert_event_monitor_event(conn, event, action_time)
                self._upsert_event_monitor_alert_rule(conn, event, monitor_event_id, action_time)
            return self._event_monitor_response(
                market=market,
                watchlist_symbols=watchlist_symbols,
                snapshot=snapshot,
            )

    def get_event_monitor(self, market: str | None = None) -> TenxEventMonitorResponse:
        return self.refresh_event_monitor(market, fetch_remote=False)

    def list_alerts(self, market: str | None) -> TenxAlertCenterResponse:
        market = self._normalize_market(market, self._settings)
        with connect(self._settings) as conn:
            self._ensure_event_monitor_table(conn)
            rows = conn.execute(
                """
                SELECT alert_id AS id, market, symbol, alert_message AS title, alert_message AS summary,
                       CASE
                           WHEN severity = 'high' THEN 'P1'
                           WHEN severity = 'medium' THEN 'P2'
                           ELSE 'P3'
                       END AS severity,
                       alert_type, 'system' AS source, created_at, '查看研究卡片并复核' AS next_action,
                       'active' AS status, '{}'::jsonb AS rule_payload
                FROM olap.watchlist_alert_daily
                WHERE user_id = %s
                  AND market = %s
                UNION ALL
                SELECT rule_id AS id, market, symbol, title, note AS summary,
                       severity, rule_type AS alert_type,
                       COALESCE(NULLIF(rule_payload->>'source_label', ''), 'user-draft') AS source,
                       updated_at AS created_at,
                       COALESCE(rule_payload->>'next_action', '完善提醒规则') AS next_action,
                       status, rule_payload
                FROM oltp.user_alert_rule_current
                WHERE user_id = %s
                  AND market = %s
                ORDER BY created_at DESC
                """,
                (DEFAULT_USER_ID, market, DEFAULT_USER_ID, market),
            ).fetchall()
            freshness = self._freshness(self._format_timestamp(datetime.now(timezone.utc)), market)
            items: list[TenxAlertItemRow] = []
            for row in rows:
                rule_payload = self._as_dict(row["rule_payload"])
                items.append(
                    TenxAlertItemRow(
                        id=str(row["id"]),
                        market=market,
                        symbol=row["symbol"],
                        title=row["title"],
                        summary=row["summary"],
                        severity=row["severity"],
                        alert_type=row["alert_type"],
                        source=row["source"],
                        created_at=self._format_timestamp(row["created_at"]),
                        next_action=row["next_action"],
                        evidence_grade=self._rule_payload_text(rule_payload, "evidence_grade", "D"),
                        confidence=self._rule_payload_text(rule_payload, "confidence", "low"),
                        status=self._rule_payload_text(rule_payload, "status", row["status"] or "draft"),
                        due_at=self._rule_payload_text(rule_payload, "due_at") or None,
                        source_note=self._rule_payload_text(rule_payload, "source_note"),
                        event_layer=self._rule_payload_list(rule_payload, "event_layer"),
                        structure_layer=self._rule_payload_list(rule_payload, "structure_layer"),
                        execution_layer=self._rule_payload_list(rule_payload, "execution_layer"),
                        invalidation_signals=self._rule_payload_list(rule_payload, "invalidation_signals"),
                    )
                )
            return TenxAlertCenterResponse(
                market=market,
                freshness=freshness,
                available_actions=self._available_actions(),
                items=items,
            )

    def create_watchlist(self, payload: TenxWatchlistMutationRequest) -> TenxMutationResponse:
        with connect(self._settings) as conn:
            security = conn.execute(
                "SELECT security_id FROM dim.security WHERE market = %s AND symbol = %s",
                (payload.market, payload.symbol.upper()),
            ).fetchone()
            if security is None:
                raise ValueError(f"unknown symbol: {payload.market}:{payload.symbol}")
            action_id = str(uuid4())
            action_time = datetime.now(timezone.utc)
            conn.execute(
                """
                INSERT INTO oltp.user_watch_action_raw (
                    action_id, user_id, market, symbol, action, action_time,
                    action_source, trigger_scene, session_id, device_id, raw_payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    action_id,
                    DEFAULT_USER_ID,
                    payload.market,
                    payload.symbol.upper(),
                    payload.action,
                    action_time,
                    "tenx-api",
                    payload.trigger_scene or "workspace",
                    None,
                    None,
                    Jsonb({"market": payload.market, "symbol": payload.symbol.upper(), "action": payload.action}),
                ),
            )
            conn.execute(
                """
                INSERT INTO oltp.user_watchlist_state_current (
                    user_id, security_id, market, symbol, state, latest_action_time
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, security_id) DO UPDATE SET
                    market = EXCLUDED.market,
                    symbol = EXCLUDED.symbol,
                    state = EXCLUDED.state,
                    latest_action_time = EXCLUDED.latest_action_time
                """,
                (
                    DEFAULT_USER_ID,
                    security["security_id"],
                    payload.market,
                    payload.symbol.upper(),
                    "watching" if payload.action == "watch" else "inactive",
                    action_time,
                ),
            )
            if payload.action == "watch":
                due_at = (action_time + timedelta(days=7)).date().isoformat()
                existing_rule = conn.execute(
                    """
                    SELECT rule_id
                    FROM oltp.user_alert_rule_current
                    WHERE user_id = %s
                      AND market = %s
                      AND symbol = %s
                      AND rule_type = 'event-tracking'
                      AND status <> 'archived'
                    LIMIT 1
                    """,
                    (DEFAULT_USER_ID, payload.market, payload.symbol.upper()),
                ).fetchone()
                rule_payload = {
                    "status": "active",
                    "evidence_grade": "C",
                    "confidence": "medium",
                    "due_at": due_at,
                    "next_action": "复核最新事件、价格结构和反证条件",
                    "source_note": "观察池默认事件追踪规则，由加入观察池动作自动创建。",
                    "event_layer": [
                        "是否出现改变收入/订单/交付预期的新事件",
                        "是否出现公司披露、财报或监管文件的新证据",
                    ],
                    "structure_layer": [
                        "价格是否进入 Base/Bull/Bear 目标区",
                        "估值、拥挤度或期权结构是否变得极端",
                    ],
                    "execution_layer": [
                        "未复核价格地图和最大亏损前不升级为交易表达",
                    ],
                    "invalidation_signals": [
                        "核心事件低于预期",
                        "价格跌破无效区且没有新增证据支撑",
                    ],
                }
                if existing_rule:
                    conn.execute(
                        """
                        UPDATE oltp.user_alert_rule_current
                        SET severity = 'P2',
                            title = %s,
                            note = %s,
                            status = 'active',
                            rule_payload = %s,
                            updated_at = %s
                        WHERE rule_id = %s
                        """,
                        (
                            f"{payload.symbol.upper()} 观察池事件追踪",
                            "进入观察池后自动跟踪事件、结构和反证条件。",
                            Jsonb(rule_payload),
                            action_time,
                            existing_rule["rule_id"],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO oltp.user_alert_rule_current (
                            rule_id, user_id, market, symbol, rule_type, severity, title,
                            note, status, rule_payload, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(uuid4()),
                            DEFAULT_USER_ID,
                            payload.market,
                            payload.symbol.upper(),
                            "event-tracking",
                            "P2",
                            f"{payload.symbol.upper()} 观察池事件追踪",
                            "进入观察池后自动跟踪事件、结构和反证条件。",
                            "active",
                            Jsonb(rule_payload),
                            action_time,
                            action_time,
                        ),
                    )
            else:
                conn.execute(
                    """
                    UPDATE oltp.user_alert_rule_current
                    SET status = 'archived',
                        updated_at = %s
                    WHERE user_id = %s
                      AND market = %s
                      AND symbol = %s
                      AND rule_type = 'event-tracking'
                    """,
                    (action_time, DEFAULT_USER_ID, payload.market, payload.symbol.upper()),
                )
        return TenxMutationResponse(message=f"{payload.symbol.upper()} 已更新观察池状态。")

    def update_watchlist(self, symbol: str, payload: TenxWatchlistUpdateRequest) -> TenxMutationResponse:
        action = "watch" if payload.state == "watching" else "unwatch"
        return self.create_watchlist(
            TenxWatchlistMutationRequest(
                market=payload.market,
                symbol=symbol.upper(),
                action=action,
                trigger_scene=payload.trigger_scene,
            )
        )

    def create_alert(self, payload: TenxAlertCreateRequest) -> TenxMutationResponse:
        with connect(self._settings) as conn:
            conn.execute(
                """
                INSERT INTO oltp.user_alert_rule_current (
                    rule_id, user_id, market, symbol, rule_type, severity, title,
                    note, status, rule_payload, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid4()),
                    DEFAULT_USER_ID,
                    payload.market,
                    payload.symbol.upper(),
                    payload.alert_type,
                    payload.severity,
                    payload.title,
                    payload.note,
                    "draft",
                    Jsonb(payload.rule_payload),
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                ),
            )
        return TenxMutationResponse(message=f"{payload.symbol.upper()} 的提醒草稿已保存。")
