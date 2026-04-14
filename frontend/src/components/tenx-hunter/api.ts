import type {
  TenxCandidate,
  TenxOverviewMetric,
  TenxResearchCard,
  TenxTheme,
  TenxTimelineEvent,
  TenxWatchlistItem,
  TenxWorkspaceSnapshot,
} from "@/components/tenx-hunter/types";

type TenxCandidateApi = {
  symbol: string;
  name: string;
  sector: string;
  theme: string;
  stage: TenxCandidate["stage"];
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
};

type TenxThemeApi = {
  slug: string;
  name: string;
  heat: number;
  trend: TenxTheme["trend"];
  driver: string;
  evidence: string[];
  related_symbols: string[];
};

type TenxWatchlistApi = {
  symbol: string;
  name: string;
  thesis_status: TenxWatchlistItem["thesisStatus"];
  alert_type: string;
  last_event: string;
  next_check: string;
  risk_level: TenxWatchlistItem["riskLevel"];
  score: number;
};

type TenxTimelineApi = {
  id: string;
  symbol: string;
  date: string;
  title: string;
  type: TenxTimelineEvent["type"];
  summary: string;
};

type TenxWorkspaceSnapshotApi = {
  market: "US";
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
  candidates: TenxCandidateApi[];
  themes: TenxThemeApi[];
  watchlist: TenxWatchlistApi[];
  timeline: TenxTimelineApi[];
  copilot_prompts: string[];
};

type TenxResearchEvidenceApi = {
  source: string;
  published_at: string;
  note: string;
};

type TenxResearchCardApi = {
  symbol: string;
  name: string;
  sector: string;
  theme: string;
  stage: TenxResearchCard["stage"];
  score: number;
  thesis_summary: string;
  selection_reason: string;
  stage_reason: string;
  crowding_note: string;
  score_drivers: string[];
  facts: string[];
  thesis_points: string[];
  risks: string[];
  next_checkpoints: string[];
  evidence: TenxResearchEvidenceApi[];
};

const configuredApiBase = [
  process.env.NEXT_PUBLIC_TENX_HUNTER_API_URL,
  process.env.NEXT_PUBLIC_API_URL,
  "http://127.0.0.1:8000",
].find((item) => typeof item === "string" && item.trim().length > 0);

const apiBase = (configuredApiBase ?? "http://127.0.0.1:8000").replace(/\/$/, "");

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
  return `${apiBase}${path}`;
}

async function requestJson<T>(url: string): Promise<T> {
  if (typeof fetch !== "function") {
    throw new TenxApiError("TenX API is unavailable because fetch() is not present in this runtime.", url);
  }

  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    throw new TenxApiError(`TenX API request failed with HTTP ${response.status}.`, url, response.status);
  }
  return (await response.json()) as T;
}

function mapCandidate(item: TenxCandidateApi): TenxCandidate {
  return {
    symbol: item.symbol,
    name: item.name,
    sector: item.sector,
    theme: item.theme,
    stage: item.stage,
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
  };
}

function mapTheme(item: TenxThemeApi): TenxTheme {
  return {
    slug: item.slug,
    name: item.name,
    heat: item.heat,
    trend: item.trend,
    driver: item.driver,
    evidence: item.evidence,
    relatedSymbols: item.related_symbols,
  };
}

function mapWatchlist(item: TenxWatchlistApi): TenxWatchlistItem {
  return {
    symbol: item.symbol,
    name: item.name,
    thesisStatus: item.thesis_status,
    alertType: item.alert_type,
    lastEvent: item.last_event,
    nextCheck: item.next_check,
    riskLevel: item.risk_level,
    score: item.score,
  };
}

function mapTimeline(item: TenxTimelineApi): TenxTimelineEvent {
  return {
    id: item.id,
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
    candidates: payload.candidates.map(mapCandidate),
    themes: payload.themes.map(mapTheme),
    watchlist: payload.watchlist.map(mapWatchlist),
    timeline: payload.timeline.map(mapTimeline),
    copilotPrompts: payload.copilot_prompts,
  };
}

function mapResearchCard(payload: TenxResearchCardApi): TenxResearchCard {
  return {
    symbol: payload.symbol,
    name: payload.name,
    sector: payload.sector,
    theme: payload.theme,
    stage: payload.stage,
    score: payload.score,
    thesisSummary: payload.thesis_summary,
    selectionReason: payload.selection_reason,
    stageReason: payload.stage_reason,
    crowdingNote: payload.crowding_note,
    scoreDrivers: payload.score_drivers,
    facts: payload.facts,
    thesisPoints: payload.thesis_points,
    risks: payload.risks,
    nextCheckpoints: payload.next_checkpoints,
    evidence: payload.evidence.map((item) => ({
      source: item.source,
      publishedAt: item.published_at,
      note: item.note,
    })),
  };
}

export async function loadTenxWorkspaceSnapshot(): Promise<TenxWorkspaceSnapshot> {
  const payload = await requestJson<TenxWorkspaceSnapshotApi>(buildUrl("/api/v1/tenx-hunter/workspace"));
  return mapWorkspaceSnapshot(payload);
}

export async function loadTenxResearchCard(symbol: string): Promise<TenxResearchCard | null> {
  try {
    const payload = await requestJson<TenxResearchCardApi>(
      buildUrl(`/api/v1/tenx-hunter/research/${encodeURIComponent(symbol)}`),
    );
    return mapResearchCard(payload);
  } catch (error) {
    if (error instanceof TenxApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
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
      delta: "偏向验证期与加速期",
      tone: "green",
    },
    {
      label: "升温主题",
      value: String(risingThemes),
      delta: snapshot.themes[0] ? `${snapshot.themes[0].name} 领跑` : "等待主题数据",
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

export function getThemeBySlug(slug: string, snapshot: TenxWorkspaceSnapshot): TenxTheme | null {
  return snapshot.themes.find((item) => item.slug === slug) ?? null;
}

export function getRelatedCandidatesForTheme(slug: string, snapshot: TenxWorkspaceSnapshot): TenxCandidate[] {
  const theme = getThemeBySlug(slug, snapshot);
  if (!theme) {
    return [];
  }
  return snapshot.candidates.filter((item) => theme.relatedSymbols.includes(item.symbol));
}

export function getTimelineForSymbol(symbol: string, snapshot: TenxWorkspaceSnapshot): TenxTimelineEvent[] {
  return snapshot.timeline.filter((item) => item.symbol.toUpperCase() === symbol.toUpperCase());
}

export function getCopilotContext(snapshot: TenxWorkspaceSnapshot): string[] {
  return [
    `市场：${snapshot.market}`,
    `范围：${snapshot.universe}`,
    `更新时间：${snapshot.snapshotAt}`,
    `当前最热主题：${snapshot.themes
      .slice()
      .sort((a, b) => b.heat - a.heat)
      .slice(0, 2)
      .map((item) => item.name)
      .join(" / ")}`,
  ];
}
