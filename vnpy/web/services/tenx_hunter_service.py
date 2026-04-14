from __future__ import annotations

from datetime import date, datetime
from typing import Any

from vnpy.web.contracts.tenx_hunter import (
    TenxCandidateRow,
    TenxResearchCardResponse,
    TenxResearchEvidenceRow,
    TenxThemeRow,
    TenxTimelineEventRow,
    TenxUniverseBucketRow,
    TenxWatchlistItemRow,
    TenxWorkspaceSnapshotResponse,
)
from vnpy.web.tenx_hunter.config import load_settings
from vnpy.web.tenx_hunter.db import connect
from vnpy.web.tenx_hunter.scoring import CandidateExplanation, ScoreComponents, build_candidate_explanation


class TenxHunterService:
    def __init__(self) -> None:
        self._settings = load_settings()

    def _universe_label(self) -> str:
        count = len(self._settings.real_symbols)
        if count > 0:
            return f"{self._settings.real_universe_name} · {count} names"
        return self._settings.real_universe_name

    @staticmethod
    def _score_components_from_row(row: Any) -> ScoreComponents:
        return ScoreComponents(
            growth=float(row["growth_score"] or 0.0),
            quality=float(row["quality_score"] or 0.0),
            momentum=float(row["momentum_score"] or 0.0),
            valuation=float(row["valuation_score"] or 0.0),
            size=float(row["size_score"] or 0.0),
            evidence=float(row["evidence_score"] or 0.0),
            theme=float(row["theme_score"] or 0.0),
            risk=float(row["risk_score"] or 0.0),
        )

    @classmethod
    def _candidate_explanation(cls, row: Any) -> CandidateExplanation:
        components = cls._score_components_from_row(row)
        return build_candidate_explanation(
            cls._stage_value(row["stage"], float(row["total_score"] or 0.0)),
            components,
            ps_ttm=float(row["ps_ttm"] or 0.0) if row["ps_ttm"] is not None else None,
            market_cap=float(row["market_cap"] or 0.0) if row["market_cap"] is not None else None,
            return_5d=float(row["return_5d"] or 0.0) if row["return_5d"] is not None else None,
            distance_from_high=float(row["distance_from_recent_high"] or 0.0) if row["distance_from_recent_high"] is not None else None,
        )

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if value in (None, ""):
            return []
        return [value]

    @staticmethod
    def _slugify(value: str) -> str:
        return value.strip().lower().replace("/", " ").replace("_", " ").replace("  ", " ").replace(" ", "-")

    @staticmethod
    def _stage_value(stage: str | None, score: float) -> str:
        if stage:
            return stage
        if score >= 88:
            return "acceleration"
        if score >= 74:
            return "validation"
        if score >= 62:
            return "early"
        return "crowded"

    @staticmethod
    def _momentum_from_return(return_5d: float | None) -> str:
        value = return_5d or 0.0
        if value >= 0.05:
            return "strengthening"
        if value <= -0.05:
            return "cooling"
        return "stable"

    @staticmethod
    def _risk_level(risk_tags: list[Any], negative_event_count: int) -> str:
        total_risk = len(risk_tags) + negative_event_count
        if total_risk >= 3:
            return "high"
        if total_risk >= 1:
            return "medium"
        return "low"

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
        if "earn" in lowered or "10-" in lowered or "20-f" in lowered or "40-f" in lowered:
            return "earnings"
        if "8-k" in lowered or "filing" in lowered:
            return "capex"
        if "risk" in lowered:
            return "risk"
        if "supply" in lowered:
            return "supply-chain"
        return "price" if source_kind == "news" else "earnings"

    @staticmethod
    def _market_cap_label(market_cap: float | None) -> str:
        if market_cap is None:
            return "N/A"
        if market_cap >= 1_000_000_000_000:
            return f"${market_cap / 1_000_000_000_000:.1f}T"
        if market_cap >= 1_000_000_000:
            return f"${market_cap / 1_000_000_000:.0f}B"
        if market_cap >= 1_000_000:
            return f"${market_cap / 1_000_000:.0f}M"
        return f"${market_cap:.0f}"

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
            return value.strftime("%Y-%m-%d %H:%M UTC")
        return str(value)

    def get_workspace_snapshot(self) -> TenxWorkspaceSnapshotResponse:
        with connect(self._settings) as conn:
            snapshot_row = conn.execute(
                "SELECT MAX(trade_date) AS trade_date FROM ads.candidate_pool_daily"
            ).fetchone()
            latest_trade_date = snapshot_row["trade_date"] if snapshot_row else None
            if latest_trade_date is None:
                universe_buckets = [
                    TenxUniverseBucketRow(
                        slug=str(bucket["slug"]),
                        label=str(bucket["label"]),
                        rationale=str(bucket["rationale"]),
                        symbol_count=len(bucket.get("symbols", []) or []),
                        sample_symbols=[str(item) for item in (bucket.get("symbols", []) or [])[:4]],
                    )
                    for bucket in self._settings.real_universe_buckets
                ]
                return TenxWorkspaceSnapshotResponse(
                    universe=self._universe_label(),
                    universe_strategy=self._settings.real_universe_strategy,
                    universe_description=self._settings.real_universe_description,
                    universe_buckets=universe_buckets,
                    snapshot_at="",
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
                    GROUP BY security_id
                ),
                latest_event AS (
                    SELECT DISTINCT ON (security_id)
                        security_id,
                        title,
                        event_time
                    FROM dwd.security_event_timeline
                    ORDER BY security_id, event_time DESC
                ),
                theme_pick AS (
                    SELECT
                        st.security_id,
                        MIN(t.theme_name) AS theme_name
                    FROM dim.security_theme st
                    JOIN dim.theme t ON t.theme_id = st.theme_id
                    GROUP BY st.security_id
                )
                SELECT
                    c.security_id,
                    c.symbol,
                    d.company_name,
                    COALESCE(d.sector, d.industry, 'Unknown') AS sector,
                    COALESCE(tp.theme_name, 'Growth Tech') AS theme_name,
                    c.total_score,
                    c.stage,
                    c.reason_summary,
                    c.risk_tags,
                    m.close,
                    m.return_1d,
                    m.return_5d,
                    m.distance_from_recent_high,
                    m.ps_ttm,
                    m.market_cap,
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
                    sc.theme_score
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
                WHERE c.trade_date = %s
                ORDER BY c.rank_no
                LIMIT 20
                """,
                (latest_trade_date,),
            ).fetchall()

            universe_buckets = [
                TenxUniverseBucketRow(
                    slug=str(bucket["slug"]),
                    label=str(bucket["label"]),
                    rationale=str(bucket["rationale"]),
                    symbol_count=len(bucket.get("symbols", []) or []),
                    sample_symbols=[str(item) for item in (bucket.get("symbols", []) or [])[:4]],
                )
                for bucket in self._settings.real_universe_buckets
            ]
            candidates: list[TenxCandidateRow] = []
            for row in candidate_rows:
                stage_value = self._stage_value(row["stage"], float(row["total_score"] or 0.0))
                explanation = self._candidate_explanation(row)
                candidates.append(
                    TenxCandidateRow(
                        symbol=row["symbol"],
                        name=row["company_name"],
                        sector=row["sector"],
                        theme=row["theme_name"],
                        stage=stage_value,
                        score=int(round(float(row["total_score"] or 0.0))),
                        score_change=round(float(row["return_5d"] or 0.0) * 100, 1),
                        price=float(row["close"] or 0.0),
                        price_change_pct=round(float(row["return_1d"] or 0.0) * 100, 1),
                        market_cap_label=self._market_cap_label(float(row["market_cap"])) if row["market_cap"] is not None else "N/A",
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
                    )
                )

            theme_rows = conn.execute(
                """
                SELECT
                    r.theme_id,
                    r.theme_name,
                    r.heat_score,
                    r.status,
                    r.key_drivers,
                    r.representative_symbols
                FROM ads.theme_radar_daily r
                WHERE r.trade_date = %s
                ORDER BY r.heat_score DESC
                """,
                (latest_trade_date,),
            ).fetchall()
            themes = [
                TenxThemeRow(
                    slug=self._slugify(row["theme_id"]),
                    name=row["theme_name"],
                    heat=int(round(float(row["heat_score"] or 0.0))),
                    trend=self._theme_trend(row["status"]),
                    driver=(self._as_list(row["key_drivers"]) or [row["theme_name"]])[0],
                    evidence=[str(item) for item in self._as_list(row["key_drivers"])],
                    related_symbols=[str(item) for item in self._as_list(row["representative_symbols"])],
                )
                for row in theme_rows
            ]

            watchlist_rows = conn.execute(
                """
                SELECT
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
                      AND a.symbol = w.symbol
                      AND a.trade_date = %s
                    ORDER BY a.created_at DESC
                    LIMIT 1
                ) a ON TRUE
                LEFT JOIN ads.candidate_pool_daily c
                  ON c.security_id = w.security_id AND c.trade_date = %s
                WHERE w.state = 'watching'
                ORDER BY c.total_score DESC NULLS LAST, w.symbol
                """,
                (latest_trade_date, latest_trade_date),
            ).fetchall()
            watchlist = []
            for row in watchlist_rows:
                risk_level = self._risk_level(self._as_list(row["risk_tags"]), 1 if row["severity"] == "high" else 0)
                score = int(round(float(row["total_score"] or 0.0)))
                watchlist.append(
                    TenxWatchlistItemRow(
                        symbol=row["symbol"],
                        name=row["company_name"],
                        thesis_status=self._watchlist_status(risk_level, score, row["alert_type"]),
                        alert_type=row["alert_type"],
                        last_event=row["alert_message"],
                        next_check="刷新最新 filing / news 后复核",
                        risk_level=risk_level,
                        score=score,
                    )
                )

            timeline_rows = conn.execute(
                """
                SELECT
                    e.event_id,
                    e.symbol,
                    e.event_time,
                    e.title,
                    e.event_type,
                    e.source_kind,
                    COALESCE(s.summary, e.title) AS summary
                FROM dwd.security_event_timeline e
                LEFT JOIN dwd.security_document_signal s ON s.event_id = e.event_id
                ORDER BY e.event_time DESC
                LIMIT 20
                """
            ).fetchall()
            timeline = [
                TenxTimelineEventRow(
                    id=row["event_id"],
                    symbol=row["symbol"],
                    date=self._format_date(row["event_time"]),
                    title=row["title"],
                    type=self._timeline_type(row["event_type"], row["source_kind"]),
                    summary=row["summary"],
                )
                for row in timeline_rows
            ]

            prompts = [
                "这期候选池里，哪些名字是真正被财务和事件同时验证的？",
                "最新负面事件里，哪些是噪音，哪些会实质伤害逻辑？",
                "如果只能优先跟踪 3 只票，今天应该保留谁？",
            ]

            return TenxWorkspaceSnapshotResponse(
                universe=self._universe_label(),
                universe_strategy=self._settings.real_universe_strategy,
                universe_description=self._settings.real_universe_description,
                universe_buckets=universe_buckets,
                snapshot_at=self._format_date(latest_trade_date),
                candidates=candidates,
                themes=themes,
                watchlist=watchlist,
                timeline=timeline,
                copilot_prompts=prompts,
            )

    def get_research_card(self, symbol: str) -> TenxResearchCardResponse | None:
        with connect(self._settings) as conn:
            row = conn.execute(
                """
                SELECT
                    rc.symbol,
                    d.company_name,
                    COALESCE(d.sector, d.industry, 'Unknown') AS sector,
                    COALESCE(MIN(t.theme_name), 'Growth Tech') AS theme_name,
                    rc.thesis,
                    rc.key_points,
                    rc.risk_points,
                    rc.next_watch_items,
                    rc.stage,
                    rc.total_score,
                    f.revenue_yoy,
                    f.op_margin,
                    f.fcf_margin,
                    m.close,
                    m.return_1d,
                    m.return_5d,
                    m.distance_from_recent_high,
                    m.ps_ttm,
                    m.market_cap,
                    sc.growth_score,
                    sc.quality_score,
                    sc.momentum_score,
                    sc.valuation_score,
                    sc.size_score,
                    sc.evidence_score,
                    sc.risk_score,
                    sc.theme_score
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
                WHERE rc.symbol = %s
                GROUP BY
                    rc.symbol, d.company_name, d.sector, d.industry, rc.thesis,
                    rc.key_points, rc.risk_points, rc.next_watch_items, rc.stage, rc.total_score,
                    f.revenue_yoy, f.op_margin, f.fcf_margin, m.close, m.return_1d, m.return_5d,
                    m.distance_from_recent_high, m.ps_ttm, m.market_cap,
                    sc.growth_score, sc.quality_score, sc.momentum_score, sc.valuation_score,
                    sc.size_score, sc.evidence_score, sc.risk_score, sc.theme_score
                """,
                (symbol.upper(),),
            ).fetchone()
            if row is None:
                return None

            evidence_rows = conn.execute(
                """
                SELECT
                    e.source_kind,
                    e.event_time,
                    COALESCE(s.summary, e.title) AS summary
                FROM dwd.security_event_timeline e
                LEFT JOIN dwd.security_document_signal s ON s.event_id = e.event_id
                WHERE e.symbol = %s
                ORDER BY e.event_time DESC
                LIMIT 6
                """,
                (symbol.upper(),),
            ).fetchall()
            evidence = [
                TenxResearchEvidenceRow(
                    source=str(item["source_kind"]).upper(),
                    published_at=self._format_timestamp(item["event_time"]),
                    note=item["summary"],
                )
                for item in evidence_rows
            ]

            facts = [
                f"最新价格 {float(row['close'] or 0.0):.2f} 美元，单日变动 {float(row['return_1d'] or 0.0) * 100:.1f}%" if row["close"] is not None else "价格快照暂缺",
                f"最近 5 日变化 {float(row['return_5d'] or 0.0) * 100:.1f}%" if row["return_5d"] is not None else "5 日走势暂缺",
                f"营收同比 {float(row['revenue_yoy'] or 0.0) * 100:.1f}%" if row["revenue_yoy"] is not None else "营收同比暂缺",
                f"经营利润率 {float(row['op_margin'] or 0.0) * 100:.1f}%" if row["op_margin"] is not None else "经营利润率暂缺",
                f"自由现金流率 {float(row['fcf_margin'] or 0.0) * 100:.1f}%" if row["fcf_margin"] is not None else "自由现金流率暂缺",
            ]
            thesis_points = [str(item) for item in self._as_list(row["key_points"])]
            risks = [str(item) for item in self._as_list(row["risk_points"])] or ["暂无显著负面事件"]
            next_checkpoints = [str(item) for item in self._as_list(row["next_watch_items"])]
            explanation = self._candidate_explanation(row)

            return TenxResearchCardResponse(
                symbol=row["symbol"],
                name=row["company_name"],
                sector=row["sector"],
                theme=row["theme_name"],
                stage=self._stage_value(row["stage"], float(row["total_score"] or 0.0)),
                score=int(round(float(row["total_score"] or 0.0))),
                thesis_summary=row["thesis"],
                selection_reason=explanation.selection_reason,
                stage_reason=explanation.stage_reason,
                crowding_note=explanation.crowding_note,
                score_drivers=explanation.score_drivers,
                facts=facts,
                thesis_points=thesis_points,
                risks=risks,
                next_checkpoints=next_checkpoints,
                evidence=evidence,
            )
