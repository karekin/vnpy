from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from vnpy.web.contracts.tenx_hunter import (
    TenxActionRow,
    TenxAlertCenterResponse,
    TenxAlertCreateRequest,
    TenxAlertItemRow,
    TenxCandidateRow,
    TenxEvidenceItemRow,
    TenxFreshnessRow,
    TenxLifecycleStageRow,
    TenxMutationResponse,
    TenxResearchCardResponse,
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
from vnpy.web.tenx_hunter.config import Settings, load_settings
from vnpy.web.tenx_hunter.db import connect
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
    def _available_actions(symbol: str | None = None) -> list[TenxActionRow]:
        actions = [
            TenxActionRow(id="add-watchlist", label="加入观察池", kind="watchlist"),
            TenxActionRow(id="create-alert", label="创建提醒", kind="alert"),
        ]
        if symbol:
            actions.append(TenxActionRow(id="export-summary", label="导出摘要", kind="export"))
        return actions

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

    def get_workspace_snapshot(self, market: str | None = None) -> TenxWorkspaceSnapshotResponse:
        market = self._normalize_market(market, self._settings)
        universe_name, universe_strategy, universe_description, universe_buckets = self._universe(market)
        with connect(self._settings) as conn:
            snapshot_row = conn.execute(
                "SELECT MAX(trade_date) AS trade_date FROM ads.candidate_pool_daily WHERE market = %s",
                (market,),
            ).fetchone()
            latest_trade_date = snapshot_row["trade_date"] if snapshot_row else None
            if latest_trade_date is None:
                return TenxWorkspaceSnapshotResponse(
                    market=market,
                    universe=universe_name,
                    universe_strategy=universe_strategy,
                    universe_description=universe_description,
                    universe_buckets=universe_buckets,
                    snapshot_at="",
                    freshness=self._freshness("", market),
                    available_actions=self._available_actions(),
                    candidates=[],
                    themes=[],
                    watchlist=[],
                    timeline=[],
                    copilot_prompts=[],
                )

            candidate_rows = conn.execute(
                """
                WITH evidence AS (
                    SELECT security_id, COUNT(*) AS evidence_count
                    FROM dwd.security_document_signal
                    WHERE market = %s
                    GROUP BY security_id
                ),
                latest_event AS (
                    SELECT DISTINCT ON (security_id)
                        security_id,
                        title,
                        event_time
                    FROM dwd.security_event_timeline
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
                FROM ads.candidate_pool_daily c
                JOIN dim.security d ON d.security_id = c.security_id
                LEFT JOIN dwd.security_market_daily m
                  ON m.security_id = c.security_id AND m.trade_date = c.trade_date
                LEFT JOIN ads.research_card_current rc ON rc.security_id = c.security_id
                LEFT JOIN dws.security_score_component_daily sc
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
            for row in candidate_rows:
                explanation = self._candidate_explanation(row, market)
                stage = self._canonical_stage(row["stage"])
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
                        evidence_count=int(row["evidence_count"] or 0),
                        risk_level=self._risk_level(self._as_list(row["risk_tags"]), 0),
                        momentum=self._momentum_from_return(float(row["return_5d"] or 0.0)),
                        next_event=row["next_event"] or "等待下一事件更新",
                        thesis=row["thesis"] or row["reason_summary"],
                        key_signal=row["reason_summary"],
                        selection_reason=explanation.selection_reason,
                        stage_reason=explanation.stage_reason,
                        crowding_note=explanation.crowding_note,
                        score_drivers=explanation.score_drivers,
                        why_selected=TenxWhySelectedRow(summary=explanation.selection_reason, bullets=explanation.score_drivers),
                        score_breakdown=self._score_breakdown(row, market),
                        freshness=freshness,
                        available_actions=self._available_actions(row["symbol"]),
                    )
                )

            theme_rows = conn.execute(
                """
                SELECT market, theme_id, theme_name, heat_score, status, key_drivers, representative_symbols
                FROM ads.theme_radar_daily
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
                    COALESCE(c.risk_tags, '[]'::jsonb) AS risk_tags
                FROM dwd.user_watchlist_state_current w
                JOIN dim.security d ON d.security_id = w.security_id
                LEFT JOIN LATERAL (
                    SELECT alert_type, severity, alert_message
                    FROM ads.watchlist_alert_daily a
                    WHERE a.user_id = w.user_id
                      AND a.market = w.market
                      AND a.symbol = w.symbol
                    ORDER BY a.created_at DESC
                    LIMIT 1
                ) a ON TRUE
                LEFT JOIN ads.candidate_pool_daily c
                  ON c.security_id = w.security_id AND c.trade_date = %s AND c.market = w.market
                WHERE w.market = %s AND w.state = 'watching'
                ORDER BY c.total_score DESC NULLS LAST, w.symbol
                """,
                (latest_trade_date, market),
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
                        available_actions=self._available_actions(row["symbol"]),
                    )
                )

            if not watchlist and candidates:
                for candidate in candidates[:3]:
                    watchlist.append(
                        TenxWatchlistItemRow(
                            market=market,
                            symbol=candidate.symbol,
                            name=candidate.name,
                            thesis_status="strengthening" if candidate.stage in {"validation", "acceleration"} else "needs-review",
                            alert_type="system-focus",
                            last_event=candidate.why_selected.summary,
                            next_check="加入观察池后继续跟踪财务兑现与主题变化",
                            risk_level=candidate.risk_level,
                            score=candidate.score,
                            available_actions=self._available_actions(candidate.symbol),
                        )
                    )

            timeline_rows = conn.execute(
                """
                SELECT e.event_id, e.market, e.symbol, e.event_time, e.title, e.event_type, e.source_kind,
                       COALESCE(s.summary, e.title) AS summary
                FROM dwd.security_event_timeline e
                LEFT JOIN dwd.security_document_signal s ON s.event_id = e.event_id
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
                FROM ads.research_card_current rc
                JOIN dim.security d ON d.security_id = rc.security_id
                LEFT JOIN dim.security_theme st ON st.security_id = rc.security_id
                LEFT JOIN dim.theme t ON t.theme_id = st.theme_id
                LEFT JOIN dwd.security_financial_quarterly f
                  ON f.security_id = rc.security_id
                 AND f.report_period = (
                    SELECT MAX(report_period) FROM dwd.security_financial_quarterly WHERE security_id = rc.security_id
                 )
                LEFT JOIN dwd.security_market_daily m
                  ON m.security_id = rc.security_id
                 AND m.trade_date = (
                    SELECT MAX(trade_date) FROM dwd.security_market_daily WHERE security_id = rc.security_id
                 )
                LEFT JOIN dws.security_score_component_daily sc
                  ON sc.security_id = rc.security_id
                 AND sc.trade_date = (
                    SELECT MAX(trade_date) FROM dws.security_score_component_daily WHERE security_id = rc.security_id
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
                FROM dwd.security_event_timeline e
                LEFT JOIN dwd.security_document_signal s ON s.event_id = e.event_id
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
                freshness=freshness,
                available_actions=self._available_actions(row["symbol"]),
            )

    def list_alerts(self, market: str | None) -> TenxAlertCenterResponse:
        market = self._normalize_market(market, self._settings)
        with connect(self._settings) as conn:
            rows = conn.execute(
                """
                SELECT alert_id AS id, market, symbol, alert_message AS title, alert_message AS summary,
                       CASE
                           WHEN severity = 'high' THEN 'P1'
                           WHEN severity = 'medium' THEN 'P2'
                           ELSE 'P3'
                       END AS severity,
                       alert_type, 'system' AS source, created_at, '查看研究卡片并复核' AS next_action
                FROM ads.watchlist_alert_daily
                WHERE market = %s
                UNION ALL
                SELECT rule_id AS id, market, symbol, title, note AS summary,
                       severity, rule_type AS alert_type, 'user-draft' AS source, updated_at AS created_at,
                       '完善提醒规则' AS next_action
                FROM dwd.user_alert_rule_current
                WHERE market = %s
                ORDER BY created_at DESC
                """,
                (market, market),
            ).fetchall()
            freshness = self._freshness(self._format_timestamp(datetime.now(timezone.utc)), market)
            return TenxAlertCenterResponse(
                market=market,
                freshness=freshness,
                available_actions=self._available_actions(),
                items=[
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
                    )
                    for row in rows
                ],
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
                INSERT INTO ods.user_watch_action_raw (
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
                INSERT INTO dwd.user_watchlist_state_current (
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
                INSERT INTO dwd.user_alert_rule_current (
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
