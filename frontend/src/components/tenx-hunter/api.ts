import type {
  TenxAlertCenter,
  TenxAlertItem,
  TenxAlertSeverity,
  TenxCandidate,
  TenxEarningsDeskData,
  TenxEarningsDeskEvent,
  TenxEarningsDeskMetrics,
  TenxEarningsLens,
  TenxEventMonitor,
  TenxFreshness,
  TenxMarket,
  TenxMarketSentiment,
  TenxOverviewMetric,
  TenxPoliticalSignal,
  TenxPriceMap,
  TenxPriceSnapshot,
  TenxResearchCard,
  TenxResearchReport,
  TenxTheme,
  TenxTimelineEvent,
  TenxWatchlistItem,
  TenxWorkspaceSnapshot,
} from "@/components/tenx-hunter/types";

function runtimeEnv(name: string) {
  return typeof process !== "undefined" ? process.env[name] : undefined;
}

function configuredServerApiBase() {
  const configured = [
    runtimeEnv("TENX_INTERNAL_API_URL"),
    runtimeEnv("TENX_DEERFLOW_API_URL"),
    runtimeEnv("NEXT_PUBLIC_TENX_HUNTER_API_URL"),
    runtimeEnv("NEXT_PUBLIC_API_URL"),
    "http://127.0.0.1:8000",
  ].find((item) => typeof item === "string" && item.trim().length > 0);

  return (configured ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

export class TenxApiError extends Error {
  status?: number;
  url: string;

  constructor(message: string, url: string, status?: number) {
    super(message);
    this.name = "TenxApiError";
    this.url = url;
    this.status = status;
  }
}

function buildUrl(path: string) {
  if (typeof window !== "undefined") {
    return path;
  }

  return `${configuredServerApiBase()}${path}`;
}

function toMarketParam(market: string) {
  return market.toUpperCase() === "US" ? "US" : "CN";
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  if (typeof fetch !== "function") {
    throw new TenxApiError("TenX API is unavailable because fetch() is not present in this runtime.", url);
  }

  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });
  if (!response.ok) {
    throw new TenxApiError(`TenX API request failed with HTTP ${response.status}.`, url, response.status);
  }
  return (await response.json()) as T;
}

type TenxApiFreshness = {
  updated_at: string;
  data_complete: boolean;
  source_summary: string;
  coverage: string;
};

type TenxApiAction = {
  id: string;
  label: string;
  kind: string;
  enabled: boolean;
};

type TenxMarketSentimentMetricApi = {
  key: string;
  label: string;
  category: string;
  value: number | null;
  display_value: string;
  score: number | null;
  tone: TenxMarketSentiment["regime"];
  status_label: string;
  detail: string;
  source: string;
  source_url: string;
  updated_at: string;
  previous_value: number | null;
  change: number | null;
  history: Array<{
    date: string;
    value: number;
  }>;
};

type TenxMarketSentimentApi = {
  market: TenxMarket;
  snapshot_at: string;
  composite_score: number | null;
  regime: TenxMarketSentiment["regime"];
  regime_label: string;
  summary: string;
  risk_posture: string;
  data_quality: string;
  freshness: TenxApiFreshness;
  metrics: TenxMarketSentimentMetricApi[];
  notes: string[];
};

type TenxPoliticalDisclosureApi = {
  source: string;
  source_url: string;
  filing_type: string;
  latest_filing_date: string;
  transaction_window: string;
  total_trades: number | null;
  purchases: number | null;
  sales: number | null;
  late_filings: number | null;
  late_filing_pct: number | null;
  detail: string;
};

type TenxPoliticalTradeApi = {
  date: string;
  symbol: string;
  description: string;
  trade_type: string;
  amount: string;
  is_late: boolean;
  source_url: string;
};

type TenxPoliticalMentionApi = {
  symbol: string;
  name: string;
  event_date: string;
  event_type: string;
  status: TenxPoliticalSignal["mentions"][number]["status"];
  evidence_grade: TenxPoliticalSignal["mentions"][number]["evidenceGrade"];
  headline: string;
  summary: string;
  source: string;
  source_url: string;
  verification_note: string;
  next_action: string;
  watchlist_rule: string;
};

type TenxPoliticalSignalApi = {
  market: TenxMarket;
  person: string;
  snapshot_at: string;
  thesis: string;
  freshness: TenxApiFreshness;
  disclosure: TenxPoliticalDisclosureApi;
  recent_trades: TenxPoliticalTradeApi[];
  mentions: TenxPoliticalMentionApi[];
  monitoring_rules: string[];
  notes: string[];
};

type TenxEventMonitorApi = {
  market: TenxMarket;
  snapshot_at: string;
  freshness: TenxApiFreshness;
  watchlist_symbols: string[];
  generated_alerts: number;
  source_status: Array<{
    key: string;
    label: string;
    source: string;
    source_url: string;
    status: TenxEventMonitor["sourceStatus"][number]["status"];
    detail: string;
    updated_at: string;
  }>;
  rules: Array<{
    key: string;
    label: string;
    event_type: string;
    priority: TenxAlertSeverity;
    scope: string;
    cadence: string;
    enabled: boolean;
    source: string;
    source_url: string;
  }>;
  events: Array<{
    event_id: string;
    market: TenxMarket;
    symbol: string;
    event_type: string;
    title: string;
    summary: string;
    event_time: string;
    due_at?: string | null;
    priority: TenxAlertSeverity;
    evidence_grade: string;
    confidence: string;
    source: string;
    source_url: string;
    status: string;
    matched_rule: string;
    asset_relevance: string;
  }>;
  notes: string[];
};

type TenxApiScoreBreakdown = {
  key: string;
  label: string;
  score: number;
  weight: number;
  summary: string;
  positive_notes: string[];
  negative_notes: string[];
};

type TenxApiLifecycle = {
  key: TenxCandidate["stage"];
  label: string;
  summary: string;
};

type TenxApiWhySelected = {
  summary: string;
  bullets: string[];
};

type TenxCandidateApi = {
  market: TenxMarket;
  symbol: string;
  name: string;
  sector: string;
  theme: string;
  stage: TenxCandidate["stage"];
  lifecycle_stage: TenxApiLifecycle;
  score: number;
  score_change: number;
  price: number;
  price_change_pct: number;
  market_cap_label: string;
  evidence_count: number;
  risk_level: TenxCandidate["riskLevel"];
  momentum: TenxCandidate["momentum"];
  next_event: string;
  thesis: string;
  key_signal: string;
  selection_reason: string;
  stage_reason: string;
  crowding_note: string;
  score_drivers: string[];
  why_selected: TenxApiWhySelected;
  score_breakdown: TenxApiScoreBreakdown[];
  flow_status?: TenxCandidate["flowStatus"];
  flow_status_label?: string;
  promotion_summary?: string;
  promotion_checks?: Array<{
    key: string;
    label: string;
    passed: boolean;
    detail: string;
  }>;
  freshness: TenxApiFreshness;
  available_actions: TenxApiAction[];
};

type TenxThemeApi = {
  market: TenxMarket;
  slug: string;
  name: string;
  heat: number;
  trend: TenxTheme["trend"];
  driver: string;
  evidence: string[];
  related_symbols: string[];
  freshness: TenxApiFreshness;
};

type TenxWatchlistApi = {
  market: TenxMarket;
  symbol: string;
  name: string;
  thesis_status: TenxWatchlistItem["thesisStatus"];
  alert_type: string;
  last_event: string;
  next_check: string;
  risk_level: TenxWatchlistItem["riskLevel"];
  score: number;
  price_snapshot?: TenxPriceSnapshotApi | null;
  tracking_status?: string;
  active_alert_count?: number;
  next_alert_due?: string | null;
  available_actions: TenxApiAction[];
};

type TenxTimelineApi = {
  id: string;
  market: TenxMarket;
  symbol: string;
  date: string;
  title: string;
  type: TenxTimelineEvent["type"];
  summary: string;
};

type TenxWorkspaceSnapshotApi = {
  market: TenxMarket;
  universe: string;
  universe_strategy: string;
  universe_description: string;
  universe_buckets: {
    slug: string;
    label: string;
    rationale: string;
    symbol_count: number;
    sample_symbols: string[];
  }[];
  snapshot_at: string;
  freshness: TenxApiFreshness;
  available_actions: TenxApiAction[];
  candidates: TenxCandidateApi[];
  themes: TenxThemeApi[];
  watchlist: TenxWatchlistApi[];
  timeline: TenxTimelineApi[];
  copilot_prompts: string[];
};

type TenxEarningsShortlineApi = {
  market: TenxMarket;
  symbol: string;
  name: string;
  theme: string;
  stage: TenxCandidate["stage"];
  flow_status: TenxCandidate["flowStatus"];
  flow_status_label: string;
  score: number;
  score_change: number;
  risk_level: TenxCandidate["riskLevel"];
  momentum: TenxCandidate["momentum"];
  next_event: string;
  next_earnings_date?: string | null;
  days_to_earnings?: number | null;
  fiscal_period: string;
  time_of_day: string;
  eps_estimate?: number | null;
  revenue_estimate?: number | null;
  currency: string;
  earnings_quality: string;
  source_vendor: string;
  shortline_signal: string;
  action_label: string;
};

type TenxEarningsOptionApi = {
  market: TenxMarket;
  symbol: string;
  name: string;
  next_earnings_date?: string | null;
  days_to_earnings?: number | null;
  score: number;
  underlying_price?: number | null;
  nearest_expiration?: string | null;
  expiration_count: number;
  contract_count: number;
  total_call_volume: number;
  total_put_volume: number;
  call_put_volume_ratio?: number | null;
  total_call_open_interest: number;
  total_put_open_interest: number;
  call_put_open_interest_ratio?: number | null;
  avg_implied_volatility?: number | null;
  max_pain_strike?: number | null;
  liquidity_score?: number | null;
  flow_score?: number | null;
  option_selection_score?: number | null;
  flow_sentiment: string;
  data_quality_flag: string;
  updated_at: string;
  option_signal: string;
  action_label: string;
};

type TenxEarningsLensApi = {
  market: TenxMarket;
  snapshot_at: string;
  freshness: TenxApiFreshness;
  shortline: TenxEarningsShortlineApi[];
  options: TenxEarningsOptionApi[];
  notes: string[];
};

type TenxEarningsDeskEventApi = {
  market: TenxMarket;
  symbol: string;
  name: string;
  sector: string;
  next_earnings_date: string | null;
  days_to_earnings: number | null;
  fiscal_period: string;
  time_of_day: string;
  eps_estimate: number | null;
  revenue_estimate: number | null;
  currency: string;
  data_quality_flag: string;
  source_vendor: string;
  avg_implied_volatility: number | null;
  max_pain_strike: number | null;
  liquidity_score: number | null;
  flow_score: number | null;
  option_selection_score: number | null;
  flow_sentiment: string;
  option_signal: string;
  priority: TenxAlertSeverity;
  action_label: string;
};

type TenxEarningsDeskMetricsApi = {
  total_events: number;
  p1_count: number;
  option_readable_count: number;
  avg_expected_move: number | null;
};

type TenxEarningsDeskApi = {
  market: TenxMarket;
  snapshot_at: string;
  freshness: TenxApiFreshness;
  metrics: TenxEarningsDeskMetricsApi;
  events: TenxEarningsDeskEventApi[];
  notes: string[];
};

type TenxResearchCardApi = {
  market: TenxMarket;
  symbol: string;
  name: string;
  sector: string;
  theme: string;
  stage: TenxResearchCard["stage"];
  lifecycle_stage: TenxApiLifecycle;
  score: number;
  thesis_summary: string;
  selection_reason: string;
  stage_reason: string;
  crowding_note: string;
  score_drivers: string[];
  why_selected: TenxApiWhySelected;
  score_breakdown: TenxApiScoreBreakdown[];
  facts: string[];
  thesis_points: string[];
  evidence_items: {
    id: string;
    source: string;
    published_at: string;
    title: string;
    note: string;
    linked_to: string[];
  }[];
  risk_items: {
    title: string;
    severity: TenxResearchCard["riskItems"][number]["severity"];
    trigger: string;
    note: string;
  }[];
  next_watch_points: string[];
  price_map?: TenxPriceMapApi | null;
  freshness: TenxApiFreshness;
  available_actions: TenxApiAction[];
};

type TenxResearchReportApi = {
  report_id: string;
  market: TenxMarket;
  symbol: string;
  title: string;
  source_filename: string;
  content_markdown: string;
  word_count: number;
  status: string;
  created_at: string;
  updated_at: string;
};

type TenxTargetRangeApi = {
  scenario: "bear" | "base" | "bull";
  horizon: string;
  low: number | null;
  high: number | null;
  mid: number | null;
  upside_pct_mid: number | null;
  method: string;
  confidence: "low" | "medium" | "high";
  assumptions: Record<string, unknown>;
  evidence_refs: string[];
};

type TenxKeyLevelApi = {
  level_type: string;
  label: string;
  low: number | null;
  high: number | null;
  strength: string;
  distance_pct: number | null;
  source: string;
  note: string;
  evidence_refs: string[];
};

type TenxScenarioPathApi = {
  name: string;
  probability: number;
  confidence: "low" | "medium" | "high";
  trigger: string;
  target_scenario: string;
  invalidation: string;
  explanation: string;
  evidence_refs: string[];
};

type TenxPriceMapApi = {
  market: TenxMarket;
  symbol: string;
  as_of_date: string;
  current_price: number | null;
  posture: string;
  posture_label: string;
  confidence: "low" | "medium" | "high";
  base_target: TenxTargetRangeApi;
  bull_target: TenxTargetRangeApi;
  bear_zone: TenxTargetRangeApi;
  key_levels: TenxKeyLevelApi[];
  scenario_paths: TenxScenarioPathApi[];
  invalidation_rules: Record<string, unknown>[];
  evidence_refs: string[];
  explanation: Record<string, string>;
  hit_reviews: {
    snapshot_date: string;
    review_date: string;
    horizon_days: number;
    base_hit: boolean | null;
    bull_hit: boolean | null;
    bear_breached: boolean | null;
    max_close: number | null;
    min_close: number | null;
    hit_summary: string;
  }[];
};

type TenxPriceSnapshotApi = {
  as_of_date: string;
  current_price: number | null;
  posture: string;
  posture_label: string;
  confidence: "low" | "medium" | "high";
  base_target_low: number | null;
  base_target_high: number | null;
  bull_target_low: number | null;
  bull_target_high: number | null;
  bear_zone_low: number | null;
  bear_zone_high: number | null;
  upside_pct_mid: number | null;
  downside_pct_mid: number | null;
};

type TenxAlertCenterApi = {
  market: TenxMarket;
  freshness: TenxApiFreshness;
  available_actions: TenxApiAction[];
  items: {
    id: string;
    market: TenxMarket;
    symbol: string;
    title: string;
    summary: string;
    severity: TenxAlertItem["severity"];
    alert_type: string;
    source: string;
    created_at: string;
    next_action: string;
    evidence_grade?: string;
    confidence?: string;
    status?: string;
    due_at?: string | null;
    source_note?: string;
    event_layer?: string[];
    structure_layer?: string[];
    execution_layer?: string[];
    invalidation_signals?: string[];
  }[];
};

function mapFreshness(payload: TenxApiFreshness): TenxFreshness {
  return {
    updatedAt: payload.updated_at,
    dataComplete: payload.data_complete,
    sourceSummary: payload.source_summary,
    coverage: payload.coverage,
  };
}

function mapActions(items: TenxApiAction[]) {
  return items.map((item) => ({
    id: item.id,
    label: item.label,
    kind: item.kind,
    enabled: item.enabled,
  }));
}

function mapMarketSentiment(payload: TenxMarketSentimentApi): TenxMarketSentiment {
  return {
    market: payload.market,
    snapshotAt: payload.snapshot_at,
    compositeScore: payload.composite_score,
    regime: payload.regime,
    regimeLabel: payload.regime_label,
    summary: payload.summary,
    riskPosture: payload.risk_posture,
    dataQuality: payload.data_quality,
    freshness: mapFreshness(payload.freshness),
    metrics: payload.metrics.map((metric) => ({
      key: metric.key,
      label: metric.label,
      category: metric.category,
      value: metric.value,
      displayValue: metric.display_value,
      score: metric.score,
      tone: metric.tone,
      statusLabel: metric.status_label,
      detail: metric.detail,
      source: metric.source,
      sourceUrl: metric.source_url,
      updatedAt: metric.updated_at,
      previousValue: metric.previous_value,
      change: metric.change,
      history: metric.history,
    })),
    notes: payload.notes,
  };
}

function mapPoliticalSignal(payload: TenxPoliticalSignalApi): TenxPoliticalSignal {
  return {
    market: payload.market,
    person: payload.person,
    snapshotAt: payload.snapshot_at,
    thesis: payload.thesis,
    freshness: mapFreshness(payload.freshness),
    disclosure: {
      source: payload.disclosure.source,
      sourceUrl: payload.disclosure.source_url,
      filingType: payload.disclosure.filing_type,
      latestFilingDate: payload.disclosure.latest_filing_date,
      transactionWindow: payload.disclosure.transaction_window,
      totalTrades: payload.disclosure.total_trades,
      purchases: payload.disclosure.purchases,
      sales: payload.disclosure.sales,
      lateFilings: payload.disclosure.late_filings,
      lateFilingPct: payload.disclosure.late_filing_pct,
      detail: payload.disclosure.detail,
    },
    recentTrades: payload.recent_trades.map((trade) => ({
      date: trade.date,
      symbol: trade.symbol,
      description: trade.description,
      tradeType: trade.trade_type,
      amount: trade.amount,
      isLate: trade.is_late,
      sourceUrl: trade.source_url,
    })),
    mentions: payload.mentions.map((mention) => ({
      symbol: mention.symbol,
      name: mention.name,
      eventDate: mention.event_date,
      eventType: mention.event_type,
      status: mention.status,
      evidenceGrade: mention.evidence_grade,
      headline: mention.headline,
      summary: mention.summary,
      source: mention.source,
      sourceUrl: mention.source_url,
      verificationNote: mention.verification_note,
      nextAction: mention.next_action,
      watchlistRule: mention.watchlist_rule,
    })),
    monitoringRules: payload.monitoring_rules,
    notes: payload.notes,
  };
}

function mapEventMonitor(payload: TenxEventMonitorApi): TenxEventMonitor {
  return {
    market: payload.market,
    snapshotAt: payload.snapshot_at,
    freshness: mapFreshness(payload.freshness),
    watchlistSymbols: payload.watchlist_symbols,
    generatedAlerts: payload.generated_alerts,
    sourceStatus: payload.source_status.map((source) => ({
      key: source.key,
      label: source.label,
      source: source.source,
      sourceUrl: source.source_url,
      status: source.status,
      detail: source.detail,
      updatedAt: source.updated_at,
    })),
    rules: payload.rules.map((rule) => ({
      key: rule.key,
      label: rule.label,
      eventType: rule.event_type,
      priority: rule.priority,
      scope: rule.scope,
      cadence: rule.cadence,
      enabled: rule.enabled,
      source: rule.source,
      sourceUrl: rule.source_url,
    })),
    events: payload.events.map((event) => ({
      eventId: event.event_id,
      market: event.market,
      symbol: event.symbol,
      eventType: event.event_type,
      title: event.title,
      summary: event.summary,
      eventTime: event.event_time,
      dueAt: event.due_at,
      priority: event.priority,
      evidenceGrade: event.evidence_grade,
      confidence: event.confidence,
      source: event.source,
      sourceUrl: event.source_url,
      status: event.status,
      matchedRule: event.matched_rule,
      assetRelevance: event.asset_relevance,
    })),
    notes: payload.notes,
  };
}

function mapCandidate(item: TenxCandidateApi): TenxCandidate {
  const flowStatus = item.flow_status ?? "candidate";
  return {
    market: item.market,
    symbol: item.symbol,
    name: item.name,
    sector: item.sector,
    theme: item.theme,
    stage: item.stage,
    lifecycleStage: item.lifecycle_stage,
    score: item.score,
    scoreChange: item.score_change,
    price: item.price,
    priceChangePct: item.price_change_pct,
    marketCapLabel: item.market_cap_label,
    evidenceCount: item.evidence_count,
    riskLevel: item.risk_level,
    momentum: item.momentum,
    nextEvent: item.next_event,
    thesis: item.thesis,
    keySignal: item.key_signal,
    selectionReason: item.selection_reason,
    stageReason: item.stage_reason,
    crowdingNote: item.crowding_note,
    scoreDrivers: item.score_drivers,
    whySelected: item.why_selected,
    scoreBreakdown: item.score_breakdown.map((entry) => ({
      key: entry.key,
      label: entry.label,
      score: entry.score,
      weight: entry.weight,
      summary: entry.summary,
      positiveNotes: entry.positive_notes,
      negativeNotes: entry.negative_notes,
    })),
    flowStatus,
    flowStatusLabel: item.flow_status_label ?? "候选验证",
    promotionSummary: item.promotion_summary ?? "继续补证据后再判断是否进入观察池。",
    promotionChecks: (item.promotion_checks ?? []).map((check) => ({
      key: check.key,
      label: check.label,
      passed: check.passed,
      detail: check.detail,
    })),
    freshness: mapFreshness(item.freshness),
    availableActions: mapActions(item.available_actions),
  };
}

function mapTheme(item: TenxThemeApi): TenxTheme {
  return {
    market: item.market,
    slug: item.slug,
    name: item.name,
    heat: item.heat,
    trend: item.trend,
    driver: item.driver,
    evidence: item.evidence,
    relatedSymbols: item.related_symbols,
    freshness: mapFreshness(item.freshness),
  };
}

function mapTargetRange(item: TenxTargetRangeApi) {
  return {
    scenario: item.scenario,
    horizon: item.horizon,
    low: item.low,
    high: item.high,
    mid: item.mid,
    upsidePctMid: item.upside_pct_mid,
    method: item.method,
    confidence: item.confidence,
    assumptions: item.assumptions,
    evidenceRefs: item.evidence_refs,
  };
}

function mapPriceSnapshot(item?: TenxPriceSnapshotApi | null): TenxPriceSnapshot | null {
  if (!item) return null;
  return {
    asOfDate: item.as_of_date,
    currentPrice: item.current_price,
    posture: item.posture,
    postureLabel: item.posture_label,
    confidence: item.confidence,
    baseTargetLow: item.base_target_low,
    baseTargetHigh: item.base_target_high,
    bullTargetLow: item.bull_target_low,
    bullTargetHigh: item.bull_target_high,
    bearZoneLow: item.bear_zone_low,
    bearZoneHigh: item.bear_zone_high,
    upsidePctMid: item.upside_pct_mid,
    downsidePctMid: item.downside_pct_mid,
  };
}

function mapPriceMap(item?: TenxPriceMapApi | null): TenxPriceMap | null {
  if (!item) return null;
  return {
    market: item.market,
    symbol: item.symbol,
    asOfDate: item.as_of_date,
    currentPrice: item.current_price,
    posture: item.posture,
    postureLabel: item.posture_label,
    confidence: item.confidence,
    baseTarget: mapTargetRange(item.base_target),
    bullTarget: mapTargetRange(item.bull_target),
    bearZone: mapTargetRange(item.bear_zone),
    keyLevels: item.key_levels.map((level) => ({
      levelType: level.level_type,
      label: level.label,
      low: level.low,
      high: level.high,
      strength: level.strength,
      distancePct: level.distance_pct,
      source: level.source,
      note: level.note,
      evidenceRefs: level.evidence_refs,
    })),
    scenarioPaths: item.scenario_paths.map((path) => ({
      name: path.name,
      probability: path.probability,
      confidence: path.confidence,
      trigger: path.trigger,
      targetScenario: path.target_scenario,
      invalidation: path.invalidation,
      explanation: path.explanation,
      evidenceRefs: path.evidence_refs,
    })),
    invalidationRules: item.invalidation_rules,
    evidenceRefs: item.evidence_refs,
    explanation: item.explanation,
    hitReviews: (item.hit_reviews ?? []).map((review) => ({
      snapshotDate: review.snapshot_date,
      reviewDate: review.review_date,
      horizonDays: review.horizon_days,
      baseHit: review.base_hit,
      bullHit: review.bull_hit,
      bearBreached: review.bear_breached,
      maxClose: review.max_close,
      minClose: review.min_close,
      hitSummary: review.hit_summary,
    })),
  };
}

function mapWatchlist(item: TenxWatchlistApi): TenxWatchlistItem {
  return {
    market: item.market,
    symbol: item.symbol,
    name: item.name,
    thesisStatus: item.thesis_status,
    alertType: item.alert_type,
    lastEvent: item.last_event,
    nextCheck: item.next_check,
    riskLevel: item.risk_level,
    score: item.score,
    priceSnapshot: mapPriceSnapshot(item.price_snapshot),
    trackingStatus: item.tracking_status ?? "事件追踪中",
    activeAlertCount: item.active_alert_count ?? 0,
    nextAlertDue: item.next_alert_due ?? null,
    availableActions: mapActions(item.available_actions),
  };
}

function mapTimeline(item: TenxTimelineApi): TenxTimelineEvent {
  return {
    id: item.id,
    market: item.market,
    symbol: item.symbol,
    date: item.date,
    title: item.title,
    type: item.type,
    summary: item.summary,
  };
}

function mapWorkspaceSnapshot(payload: TenxWorkspaceSnapshotApi): TenxWorkspaceSnapshot {
  return {
    market: payload.market,
    universe: payload.universe,
    universeStrategy: payload.universe_strategy,
    universeDescription: payload.universe_description,
    universeBuckets: payload.universe_buckets.map((item) => ({
      slug: item.slug,
      label: item.label,
      rationale: item.rationale,
      symbolCount: item.symbol_count,
      sampleSymbols: item.sample_symbols,
    })),
    snapshotAt: payload.snapshot_at,
    freshness: mapFreshness(payload.freshness),
    availableActions: mapActions(payload.available_actions),
    candidates: payload.candidates.map(mapCandidate),
    themes: payload.themes.map(mapTheme),
    watchlist: payload.watchlist.map(mapWatchlist),
    timeline: payload.timeline.map(mapTimeline),
    copilotPrompts: payload.copilot_prompts,
  };
}

function mapEarningsLens(payload: TenxEarningsLensApi): TenxEarningsLens {
  return {
    market: payload.market,
    snapshotAt: payload.snapshot_at,
    freshness: mapFreshness(payload.freshness),
    shortline: payload.shortline.map((item) => ({
      market: item.market,
      symbol: item.symbol,
      name: item.name,
      theme: item.theme,
      stage: item.stage,
      flowStatus: item.flow_status,
      flowStatusLabel: item.flow_status_label,
      score: item.score,
      scoreChange: item.score_change,
      riskLevel: item.risk_level,
      momentum: item.momentum,
      nextEvent: item.next_event,
      nextEarningsDate: item.next_earnings_date ?? null,
      daysToEarnings: item.days_to_earnings ?? null,
      fiscalPeriod: item.fiscal_period,
      timeOfDay: item.time_of_day,
      epsEstimate: item.eps_estimate ?? null,
      revenueEstimate: item.revenue_estimate ?? null,
      currency: item.currency,
      earningsQuality: item.earnings_quality,
      sourceVendor: item.source_vendor,
      shortlineSignal: item.shortline_signal,
      actionLabel: item.action_label,
    })),
    options: payload.options.map((item) => ({
      market: item.market,
      symbol: item.symbol,
      name: item.name,
      nextEarningsDate: item.next_earnings_date ?? null,
      daysToEarnings: item.days_to_earnings ?? null,
      score: item.score,
      underlyingPrice: item.underlying_price ?? null,
      nearestExpiration: item.nearest_expiration ?? null,
      expirationCount: item.expiration_count,
      contractCount: item.contract_count,
      totalCallVolume: item.total_call_volume,
      totalPutVolume: item.total_put_volume,
      callPutVolumeRatio: item.call_put_volume_ratio ?? null,
      totalCallOpenInterest: item.total_call_open_interest,
      totalPutOpenInterest: item.total_put_open_interest,
      callPutOpenInterestRatio: item.call_put_open_interest_ratio ?? null,
      avgImpliedVolatility: item.avg_implied_volatility ?? null,
      maxPainStrike: item.max_pain_strike ?? null,
      liquidityScore: item.liquidity_score ?? null,
      flowScore: item.flow_score ?? null,
      optionSelectionScore: item.option_selection_score ?? null,
      flowSentiment: item.flow_sentiment,
      dataQualityFlag: item.data_quality_flag,
      updatedAt: item.updated_at,
      optionSignal: item.option_signal,
      actionLabel: item.action_label,
    })),
    notes: payload.notes,
  };
}

function mapResearchCard(payload: TenxResearchCardApi): TenxResearchCard {
  return {
    market: payload.market,
    symbol: payload.symbol,
    name: payload.name,
    sector: payload.sector,
    theme: payload.theme,
    stage: payload.stage,
    lifecycleStage: payload.lifecycle_stage,
    score: payload.score,
    thesisSummary: payload.thesis_summary,
    selectionReason: payload.selection_reason,
    stageReason: payload.stage_reason,
    crowdingNote: payload.crowding_note,
    scoreDrivers: payload.score_drivers,
    whySelected: payload.why_selected,
    scoreBreakdown: payload.score_breakdown.map((entry) => ({
      key: entry.key,
      label: entry.label,
      score: entry.score,
      weight: entry.weight,
      summary: entry.summary,
      positiveNotes: entry.positive_notes,
      negativeNotes: entry.negative_notes,
    })),
    facts: payload.facts,
    thesisPoints: payload.thesis_points,
    evidenceItems: payload.evidence_items.map((item) => ({
      id: item.id,
      source: item.source,
      publishedAt: item.published_at,
      title: item.title,
      note: item.note,
      linkedTo: item.linked_to,
    })),
    riskItems: payload.risk_items.map((item) => ({
      title: item.title,
      severity: item.severity,
      trigger: item.trigger,
      note: item.note,
    })),
    nextWatchPoints: payload.next_watch_points,
    priceMap: mapPriceMap(payload.price_map),
    freshness: mapFreshness(payload.freshness),
    availableActions: mapActions(payload.available_actions),
  };
}

function mapResearchReport(payload: TenxResearchReportApi): TenxResearchReport {
  return {
    reportId: payload.report_id,
    market: payload.market,
    symbol: payload.symbol,
    title: payload.title,
    sourceFilename: payload.source_filename,
    contentMarkdown: payload.content_markdown,
    wordCount: payload.word_count,
    status: payload.status,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  };
}

function mapAlertCenter(payload: TenxAlertCenterApi): TenxAlertCenter {
  return {
    market: payload.market,
    freshness: mapFreshness(payload.freshness),
    availableActions: mapActions(payload.available_actions),
    items: payload.items.map((item) => ({
      id: item.id,
      market: item.market,
      symbol: item.symbol,
      title: item.title,
      summary: item.summary,
      severity: item.severity,
      alertType: item.alert_type,
      source: item.source,
      createdAt: item.created_at,
      nextAction: item.next_action,
      evidenceGrade: item.evidence_grade ?? "D",
      confidence: item.confidence ?? "low",
      status: item.status ?? "draft",
      dueAt: item.due_at ?? null,
      sourceNote: item.source_note ?? "",
      eventLayer: item.event_layer ?? [],
      structureLayer: item.structure_layer ?? [],
      executionLayer: item.execution_layer ?? [],
      invalidationSignals: item.invalidation_signals ?? [],
    })),
  };
}

export async function loadTenxWorkspaceSnapshot(market: TenxMarket): Promise<TenxWorkspaceSnapshot> {
  const payload = await requestJson<TenxWorkspaceSnapshotApi>(
    buildUrl(`/api/v1/tenx-hunter/workspace?market=${encodeURIComponent(toMarketParam(market))}`),
  );
  return mapWorkspaceSnapshot(payload);
}

export async function loadTenxEarningsLens(market: TenxMarket): Promise<TenxEarningsLens> {
  const payload = await requestJson<TenxEarningsLensApi>(
    buildUrl(`/api/v1/tenx-hunter/earnings-lens?market=${encodeURIComponent(toMarketParam(market))}`),
  );
  return mapEarningsLens(payload);
}

function mapEarningsDeskMetrics(payload: TenxEarningsDeskMetricsApi): TenxEarningsDeskMetrics {
  return {
    totalEvents: payload.total_events,
    p1Count: payload.p1_count,
    optionReadableCount: payload.option_readable_count,
    avgExpectedMove: payload.avg_expected_move,
  };
}

function mapEarningsDeskEvent(payload: TenxEarningsDeskEventApi): TenxEarningsDeskEvent {
  return {
    market: payload.market,
    symbol: payload.symbol,
    name: payload.name,
    sector: payload.sector,
    nextEarningsDate: payload.next_earnings_date,
    daysToEarnings: payload.days_to_earnings,
    fiscalPeriod: payload.fiscal_period,
    timeOfDay: payload.time_of_day,
    epsEstimate: payload.eps_estimate,
    revenueEstimate: payload.revenue_estimate,
    currency: payload.currency,
    dataQualityFlag: payload.data_quality_flag,
    sourceVendor: payload.source_vendor,
    avgImpliedVolatility: payload.avg_implied_volatility,
    maxPainStrike: payload.max_pain_strike,
    liquidityScore: payload.liquidity_score,
    flowScore: payload.flow_score,
    optionSelectionScore: payload.option_selection_score,
    flowSentiment: payload.flow_sentiment,
    optionSignal: payload.option_signal,
    priority: payload.priority,
    actionLabel: payload.action_label,
  };
}

export async function loadTenxEarningsDesk(market: TenxMarket, horizon = 90): Promise<TenxEarningsDeskData> {
  const payload = await requestJson<TenxEarningsDeskApi>(
    buildUrl(`/api/v1/tenx-hunter/earnings-desk?market=${encodeURIComponent(toMarketParam(market))}&horizon=${horizon}`),
  );
  return {
    market: payload.market,
    snapshotAt: payload.snapshot_at,
    freshness: mapFreshness(payload.freshness),
    metrics: mapEarningsDeskMetrics(payload.metrics),
    events: payload.events.map(mapEarningsDeskEvent),
    notes: payload.notes,
  };
}

export async function loadTenxMarketSentiment(market: TenxMarket): Promise<TenxMarketSentiment> {
  const payload = await requestJson<TenxMarketSentimentApi>(
    buildUrl(`/api/v1/tenx-hunter/market-sentiment?market=${encodeURIComponent(toMarketParam(market))}`),
  );
  return mapMarketSentiment(payload);
}

export async function loadTenxPoliticalSignals(market: TenxMarket): Promise<TenxPoliticalSignal> {
  const payload = await requestJson<TenxPoliticalSignalApi>(
    buildUrl(`/api/v1/tenx-hunter/political-signals?market=${encodeURIComponent(toMarketParam(market))}&person=trump`),
  );
  return mapPoliticalSignal(payload);
}

export async function loadTenxEventMonitor(market: TenxMarket): Promise<TenxEventMonitor> {
  const payload = await requestJson<TenxEventMonitorApi>(
    buildUrl(`/api/v1/tenx-hunter/event-monitor?market=${encodeURIComponent(toMarketParam(market))}`),
  );
  return mapEventMonitor(payload);
}

export async function loadTenxResearchCard(market: TenxMarket, symbol: string): Promise<TenxResearchCard | null> {
  try {
    const payload = await requestJson<TenxResearchCardApi>(
      buildUrl(`/api/v1/tenx-hunter/research/${encodeURIComponent(symbol)}?market=${encodeURIComponent(toMarketParam(market))}`),
    );
    return mapResearchCard(payload);
  } catch (error) {
    if (error instanceof TenxApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function loadTenxResearchReport(market: TenxMarket, symbol: string): Promise<TenxResearchReport | null> {
  try {
    const payload = await requestJson<TenxResearchReportApi>(
      buildUrl(`/api/v1/tenx-hunter/reports/${encodeURIComponent(symbol)}?market=${encodeURIComponent(toMarketParam(market))}`),
    );
    return mapResearchReport(payload);
  } catch (error) {
    if (error instanceof TenxApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function uploadTenxResearchReport(
  market: TenxMarket,
  symbol: string,
  file: File,
): Promise<{ ok: boolean; message: string; report: TenxResearchReport }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    buildUrl(`/api/v1/tenx-hunter/reports/${encodeURIComponent(symbol)}?market=${encodeURIComponent(toMarketParam(market))}`),
    {
      method: "POST",
      body: formData,
    },
  );
  if (!response.ok) {
    throw new TenxApiError(`TenX report upload failed with HTTP ${response.status}.`, response.url, response.status);
  }
  const payload = (await response.json()) as { ok: boolean; message: string; report: TenxResearchReportApi };
  return {
    ok: payload.ok,
    message: payload.message,
    report: mapResearchReport(payload.report),
  };
}

export async function createDiscoverCandidate(
  market: TenxMarket,
  payload: {
    symbol: string;
    name?: string;
    source?: string;
    stage?: TenxCandidate["stage"];
    theme?: string;
    thesis?: string;
    note?: string;
    triggerScene?: string;
    sourcePayload?: Record<string, unknown>;
  },
) {
  return requestJson<{ ok: boolean; message: string }>(buildUrl("/api/v1/tenx-hunter/discover"), {
    method: "POST",
    body: JSON.stringify({
      market: toMarketParam(market),
      symbol: payload.symbol,
      name: payload.name,
      source: payload.source ?? "manual",
      stage: payload.stage ?? "discovery",
      theme: payload.theme,
      thesis: payload.thesis,
      note: payload.note,
      trigger_scene: payload.triggerScene ?? "manual-discover-intake",
      source_payload: payload.sourcePayload ?? {},
    }),
  });
}

export async function loadTenxPriceMap(market: TenxMarket, symbol: string): Promise<TenxPriceMap | null> {
  try {
    const payload = await requestJson<TenxPriceMapApi>(
      buildUrl(`/api/v1/tenx-hunter/price-map/${encodeURIComponent(symbol)}?market=${encodeURIComponent(toMarketParam(market))}`),
    );
    return mapPriceMap(payload);
  } catch (error) {
    if (error instanceof TenxApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function loadTenxAlerts(market: TenxMarket): Promise<TenxAlertCenter> {
  const payload = await requestJson<TenxAlertCenterApi>(
    buildUrl(`/api/v1/tenx-hunter/alerts?market=${encodeURIComponent(toMarketParam(market))}`),
  );
  return mapAlertCenter(payload);
}

export async function createWatchlistEntry(market: TenxMarket, symbol: string, action: "watch" | "unwatch") {
  return requestJson<{ ok: boolean; message: string }>(buildUrl("/api/v1/tenx-hunter/watchlist"), {
    method: "POST",
    body: JSON.stringify({
      market: toMarketParam(market),
      symbol,
      action,
      trigger_scene: "ui-action-drawer",
    }),
  });
}

type TenxAlertDraftOptions = {
  severity?: TenxAlertSeverity;
  alertType?: string;
  rulePayload?: Record<string, unknown>;
};

export async function createAlertDraft(
  market: TenxMarket,
  symbol: string,
  title: string,
  note: string,
  options: TenxAlertDraftOptions = {},
) {
  return requestJson<{ ok: boolean; message: string }>(buildUrl("/api/v1/tenx-hunter/alerts"), {
    method: "POST",
    body: JSON.stringify({
      market: toMarketParam(market),
      symbol,
      severity: options.severity ?? "P2",
      alert_type: options.alertType ?? "custom",
      title,
      note,
      rule_payload: options.rulePayload ?? {},
    }),
  });
}

export async function loadTenxDeerFlowState(threadId: string): Promise<Record<string, unknown> | null> {
  try {
    return await requestJson<Record<string, unknown>>(
      buildUrl(`/api/v1/tenx-hunter/deerflow/state?thread_id=${encodeURIComponent(threadId)}`),
    );
  } catch (error) {
    if (error instanceof TenxApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function loadTenxDeerFlowHistory(
  threadId: string,
  limit = 10,
): Promise<Array<Record<string, unknown>>> {
  return requestJson<Array<Record<string, unknown>>>(buildUrl("/api/v1/tenx-hunter/deerflow/history"), {
    method: "POST",
    body: JSON.stringify({
      thread_id: threadId,
      limit,
    }),
  });
}

export async function loadTenxDeerFlowThreads(limit = 20): Promise<Array<Record<string, unknown>>> {
  return requestJson<Array<Record<string, unknown>>>(buildUrl("/api/v1/tenx-hunter/deerflow/threads/search"), {
    method: "POST",
    body: JSON.stringify({
      limit,
      metadata: {
        source: "vnpy",
      },
    }),
  });
}

export async function loadTenxDeerFlowUploads(
  threadId: string,
): Promise<{ files: Array<{ filename: string; size?: number; created_at?: string }>; count?: number }> {
  return requestJson<{ files: Array<{ filename: string; size?: number; created_at?: string }>; count?: number }>(
    buildUrl(`/api/v1/tenx-hunter/deerflow/uploads?thread_id=${encodeURIComponent(threadId)}`),
  );
}

export async function uploadTenxDeerFlowFiles(
  threadId: string,
  files: File[] | FileList,
): Promise<{
  success: boolean;
  files: Array<{
    filename: string;
    size: string;
    path: string;
    virtual_path: string;
    artifact_url: string;
    markdown_file?: string;
    markdown_path?: string;
    markdown_virtual_path?: string;
    markdown_artifact_url?: string;
  }>;
  message: string;
}> {
  const formData = new FormData();
  for (const file of Array.from(files)) {
    formData.append("files", file);
  }

  const response = await fetch(
    buildUrl(`/api/v1/tenx-hunter/deerflow/uploads?thread_id=${encodeURIComponent(threadId)}`),
    {
      method: "POST",
      body: formData,
      cache: "no-store",
    },
  );

  if (!response.ok) {
    throw new TenxApiError(`TenX DeerFlow upload failed with HTTP ${response.status}.`, response.url, response.status);
  }

  return (await response.json()) as {
    success: boolean;
    files: Array<{
      filename: string;
      size: string;
      path: string;
      virtual_path: string;
      artifact_url: string;
      markdown_file?: string;
      markdown_path?: string;
      markdown_virtual_path?: string;
      markdown_artifact_url?: string;
    }>;
    message: string;
  };
}

export function getTenxDeerFlowArtifactUrl(threadId: string, path: string, download = false) {
  return buildUrl(
    `/api/v1/tenx-hunter/deerflow/artifact?thread_id=${encodeURIComponent(threadId)}&path=${encodeURIComponent(path)}&download=${download ? "true" : "false"}`,
  );
}

export function getTenxErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown TenX API error.";
}

export function getOverviewMetrics(snapshot: TenxWorkspaceSnapshot): TenxOverviewMetric[] {
  const strengtheningCount = snapshot.candidates.filter((item) => item.momentum === "strengthening").length;
  const highRiskCount = snapshot.watchlist.filter((item) => item.riskLevel === "high").length;
  const risingThemes = snapshot.themes.filter((item) => item.trend === "rising").length;
  const leadingTheme = snapshot.themes
    .slice()
    .sort((a, b) => b.heat - a.heat)[0];
  const avgScore = Math.round(
    snapshot.candidates.reduce((sum, item) => sum + item.score, 0) / Math.max(snapshot.candidates.length, 1),
  );

  return [
    {
      label: "今日候选",
      value: String(snapshot.candidates.length),
      delta: `${strengtheningCount} 只逻辑增强`,
      tone: "blue",
    },
    {
      label: "平均评分",
      value: String(avgScore),
      delta: snapshot.market === "CN" ? "偏向验证期与加速期" : "偏向验证期与成长延续",
      tone: "green",
    },
    {
      label: "升温主题",
      value: String(risingThemes),
      delta: risingThemes > 0 ? `${leadingTheme?.name ?? "当前主线"} 领跑` : leadingTheme ? `当前最热：${leadingTheme.name}` : "等待主题数据",
      tone: "green",
    },
    {
      label: "高风险观察",
      value: String(highRiskCount),
      delta: highRiskCount > 0 ? "需要人工复核" : "暂无高优先风险",
      tone: highRiskCount > 0 ? "yellow" : "slate",
    },
  ];
}

export function getRelatedCandidatesForTheme(slug: string, snapshot: TenxWorkspaceSnapshot): TenxCandidate[] {
  const theme = getThemeBySlug(slug, snapshot);
  if (!theme) {
    return [];
  }
  return snapshot.candidates.filter((item) => theme.relatedSymbols.includes(item.symbol));
}

export function getThemeBySlug(slug: string, snapshot: TenxWorkspaceSnapshot): TenxTheme | null {
  return snapshot.themes.find((item) => item.slug === slug) ?? null;
}

export function getTimelineForSymbol(symbol: string, snapshot: TenxWorkspaceSnapshot): TenxTimelineEvent[] {
  return snapshot.timeline.filter((item) => item.symbol.toUpperCase() === symbol.toUpperCase());
}

export function marketLabel(market: TenxMarket) {
  return market === "CN" ? "A股成长研究工作台" : "US Growth Research";
}

export function toMarketSlug(market: TenxMarket) {
  return market.toLowerCase();
}

export function fromMarketSlug(market: string): TenxMarket {
  return market.toLowerCase() === "us" ? "US" : "CN";
}
