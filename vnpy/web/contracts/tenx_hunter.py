from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


TenxStage = Literal["early", "validation", "acceleration", "crowded"]
TenxRiskLevel = Literal["low", "medium", "high"]
TenxMomentum = Literal["strengthening", "stable", "cooling"]
TenxThemeTrend = Literal["rising", "stable", "weakening"]
TenxThesisStatus = Literal["strengthening", "needs-review", "at-risk"]
TenxTimelineType = Literal["earnings", "capex", "price", "supply-chain", "risk"]


class TenxCandidateRow(BaseModel):
    symbol: str
    name: str
    sector: str
    theme: str
    stage: TenxStage
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


class TenxUniverseBucketRow(BaseModel):
    slug: str
    label: str
    rationale: str
    symbol_count: int
    sample_symbols: list[str]


class TenxThemeRow(BaseModel):
    slug: str
    name: str
    heat: int
    trend: TenxThemeTrend
    driver: str
    evidence: list[str]
    related_symbols: list[str]


class TenxWatchlistItemRow(BaseModel):
    symbol: str
    name: str
    thesis_status: TenxThesisStatus
    alert_type: str
    last_event: str
    next_check: str
    risk_level: TenxRiskLevel
    score: int


class TenxTimelineEventRow(BaseModel):
    id: str
    symbol: str
    date: str
    title: str
    type: TenxTimelineType
    summary: str


class TenxWorkspaceSnapshotResponse(BaseModel):
    market: Literal["US"] = "US"
    universe: str
    universe_strategy: str
    universe_description: str
    universe_buckets: list[TenxUniverseBucketRow]
    snapshot_at: str
    candidates: list[TenxCandidateRow]
    themes: list[TenxThemeRow]
    watchlist: list[TenxWatchlistItemRow]
    timeline: list[TenxTimelineEventRow]
    copilot_prompts: list[str]


class TenxResearchEvidenceRow(BaseModel):
    source: str
    published_at: str
    note: str


class TenxResearchCardResponse(BaseModel):
    symbol: str
    name: str
    sector: str
    theme: str
    stage: TenxStage
    score: int
    thesis_summary: str
    selection_reason: str
    stage_reason: str
    crowding_note: str
    score_drivers: list[str]
    facts: list[str]
    thesis_points: list[str]
    risks: list[str]
    next_checkpoints: list[str]
    evidence: list[TenxResearchEvidenceRow]
