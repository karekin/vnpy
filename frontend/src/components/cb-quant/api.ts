export type WindowName = "full" | "3y" | "1y" | "1w";
export type StrategyTemplateStatus = "active" | "draft" | "archived";
export type BacktestJobStatus = "queued" | "running" | "finished" | "failed" | "cancelled";

export type StrategyParamSpaceRow = {
  factorKey: string;
  valueType: "number" | "enum";
  enabled: boolean;
  minValue: number | null;
  maxValue: number | null;
  step: number | null;
  enumValues: string[];
};

export type StrategyTemplate = {
  id: string;
  name: string;
  version: string;
  status: StrategyTemplateStatus;
  factorCount: number;
  rebalance: string;
  riskPreset: string;
  comboSize: number;
  owner: string;
  updatedAt: string;
};

export type StrategyTemplateConfig = {
  templateId: string;
  factorKeys: string[];
  expressionDraft: string;
  parameterSpace: StrategyParamSpaceRow[];
  comboSize: number;
  updatedAt: string;
};

export type StrategyTemplateBatchResult = {
  ok: boolean;
  affected: number;
  missingIds: string[];
  message: string;
};

export type StrategyTemplateDetail = {
  template: StrategyTemplate;
  config: StrategyTemplateConfig;
};

export type CandidateRow = {
  rank: number;
  templateId: string;
  template: string;
  comboId: string;
  estCombos: number;
  status: string;
  passRate: number | null;
  window: WindowName;
  source: "generated" | "mock";
  runId: string | null;
  generatedAt: string | null;
};

export type CandidateGenerateResult = {
  runId: string;
  templateId: string;
  templateName: string;
  createdCount: number;
  estCombos: number;
  windows: WindowName[];
  items: CandidateRow[];
  message: string;
};

export type BacktestJob = {
  jobId: string;
  strategyId: string;
  comboId: string;
  rulePackId: string;
  template: string;
  window: string;
  status: BacktestJobStatus;
  progress: number;
  businessDate: string | null;
  createdAt: string | null;
  startedAt: string;
  eta: string;
  worker: string;
};

export type BacktestLeaderboardRow = {
  rank: number;
  strategyId: string;
  comboId: string;
  rulePackId: string;
  template: string;
  cagr: number;
  mdd: number;
  calmar: number;
  winRate: number;
  turnover: number;
  recent1y: number;
  robustScore: number;
  window: WindowName;
};

export type BacktestCompareRow = {
  metric: string;
  category: "return" | "risk" | "trade";
  baseline: number;
  candidateA: number;
  candidateB: number;
  candidateC: number;
};

export type BacktestStats = {
  runningJobs: number;
  queuedJobs: number;
  finishedJobs: number;
  failedJobs: number;
  cancelledJobs: number;
  rulePackCount: number;
  topCagr: number;
};

export type BacktestQueueRequest = {
  comboId: string;
  template: string;
  sourceMode: "inherit" | "candidate" | "custom";
  rulePackId?: string;
  windows: WindowName[];
  businessDate?: string;
  startDate: string;
  endDate: string;
  capitalWan: number;
  benchmark: string;
  estStrategies?: number;
};

export type BacktestQueueResult = {
  batchId: string;
  comboId: string;
  rulePackId: string;
  sourceMode: "inherit" | "candidate" | "custom";
  createdCount: number;
  windows: WindowName[];
  jobs: BacktestJob[];
  message: string;
};

export type HistoryDataSummary = {
  snapshotCount: number;
  dateStart: string | null;
  dateEnd: string | null;
  latestTradeDate: string | null;
  latestBondCount: number;
  dataDir: string;
};

export type HistorySyncStatus = {
  hasLog: boolean;
  syncAt: string | null;
  mode: string | null;
  source: string | null;
  tradeDate: string | null;
  upserted: number;
  status: string | null;
  message: string | null;
};

export type TushareDataSummary = {
  cbTradeDays: number;
  cbDateStart: string | null;
  cbDateEnd: string | null;
  factorTradeDays: number;
  factorDateStart: string | null;
  factorDateEnd: string | null;
  eventRows: number;
  dbPath: string;
};

export type TushareSyncStatus = {
  hasLog: boolean;
  syncAt: string | null;
  mode: string | null;
  source: string | null;
  startDate: string | null;
  endDate: string | null;
  tradeDays: number;
  cbDailyRows: number;
  stockDailyRows: number;
  eventRows: number;
  factorRows: number;
  snapshotRows: number;
  status: string | null;
  message: string | null;
};

export type TushareSyncResult = {
  ok: boolean;
  mode: string;
  source: string;
  startDate: string;
  endDate: string;
  tradeDays: number;
  cbDailyRows: number;
  stockDailyRows: number;
  eventRows: number;
  factorRows: number;
  snapshotRows: number;
  message: string;
};

export type StrategyOptimizeTaskStatus = "queued" | "running" | "finished" | "failed";

export type BacktestTaskConfig = {
  initialCapitalWan: number;
  benchmarkName: string;
  rebalanceIntervalType: "trade_day" | "calendar_day" | "week" | "month";
  rebalanceIntervalValue: number;
  maxPositionPct: number;
  maxHoldCount: number;
  excludeRedeemDaysBelow: number | null;
  takeProfitPct: number | null;
  stopLossPct: number | null;
};

export type StrategyOptimizeTask = {
  taskId: string;
  templateId: string;
  templateName: string;
  status: StrategyOptimizeTaskStatus;
  progress: number;
  totalCombinations: number;
  evaluatedCombinations: number;
  windows: WindowName[];
  startDate: string | null;
  endDate: string | null;
  eta: string;
  message: string;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  taskConfig: BacktestTaskConfig;
};

export type StrategyOptimizeResultRow = {
  rank: number;
  taskId?: string | null;
  templateId?: string | null;
  templateName?: string | null;
  comboId: string;
  robustScore: number;
  cagr: number;
  mdd: number;
  calmar: number;
  winRate: number;
  turnover: number;
  recent1y: number;
  totalReturnPct: number;
  params: Record<string, string | number | boolean | null>;
};

export type StrategyTopBondRow = {
  rank: number;
  bondId: string;
  bondName: string;
  price: number;
  premiumRt: number;
  dblow: number;
  amountWan: number | null;
  score: number;
  updateTime: string;
};

export type StrategyOptimizeTaskDetail = {
  task: StrategyOptimizeTask;
  topStrategies: StrategyOptimizeResultRow[];
  topBonds: StrategyTopBondRow[];
};

export type StrategyOptimizeSummary = {
  topStrategies: StrategyOptimizeResultRow[];
  topBonds: StrategyTopBondRow[];
  finishedTaskCount: number;
  totalResultCount: number;
  message: string;
};

export type StrategyBacktestMetricRow = {
  strategyCombo: string;
  totalReturnPct: number | null;
  cumulativeAssetWan: number | null;
  annualReturnPct: number | null;
  maxDrawdownPct: number | null;
  sharpe: number | null;
  sortino: number | null;
  calmar: number | null;
  avgTurnoverPct: number | null;
  tradeCycles: number | null;
  profitCycles: number | null;
  lossCycles: number | null;
  winRatePct: number | null;
  profitLossRatio: number | null;
  avgCycleReturnPct: number | null;
  maxCycleProfitPct: number | null;
  maxCycleLossPct: number | null;
  maxDrawdownDurationDays: number | null;
};

export type StrategyBacktestCurvePoint = {
  date: string;
  strategyCumReturnPct: number;
  benchmarkCumReturnPct: number;
  relativeExcessPct: number;
  absoluteExcessPct: number;
  drawdownPct: number;
  avgDrawdownPct: number;
};

export type StrategyBacktestDistributionRow = {
  period: string;
  strategyReturnPct: number;
  benchmarkReturnPct: number;
  excessReturnPct: number;
};

export type StrategyBacktestRotationRow = {
  rebalanceDate: string;
  weekday: string;
  holdings: string;
  holdingCount: number;
  turnoverPct: number;
  periodReturnPct: number;
  cumulativeReturnPct: number;
  navWan: number;
};

export type StrategyOptimizeTaskAnalysis = {
  taskId: string;
  templateId: string;
  templateName: string;
  comboId: string;
  benchmarkName: string;
  window: WindowName;
  metricRows: StrategyBacktestMetricRow[];
  curve: StrategyBacktestCurvePoint[];
  yearlyDistribution: StrategyBacktestDistributionRow[];
  monthlyDistribution: StrategyBacktestDistributionRow[];
  weeklyDistribution: StrategyBacktestDistributionRow[];
  rotations: StrategyBacktestRotationRow[];
  message: string;
};

export type StrategyOptimizeTaskAiInsight = {
  ok: boolean;
  enabled: boolean;
  provider: string;
  model: string;
  taskId: string;
  comboId: string;
  contextMarkdown: string;
  promptMarkdown: string;
  analysisMarkdown: string;
  executiveSummary: string;
  returnDrivers: string[];
  riskExposures: string[];
  parameterInterpretation: string[];
  nextSteps: string[];
  message: string;
  generatedAt: string | null;
  cached: boolean;
};

export type StrategyOptimizeTaskAiCompare = {
  ok: boolean;
  enabled: boolean;
  provider: string;
  model: string;
  taskId: string;
  comboIds: string[];
  contextMarkdown: string;
  promptMarkdown: string;
  analysisMarkdown: string;
  executiveSummary: string;
  winnerComboId: string;
  winnerReason: string[];
  comboAStrengths: string[];
  comboARisks: string[];
  comboBStrengths: string[];
  comboBRisks: string[];
  whatToVerifyNext: string[];
  message: string;
  generatedAt: string | null;
  cached: boolean;
};

export type FactorCatalogFactor = {
  id: string;
  factorName: string;
  factorKey: string;
  factorType: number;
  expression: string;
  expressionType: number;
  enabled: boolean;
  remark: string;
  viewStyle: number;
  viewPrecision: number;
  viewColor: boolean;
  viewRatio: number;
  viewUnit: string;
  supportLevel: "strong" | "disabled";
  templateSelectable: boolean;
};

export type FactorCatalogCategory = {
  categoryName: string;
  categoryKey: string;
  factors: FactorCatalogFactor[];
};

export type FunctionParameter = {
  name: string;
  description: string;
  typeName: string;
  type: string;
};

export type FunctionCatalogFunction = {
  name: string;
  formular: string;
  description: string;
  parameterSize: number;
  parameters: FunctionParameter[];
};

export type FunctionCatalogCategory = {
  categoryName: string;
  categoryKey: string;
  functions: FunctionCatalogFunction[];
};

type StrategyTemplateApi = {
  id: string;
  name: string;
  version: string;
  status: StrategyTemplateStatus;
  factor_count: number;
  rebalance: string;
  risk_preset: string;
  combo_size: number;
  owner: string;
  updated_at: string;
};

type StrategyTemplateConfigApi = {
  template_id: string;
  factor_keys: string[];
  expression_draft: string;
  parameter_space: Array<{
    factor_key: string;
    value_type: "number" | "enum";
    enabled: boolean;
    min_value: number | null;
    max_value: number | null;
    step: number | null;
    enum_values: string[];
  }>;
  combo_size: number;
  updated_at: string;
};

type StrategyTemplateDetailApi = {
  template: StrategyTemplateApi;
  config: StrategyTemplateConfigApi;
};

type CandidateRowApi = {
  rank: number;
  template_id?: string | null;
  template: string;
  combo_id: string;
  est_combos: number;
  status: string;
  pass_rate?: number | null;
  window: WindowName;
  source: "generated" | "mock";
  run_id?: string | null;
  generated_at?: string | null;
};

type BacktestJobApi = {
  job_id: string;
  strategy_id: string;
  combo_id: string;
  rule_pack_id: string;
  template: string;
  window: string;
  status: BacktestJobStatus;
  progress: number;
  business_date?: string | null;
  created_at?: string | null;
  started_at: string;
  eta: string;
  worker: string;
};

type BacktestLeaderboardApi = {
  rank: number;
  strategy_id: string;
  combo_id: string;
  rule_pack_id: string;
  template: string;
  cagr: number;
  mdd: number;
  calmar: number;
  win_rate: number;
  turnover: number;
  recent_1y: number;
  robust_score: number;
  window: WindowName;
};

type BacktestCompareApi = {
  metric: string;
  category: "return" | "risk" | "trade";
  baseline: number;
  candidate_a: number;
  candidate_b: number;
  candidate_c: number;
};

type FactorCatalogFactorApi = {
  id: string;
  factor_name: string;
  factor_key: string;
  factor_type: number;
  expression: string;
  expression_type: number;
  enabled: boolean;
  remark: string;
  view_style: number;
  view_precision: number;
  view_color: boolean;
  view_ratio: number;
  view_unit: string;
  support_level: "strong" | "disabled";
  template_selectable: boolean;
};

type FactorCatalogCategoryApi = {
  category_name: string;
  category_key: string;
  factors: FactorCatalogFactorApi[];
};

type FunctionParameterApi = {
  name: string;
  description: string;
  type_name: string;
  type: string;
};

type FunctionCatalogFunctionApi = {
  name: string;
  formular: string;
  description: string;
  parameter_size: number;
  parameters: FunctionParameterApi[];
};

type FunctionCatalogCategoryApi = {
  category_name: string;
  category_key: string;
  functions: FunctionCatalogFunctionApi[];
};

type HistoryDataSummaryApi = {
  snapshot_count: number;
  date_start: string | null;
  date_end: string | null;
  latest_trade_date: string | null;
  latest_bond_count: number;
  data_dir: string;
};

type HistorySyncStatusApi = {
  has_log: boolean;
  sync_at: string | null;
  mode: string | null;
  source: string | null;
  trade_date: string | null;
  upserted: number;
  status: string | null;
  message: string | null;
};

type TushareDataSummaryApi = {
  cb_trade_days: number;
  cb_date_start: string | null;
  cb_date_end: string | null;
  factor_trade_days: number;
  factor_date_start: string | null;
  factor_date_end: string | null;
  event_rows: number;
  db_path: string;
};

type TushareSyncStatusApi = {
  has_log: boolean;
  sync_at: string | null;
  mode: string | null;
  source: string | null;
  start_date: string | null;
  end_date: string | null;
  trade_days: number;
  cb_daily_rows: number;
  stock_daily_rows: number;
  event_rows: number;
  factor_rows: number;
  snapshot_rows: number;
  status: string | null;
  message: string | null;
};

type StrategyOptimizeTaskApi = {
  task_id: string;
  template_id: string;
  template_name: string;
  status: StrategyOptimizeTaskStatus;
  progress: number;
  total_combinations: number;
  evaluated_combinations: number;
  windows: WindowName[];
  start_date: string | null;
  end_date: string | null;
  eta: string;
  message: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  task_config?: {
    initial_capital_wan: number;
    benchmark_name: string;
    rebalance_interval_type: "trade_day" | "calendar_day" | "week" | "month";
    rebalance_interval_value: number;
    max_position_pct: number;
    max_hold_count: number;
    exclude_redeem_days_below: number | null;
    take_profit_pct: number | null;
    stop_loss_pct: number | null;
  };
};

type StrategyOptimizeResultRowApi = {
  rank: number;
  task_id?: string | null;
  template_id?: string | null;
  template_name?: string | null;
  combo_id: string;
  robust_score: number;
  cagr: number;
  mdd: number;
  calmar: number;
  win_rate: number;
  turnover: number;
  recent_1y: number;
  total_return_pct: number;
  params: Record<string, string | number | boolean | null>;
};

type StrategyTopBondRowApi = {
  rank: number;
  bond_id: string;
  bond_name: string;
  price: number;
  premium_rt: number;
  dblow: number;
  amount_wan: number | null;
  score: number;
  update_time: string;
};

type StrategyBacktestMetricRowApi = {
  strategy_combo: string;
  total_return_pct: number | null;
  cumulative_asset_wan: number | null;
  annual_return_pct: number | null;
  max_drawdown_pct: number | null;
  sharpe: number | null;
  sortino: number | null;
  calmar: number | null;
  avg_turnover_pct: number | null;
  trade_cycles: number | null;
  profit_cycles: number | null;
  loss_cycles: number | null;
  win_rate_pct: number | null;
  profit_loss_ratio: number | null;
  avg_cycle_return_pct: number | null;
  max_cycle_profit_pct: number | null;
  max_cycle_loss_pct: number | null;
  max_drawdown_duration_days: number | null;
};

type StrategyBacktestCurvePointApi = {
  date: string;
  strategy_cum_return_pct: number;
  benchmark_cum_return_pct: number;
  relative_excess_pct: number;
  absolute_excess_pct: number;
  drawdown_pct: number;
  avg_drawdown_pct: number;
};

type StrategyBacktestDistributionRowApi = {
  period: string;
  strategy_return_pct: number;
  benchmark_return_pct: number;
  excess_return_pct: number;
};

type StrategyBacktestRotationRowApi = {
  rebalance_date: string;
  weekday: string;
  holdings: string;
  holding_count: number;
  turnover_pct: number;
  period_return_pct: number;
  cumulative_return_pct: number;
  nav_wan: number;
};

type StrategyOptimizeTaskAnalysisApi = {
  task_id: string;
  template_id: string;
  template_name: string;
  combo_id: string;
  benchmark_name: string;
  window: WindowName;
  metric_rows: StrategyBacktestMetricRowApi[];
  curve: StrategyBacktestCurvePointApi[];
  yearly_distribution: StrategyBacktestDistributionRowApi[];
  monthly_distribution: StrategyBacktestDistributionRowApi[];
  weekly_distribution: StrategyBacktestDistributionRowApi[];
  rotations: StrategyBacktestRotationRowApi[];
  message: string;
};

type StrategyOptimizeTaskAiInsightApi = {
  ok: boolean;
  enabled: boolean;
  provider: string;
  model: string;
  task_id: string;
  combo_id: string;
  context_markdown: string;
  prompt_markdown: string;
  analysis_markdown: string;
  executive_summary: string;
  return_drivers: string[];
  risk_exposures: string[];
  parameter_interpretation: string[];
  next_steps: string[];
  message: string;
  generated_at: string | null;
  cached: boolean;
};

type StrategyOptimizeTaskAiCompareApi = {
  ok: boolean;
  enabled: boolean;
  provider: string;
  model: string;
  task_id: string;
  combo_ids: string[];
  context_markdown: string;
  prompt_markdown: string;
  analysis_markdown: string;
  executive_summary: string;
  winner_combo_id: string;
  winner_reason: string[];
  combo_a_strengths: string[];
  combo_a_risks: string[];
  combo_b_strengths: string[];
  combo_b_risks: string[];
  what_to_verify_next: string[];
  message: string;
  generated_at: string | null;
  cached: boolean;
};

const configuredApiBase = [
  process.env.NEXT_PUBLIC_CB_QUANT_API_URL,
  process.env.NEXT_PUBLIC_API_URL,
  "http://127.0.0.1:8000",
].find((item) => typeof item === "string" && item.trim().length > 0);

const apiBase = (configuredApiBase ?? "http://127.0.0.1:8000").replace(/\/$/, "");

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>) {
  const search = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") {
        return;
      }
      search.set(key, String(value));
    });
  }
  const qs = search.toString();
  return `${apiBase}${path}${qs ? `?${qs}` : ""}`;
}

async function requestJson<T>(
  url: string,
  init?: RequestInit,
  options?: { timeoutMs?: number },
): Promise<T> {
  const controller = new AbortController();
  const timeoutMs = options?.timeoutMs ?? 15_000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(url, {
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      ...init,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`请求超时（>${timeoutMs / 1000}s）: ${url}`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    const text = await response.text();
    if (contentType.includes("text/html")) {
      throw new Error(
        `HTTP ${response.status}: received HTML instead of JSON (check NEXT_PUBLIC_CB_QUANT_API_URL/NEXT_PUBLIC_API_URL).`,
      );
    }
    throw new Error(text || `HTTP ${response.status}`);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    if (text.startsWith("<!DOCTYPE html") || text.startsWith("<html")) {
      throw new Error(
        "API returned HTML instead of JSON. Please check backend URL configuration.",
      );
    }
    throw new Error("API did not return JSON payload.");
  }

  return (await response.json()) as T;
}

function mapTemplate(row: StrategyTemplateApi): StrategyTemplate {
  return {
    id: row.id,
    name: row.name,
    version: row.version,
    status: row.status,
    factorCount: row.factor_count,
    rebalance: row.rebalance,
    riskPreset: row.risk_preset,
    comboSize: row.combo_size,
    owner: row.owner,
    updatedAt: row.updated_at,
  };
}

function mapTemplateConfig(row: StrategyTemplateConfigApi): StrategyTemplateConfig {
  return {
    templateId: row.template_id,
    factorKeys: row.factor_keys,
    expressionDraft: row.expression_draft,
    parameterSpace: row.parameter_space.map((item) => ({
      factorKey: item.factor_key,
      valueType: item.value_type,
      enabled: item.enabled,
      minValue: item.min_value,
      maxValue: item.max_value,
      step: item.step,
      enumValues: item.enum_values,
    })),
    comboSize: row.combo_size,
    updatedAt: row.updated_at,
  };
}

function mapCandidate(row: CandidateRowApi): CandidateRow {
  return {
    rank: row.rank,
    templateId: row.template_id ?? "unknown",
    template: row.template,
    comboId: row.combo_id,
    estCombos: row.est_combos,
    status: row.status,
    passRate: row.pass_rate ?? null,
    window: row.window,
    source: row.source,
    runId: row.run_id ?? null,
    generatedAt: row.generated_at ?? null,
  };
}

function mapBacktestJob(row: BacktestJobApi): BacktestJob {
  return {
    jobId: row.job_id,
    strategyId: row.strategy_id,
    comboId: row.combo_id,
    rulePackId: row.rule_pack_id,
    template: row.template,
    window: row.window,
    status: row.status,
    progress: row.progress,
    businessDate: row.business_date ?? null,
    createdAt: row.created_at ?? null,
    startedAt: row.started_at,
    eta: row.eta,
    worker: row.worker,
  };
}

function mapBacktestLeaderboardRow(row: BacktestLeaderboardApi): BacktestLeaderboardRow {
  return {
    rank: row.rank,
    strategyId: row.strategy_id,
    comboId: row.combo_id,
    rulePackId: row.rule_pack_id,
    template: row.template,
    cagr: row.cagr,
    mdd: row.mdd,
    calmar: row.calmar,
    winRate: row.win_rate,
    turnover: row.turnover,
    recent1y: row.recent_1y,
    robustScore: row.robust_score,
    window: row.window,
  };
}

function mapBacktestCompareRow(row: BacktestCompareApi): BacktestCompareRow {
  return {
    metric: row.metric,
    category: row.category,
    baseline: row.baseline,
    candidateA: row.candidate_a,
    candidateB: row.candidate_b,
    candidateC: row.candidate_c,
  };
}

function mapFactorCatalogFactor(row: FactorCatalogFactorApi): FactorCatalogFactor {
  return {
    id: row.id,
    factorName: row.factor_name,
    factorKey: row.factor_key,
    factorType: row.factor_type,
    expression: row.expression,
    expressionType: row.expression_type,
    enabled: row.enabled,
    remark: row.remark,
    viewStyle: row.view_style,
    viewPrecision: row.view_precision,
    viewColor: row.view_color,
    viewRatio: row.view_ratio,
    viewUnit: row.view_unit,
    supportLevel: row.support_level,
    templateSelectable: row.template_selectable,
  };
}

function mapFunctionParameter(row: FunctionParameterApi): FunctionParameter {
  return {
    name: row.name,
    description: row.description,
    typeName: row.type_name,
    type: row.type,
  };
}

function mapHistorySummary(row: HistoryDataSummaryApi): HistoryDataSummary {
  return {
    snapshotCount: row.snapshot_count,
    dateStart: row.date_start,
    dateEnd: row.date_end,
    latestTradeDate: row.latest_trade_date,
    latestBondCount: row.latest_bond_count,
    dataDir: row.data_dir,
  };
}

function mapHistorySyncStatus(row: HistorySyncStatusApi): HistorySyncStatus {
  return {
    hasLog: row.has_log,
    syncAt: row.sync_at,
    mode: row.mode,
    source: row.source,
    tradeDate: row.trade_date,
    upserted: row.upserted,
    status: row.status,
    message: row.message,
  };
}

function mapTushareSummary(row: TushareDataSummaryApi): TushareDataSummary {
  return {
    cbTradeDays: row.cb_trade_days,
    cbDateStart: row.cb_date_start,
    cbDateEnd: row.cb_date_end,
    factorTradeDays: row.factor_trade_days,
    factorDateStart: row.factor_date_start,
    factorDateEnd: row.factor_date_end,
    eventRows: row.event_rows,
    dbPath: row.db_path,
  };
}

function mapTushareSyncStatus(row: TushareSyncStatusApi): TushareSyncStatus {
  return {
    hasLog: row.has_log,
    syncAt: row.sync_at,
    mode: row.mode,
    source: row.source,
    startDate: row.start_date,
    endDate: row.end_date,
    tradeDays: row.trade_days,
    cbDailyRows: row.cb_daily_rows,
    stockDailyRows: row.stock_daily_rows,
    eventRows: row.event_rows,
    factorRows: row.factor_rows,
    snapshotRows: row.snapshot_rows,
    status: row.status,
    message: row.message,
  };
}

function mapOptimizeTask(row: StrategyOptimizeTaskApi): StrategyOptimizeTask {
  const taskConfig = row.task_config ?? {
    initial_capital_wan: 100,
    benchmark_name: "转债等权",
    rebalance_interval_type: "trade_day",
    rebalance_interval_value: 1,
    max_position_pct: 20,
    max_hold_count: 12,
    exclude_redeem_days_below: null,
    take_profit_pct: null,
    stop_loss_pct: null,
  };
  return {
    taskId: row.task_id,
    templateId: row.template_id,
    templateName: row.template_name,
    status: row.status,
    progress: row.progress,
    totalCombinations: row.total_combinations,
    evaluatedCombinations: row.evaluated_combinations,
    windows: row.windows,
    startDate: row.start_date,
    endDate: row.end_date,
    eta: row.eta,
    message: row.message,
    createdAt: row.created_at,
    startedAt: row.started_at,
    finishedAt: row.finished_at,
    taskConfig: {
      initialCapitalWan: taskConfig.initial_capital_wan,
      benchmarkName: taskConfig.benchmark_name,
      rebalanceIntervalType: taskConfig.rebalance_interval_type,
      rebalanceIntervalValue: taskConfig.rebalance_interval_value,
      maxPositionPct: taskConfig.max_position_pct,
      maxHoldCount: taskConfig.max_hold_count,
      excludeRedeemDaysBelow: taskConfig.exclude_redeem_days_below,
      takeProfitPct: taskConfig.take_profit_pct,
      stopLossPct: taskConfig.stop_loss_pct,
    },
  };
}

function mapOptimizeResultRow(row: StrategyOptimizeResultRowApi): StrategyOptimizeResultRow {
  return {
    rank: row.rank,
    taskId: row.task_id ?? null,
    templateId: row.template_id ?? null,
    templateName: row.template_name ?? null,
    comboId: row.combo_id,
    robustScore: row.robust_score,
    cagr: row.cagr,
    mdd: row.mdd,
    calmar: row.calmar,
    winRate: row.win_rate,
    turnover: row.turnover,
    recent1y: row.recent_1y,
    totalReturnPct: row.total_return_pct,
    params: row.params,
  };
}

function mapTopBondRow(row: StrategyTopBondRowApi): StrategyTopBondRow {
  return {
    rank: row.rank,
    bondId: row.bond_id,
    bondName: row.bond_name,
    price: row.price,
    premiumRt: row.premium_rt,
    dblow: row.dblow,
    amountWan: row.amount_wan,
    score: row.score,
    updateTime: row.update_time,
  };
}

function mapBacktestMetricRow(row: StrategyBacktestMetricRowApi): StrategyBacktestMetricRow {
  return {
    strategyCombo: row.strategy_combo,
    totalReturnPct: row.total_return_pct,
    cumulativeAssetWan: row.cumulative_asset_wan,
    annualReturnPct: row.annual_return_pct,
    maxDrawdownPct: row.max_drawdown_pct,
    sharpe: row.sharpe,
    sortino: row.sortino,
    calmar: row.calmar,
    avgTurnoverPct: row.avg_turnover_pct,
    tradeCycles: row.trade_cycles,
    profitCycles: row.profit_cycles,
    lossCycles: row.loss_cycles,
    winRatePct: row.win_rate_pct,
    profitLossRatio: row.profit_loss_ratio,
    avgCycleReturnPct: row.avg_cycle_return_pct,
    maxCycleProfitPct: row.max_cycle_profit_pct,
    maxCycleLossPct: row.max_cycle_loss_pct,
    maxDrawdownDurationDays: row.max_drawdown_duration_days,
  };
}

function mapBacktestCurvePoint(row: StrategyBacktestCurvePointApi): StrategyBacktestCurvePoint {
  return {
    date: row.date,
    strategyCumReturnPct: row.strategy_cum_return_pct,
    benchmarkCumReturnPct: row.benchmark_cum_return_pct,
    relativeExcessPct: row.relative_excess_pct,
    absoluteExcessPct: row.absolute_excess_pct,
    drawdownPct: row.drawdown_pct,
    avgDrawdownPct: row.avg_drawdown_pct,
  };
}

function mapBacktestDistributionRow(row: StrategyBacktestDistributionRowApi): StrategyBacktestDistributionRow {
  return {
    period: row.period,
    strategyReturnPct: row.strategy_return_pct,
    benchmarkReturnPct: row.benchmark_return_pct,
    excessReturnPct: row.excess_return_pct,
  };
}

function mapBacktestRotationRow(row: StrategyBacktestRotationRowApi): StrategyBacktestRotationRow {
  return {
    rebalanceDate: row.rebalance_date,
    weekday: row.weekday,
    holdings: row.holdings,
    holdingCount: row.holding_count,
    turnoverPct: row.turnover_pct,
    periodReturnPct: row.period_return_pct,
    cumulativeReturnPct: row.cumulative_return_pct,
    navWan: row.nav_wan,
  };
}

export async function listStrategyTemplates(params?: {
  keyword?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}): Promise<{ items: StrategyTemplate[]; total: number; page: number; pageSize: number }> {
  const payload = await requestJson<{
    items: StrategyTemplateApi[];
    total: number;
    page: number;
    page_size: number;
  }>(
    buildUrl("/api/v1/cb-quant/strategy/templates", {
      keyword: params?.keyword ?? "",
      status: params?.status ?? "all",
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 50,
    }),
    undefined,
    { timeoutMs: 60_000 },
  );

  return {
    items: payload.items.map(mapTemplate),
    total: payload.total,
    page: payload.page,
    pageSize: payload.page_size,
  };
}

export async function getHistoryDataSummary(): Promise<HistoryDataSummary> {
  const payload = await requestJson<HistoryDataSummaryApi>(
    buildUrl("/api/v1/cb-quant/strategy/history-summary"),
  );
  return mapHistorySummary(payload);
}

export async function triggerHistorySync(): Promise<{ ok: boolean; message: string; upserted: number }> {
  const payload = await requestJson<{
    ok: boolean;
    message: string;
    upserted: number;
  }>(buildUrl("/api/v1/cb-quant/strategy/history-sync"), {
    method: "POST",
    body: JSON.stringify({}),
  });
  return payload;
}

export async function getHistorySyncStatus(): Promise<HistorySyncStatus> {
  const payload = await requestJson<HistorySyncStatusApi>(
    buildUrl("/api/v1/cb-quant/strategy/history-sync/status"),
  );
  return mapHistorySyncStatus(payload);
}

export async function triggerTushareHistorySync(payload?: {
  startDate?: string;
  endDate?: string;
  maxTradeDays?: number;
  incremental?: boolean;
}): Promise<TushareSyncResult> {
  const response = await requestJson<{
    ok: boolean;
    mode: string;
    source: string;
    start_date: string;
    end_date: string;
    trade_days: number;
    cb_daily_rows: number;
    stock_daily_rows: number;
    event_rows: number;
    factor_rows: number;
    snapshot_rows: number;
    message: string;
  }>(buildUrl("/api/v1/cb-quant/strategy/history-sync/tushare"), {
    method: "POST",
    body: JSON.stringify({
      start_date: payload?.startDate,
      end_date: payload?.endDate,
      max_trade_days: payload?.maxTradeDays ?? 1500,
      incremental: payload?.incremental ?? false,
    }),
  }, { timeoutMs: 10 * 60_000 });
  return {
    ok: response.ok,
    mode: response.mode,
    source: response.source,
    startDate: response.start_date,
    endDate: response.end_date,
    tradeDays: response.trade_days,
    cbDailyRows: response.cb_daily_rows,
    stockDailyRows: response.stock_daily_rows,
    eventRows: response.event_rows,
    factorRows: response.factor_rows,
    snapshotRows: response.snapshot_rows,
    message: response.message,
  };
}

export async function getTushareHistorySyncStatus(): Promise<TushareSyncStatus> {
  const payload = await requestJson<TushareSyncStatusApi>(
    buildUrl("/api/v1/cb-quant/strategy/history-sync/tushare/status"),
  );
  return mapTushareSyncStatus(payload);
}

export async function getTushareHistorySummary(): Promise<TushareDataSummary> {
  const payload = await requestJson<TushareDataSummaryApi>(
    buildUrl("/api/v1/cb-quant/strategy/history-sync/tushare/summary"),
  );
  return mapTushareSummary(payload);
}

export async function listFactorCatalog(params?: {
  category?: string;
  keyword?: string;
  enabledOnly?: boolean;
  templateOnly?: boolean;
}): Promise<{ items: FactorCatalogCategory[]; totalCategories: number; totalFactors: number }> {
  const payload = await requestJson<{
    items: FactorCatalogCategoryApi[];
    total_categories: number;
    total_factors: number;
  }>(
    buildUrl("/api/v1/cb-quant/catalog/factors", {
      category: params?.category ?? "all",
      keyword: params?.keyword ?? "",
      enabled_only: params?.enabledOnly ?? false,
      template_only: params?.templateOnly ?? false,
    }),
  );

  return {
    items: payload.items.map((category) => ({
      categoryName: category.category_name,
      categoryKey: category.category_key,
      factors: category.factors.map(mapFactorCatalogFactor),
    })),
    totalCategories: payload.total_categories,
    totalFactors: payload.total_factors,
  };
}

export async function listFunctionCatalog(params?: {
  category?: string;
  keyword?: string;
}): Promise<{ items: FunctionCatalogCategory[]; totalCategories: number; totalFunctions: number }> {
  const payload = await requestJson<{
    items: FunctionCatalogCategoryApi[];
    total_categories: number;
    total_functions: number;
  }>(
    buildUrl("/api/v1/cb-quant/catalog/functions", {
      category: params?.category ?? "all",
      keyword: params?.keyword ?? "",
    }),
  );

  return {
    items: payload.items.map((category) => ({
      categoryName: category.category_name,
      categoryKey: category.category_key,
      functions: category.functions.map((fn) => ({
        name: fn.name,
        formular: fn.formular,
        description: fn.description,
        parameterSize: fn.parameter_size,
        parameters: fn.parameters.map(mapFunctionParameter),
      })),
    })),
    totalCategories: payload.total_categories,
    totalFunctions: payload.total_functions,
  };
}

export async function createStrategyTemplate(payload: { name: string; owner?: string }): Promise<StrategyTemplate> {
  const response = await requestJson<StrategyTemplateApi>(
    buildUrl("/api/v1/cb-quant/strategy/templates"),
    {
      method: "POST",
      body: JSON.stringify({ name: payload.name, owner: payload.owner ?? "quant_new" }),
    },
  );
  return mapTemplate(response);
}

export async function expandStrategyFactorCombos(
  templateId: string,
  payload?: {
    minFactorCount?: number;
    maxFactorCount?: number;
    maxStrategies?: number;
  },
): Promise<{
  sourceTemplateId: string;
  sourceTemplateName: string;
  minFactorCount: number;
  maxFactorCount: number;
  totalSubsets: number;
  createdCount: number;
  truncated: boolean;
  message: string;
}> {
  const response = await requestJson<{
    source_template_id: string;
    source_template_name: string;
    min_factor_count: number;
    max_factor_count: number;
    total_subsets: number;
    created_count: number;
    truncated: boolean;
    message: string;
  }>(buildUrl(`/api/v1/cb-quant/strategy/templates/${templateId}/expand-factor-combos`), {
    method: "POST",
    body: JSON.stringify({
      min_factor_count: payload?.minFactorCount ?? 1,
      max_factor_count: payload?.maxFactorCount,
      max_strategies: payload?.maxStrategies,
    }),
  });

  return {
    sourceTemplateId: response.source_template_id,
    sourceTemplateName: response.source_template_name,
    minFactorCount: response.min_factor_count,
    maxFactorCount: response.max_factor_count,
    totalSubsets: response.total_subsets,
    createdCount: response.created_count,
    truncated: response.truncated,
    message: response.message,
  };
}

export async function updateStrategyTemplate(
  templateId: string,
  payload: {
    name?: string;
    status?: StrategyTemplateStatus;
    rebalance?: string;
    riskPreset?: string;
    owner?: string;
  },
): Promise<StrategyTemplate> {
  const response = await requestJson<StrategyTemplateApi>(
    buildUrl(`/api/v1/cb-quant/strategy/templates/${templateId}`),
    {
      method: "PUT",
      body: JSON.stringify({
        name: payload.name,
        status: payload.status,
        rebalance: payload.rebalance,
        risk_preset: payload.riskPreset,
        owner: payload.owner,
      }),
    },
  );
  return mapTemplate(response);
}

export async function deleteStrategyTemplate(templateId: string): Promise<void> {
  await requestJson<{ ok: boolean; message: string }>(
    buildUrl(`/api/v1/cb-quant/strategy/templates/${templateId}`),
    { method: "DELETE" },
  );
}

export async function batchEnableStrategyTemplates(
  templateIds: string[],
  status: StrategyTemplateStatus = "active",
): Promise<StrategyTemplateBatchResult> {
  const payload = await requestJson<{
    ok: boolean;
    affected: number;
    missing_ids: string[];
    message: string;
  }>(buildUrl("/api/v1/cb-quant/strategy/templates/batch/enable"), {
    method: "POST",
    body: JSON.stringify({
      template_ids: templateIds,
      status,
    }),
  });
  return {
    ok: payload.ok,
    affected: payload.affected,
    missingIds: payload.missing_ids,
    message: payload.message,
  };
}

export async function batchDeleteStrategyTemplates(
  templateIds: string[],
): Promise<StrategyTemplateBatchResult> {
  const payload = await requestJson<{
    ok: boolean;
    affected: number;
    missing_ids: string[];
    message: string;
  }>(buildUrl("/api/v1/cb-quant/strategy/templates/batch/delete"), {
    method: "POST",
    body: JSON.stringify({
      template_ids: templateIds,
    }),
  });
  return {
    ok: payload.ok,
    affected: payload.affected,
    missingIds: payload.missing_ids,
    message: payload.message,
  };
}

export async function getStrategyTemplateDetail(templateId: string): Promise<StrategyTemplateDetail> {
  const payload = await requestJson<StrategyTemplateDetailApi>(
    buildUrl(`/api/v1/cb-quant/strategy/templates/${templateId}`),
  );
  return {
    template: mapTemplate(payload.template),
    config: mapTemplateConfig(payload.config),
  };
}

export async function updateStrategyTemplateConfig(
  templateId: string,
  payload: { factorKeys: string[]; expressionDraft: string; parameterSpace?: StrategyParamSpaceRow[] },
): Promise<StrategyTemplateConfig> {
  const response = await requestJson<StrategyTemplateConfigApi>(
    buildUrl(`/api/v1/cb-quant/strategy/templates/${templateId}/config`),
    {
      method: "PUT",
      body: JSON.stringify({
        factor_keys: payload.factorKeys,
        expression_draft: payload.expressionDraft,
        parameter_space: (payload.parameterSpace ?? []).map((item) => ({
          factor_key: item.factorKey,
          value_type: item.valueType,
          enabled: item.enabled,
          min_value: item.minValue,
          max_value: item.maxValue,
          step: item.step,
          enum_values: item.enumValues,
        })),
      }),
    },
  );
  return mapTemplateConfig(response);
}

export async function generateStrategyCandidates(
  templateId: string,
  payload?: { windows?: WindowName[]; rowsPerWindow?: number },
): Promise<CandidateGenerateResult> {
  const response = await requestJson<{
    run_id: string;
    template_id: string;
    template_name: string;
    created_count: number;
    est_combos: number;
    windows: WindowName[];
    items: CandidateRowApi[];
    message: string;
  }>(
    buildUrl(`/api/v1/cb-quant/strategy/templates/${templateId}/generate-candidates`),
    {
      method: "POST",
      body: JSON.stringify({
        windows: payload?.windows ?? ["full", "3y", "1y"],
        rows_per_window: payload?.rowsPerWindow ?? 5,
      }),
    },
  );

  return {
    runId: response.run_id,
    templateId: response.template_id,
    templateName: response.template_name,
    createdCount: response.created_count,
    estCombos: response.est_combos,
    windows: response.windows,
    items: response.items.map(mapCandidate),
    message: response.message,
  };
}

export async function listStrategyCandidates(params?: {
  keyword?: string;
  window?: string;
  templateId?: string;
}): Promise<{ items: CandidateRow[]; total: number }> {
  const payload = await requestJson<{
    items: CandidateRowApi[];
    total: number;
  }>(
    buildUrl("/api/v1/cb-quant/strategy/candidates", {
      keyword: params?.keyword ?? "",
      window: params?.window ?? "all",
      template_id: params?.templateId ?? "all",
    }),
  );

  return {
    items: payload.items.map(mapCandidate),
    total: payload.total,
  };
}

export async function createStrategyOptimizeTask(payload: {
  templateId: string;
  windows: WindowName[];
  startDate?: string;
  endDate?: string;
  topN?: number;
  maxCombinations?: number;
  currentTopN?: number;
  taskConfig?: BacktestTaskConfig;
}): Promise<{ task: StrategyOptimizeTask; message: string }> {
  const taskConfig = payload.taskConfig ?? {
    initialCapitalWan: 100,
    benchmarkName: "转债等权",
    rebalanceIntervalType: "trade_day",
    rebalanceIntervalValue: 1,
    maxPositionPct: 20,
    maxHoldCount: 12,
    excludeRedeemDaysBelow: null,
    takeProfitPct: null,
    stopLossPct: null,
  };
  const response = await requestJson<{
    task: StrategyOptimizeTaskApi;
    message: string;
  }>(buildUrl("/api/v1/cb-quant/strategy/optimize-tasks"), {
    method: "POST",
    body: JSON.stringify({
      template_id: payload.templateId,
      windows: payload.windows,
      start_date: payload.startDate,
      end_date: payload.endDate,
      top_n: payload.topN ?? 20,
      max_combinations: payload.maxCombinations,
      current_top_n: payload.currentTopN ?? 20,
      task_config: {
        initial_capital_wan: taskConfig.initialCapitalWan,
        benchmark_name: taskConfig.benchmarkName,
        rebalance_interval_type: taskConfig.rebalanceIntervalType,
        rebalance_interval_value: taskConfig.rebalanceIntervalValue,
        max_position_pct: taskConfig.maxPositionPct,
        max_hold_count: taskConfig.maxHoldCount,
        exclude_redeem_days_below: taskConfig.excludeRedeemDaysBelow,
        take_profit_pct: taskConfig.takeProfitPct,
        stop_loss_pct: taskConfig.stopLossPct,
      },
    }),
  });
  return {
    task: mapOptimizeTask(response.task),
    message: response.message,
  };
}

export async function listStrategyOptimizeTasks(params?: {
  templateId?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}): Promise<{ items: StrategyOptimizeTask[]; total: number; page: number; pageSize: number }> {
  const payload = await requestJson<{
    items: StrategyOptimizeTaskApi[];
    total: number;
    page: number;
    page_size: number;
  }>(
    buildUrl("/api/v1/cb-quant/strategy/optimize-tasks", {
      template_id: params?.templateId ?? "all",
      status: params?.status ?? "all",
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 20,
    }),
  );
  return {
    items: payload.items.map(mapOptimizeTask),
    total: payload.total,
    page: payload.page,
    pageSize: payload.page_size,
  };
}

export async function getStrategyOptimizeTaskDetail(taskId: string): Promise<StrategyOptimizeTaskDetail> {
  const payload = await requestJson<{
    task: StrategyOptimizeTaskApi;
    top_strategies: StrategyOptimizeResultRowApi[];
    top_bonds: StrategyTopBondRowApi[];
  }>(buildUrl(`/api/v1/cb-quant/strategy/optimize-tasks/${taskId}`));
  return {
    task: mapOptimizeTask(payload.task),
    topStrategies: payload.top_strategies.map(mapOptimizeResultRow),
    topBonds: payload.top_bonds.map(mapTopBondRow),
  };
}

export async function getStrategyOptimizeSummary(params?: {
  topN?: number;
  currentTopN?: number;
}): Promise<StrategyOptimizeSummary> {
  const payload = await requestJson<{
    top_strategies: StrategyOptimizeResultRowApi[];
    top_bonds: StrategyTopBondRowApi[];
    finished_task_count: number;
    total_result_count: number;
    message: string;
  }>(
    buildUrl("/api/v1/cb-quant/strategy/optimize-summary", {
      top_n: params?.topN ?? 20,
      current_top_n: params?.currentTopN ?? 20,
    }),
    undefined,
    { timeoutMs: 60_000 },
  );
  return {
    topStrategies: payload.top_strategies.map(mapOptimizeResultRow),
    topBonds: payload.top_bonds.map(mapTopBondRow),
    finishedTaskCount: payload.finished_task_count,
    totalResultCount: payload.total_result_count,
    message: payload.message,
  };
}

export async function getStrategyOptimizeTaskAnalysis(
  taskId: string,
  params?: { comboId?: string; initialCapitalWan?: number },
): Promise<StrategyOptimizeTaskAnalysis> {
  const payload = await requestJson<StrategyOptimizeTaskAnalysisApi>(
    buildUrl(`/api/v1/cb-quant/strategy/optimize-tasks/${taskId}/analysis`, {
      combo_id: params?.comboId,
      initial_capital_wan: params?.initialCapitalWan ?? 100,
    }),
    undefined,
    { timeoutMs: 60_000 },
  );
  return {
    taskId: payload.task_id,
    templateId: payload.template_id,
    templateName: payload.template_name,
    comboId: payload.combo_id,
    benchmarkName: payload.benchmark_name,
    window: payload.window,
    metricRows: payload.metric_rows.map(mapBacktestMetricRow),
    curve: payload.curve.map(mapBacktestCurvePoint),
    yearlyDistribution: payload.yearly_distribution.map(mapBacktestDistributionRow),
    monthlyDistribution: payload.monthly_distribution.map(mapBacktestDistributionRow),
    weeklyDistribution: payload.weekly_distribution.map(mapBacktestDistributionRow),
    rotations: payload.rotations.map(mapBacktestRotationRow),
    message: payload.message,
  };
}

export async function getStrategyOptimizeTaskAiInsight(
  taskId: string,
  params?: { comboId?: string; initialCapitalWan?: number },
): Promise<StrategyOptimizeTaskAiInsight> {
  const payload = await requestJson<StrategyOptimizeTaskAiInsightApi>(
    buildUrl(`/api/v1/cb-quant/strategy/optimize-tasks/${taskId}/analysis/ai`),
    {
      method: "POST",
      body: JSON.stringify({
        combo_id: params?.comboId,
        initial_capital_wan: params?.initialCapitalWan ?? 100,
      }),
    },
    { timeoutMs: 120_000 },
  );
  return {
    ok: payload.ok,
    enabled: payload.enabled,
    provider: payload.provider,
    model: payload.model,
    taskId: payload.task_id,
    comboId: payload.combo_id,
    contextMarkdown: payload.context_markdown,
    promptMarkdown: payload.prompt_markdown,
    analysisMarkdown: payload.analysis_markdown,
    executiveSummary: payload.executive_summary,
    returnDrivers: payload.return_drivers,
    riskExposures: payload.risk_exposures,
    parameterInterpretation: payload.parameter_interpretation,
    nextSteps: payload.next_steps,
    message: payload.message,
    generatedAt: payload.generated_at,
    cached: payload.cached,
  };
}

export async function compareStrategyOptimizeTaskAiInsight(
  taskId: string,
  payload: { comboIds: string[]; initialCapitalWan?: number },
): Promise<StrategyOptimizeTaskAiCompare> {
  const response = await requestJson<StrategyOptimizeTaskAiCompareApi>(
    buildUrl(`/api/v1/cb-quant/strategy/optimize-tasks/${taskId}/analysis/ai-compare`),
    {
      method: "POST",
      body: JSON.stringify({
        combo_ids: payload.comboIds,
        initial_capital_wan: payload.initialCapitalWan ?? 100,
      }),
    },
    { timeoutMs: 120_000 },
  );
  return {
    ok: response.ok,
    enabled: response.enabled,
    provider: response.provider,
    model: response.model,
    taskId: response.task_id,
    comboIds: response.combo_ids,
    contextMarkdown: response.context_markdown,
    promptMarkdown: response.prompt_markdown,
    analysisMarkdown: response.analysis_markdown,
    executiveSummary: response.executive_summary,
    winnerComboId: response.winner_combo_id,
    winnerReason: response.winner_reason,
    comboAStrengths: response.combo_a_strengths,
    comboARisks: response.combo_a_risks,
    comboBStrengths: response.combo_b_strengths,
    comboBRisks: response.combo_b_risks,
    whatToVerifyNext: response.what_to_verify_next,
    message: response.message,
    generatedAt: response.generated_at,
    cached: response.cached,
  };
}

export async function getBacktestStats(): Promise<BacktestStats> {
  const payload = await requestJson<{
    running_jobs: number;
    queued_jobs: number;
    finished_jobs: number;
    failed_jobs: number;
    cancelled_jobs?: number;
    rule_pack_count: number;
    top_cagr: number;
  }>(buildUrl("/api/v1/cb-quant/backtest/stats"));

  return {
    runningJobs: payload.running_jobs,
    queuedJobs: payload.queued_jobs,
    finishedJobs: payload.finished_jobs,
    failedJobs: payload.failed_jobs,
    cancelledJobs: payload.cancelled_jobs ?? 0,
    rulePackCount: payload.rule_pack_count,
    topCagr: payload.top_cagr,
  };
}

export async function listBacktestJobs(params?: {
  keyword?: string;
  status?: string;
  businessDate?: string;
  businessDateFrom?: string;
  businessDateTo?: string;
  page?: number;
  pageSize?: number;
}): Promise<{ items: BacktestJob[]; total: number; page: number; pageSize: number }> {
  const payload = await requestJson<{
    items: BacktestJobApi[];
    total: number;
    page: number;
    page_size: number;
  }>(
    buildUrl("/api/v1/cb-quant/backtest/jobs", {
      keyword: params?.keyword ?? "",
      status: params?.status ?? "all",
      business_date: params?.businessDate ?? "",
      business_date_from: params?.businessDateFrom ?? "",
      business_date_to: params?.businessDateTo ?? "",
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 20,
    }),
  );

  return {
    items: payload.items.map(mapBacktestJob),
    total: payload.total,
    page: payload.page,
    pageSize: payload.page_size,
  };
}

export async function queueBacktestJobs(payload: BacktestQueueRequest): Promise<BacktestQueueResult> {
  const response = await requestJson<{
    batch_id: string;
    combo_id: string;
    rule_pack_id: string;
    source_mode: "inherit" | "candidate" | "custom";
    created_count: number;
    windows: WindowName[];
    jobs: BacktestJobApi[];
    message: string;
  }>(buildUrl("/api/v1/cb-quant/backtest/jobs"), {
    method: "POST",
    body: JSON.stringify({
      combo_id: payload.comboId,
      template: payload.template,
      source_mode: payload.sourceMode,
      rule_pack_id: payload.rulePackId,
      windows: payload.windows,
      business_date: payload.businessDate,
      start_date: payload.startDate,
      end_date: payload.endDate,
      capital_wan: payload.capitalWan,
      benchmark: payload.benchmark,
      est_strategies: payload.estStrategies,
    }),
  });

  return {
    batchId: response.batch_id,
    comboId: response.combo_id,
    rulePackId: response.rule_pack_id,
    sourceMode: response.source_mode,
    createdCount: response.created_count,
    windows: response.windows,
    jobs: response.jobs.map(mapBacktestJob),
    message: response.message,
  };
}

export async function cancelBacktestJob(jobId: string): Promise<{ ok: boolean; message: string }> {
  return requestJson<{ ok: boolean; message: string }>(
    buildUrl(`/api/v1/cb-quant/backtest/jobs/${encodeURIComponent(jobId)}/cancel`),
    {
      method: "POST",
    },
  );
}

export async function listBacktestLeaderboard(params?: {
  keyword?: string;
  window?: string;
  page?: number;
  pageSize?: number;
}): Promise<{ items: BacktestLeaderboardRow[]; total: number; page: number; pageSize: number }> {
  const payload = await requestJson<{
    items: BacktestLeaderboardApi[];
    total: number;
    page: number;
    page_size: number;
  }>(
    buildUrl("/api/v1/cb-quant/backtest/leaderboard", {
      keyword: params?.keyword ?? "",
      window: params?.window ?? "all",
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 20,
    }),
  );

  return {
    items: payload.items.map(mapBacktestLeaderboardRow),
    total: payload.total,
    page: payload.page,
    pageSize: payload.page_size,
  };
}

export async function listBacktestCompare(params?: {
  keyword?: string;
  category?: string;
}): Promise<{ items: BacktestCompareRow[]; total: number }> {
  const payload = await requestJson<{
    items: BacktestCompareApi[];
    total: number;
  }>(
    buildUrl("/api/v1/cb-quant/backtest/compare", {
      keyword: params?.keyword ?? "",
      category: params?.category ?? "all",
    }),
  );

  return {
    items: payload.items.map(mapBacktestCompareRow),
    total: payload.total,
  };
}
