import type {
  TenxAlertCenter,
  TenxAlertItem,
  TenxCandidate,
  TenxFreshness,
  TenxMarket,
  TenxOverviewMetric,
  TenxResearchCard,
  TenxTheme,
  TenxTimelineEvent,
  TenxWatchlistItem,
  TenxWorkspaceSnapshot,
} from "@/components/tenx-hunter/types";

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
  if (typeof window !== "undefined") {
    return path;
  }

  return `${apiBase}${path}`;
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
  freshness: TenxApiFreshness;
  available_actions: TenxApiAction[];
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

function mapCandidate(item: TenxCandidateApi): TenxCandidate {
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
    freshness: mapFreshness(payload.freshness),
    availableActions: mapActions(payload.available_actions),
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
    })),
  };
}

export async function loadTenxWorkspaceSnapshot(market: TenxMarket): Promise<TenxWorkspaceSnapshot> {
  const payload = await requestJson<TenxWorkspaceSnapshotApi>(
    buildUrl(`/api/v1/tenx-hunter/workspace?market=${encodeURIComponent(toMarketParam(market))}`),
  );
  return mapWorkspaceSnapshot(payload);
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

export async function createAlertDraft(market: TenxMarket, symbol: string, title: string, note: string) {
  return requestJson<{ ok: boolean; message: string }>(buildUrl("/api/v1/tenx-hunter/alerts"), {
    method: "POST",
    body: JSON.stringify({
      market: toMarketParam(market),
      symbol,
      severity: "P2",
      alert_type: "custom",
      title,
      note,
      rule_payload: {},
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
