export type TenxStage = "early" | "validation" | "acceleration" | "crowded";
export type TenxRiskLevel = "low" | "medium" | "high";
export type TenxMomentum = "strengthening" | "stable" | "cooling";
export type TenxThemeTrend = "rising" | "stable" | "weakening";
export type TenxThesisStatus = "strengthening" | "needs-review" | "at-risk";
export type TenxTimelineType = "earnings" | "capex" | "price" | "supply-chain" | "risk";

export type TenxCandidate = {
  symbol: string;
  name: string;
  sector: string;
  theme: string;
  stage: TenxStage;
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
  selectionReason?: string;
  stageReason?: string;
  crowdingNote?: string;
  scoreDrivers?: string[];
};

export type TenxTheme = {
  slug: string;
  name: string;
  heat: number;
  trend: TenxThemeTrend;
  driver: string;
  evidence: string[];
  relatedSymbols: string[];
};

export type TenxWatchlistItem = {
  symbol: string;
  name: string;
  thesisStatus: TenxThesisStatus;
  alertType: string;
  lastEvent: string;
  nextCheck: string;
  riskLevel: TenxRiskLevel;
  score: number;
};

export type TenxEvidence = {
  source: string;
  publishedAt: string;
  note: string;
};

export type TenxResearchCard = {
  symbol: string;
  name: string;
  sector: string;
  theme: string;
  stage: TenxStage;
  score: number;
  thesisSummary: string;
  selectionReason?: string;
  stageReason?: string;
  crowdingNote?: string;
  scoreDrivers?: string[];
  facts: string[];
  thesisPoints: string[];
  risks: string[];
  nextCheckpoints: string[];
  evidence: TenxEvidence[];
};

export type TenxTimelineEvent = {
  id: string;
  symbol: string;
  date: string;
  title: string;
  type: TenxTimelineType;
  summary: string;
};

export type TenxWorkspaceSnapshot = {
  market: "US";
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
  candidates: TenxCandidate[];
  themes: TenxTheme[];
  watchlist: TenxWatchlistItem[];
  timeline: TenxTimelineEvent[];
  copilotPrompts: string[];
};

export type TenxOverviewMetric = {
  label: string;
  value: string;
  delta: string;
  tone: "green" | "yellow" | "blue" | "slate";
};
