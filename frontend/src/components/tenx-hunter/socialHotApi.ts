function configuredApiBase() {
  const configured = [
    process.env.SOCIAL_HOT_INTERNAL_API_URL,
    process.env.TENX_INTERNAL_API_URL,
    process.env.NEXT_PUBLIC_SOCIAL_HOT_API_URL,
    process.env.NEXT_PUBLIC_TENX_HUNTER_API_URL,
    process.env.NEXT_PUBLIC_API_URL,
    "http://127.0.0.1:8000",
  ].find((item) => typeof item === "string" && item.trim().length > 0);

  return (configured ?? "http://127.0.0.1:8000").replace(/\/$/, "");
}

function buildUrl(path: string) {
  return `${configuredApiBase()}${path}`;
}

export class SocialHotApiError extends Error {
  status?: number;
  url: string;

  constructor(message: string, url: string, status?: number) {
    super(message);
    this.name = "SocialHotApiError";
    this.url = url;
    this.status = status;
  }
}

async function requestJson<T>(url: string): Promise<T> {
  if (typeof fetch !== "function") {
    throw new SocialHotApiError("Social hot stocks API is unavailable because fetch() is not present.", url);
  }

  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    throw new SocialHotApiError(`Social hot stocks request failed with HTTP ${response.status}.`, url, response.status);
  }
  return (await response.json()) as T;
}

type SocialHotStockApiItem = {
  source: string;
  source_filter: string;
  source_url: string;
  rank: number;
  symbol: string;
  name: string;
  mentions: number;
  upvotes: number;
  rank_24h_ago: number | null;
  mentions_24h_ago: number | null;
  mention_change: number | null;
  mention_change_pct: number | null;
  rank_change: number | null;
};

type SocialHotStocksApiResponse = {
  source: string;
  source_label: string;
  source_url: string;
  source_filter: string;
  window_hours: number;
  refresh_seconds: number;
  generated_at: string;
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  returned_count: number;
  cache_status: string;
  snapshot_id: number | null;
  persisted_at: string | null;
  items: SocialHotStockApiItem[];
};

export type SocialHotStockItem = {
  source: string;
  sourceFilter: string;
  sourceUrl: string;
  rank: number;
  symbol: string;
  name: string;
  mentions: number;
  upvotes: number;
  rank24hAgo: number | null;
  mentions24hAgo: number | null;
  mentionChange: number | null;
  mentionChangePct: number | null;
  rankChange: number | null;
};

export type SocialHotStocksResponse = {
  source: string;
  sourceLabel: string;
  sourceUrl: string;
  sourceFilter: string;
  windowHours: number;
  refreshSeconds: number;
  generatedAt: string;
  count: number;
  page: number;
  pageSize: number;
  totalPages: number;
  returnedCount: number;
  cacheStatus: string;
  snapshotId: number | null;
  persistedAt: string | null;
  items: SocialHotStockItem[];
};

export type LoadSocialHotStocksOptions = {
  page?: number;
  pageSize?: number;
  limit?: number;
  refresh?: boolean;
};

function mapResponse(payload: SocialHotStocksApiResponse): SocialHotStocksResponse {
  return {
    source: payload.source,
    sourceLabel: payload.source_label,
    sourceUrl: payload.source_url,
    sourceFilter: payload.source_filter,
    windowHours: payload.window_hours,
    refreshSeconds: payload.refresh_seconds,
    generatedAt: payload.generated_at,
    count: payload.count,
    page: payload.page,
    pageSize: payload.page_size,
    totalPages: payload.total_pages,
    returnedCount: payload.returned_count,
    cacheStatus: payload.cache_status,
    snapshotId: payload.snapshot_id,
    persistedAt: payload.persisted_at,
    items: payload.items.map((item) => ({
      source: item.source,
      sourceFilter: item.source_filter,
      sourceUrl: item.source_url,
      rank: item.rank,
      symbol: item.symbol,
      name: item.name,
      mentions: item.mentions,
      upvotes: item.upvotes,
      rank24hAgo: item.rank_24h_ago,
      mentions24hAgo: item.mentions_24h_ago,
      mentionChange: item.mention_change,
      mentionChangePct: item.mention_change_pct,
      rankChange: item.rank_change,
    })),
  };
}

export async function loadSocialHotStocks(options: LoadSocialHotStocksOptions | number = {}): Promise<SocialHotStocksResponse> {
  const normalizedOptions = typeof options === "number" ? { pageSize: options } : options;
  const params = new URLSearchParams({
    source: "apewisdom",
    filter: "all-stocks",
    page: String(normalizedOptions.page ?? 1),
    page_size: String(normalizedOptions.pageSize ?? normalizedOptions.limit ?? 50),
  });
  if (normalizedOptions.refresh) {
    params.set("refresh", "true");
  }

  const payload = await requestJson<SocialHotStocksApiResponse>(buildUrl(`/api/v1/social-hot-stocks?${params.toString()}`));
  return mapResponse(payload);
}

export function getSocialHotErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown social hot stocks API error.";
}
