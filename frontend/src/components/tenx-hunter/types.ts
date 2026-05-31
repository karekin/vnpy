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
