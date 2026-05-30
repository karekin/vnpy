import type {
  InvestmentCopilotActionDecision,
  InvestmentCopilotActionPreflight,
  InvestmentCopilotActionStatus,
  InvestmentCopilotDailyBrief,
  InvestmentCopilotInvestorPolicy,
  InvestmentLedgerBootstrapRequest,
  InvestmentLedgerBootstrapResponse,
  InvestmentLedgerCsvImportRequest,
  InvestmentLedgerCsvImportResponse,
  InvestmentLedgerSummary,
} from "@/components/investment-copilot/types";

function configuredServerApiBase() {
  if (typeof window !== "undefined") {
    const publicApiBase = process.env.NEXT_PUBLIC_INVESTMENT_COPILOT_API_URL;
    return typeof publicApiBase === "string" && publicApiBase.trim().length > 0
      ? publicApiBase.replace(/\/$/, "")
      : "";
  }

  const configured = [
    process.env.INVESTMENT_COPILOT_INTERNAL_API_URL,
    process.env.TENX_INTERNAL_API_URL,
    process.env.NEXT_PUBLIC_INVESTMENT_COPILOT_API_URL,
    process.env.NEXT_PUBLIC_API_URL,
    "http://127.0.0.1:8002",
  ].find((item) => typeof item === "string" && item.trim().length > 0);

  return (configured ?? "http://127.0.0.1:8002").replace(/\/$/, "");
}

function buildUrl(path: string) {
  return `${configuredServerApiBase()}${path}`;
}

export class InvestmentCopilotApiError extends Error {
  status?: number;
  url: string;

  constructor(message: string, url: string, status?: number) {
    super(message);
    this.name = "InvestmentCopilotApiError";
    this.url = url;
    this.status = status;
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });

  if (!response.ok) {
    throw new InvestmentCopilotApiError(`Investment Copilot API request failed with HTTP ${response.status}.`, url, response.status);
  }

  return (await response.json()) as T;
}

export function loadInvestmentCopilotDailyBrief(market = "US") {
  const params = new URLSearchParams({ market });
  return requestJson<InvestmentCopilotDailyBrief>(buildUrl(`/api/v1/investment-copilot/daily-brief?${params.toString()}`));
}

export function loadInvestmentLedgerSummary() {
  return requestJson<InvestmentLedgerSummary>(buildUrl("/api/v1/investment-copilot/ledger/summary"));
}

export function bootstrapInvestmentLedger(payload: InvestmentLedgerBootstrapRequest) {
  return requestJson<InvestmentLedgerBootstrapResponse>(buildUrl("/api/v1/investment-copilot/ledger/bootstrap"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function importInvestmentLedgerCsv(payload: InvestmentLedgerCsvImportRequest) {
  return requestJson<InvestmentLedgerCsvImportResponse>(buildUrl("/api/v1/investment-copilot/ledger/import-csv"), {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateInvestmentCopilotPolicy(policy: InvestmentCopilotInvestorPolicy) {
  return requestJson<InvestmentCopilotInvestorPolicy>(buildUrl("/api/v1/investment-copilot/policy"), {
    method: "PUT",
    body: JSON.stringify(policy),
  });
}

export function loadInvestmentCopilotActionDecisions() {
  return requestJson<InvestmentCopilotActionDecision[]>(buildUrl("/api/v1/investment-copilot/actions/decisions"));
}

export function recordInvestmentCopilotActionDecision(
  actionId: string,
  payload: {
    status: InvestmentCopilotActionStatus;
    user_note?: string;
    decision_reason?: string;
  },
  market = "US",
) {
  const params = new URLSearchParams({ market });
  return requestJson<InvestmentCopilotActionDecision>(
    buildUrl(`/api/v1/investment-copilot/actions/${encodeURIComponent(actionId)}/decision?${params.toString()}`),
    {
      method: "POST",
      body: JSON.stringify({
        status: payload.status,
        user_note: payload.user_note ?? "",
        decision_reason: payload.decision_reason ?? "",
      }),
    },
  );
}

export function preflightInvestmentCopilotAction(
  actionId: string,
  payload: {
    market?: string;
    intended_action?: string;
    acknowledged_human_confirmation?: boolean;
  },
) {
  return requestJson<InvestmentCopilotActionPreflight>(
    buildUrl(`/api/v1/investment-copilot/actions/${encodeURIComponent(actionId)}/preflight`),
    {
      method: "POST",
      body: JSON.stringify({
        market: payload.market ?? "US",
        intended_action: payload.intended_action ?? "",
        acknowledged_human_confirmation: payload.acknowledged_human_confirmation ?? false,
      }),
    },
  );
}
