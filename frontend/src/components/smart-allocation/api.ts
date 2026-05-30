import type {
  SmartAllocationCallSpreadDailyRecommendation,
  SmartAllocationDashboard,
  SmartAllocationCashflowEvent,
  SmartAllocationLeapsCandidate,
  SmartAllocationRecommendation,
  SmartAllocationWaterfallTransfer,
  SmartAllocationWheelCandidate,
  SmartAllocationWheelDailyRecommendation,
} from "@/components/smart-allocation/types";

const configuredApiBase = [
  process.env.NEXT_PUBLIC_SMART_ALLOCATION_API_URL,
  process.env.NEXT_PUBLIC_API_URL,
].find((item) => typeof item === "string" && item.trim().length > 0);

const apiBases = Array.from(
  new Set(
    [
      configuredApiBase,
      "http://127.0.0.1:8003",
      "http://127.0.0.1:8000",
    ]
      .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      .map((item) => item.replace(/\/$/, "")),
  ),
);

function buildUrls(path: string) {
  if (typeof window !== "undefined") {
    return [path, ...apiBases.map((base) => `${base}${path}`)];
  }
  return apiBases.map((base) => `${base}${path}`);
}

export class SmartAllocationApiError extends Error {
  status?: number;
  url: string;

  constructor(message: string, url: string, status?: number) {
    super(message);
    this.name = "SmartAllocationApiError";
    this.url = url;
    this.status = status;
  }
}

async function requestJson<T>(urls: string[], init?: RequestInit): Promise<T> {
  let lastError: SmartAllocationApiError | null = null;
  for (const url of urls) {
    try {
      const response = await fetch(url, {
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        ...init,
      });
      if (response.ok) {
        return (await response.json()) as T;
      }
      lastError = new SmartAllocationApiError(`智能仓位 API 请求失败：HTTP ${response.status}`, url, response.status);
      if (![404, 500, 502, 503, 504].includes(response.status)) {
        throw lastError;
      }
    } catch (error) {
      if (error instanceof SmartAllocationApiError && error.status && ![404, 500, 502, 503, 504].includes(error.status)) {
        throw error;
      }
      lastError = error instanceof SmartAllocationApiError
        ? error
        : new SmartAllocationApiError(error instanceof Error ? error.message : "智能仓位 API 请求失败", url);
    }
  }
  throw lastError ?? new SmartAllocationApiError("智能仓位 API 请求失败", urls[0] ?? "");
}

export function loadSmartAllocationDashboard() {
  return requestJson<SmartAllocationDashboard>(buildUrls("/api/v1/smart-allocation/dashboard"));
}

export function createSmartAllocationProfile(payload: {
  age: number;
  income_status: "stable" | "unstable" | "retired";
  name: string;
  rebalance_threshold: number;
  allow_bull_market_leaps_relaxation: boolean;
  quality_stock_symbols: string[];
  wheel_symbols: string[];
  leaps_symbols: string[];
}) {
  return requestJson(buildUrls("/api/v1/smart-allocation/profiles"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateSmartAllocationProfile(
  profileId: string,
  payload: {
    age: number;
    income_status: "stable" | "unstable" | "retired";
    name: string;
    rebalance_threshold: number;
    allow_bull_market_leaps_relaxation: boolean;
    quality_stock_symbols: string[];
    wheel_symbols: string[];
    leaps_symbols: string[];
  },
) {
  return requestJson(buildUrls(`/api/v1/smart-allocation/profiles/${encodeURIComponent(profileId)}`), {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function refreshSmartAllocationSnapshot(payload: {
  total_equity: number;
  cash_value: number;
  dca_value: number;
  options_value: number;
  wheel_value: number;
  leaps_value: number;
  margin_used: number;
  unclassified_value: number;
  single_stock_values: Record<string, number>;
  latest_rsi_by_symbol: Record<string, number>;
  open_leaps_symbols: string[];
  source_inputs?: Record<string, string>;
}) {
  return requestJson<SmartAllocationDashboard>(buildUrls("/api/v1/smart-allocation/snapshots/refresh"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function recordSmartAllocationCashflow(payload: {
  event_type: string;
  amount: number;
  source_bucket: string;
  target_bucket: string;
  symbol?: string | null;
  note: string;
}) {
  return requestJson<SmartAllocationWaterfallTransfer[]>(buildUrls("/api/v1/smart-allocation/cashflow/events"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function loadSmartAllocationCashflowEvents() {
  return requestJson<SmartAllocationCashflowEvent[]>(buildUrls("/api/v1/smart-allocation/cashflow/events"));
}

export function loadSmartAllocationLeapsCandidates() {
  return requestJson<SmartAllocationLeapsCandidate[]>(buildUrls("/api/v1/smart-allocation/leaps/candidates"));
}

export function loadSmartAllocationWheelCandidates() {
  return requestJson<SmartAllocationWheelCandidate[]>(buildUrls("/api/v1/smart-allocation/wheel/candidates"));
}

export function loadSmartAllocationWheelDailyRecommendation() {
  return requestJson<SmartAllocationWheelDailyRecommendation>(buildUrls("/api/v1/smart-allocation/wheel/daily-recommendations"));
}

export function loadSmartAllocationCallSpreadDailyRecommendation() {
  return requestJson<SmartAllocationCallSpreadDailyRecommendation>(buildUrls("/api/v1/smart-allocation/call-spread/daily-recommendations"));
}

export function updateSmartAllocationRecommendation(
  id: string,
  action: "accept" | "ignore" | "mark-executed",
  userNote = "",
) {
  return requestJson<SmartAllocationRecommendation[]>(
    buildUrls(`/api/v1/smart-allocation/recommendations/${encodeURIComponent(id)}/${action}`),
    {
      method: "POST",
      body: JSON.stringify({ user_note: userNote }),
    },
  );
}
