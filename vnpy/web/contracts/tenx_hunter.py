from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TenxMarket = Literal["CN", "US"]
TenxStage = Literal["discovery", "validation", "acceleration", "crowded", "falsified"]
TenxRiskLevel = Literal["low", "medium", "high"]
TenxMomentum = Literal["strengthening", "stable", "cooling"]
TenxThemeTrend = Literal["rising", "stable", "weakening"]
TenxThesisStatus = Literal["strengthening", "needs-review", "at-risk"]
TenxTimelineType = Literal["earnings", "capex", "price", "supply-chain", "risk", "filing"]
TenxAlertSeverity = Literal["P1", "P2", "P3"]
TenxPriceConfidence = Literal["low", "medium", "high"]
TenxFlowStatus = Literal["hot-lead", "candidate", "watch-ready", "watching", "alerting", "blocked"]
TenxMarketSentimentTone = Literal["extreme-fear", "fear", "neutral", "greed", "extreme-greed", "unavailable"]
TenxPoliticalEvidenceGrade = Literal["A", "B", "C", "D"]
TenxPoliticalSignalStatus = Literal["confirmed", "watching", "needs-verification", "discarded"]
TenxEventMonitorSourceStatus = Literal["ok", "degraded", "unavailable"]


class TenxFreshnessRow(BaseModel):
    updated_at: str
    data_complete: bool
    source_summary: str
    coverage: str


class TenxMarketSentimentPointRow(BaseModel):
    date: str
    value: float


class TenxMarketSentimentMetricRow(BaseModel):
    key: str
    label: str
    category: str
    value: float | None = None
    display_value: str
    score: float | None = None
    tone: TenxMarketSentimentTone
    status_label: str
    detail: str
    source: str
    source_url: str
    updated_at: str
    previous_value: float | None = None
    change: float | None = None
    history: list[TenxMarketSentimentPointRow] = Field(default_factory=list)


class TenxMarketSentimentResponse(BaseModel):
    market: TenxMarket
    snapshot_at: str
    composite_score: float | None = None
    regime: TenxMarketSentimentTone
    regime_label: str
    summary: str
    risk_posture: str
    data_quality: str
    freshness: TenxFreshnessRow
    metrics: list[TenxMarketSentimentMetricRow]
    notes: list[str] = Field(default_factory=list)


class TenxPoliticalDisclosureSummaryRow(BaseModel):
    source: str
    source_url: str
    filing_type: str
    latest_filing_date: str
    transaction_window: str
    total_trades: int | None = None
    purchases: int | None = None
    sales: int | None = None
    late_filings: int | None = None
    late_filing_pct: float | None = None
    detail: str


class TenxPoliticalTradeRow(BaseModel):
    date: str
    symbol: str
    description: str
    trade_type: str
    amount: str
    is_late: bool = False
    source_url: str


class TenxPoliticalMentionRow(BaseModel):
    symbol: str
    name: str
    event_date: str
    event_type: str
    status: TenxPoliticalSignalStatus
    evidence_grade: TenxPoliticalEvidenceGrade
    headline: str
    summary: str
    source: str
    source_url: str
    verification_note: str
    next_action: str
    watchlist_rule: str


class TenxPoliticalSignalResponse(BaseModel):
    market: TenxMarket
    person: str
    snapshot_at: str
    thesis: str
    freshness: TenxFreshnessRow
    disclosure: TenxPoliticalDisclosureSummaryRow
    recent_trades: list[TenxPoliticalTradeRow]
    mentions: list[TenxPoliticalMentionRow]
    monitoring_rules: list[str]
    notes: list[str] = Field(default_factory=list)


class TenxEventMonitorSourceRow(BaseModel):
    key: str
    label: str
    source: str
    source_url: str
    status: TenxEventMonitorSourceStatus
    detail: str
    updated_at: str


class TenxEventMonitorRuleRow(BaseModel):
    key: str
    label: str
    event_type: str
    priority: TenxAlertSeverity
    scope: str
    cadence: str
    enabled: bool = True
    source: str
    source_url: str


class TenxEventMonitorEventRow(BaseModel):
    event_id: str
    market: TenxMarket
    symbol: str
    event_type: str
    title: str
    summary: str
    event_time: str
    due_at: str | None = None
    priority: TenxAlertSeverity
    evidence_grade: str
    confidence: str
    source: str
    source_url: str
    status: str
    matched_rule: str
    asset_relevance: str


class TenxEventMonitorResponse(BaseModel):
    market: TenxMarket
    snapshot_at: str
    freshness: TenxFreshnessRow
    watchlist_symbols: list[str]
    generated_alerts: int
    source_status: list[TenxEventMonitorSourceRow]
    rules: list[TenxEventMonitorRuleRow]
    events: list[TenxEventMonitorEventRow]
    notes: list[str] = Field(default_factory=list)


class TenxActionRow(BaseModel):
    id: str
    label: str
    kind: str
    enabled: bool = True


class TenxWhySelectedRow(BaseModel):
    summary: str
    bullets: list[str]


class TenxScoreBreakdownRow(BaseModel):
    key: str
    label: str
    score: float
    weight: int
    summary: str
    positive_notes: list[str] = Field(default_factory=list)
    negative_notes: list[str] = Field(default_factory=list)


class TenxLifecycleStageRow(BaseModel):
    key: TenxStage
    label: str
    summary: str


class TenxPromotionCheckRow(BaseModel):
    key: str
    label: str
    passed: bool
    detail: str


class TenxUniverseBucketRow(BaseModel):
    slug: str
    label: str
    rationale: str
    symbol_count: int
    sample_symbols: list[str]


class TenxCandidateRow(BaseModel):
    market: TenxMarket
    symbol: str
    name: str
    sector: str
    theme: str
    stage: TenxStage
    lifecycle_stage: TenxLifecycleStageRow
    score: int
    score_change: float
    price: float
    price_change_pct: float
    market_cap_label: str
    evidence_count: int
    risk_level: TenxRiskLevel
    momentum: TenxMomentum
    next_event: str
    thesis: str
    key_signal: str
    selection_reason: str
    stage_reason: str
    crowding_note: str
    score_drivers: list[str]
    why_selected: TenxWhySelectedRow
    score_breakdown: list[TenxScoreBreakdownRow]
    flow_status: TenxFlowStatus = "candidate"
    flow_status_label: str = "候选验证"
    promotion_summary: str = "继续补证据后再判断是否进入观察池。"
    promotion_checks: list[TenxPromotionCheckRow] = Field(default_factory=list)
    freshness: TenxFreshnessRow
    available_actions: list[TenxActionRow]


class TenxThemeRow(BaseModel):
    market: TenxMarket
    slug: str
    name: str
    heat: int
    trend: TenxThemeTrend
    driver: str
    evidence: list[str]
    related_symbols: list[str]
    freshness: TenxFreshnessRow


class TenxTargetRangeRow(BaseModel):
    scenario: Literal["bear", "base", "bull"]
    horizon: str
    low: float | None = None
    high: float | None = None
    mid: float | None = None
    upside_pct_mid: float | None = None
    method: str
    confidence: TenxPriceConfidence
    assumptions: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)


class TenxKeyLevelRow(BaseModel):
    level_type: str
    label: str
    low: float | None = None
    high: float | None = None
    strength: str
    distance_pct: float | None = None
    source: str
    note: str
    evidence_refs: list[str] = Field(default_factory=list)


class TenxScenarioPathRow(BaseModel):
    name: str
    probability: int
    confidence: TenxPriceConfidence
    trigger: str
    target_scenario: str
    invalidation: str
    explanation: str
    evidence_refs: list[str] = Field(default_factory=list)


class TenxPriceMapHitReviewRow(BaseModel):
    snapshot_date: str
    review_date: str
    horizon_days: int
    base_hit: bool | None = None
    bull_hit: bool | None = None
    bear_breached: bool | None = None
    max_close: float | None = None
    min_close: float | None = None
    hit_summary: str


class TenxPriceMapResponse(BaseModel):
    market: TenxMarket
    symbol: str
    as_of_date: str
    current_price: float | None = None
    posture: str
    posture_label: str
    confidence: TenxPriceConfidence
    base_target: TenxTargetRangeRow
    bull_target: TenxTargetRangeRow
    bear_zone: TenxTargetRangeRow
    key_levels: list[TenxKeyLevelRow] = Field(default_factory=list)
    scenario_paths: list[TenxScenarioPathRow] = Field(default_factory=list)
    invalidation_rules: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    explanation: dict[str, str] = Field(default_factory=dict)
    hit_reviews: list[TenxPriceMapHitReviewRow] = Field(default_factory=list)


class TenxPriceSnapshotRow(BaseModel):
    as_of_date: str
    current_price: float | None = None
    posture: str
    posture_label: str
    confidence: TenxPriceConfidence
    base_target_low: float | None = None
    base_target_high: float | None = None
    bull_target_low: float | None = None
    bull_target_high: float | None = None
    bear_zone_low: float | None = None
    bear_zone_high: float | None = None
    upside_pct_mid: float | None = None
    downside_pct_mid: float | None = None


class TenxWatchlistItemRow(BaseModel):
    market: TenxMarket
    symbol: str
    name: str
    thesis_status: TenxThesisStatus
    alert_type: str
    last_event: str
    next_check: str
    risk_level: TenxRiskLevel
    score: int
    price_snapshot: TenxPriceSnapshotRow | None = None
    tracking_status: str = "事件追踪中"
    active_alert_count: int = 0
    next_alert_due: str | None = None
    available_actions: list[TenxActionRow]


class TenxTimelineEventRow(BaseModel):
    id: str
    market: TenxMarket
    symbol: str
    date: str
    title: str
    type: TenxTimelineType
    summary: str


class TenxWorkspaceSnapshotResponse(BaseModel):
    market: TenxMarket
    universe: str
    universe_strategy: str
    universe_description: str
    universe_buckets: list[TenxUniverseBucketRow]
    snapshot_at: str
    freshness: TenxFreshnessRow
    available_actions: list[TenxActionRow]
    candidates: list[TenxCandidateRow]
    themes: list[TenxThemeRow]
    watchlist: list[TenxWatchlistItemRow]
    timeline: list[TenxTimelineEventRow]
    copilot_prompts: list[str]


class TenxEarningsShortlineRow(BaseModel):
    market: TenxMarket
    symbol: str
    name: str
    theme: str
    stage: TenxStage
    flow_status: TenxFlowStatus
    flow_status_label: str
    score: int
    score_change: float
    risk_level: TenxRiskLevel
    momentum: TenxMomentum
    next_event: str
    next_earnings_date: str | None = None
    days_to_earnings: int | None = None
    fiscal_period: str = ""
    time_of_day: str = ""
    eps_estimate: float | None = None
    revenue_estimate: float | None = None
    currency: str = ""
    earnings_quality: str = "unavailable"
    source_vendor: str = ""
    shortline_signal: str
    action_label: str


class TenxEarningsOptionRow(BaseModel):
    market: TenxMarket
    symbol: str
    name: str
    next_earnings_date: str | None = None
    days_to_earnings: int | None = None
    score: int
    underlying_price: float | None = None
    nearest_expiration: str | None = None
    expiration_count: int = 0
    contract_count: int = 0
    total_call_volume: int = 0
    total_put_volume: int = 0
    call_put_volume_ratio: float | None = None
    total_call_open_interest: int = 0
    total_put_open_interest: int = 0
    call_put_open_interest_ratio: float | None = None
    avg_implied_volatility: float | None = None
    max_pain_strike: float | None = None
    liquidity_score: float | None = None
    flow_score: float | None = None
    option_selection_score: float | None = None
    flow_sentiment: str = "unknown"
    data_quality_flag: str = "unavailable"
    updated_at: str = ""
    option_signal: str
    action_label: str


class TenxEarningsLensResponse(BaseModel):
    market: TenxMarket
    snapshot_at: str
    freshness: TenxFreshnessRow
    shortline: list[TenxEarningsShortlineRow]
    options: list[TenxEarningsOptionRow]
    notes: list[str] = Field(default_factory=list)


class TenxEvidenceItemRow(BaseModel):
    id: str
    source: str
    published_at: str
    title: str
    note: str
    linked_to: list[str] = Field(default_factory=list)


class TenxRiskItemRow(BaseModel):
    title: str
    severity: TenxRiskLevel
    trigger: str
    note: str


class TenxResearchCardResponse(BaseModel):
    market: TenxMarket
    symbol: str
    name: str
    sector: str
    theme: str
    stage: TenxStage
    lifecycle_stage: TenxLifecycleStageRow
    score: int
    thesis_summary: str
    selection_reason: str
    stage_reason: str
    crowding_note: str
    score_drivers: list[str]
    why_selected: TenxWhySelectedRow
    score_breakdown: list[TenxScoreBreakdownRow]
    facts: list[str]
    thesis_points: list[str]
    evidence_items: list[TenxEvidenceItemRow]
    risk_items: list[TenxRiskItemRow]
    next_watch_points: list[str]
    price_map: TenxPriceMapResponse | None = None
    freshness: TenxFreshnessRow
    available_actions: list[TenxActionRow]


class TenxResearchReportResponse(BaseModel):
    report_id: str
    market: TenxMarket
    symbol: str
    title: str
    source_filename: str
    content_markdown: str
    word_count: int
    status: str
    created_at: str
    updated_at: str


class TenxResearchReportUploadResponse(BaseModel):
    ok: bool = True
    message: str
    report: TenxResearchReportResponse


class TenxDiscoverCandidateCreateRequest(BaseModel):
    market: TenxMarket
    symbol: str
    name: str | None = None
    source: str = "manual"
    stage: TenxStage = "discovery"
    theme: str | None = None
    thesis: str | None = None
    note: str | None = None
    trigger_scene: str | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)


class TenxAlertItemRow(BaseModel):
    id: str
    market: TenxMarket
    symbol: str
    title: str
    summary: str
    severity: TenxAlertSeverity
    alert_type: str
    source: str
    created_at: str
    next_action: str
    evidence_grade: str = "D"
    confidence: str = "low"
    status: str = "draft"
    due_at: str | None = None
    source_note: str = ""
    event_layer: list[str] = Field(default_factory=list)
    structure_layer: list[str] = Field(default_factory=list)
    execution_layer: list[str] = Field(default_factory=list)
    invalidation_signals: list[str] = Field(default_factory=list)


class TenxAlertCenterResponse(BaseModel):
    market: TenxMarket
    freshness: TenxFreshnessRow
    available_actions: list[TenxActionRow]
    items: list[TenxAlertItemRow]


class TenxWatchlistMutationRequest(BaseModel):
    market: TenxMarket
    symbol: str
    action: Literal["watch", "unwatch"]
    trigger_scene: str | None = None


class TenxWatchlistUpdateRequest(BaseModel):
    market: TenxMarket
    state: Literal["watching", "inactive"]
    trigger_scene: str | None = None


class TenxAlertCreateRequest(BaseModel):
    market: TenxMarket
    symbol: str
    severity: TenxAlertSeverity = "P2"
    alert_type: str = "custom"
    title: str
    note: str
    rule_payload: dict[str, Any] = Field(default_factory=dict)


class TenxDeerFlowFileMeta(BaseModel):
    filename: str
    size: str
    path: str
    virtual_path: str
    artifact_url: str
    markdown_file: str | None = None
    markdown_path: str | None = None
    markdown_virtual_path: str | None = None
    markdown_artifact_url: str | None = None


class TenxDeerFlowChatRequest(BaseModel):
    prompt: str
    thread_id: str | None = None
    files: list[TenxDeerFlowFileMeta] = Field(default_factory=list)


class TenxDeerFlowChatResponse(BaseModel):
    ok: bool
    content: str
    backend: str
    thread_id: str | None = None
    error: str | None = None


class TenxDeerFlowHistoryRequest(BaseModel):
    thread_id: str
    limit: int = 10


class TenxDeerFlowSearchRequest(BaseModel):
    limit: int = 20
    metadata: dict[str, Any] = Field(default_factory=dict)


class TenxMutationResponse(BaseModel):
    ok: bool = True
    message: str
