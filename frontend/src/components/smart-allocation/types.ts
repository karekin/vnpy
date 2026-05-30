export type SmartAllocationRiskLevel = "green" | "yellow" | "orange" | "red";

export type SmartAllocationProfile = {
  id: string;
  age: number;
  income_status: "stable" | "unstable" | "retired";
  name: string;
  rebalance_threshold: number;
  allow_bull_market_leaps_relaxation: boolean;
  quality_stock_symbols: string[];
  wheel_symbols: string[];
  leaps_symbols: string[];
  qqqm_symbol: string;
  voo_symbol: string;
};

export type SmartAllocationSnapshot = {
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
  source_inputs: Record<string, string>;
  snapshot_at: string;
};

export type SmartAllocationTargets = {
  dca_ratio: number;
  cash_ratio: number;
  options_ratio: number;
  dca_value: number;
  cash_value: number;
  options_value: number;
  qqqm_value: number;
  voo_value: number;
  quality_stock_value: number;
  single_stock_limit: number;
  wheel_value: number;
  leaps_value: number;
  margin_limit: number;
};

export type SmartAllocationGuardrail = {
  rule_code: string;
  risk_level: SmartAllocationRiskLevel;
  message: string;
  actual_value: number;
  limit_value: number;
  recommended_action: string;
  blocking: boolean;
};

export type SmartAllocationRecommendation = {
  id: string;
  recommendation_type: string;
  priority: number;
  amount: number;
  reason: string;
  before_state: Record<string, number>;
  after_state: Record<string, number>;
  status: string;
  symbol?: string | null;
  user_note: string;
};

export type SmartAllocationLeapsCandidate = {
  symbol: string;
  rsi: number;
  status: string;
  reason: string;
};

export type SmartAllocationWheelCandidate = {
  symbol: string;
  source: string;
  score: number;
  status: string;
  estimated_cash_required: number;
  max_contracts: number;
  reason: string;
  blockers: string[];
};

export type SmartAllocationWheelCandidatePoolSource = {
  name: string;
  count: number;
  symbols: string[];
  rule: string;
};

export type SmartAllocationWheelDailyRecommendation = {
  scan_date: string;
  account_equity: number;
  wheel_target: number;
  wheel_available: number;
  candidate_count: number;
  actionable_count: number;
  candidates: SmartAllocationWheelCandidate[];
  pool_sources: SmartAllocationWheelCandidatePoolSource[];
  methodology: string[];
};

export type SmartAllocationCallSpreadCandidate = {
  symbol: string;
  source: string;
  score: number;
  status: string;
  expiration_date?: string | null;
  long_strike?: number | null;
  short_strike?: number | null;
  net_debit: number;
  max_profit: number;
  max_loss: number;
  reward_risk: number;
  break_even?: number | null;
  max_contracts: number;
  underlying_price?: number | null;
  reason: string;
  blockers: string[];
};

export type SmartAllocationCallSpreadDailyRecommendation = {
  scan_date: string;
  account_equity: number;
  options_available: number;
  per_trade_limit: number;
  candidate_count: number;
  actionable_count: number;
  candidates: SmartAllocationCallSpreadCandidate[];
  methodology: string[];
};

export type SmartAllocationWaterfallTransfer = {
  amount: number;
  source_bucket: string;
  target_bucket: string;
  target_sub_bucket?: string | null;
  reason: string;
};

export type SmartAllocationCashflowEvent = {
  event_type: string;
  amount: number;
  source_bucket: string;
  target_bucket: string;
  symbol?: string | null;
  note: string;
  created_at: string;
};

export type SmartAllocationDashboard = {
  profile: SmartAllocationProfile;
  snapshot: SmartAllocationSnapshot;
  targets: SmartAllocationTargets;
  guardrails: SmartAllocationGuardrail[];
  recommendations: SmartAllocationRecommendation[];
  health_score: number;
  risk_level: SmartAllocationRiskLevel;
  data_warnings: string[];
  profile_source: string;
  snapshot_source: string;
};
