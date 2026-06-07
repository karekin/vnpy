export type TenxMarket = "CN" | "US";
export type TenxStage = "discovery" | "validation" | "acceleration" | "crowded" | "falsified";
export type TenxRiskLevel = "low" | "medium" | "high";
export type TenxMomentum = "strengthening" | "stable" | "cooling";
export type TenxThemeTrend = "rising" | "stable" | "weakening";
export type TenxThesisStatus = "strengthening" | "needs-review" | "at-risk";
export type TenxTimelineType = "earnings" | "capex" | "price" | "supply-chain" | "risk" | "filing";
export type TenxAlertSeverity = "P1" | "P2" | "P3";
export type TenxPriceConfidence = "low" | "medium" | "high";
export type TenxFlowStatus = "hot-lead" | "candidate" | "watch-ready" | "watching" | "alerting" | "blocked";
export type TenxMarketSentimentTone = "extreme-fear" | "fear" | "neutral" | "greed" | "extreme-greed" | "unavailable";
export type TenxPoliticalEvidenceGrade = "A" | "B" | "C" | "D";
export type TenxPoliticalSignalStatus = "confirmed" | "watching" | "needs-verification" | "discarded";

export type TenxFreshness = {
  updatedAt: string;
  dataComplete: boolean;
  sourceSummary: string;
  coverage: string;
};

export type TenxMarketSentimentPoint = {
  date: string;
  value: number;
};

export type TenxMarketSentimentMetric = {
  key: string;
  label: string;
  category: string;
  value: number | null;
  displayValue: string;
  score: number | null;
  tone: TenxMarketSentimentTone;
  statusLabel: string;
  detail: string;
  source: string;
  sourceUrl: string;
  updatedAt: string;
  previousValue: number | null;
  change: number | null;
  history: TenxMarketSentimentPoint[];
};

export type TenxMarketSentiment = {
  market: TenxMarket;
  snapshotAt: string;
  compositeScore: number | null;
  regime: TenxMarketSentimentTone;
  regimeLabel: string;
  summary: string;
  riskPosture: string;
  dataQuality: string;
  freshness: TenxFreshness;
  metrics: TenxMarketSentimentMetric[];
  notes: string[];
};

export type TenxPoliticalDisclosureSummary = {
  source: string;
  sourceUrl: string;
  filingType: string;
  latestFilingDate: string;
  transactionWindow: string;
  totalTrades: number | null;
  purchases: number | null;
  sales: number | null;
  lateFilings: number | null;
  lateFilingPct: number | null;
  detail: string;
};

export type TenxPoliticalTrade = {
  date: string;
  symbol: string;
  description: string;
  tradeType: string;
  amount: string;
  isLate: boolean;
  sourceUrl: string;
};

export type TenxPoliticalMention = {
  symbol: string;
  name: string;
  eventDate: string;
  eventType: string;
  status: TenxPoliticalSignalStatus;
  evidenceGrade: TenxPoliticalEvidenceGrade;
  headline: string;
  summary: string;
  source: string;
  sourceUrl: string;
  verificationNote: string;
  nextAction: string;
  watchlistRule: string;
};

export type TenxPoliticalSignal = {
  market: TenxMarket;
  person: string;
  snapshotAt: string;
  thesis: string;
  freshness: TenxFreshness;
  disclosure: TenxPoliticalDisclosureSummary;
  recentTrades: TenxPoliticalTrade[];
  mentions: TenxPoliticalMention[];
  monitoringRules: string[];
  notes: string[];
};

export type TenxEventMonitorSourceStatus = "ok" | "degraded" | "unavailable";

export type TenxEventMonitorSource = {
  key: string;
  label: string;
  source: string;
  sourceUrl: string;
  status: TenxEventMonitorSourceStatus;
  detail: string;
  updatedAt: string;
};

export type TenxEventMonitorRule = {
  key: string;
  label: string;
  eventType: string;
  priority: TenxAlertSeverity;
  scope: string;
  cadence: string;
  enabled: boolean;
  source: string;
  sourceUrl: string;
};

export type TenxEventMonitorEvent = {
  eventId: string;
  market: TenxMarket;
  symbol: string;
  eventType: string;
  title: string;
  summary: string;
  eventTime: string;
  dueAt?: string | null;
  priority: TenxAlertSeverity;
  evidenceGrade: string;
  confidence: string;
  source: string;
  sourceUrl: string;
  status: string;
  matchedRule: string;
  assetRelevance: string;
};

export type TenxEventMonitor = {
  market: TenxMarket;
  snapshotAt: string;
  freshness: TenxFreshness;
  watchlistSymbols: string[];
  generatedAlerts: number;
  sourceStatus: TenxEventMonitorSource[];
  rules: TenxEventMonitorRule[];
  events: TenxEventMonitorEvent[];
  notes: string[];
};

export type TenxAction = {
  id: string;
  label: string;
  kind: string;
  enabled: boolean;
};

export type TenxWhySelected = {
  summary: string;
  bullets: string[];
};

export type TenxScoreBreakdown = {
  key: string;
  label: string;
  score: number;
  weight: number;
  summary: string;
  positiveNotes: string[];
  negativeNotes: string[];
};

export type TenxLifecycleStage = {
  key: TenxStage;
  label: string;
  summary: string;
};

export type TenxPromotionCheck = {
  key: string;
  label: string;
  passed: boolean;
  detail: string;
};

export type TenxCandidate = {
  market: TenxMarket;
  symbol: string;
  name: string;
  sector: string;
  theme: string;
  stage: TenxStage;
  lifecycleStage: TenxLifecycleStage;
  score: number;
  scoreChange: number;
  price: number;
  priceChangePct: number;
  marketCapLabel: string;
  evidenceCount: number;
  riskLevel: TenxRiskLevel;
  momentum: TenxMomentum;
  nextEvent: string;
  thesis: string;
  keySignal: string;
  selectionReason: string;
  stageReason: string;
  crowdingNote: string;
  scoreDrivers: string[];
  whySelected: TenxWhySelected;
  scoreBreakdown: TenxScoreBreakdown[];
  flowStatus: TenxFlowStatus;
  flowStatusLabel: string;
  promotionSummary: string;
  promotionChecks: TenxPromotionCheck[];
  freshness: TenxFreshness;
  availableActions: TenxAction[];
};

export type TenxTheme = {
  market: TenxMarket;
  slug: string;
  name: string;
  heat: number;
  trend: TenxThemeTrend;
  driver: string;
  evidence: string[];
  relatedSymbols: string[];
  freshness: TenxFreshness;
};

export type TenxWatchlistItem = {
  market: TenxMarket;
  symbol: string;
  name: string;
  thesisStatus: TenxThesisStatus;
  alertType: string;
  lastEvent: string;
  nextCheck: string;
  riskLevel: TenxRiskLevel;
  score: number;
  priceSnapshot?: TenxPriceSnapshot | null;
  trackingStatus: string;
  activeAlertCount: number;
  nextAlertDue?: string | null;
  availableActions: TenxAction[];
};

export type TenxTargetRange = {
  scenario: "bear" | "base" | "bull";
  horizon: string;
  low: number | null;
  high: number | null;
  mid: number | null;
  upsidePctMid: number | null;
  method: string;
  confidence: TenxPriceConfidence;
  assumptions: Record<string, unknown>;
  evidenceRefs: string[];
};

export type TenxKeyLevel = {
  levelType: string;
  label: string;
  low: number | null;
  high: number | null;
  strength: string;
  distancePct: number | null;
  source: string;
  note: string;
  evidenceRefs: string[];
};

export type TenxScenarioPath = {
  name: string;
  probability: number;
  confidence: TenxPriceConfidence;
  trigger: string;
  targetScenario: string;
  invalidation: string;
  explanation: string;
  evidenceRefs: string[];
};

export type TenxPriceMap = {
  market: TenxMarket;
  symbol: string;
  asOfDate: string;
  currentPrice: number | null;
  posture: string;
  postureLabel: string;
  confidence: TenxPriceConfidence;
  baseTarget: TenxTargetRange;
  bullTarget: TenxTargetRange;
  bearZone: TenxTargetRange;
  keyLevels: TenxKeyLevel[];
  scenarioPaths: TenxScenarioPath[];
  invalidationRules: Record<string, unknown>[];
  evidenceRefs: string[];
  explanation: Record<string, string>;
  hitReviews: {
    snapshotDate: string;
    reviewDate: string;
    horizonDays: number;
    baseHit: boolean | null;
    bullHit: boolean | null;
    bearBreached: boolean | null;
    maxClose: number | null;
    minClose: number | null;
    hitSummary: string;
  }[];
};

export type TenxPriceSnapshot = {
  asOfDate: string;
  currentPrice: number | null;
  posture: string;
  postureLabel: string;
  confidence: TenxPriceConfidence;
  baseTargetLow: number | null;
  baseTargetHigh: number | null;
  bullTargetLow: number | null;
  bullTargetHigh: number | null;
  bearZoneLow: number | null;
  bearZoneHigh: number | null;
  upsidePctMid: number | null;
  downsidePctMid: number | null;
};

export type TenxEvidenceItem = {
  id: string;
  source: string;
  publishedAt: string;
  title: string;
  note: string;
  linkedTo: string[];
};

export type TenxRiskItem = {
  title: string;
  severity: TenxRiskLevel;
  trigger: string;
  note: string;
};

export type TenxResearchCard = {
  market: TenxMarket;
  symbol: string;
  name: string;
  sector: string;
  theme: string;
  stage: TenxStage;
  lifecycleStage: TenxLifecycleStage;
  score: number;
  thesisSummary: string;
  selectionReason: string;
  stageReason: string;
  crowdingNote: string;
  scoreDrivers: string[];
  whySelected: TenxWhySelected;
  scoreBreakdown: TenxScoreBreakdown[];
  facts: string[];
  thesisPoints: string[];
  evidenceItems: TenxEvidenceItem[];
  riskItems: TenxRiskItem[];
  nextWatchPoints: string[];
  priceMap?: TenxPriceMap | null;
  freshness: TenxFreshness;
  availableActions: TenxAction[];
};

export type TenxResearchReport = {
  reportId: string;
  market: TenxMarket;
  symbol: string;
  title: string;
  sourceFilename: string;
  contentMarkdown: string;
  wordCount: number;
  status: string;
  createdAt: string;
  updatedAt: string;
};

export type TenxTimelineEvent = {
  id: string;
  market: TenxMarket;
  symbol: string;
  date: string;
  title: string;
  type: TenxTimelineType;
  summary: string;
};

export type TenxWorkspaceSnapshot = {
  market: TenxMarket;
  universe: string;
  universeStrategy: string;
  universeDescription: string;
  universeBuckets: {
    slug: string;
    label: string;
    rationale: string;
    symbolCount: number;
    sampleSymbols: string[];
  }[];
  snapshotAt: string;
  freshness: TenxFreshness;
  availableActions: TenxAction[];
  candidates: TenxCandidate[];
  themes: TenxTheme[];
  watchlist: TenxWatchlistItem[];
  timeline: TenxTimelineEvent[];
  copilotPrompts: string[];
};

export type TenxEarningsShortlineItem = {
  market: TenxMarket;
  symbol: string;
  name: string;
  theme: string;
  stage: TenxStage;
  flowStatus: TenxFlowStatus;
  flowStatusLabel: string;
  score: number;
  scoreChange: number;
  riskLevel: TenxRiskLevel;
  momentum: TenxMomentum;
  nextEvent: string;
  nextEarningsDate?: string | null;
  daysToEarnings?: number | null;
  fiscalPeriod: string;
  timeOfDay: string;
  epsEstimate?: number | null;
  revenueEstimate?: number | null;
  currency: string;
  earningsQuality: string;
  sourceVendor: string;
  shortlineSignal: string;
  actionLabel: string;
};

export type TenxEarningsOptionItem = {
  market: TenxMarket;
  symbol: string;
  name: string;
  nextEarningsDate?: string | null;
  daysToEarnings?: number | null;
  score: number;
  underlyingPrice?: number | null;
  nearestExpiration?: string | null;
  expirationCount: number;
  contractCount: number;
  totalCallVolume: number;
  totalPutVolume: number;
  callPutVolumeRatio?: number | null;
  totalCallOpenInterest: number;
  totalPutOpenInterest: number;
  callPutOpenInterestRatio?: number | null;
  avgImpliedVolatility?: number | null;
  maxPainStrike?: number | null;
  liquidityScore?: number | null;
  flowScore?: number | null;
  optionSelectionScore?: number | null;
  flowSentiment: string;
  dataQualityFlag: string;
  updatedAt: string;
  optionSignal: string;
  actionLabel: string;
};

export type TenxEarningsLens = {
  market: TenxMarket;
  snapshotAt: string;
  freshness: TenxFreshness;
  shortline: TenxEarningsShortlineItem[];
  options: TenxEarningsOptionItem[];
  notes: string[];
};

/* ── Earnings Event Desk（市场维度全量） ── */

export type TenxEarningsDeskMetrics = {
  totalEvents: number;
  p1Count: number;
  optionReadableCount: number;
  avgExpectedMove: number | null;
};

export type TenxEarningsDeskEvent = {
  market: TenxMarket;
  symbol: string;
  name: string;
  sector: string;
  nextEarningsDate: string | null;
  daysToEarnings: number | null;
  fiscalPeriod: string;
  timeOfDay: string;
  epsEstimate: number | null;
  revenueEstimate: number | null;
  currency: string;
  dataQualityFlag: string;
  sourceVendor: string;
  avgImpliedVolatility: number | null;
  maxPainStrike: number | null;
  liquidityScore: number | null;
  flowScore: number | null;
  optionSelectionScore: number | null;
  flowSentiment: string;
  optionSignal: string;
  priority: TenxAlertSeverity;
  actionLabel: string;
};

export type TenxEarningsDeskData = {
  market: TenxMarket;
  snapshotAt: string;
  freshness: TenxFreshness;
  metrics: TenxEarningsDeskMetrics;
  events: TenxEarningsDeskEvent[];
  notes: string[];
};

export type TenxAlertItem = {
  id: string;
  market: TenxMarket;
  symbol: string;
  title: string;
  summary: string;
  severity: TenxAlertSeverity;
  alertType: string;
  source: string;
  createdAt: string;
  nextAction: string;
  evidenceGrade: string;
  confidence: string;
  status: string;
  dueAt?: string | null;
  sourceNote: string;
  eventLayer: string[];
  structureLayer: string[];
  executionLayer: string[];
  invalidationSignals: string[];
};

export type TenxAlertCenter = {
  market: TenxMarket;
  freshness: TenxFreshness;
  availableActions: TenxAction[];
  items: TenxAlertItem[];
};

export type TenxOverviewMetric = {
  label: string;
  value: string;
  delta: string;
  tone: "green" | "yellow" | "blue" | "slate";
};

/* ── 期权策略历史回测 ── */

export type TenxBacktestTrade = {
  tradeDate: string;
  entryPrice: number;
  exitPrice: number | null;
  ivOnEntry: number | null;
  flowSentiment: string;
};

export type TenxBacktestStrategyResult = {
  key: string;
  name: string;
  nameEn: string;
  direction: string;
  totalTrades: number;
  wins: number;
  losses: number;
  winRate: number;
  avgProfitPct: number;
  avgLossPct: number;
  profitFactor: number;
  currentStreak: string;
  bestTradePct: number;
  worstTradePct: number;
  backtestLogic: string;
  sampleTrades: TenxBacktestTrade[];
};

export type TenxStrategyBacktestData = {
  market: string;
  symbol: string;
  lookbackDays: number;
  horizonDays: number;
  totalBacktestDays: number;
  snapshotAt: string;
  strategies: TenxBacktestStrategyResult[];
  notes: string[];
};
