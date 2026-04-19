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


class TenxFreshnessRow(BaseModel):
    updated_at: str
    data_complete: bool
    source_summary: str
    coverage: str


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
    freshness: TenxFreshnessRow
    available_actions: list[TenxActionRow]


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
