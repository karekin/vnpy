export type InvestmentCopilotSeverity = "info" | "watch" | "warning" | "critical";
export type InvestmentCopilotSource = "portfolio" | "research" | "cb_quant" | "data_quality";
export type InvestmentCopilotActionStatus = "pending" | "accepted" | "ignored" | "executed" | "reviewed";
export type InvestmentLedgerAssetType = "cash" | "equity" | "etf" | "bond" | "convertible_bond" | "option" | "fund" | "crypto" | "other";
export type InvestmentLedgerImportFormat = "generic_csv" | "schwab_positions" | "ibkr_positions";

export type InvestmentCopilotSourceHealth = {
  source: string;
  ok: boolean;
  summary: string;
  detail: string;
};

export type InvestmentCopilotPortfolioBrief = {
  total_equity: number;
  health_score: number;
  risk_level: string;
  cash_value: number;
  options_value: number;
  cash_gap: number;
  options_excess: number;
  margin_used: number;
  margin_limit: number;
  guardrail_count: number;
  blocking_guardrail_count: number;
  top_guardrails: string[];
};

export type InvestmentCopilotResearchCandidate = {
  symbol: string;
  name: string;
  score: number;
  risk_level: string;
  thesis: string;
  next_event: string;
};

export type InvestmentCopilotResearchBrief = {
  market: string;
  universe: string;
  snapshot_at: string;
  candidate_count: number;
  theme_count: number;
  watchlist_count: number;
  top_candidates: InvestmentCopilotResearchCandidate[];
  hot_themes: string[];
};

export type InvestmentCopilotCbQuantBrief = {
  latest_trade_date: string | null;
  latest_bond_count: number;
  snapshot_count: number;
  running_jobs: number;
  queued_jobs: number;
  finished_jobs: number;
  failed_jobs: number;
  active_optimize_tasks: number;
  top_strategy: string;
  top_cagr: number | null;
  top_drawdown: number | null;
};

export type InvestmentLedgerTopPosition = {
  symbol: string;
  asset_type: InvestmentLedgerAssetType;
  market_value: number;
  weight: number;
  account_id: string;
};

export type InvestmentLedgerSummary = {
  account_count: number;
  holding_count: number;
  total_equity: number;
  cash_value: number;
  invested_value: number;
  options_value: number;
  largest_position_weight: number;
  base_currency: string;
  top_positions: InvestmentLedgerTopPosition[];
  updated_at: string | null;
};

export type InvestmentLedgerReconciliation = {
  ok: boolean;
  summary: string;
  total_equity_delta: number;
  cash_delta: number;
  options_delta: number;
  delta_ratio: number;
  tolerance_ratio: number;
};

export type InvestmentLedgerAccountRequest = {
  account_id: string;
  name: string;
  account_type?: string;
  currency?: string;
  base_currency?: string;
  active?: boolean;
};

export type InvestmentLedgerHoldingRequest = {
  account_id: string;
  symbol: string;
  asset_type: InvestmentLedgerAssetType;
  quantity?: number;
  market_value: number;
  currency?: string;
  cost_basis?: number | null;
  as_of_date?: string | null;
};

export type InvestmentLedgerCashflowRequest = {
  account_id: string;
  event_type?: string;
  amount: number;
  currency?: string;
  symbol?: string | null;
  event_date?: string | null;
  note?: string;
};

export type InvestmentLedgerBootstrapRequest = {
  accounts: InvestmentLedgerAccountRequest[];
  holdings: InvestmentLedgerHoldingRequest[];
  cashflows?: InvestmentLedgerCashflowRequest[];
};

export type InvestmentLedgerBootstrapResponse = {
  account_count: number;
  holding_count: number;
  cashflow_count: number;
  summary: InvestmentLedgerSummary;
};

export type InvestmentLedgerCsvImportRequest = {
  account: InvestmentLedgerAccountRequest;
  raw_csv: string;
  format?: InvestmentLedgerImportFormat;
  default_currency?: string;
  as_of_date?: string | null;
};

export type InvestmentLedgerCsvImportError = {
  row_number: number;
  message: string;
  raw: Record<string, string>;
};

export type InvestmentLedgerCsvImportResponse = {
  account: InvestmentLedgerAccountRequest & { updated_at: string };
  imported_holding_count: number;
  rejected_row_count: number;
  summary: InvestmentLedgerSummary;
  errors: InvestmentLedgerCsvImportError[];
};

export type InvestmentCopilotActionCard = {
  id: string;
  source: InvestmentCopilotSource;
  severity: InvestmentCopilotSeverity;
  priority: number;
  title: string;
  rationale: string;
  suggested_action: string;
  evidence: string[];
  href: string;
  requires_confirmation: boolean;
  status: InvestmentCopilotActionStatus;
  user_note: string;
  decision_reason: string;
  decided_at: string | null;
};

export type InvestmentCopilotDecisionPolicy = {
  stance: string;
  hard_rules: string[];
  review_questions: string[];
};

export type InvestmentCopilotInvestorPolicy = {
  profile_name: string;
  stance: string;
  cash_floor_ratio: number;
  max_single_stock_ratio: number;
  max_options_ratio: number;
  max_margin_ratio: number;
  require_human_confirmation: boolean;
  allow_leaps: boolean;
  allow_wheel: boolean;
  allow_cb_quant: boolean;
  forbidden_symbols: string[];
  updated_at: string | null;
};

export type InvestmentCopilotActionDecision = {
  action_id: string;
  status: InvestmentCopilotActionStatus;
  user_note: string;
  decision_reason: string;
  updated_at: string;
};

export type InvestmentCopilotActionPreflight = {
  action_id: string;
  allowed: boolean;
  requires_human_confirmation: boolean;
  blockers: string[];
  warnings: string[];
  checklist: string[];
  generated_at: string;
};

export type InvestmentCopilotDailyBrief = {
  generated_at: string;
  headline: string;
  portfolio: InvestmentCopilotPortfolioBrief;
  ledger: InvestmentLedgerSummary;
  reconciliation: InvestmentLedgerReconciliation;
  research: InvestmentCopilotResearchBrief;
  cb_quant: InvestmentCopilotCbQuantBrief;
  source_health: InvestmentCopilotSourceHealth[];
  action_cards: InvestmentCopilotActionCard[];
  decision_policy: InvestmentCopilotDecisionPolicy;
  investor_policy: InvestmentCopilotInvestorPolicy;
};
