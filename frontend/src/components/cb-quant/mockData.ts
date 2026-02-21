export type StrategyTemplateStatus = "active" | "draft" | "archived";
export type JobStatus = "queued" | "running" | "finished" | "failed";
export type OrderStatus = "new" | "part_filled" | "filled" | "canceled" | "rejected";
export type TicketStatus = "open" | "in_progress" | "closed";
export type RolloutResult = "running" | "success" | "rollback";

export type StrategyTemplateRow = {
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

export type StrategyParameterRow = {
  key: string;
  group: "filters" | "ranking" | "portfolio" | "rebalance" | "risk";
  type: "int" | "float" | "enum" | "bool";
  range: string;
  step: string;
  defaultValue: string;
  enabled: boolean;
};

export type StrategyCandidateRow = {
  rank: number;
  template: string;
  comboId: string;
  estCombos: number;
  passRate: number;
  robustScore: number;
  window: "full" | "3y" | "1y";
};

export type BacktestJobRow = {
  jobId: string;
  strategyId: string;
  comboId: string;
  template: string;
  window: string;
  status: JobStatus;
  progress: number;
  startedAt: string;
  eta: string;
  worker: string;
};

export type BacktestLeaderboardRow = {
  rank: number;
  strategyId: string;
  comboId: string;
  template: string;
  cagr: number;
  mdd: number;
  calmar: number;
  winRate: number;
  turnover: number;
  recent1y: number;
  robustScore: number;
  window: "full" | "3y" | "1y";
};

export type BacktestCompareRow = {
  metric: string;
  category: "return" | "risk" | "trade";
  baseline: number;
  candidateA: number;
  candidateB: number;
  candidateC: number;
};

export type RebalancePlanRow = {
  symbol: string;
  name: string;
  action: "buy" | "sell" | "hold";
  currentWeight: number;
  targetWeight: number;
  diffWeight: number;
  estAmountWan: number;
  priority: "high" | "medium" | "low";
};

export type OrderBlotterRow = {
  orderId: string;
  symbol: string;
  side: "buy" | "sell";
  price: number;
  volume: number;
  filled: number;
  status: OrderStatus;
  slippageBp: number;
  submitTime: string;
};

export type ExecutionLogRow = {
  time: string;
  level: "info" | "warn" | "error";
  source: string;
  message: string;
};

export type AttributionRow = {
  strategy: string;
  period: "weekly" | "monthly";
  pnlWan: number;
  stockContribution: number;
  bondContribution: number;
  timingContribution: number;
  costContribution: number;
};

export type DeviationRow = {
  orderId: string;
  symbol: string;
  expectedPrice: number;
  filledPrice: number;
  slippageBp: number;
  reason: "liquidity" | "delay" | "rejected" | "manual";
  resolved: boolean;
  time: string;
};

export type TicketRow = {
  ticketId: string;
  type: "data" | "execution" | "risk";
  severity: "high" | "medium" | "low";
  status: TicketStatus;
  owner: string;
  summary: string;
  updatedAt: string;
};

export type TriggerRow = {
  rule: string;
  status: "armed" | "fired" | "muted";
  threshold: string;
  currentValue: string;
  hitCount: number;
  lastTriggered: string;
  action: string;
};

export type StrategyPoolRow = {
  strategy: string;
  stage: "prod" | "watch" | "out";
  robustScore: number;
  cagr: number;
  mdd: number;
  recent3m: number;
  nextAction: string;
  owner: string;
};

export type RolloutRow = {
  version: string;
  from: string;
  to: string;
  result: RolloutResult;
  startAt: string;
  endAt: string;
  operator: string;
};

export type PipelineRow = {
  stage: string;
  status: "ready" | "running" | "blocked";
  updatedAt: string;
  owner: string;
  note: string;
};

export type AlertRow = {
  id: string;
  level: "high" | "medium" | "low";
  module: string;
  message: string;
  impact: string;
  action: string;
  updatedAt: string;
};

export type ActionRow = {
  time: string;
  operator: string;
  action: string;
  target: string;
  result: "success" | "running" | "failed";
};

export const strategyTemplates: StrategyTemplateRow[] = [
  { id: "TPL-001", name: "双低稳健A", version: "v1.3.2", status: "active", factorCount: 18, rebalance: "weekly", riskPreset: "balanced", comboSize: 86400, owner: "quant_a", updatedAt: "2026-02-20 21:10" },
  { id: "TPL-002", name: "低溢价动量", version: "v0.9.5", status: "draft", factorCount: 16, rebalance: "daily", riskPreset: "aggressive", comboSize: 122880, owner: "quant_b", updatedAt: "2026-02-20 18:40" },
  { id: "TPL-003", name: "双低+评级", version: "v2.0.1", status: "active", factorCount: 20, rebalance: "weekly", riskPreset: "balanced", comboSize: 98304, owner: "quant_c", updatedAt: "2026-02-19 14:08" },
  { id: "TPL-004", name: "价量过滤", version: "v1.1.7", status: "archived", factorCount: 12, rebalance: "daily", riskPreset: "conservative", comboSize: 20480, owner: "quant_a", updatedAt: "2026-02-17 11:23" },
  { id: "TPL-005", name: "低价低溢价轮动", version: "v1.6.0", status: "active", factorCount: 22, rebalance: "weekly", riskPreset: "balanced", comboSize: 145920, owner: "quant_d", updatedAt: "2026-02-20 20:35" },
  { id: "TPL-006", name: "流动性优先", version: "v0.8.3", status: "draft", factorCount: 14, rebalance: "weekly", riskPreset: "conservative", comboSize: 57600, owner: "quant_e", updatedAt: "2026-02-18 17:40" },
  { id: "TPL-007", name: "双低回撤保护", version: "v1.0.4", status: "active", factorCount: 19, rebalance: "daily", riskPreset: "balanced", comboSize: 110592, owner: "quant_b", updatedAt: "2026-02-21 08:52" },
  { id: "TPL-008", name: "高评级稳态", version: "v1.2.0", status: "archived", factorCount: 11, rebalance: "weekly", riskPreset: "conservative", comboSize: 30720, owner: "quant_c", updatedAt: "2026-02-14 10:20" },
  { id: "TPL-009", name: "高波动降权", version: "v0.7.9", status: "draft", factorCount: 15, rebalance: "daily", riskPreset: "balanced", comboSize: 69120, owner: "quant_d", updatedAt: "2026-02-20 09:18" },
  { id: "TPL-010", name: "小盘债容量版", version: "v1.0.0", status: "active", factorCount: 17, rebalance: "weekly", riskPreset: "balanced", comboSize: 73728, owner: "quant_f", updatedAt: "2026-02-20 23:05" },
];

export const strategyParameters: StrategyParameterRow[] = [
  { key: "price_max", group: "filters", type: "float", range: "105~150", step: "1", defaultValue: "135", enabled: true },
  { key: "premium_max", group: "filters", type: "float", range: "5~35", step: "0.5", defaultValue: "22", enabled: true },
  { key: "rating_min", group: "filters", type: "enum", range: "AA/AA+/AAA", step: "-", defaultValue: "AA", enabled: true },
  { key: "volume_min_wan", group: "filters", type: "int", range: "2000~30000", step: "500", defaultValue: "6000", enabled: true },
  { key: "dblow_weight", group: "ranking", type: "float", range: "0.2~0.8", step: "0.05", defaultValue: "0.6", enabled: true },
  { key: "premium_weight", group: "ranking", type: "float", range: "0.1~0.7", step: "0.05", defaultValue: "0.3", enabled: true },
  { key: "momentum_weight", group: "ranking", type: "float", range: "0~0.4", step: "0.05", defaultValue: "0.1", enabled: false },
  { key: "top_k", group: "portfolio", type: "int", range: "5~30", step: "1", defaultValue: "12", enabled: true },
  { key: "max_weight_single", group: "portfolio", type: "float", range: "0.03~0.15", step: "0.01", defaultValue: "0.08", enabled: true },
  { key: "weight_mode", group: "portfolio", type: "enum", range: "equal/score/vol", step: "-", defaultValue: "equal", enabled: true },
  { key: "rebalance_freq", group: "rebalance", type: "enum", range: "daily/weekly", step: "-", defaultValue: "weekly", enabled: true },
  { key: "turnover_limit", group: "rebalance", type: "float", range: "0.1~0.8", step: "0.05", defaultValue: "0.35", enabled: true },
  { key: "mdd_guard", group: "risk", type: "float", range: "0.08~0.35", step: "0.01", defaultValue: "0.18", enabled: true },
  { key: "daily_loss_guard", group: "risk", type: "float", range: "0.01~0.08", step: "0.005", defaultValue: "0.03", enabled: true },
  { key: "suspend_on_data_gap", group: "risk", type: "bool", range: "true/false", step: "-", defaultValue: "true", enabled: true },
];

export const strategyCandidates: StrategyCandidateRow[] = [
  { rank: 1, template: "双低稳健A", comboId: "CMB-102883", estCombos: 86400, passRate: 9.3, robustScore: 91.2, window: "full" },
  { rank: 2, template: "双低+评级", comboId: "CMB-202551", estCombos: 98304, passRate: 8.7, robustScore: 89.6, window: "3y" },
  { rank: 3, template: "低价低溢价轮动", comboId: "CMB-140301", estCombos: 145920, passRate: 7.9, robustScore: 88.4, window: "full" },
  { rank: 4, template: "双低回撤保护", comboId: "CMB-883102", estCombos: 110592, passRate: 8.2, robustScore: 87.8, window: "1y" },
  { rank: 5, template: "小盘债容量版", comboId: "CMB-553210", estCombos: 73728, passRate: 9.1, robustScore: 86.7, window: "3y" },
  { rank: 6, template: "流动性优先", comboId: "CMB-033421", estCombos: 57600, passRate: 10.8, robustScore: 85.4, window: "1y" },
  { rank: 7, template: "低溢价动量", comboId: "CMB-932811", estCombos: 122880, passRate: 6.6, robustScore: 83.9, window: "full" },
  { rank: 8, template: "高波动降权", comboId: "CMB-502102", estCombos: 69120, passRate: 7.1, robustScore: 81.3, window: "1y" },
];

export const backtestJobs: BacktestJobRow[] = [
  { jobId: "BT-20260221-001", strategyId: "STR-001", comboId: "CMB-102883", template: "双低稳健A", window: "2018-2025", status: "running", progress: 62, startedAt: "09:31:05", eta: "7m", worker: "wk-01" },
  { jobId: "BT-20260221-002", strategyId: "STR-002", comboId: "CMB-202551", template: "双低+评级", window: "近3年", status: "queued", progress: 0, startedAt: "09:33:15", eta: "--", worker: "wk-02" },
  { jobId: "BT-20260221-003", strategyId: "STR-003", comboId: "CMB-140301", template: "低价低溢价轮动", window: "近1年", status: "finished", progress: 100, startedAt: "09:15:22", eta: "done", worker: "wk-03" },
  { jobId: "BT-20260221-004", strategyId: "STR-004", comboId: "CMB-033421", template: "流动性优先", window: "2018-2025", status: "failed", progress: 44, startedAt: "08:56:40", eta: "stopped", worker: "wk-04" },
  { jobId: "BT-20260221-005", strategyId: "STR-005", comboId: "CMB-883102", template: "双低回撤保护", window: "近3年", status: "running", progress: 81, startedAt: "09:02:11", eta: "3m", worker: "wk-05" },
  { jobId: "BT-20260221-006", strategyId: "STR-006", comboId: "CMB-553210", template: "小盘债容量版", window: "近1年", status: "finished", progress: 100, startedAt: "08:21:53", eta: "done", worker: "wk-01" },
  { jobId: "BT-20260221-007", strategyId: "STR-007", comboId: "CMB-932811", template: "低溢价动量", window: "2018-2025", status: "queued", progress: 0, startedAt: "09:40:14", eta: "--", worker: "wk-03" },
];

export const backtestLeaderboard: BacktestLeaderboardRow[] = [
  { rank: 1, strategyId: "STR-001", comboId: "CMB-102883", template: "双低稳健A", cagr: 0.342, mdd: 0.192, calmar: 1.78, winRate: 62.4, turnover: 0.29, recent1y: 0.271, robustScore: 92.2, window: "full" },
  { rank: 2, strategyId: "STR-002", comboId: "CMB-202551", template: "双低+评级", cagr: 0.331, mdd: 0.185, calmar: 1.79, winRate: 61.2, turnover: 0.27, recent1y: 0.259, robustScore: 90.9, window: "3y" },
  { rank: 3, strategyId: "STR-005", comboId: "CMB-883102", template: "双低回撤保护", cagr: 0.316, mdd: 0.169, calmar: 1.87, winRate: 59.8, turnover: 0.25, recent1y: 0.246, robustScore: 89.8, window: "1y" },
  { rank: 4, strategyId: "STR-003", comboId: "CMB-140301", template: "低价低溢价轮动", cagr: 0.354, mdd: 0.222, calmar: 1.59, winRate: 60.1, turnover: 0.33, recent1y: 0.221, robustScore: 86.4, window: "full" },
  { rank: 5, strategyId: "STR-004", comboId: "CMB-033421", template: "流动性优先", cagr: 0.288, mdd: 0.141, calmar: 2.04, winRate: 57.6, turnover: 0.21, recent1y: 0.208, robustScore: 85.2, window: "3y" },
  { rank: 6, strategyId: "STR-006", comboId: "CMB-553210", template: "小盘债容量版", cagr: 0.301, mdd: 0.201, calmar: 1.49, winRate: 58.8, turnover: 0.26, recent1y: 0.193, robustScore: 82.9, window: "1y" },
  { rank: 7, strategyId: "STR-007", comboId: "CMB-932811", template: "低溢价动量", cagr: 0.278, mdd: 0.236, calmar: 1.18, winRate: 54.1, turnover: 0.38, recent1y: 0.161, robustScore: 77.5, window: "full" },
];

export const backtestCompareRows: BacktestCompareRow[] = [
  { metric: "CAGR", category: "return", baseline: 0.214, candidateA: 0.342, candidateB: 0.331, candidateC: 0.316 },
  { metric: "近1年收益", category: "return", baseline: 0.112, candidateA: 0.271, candidateB: 0.259, candidateC: 0.246 },
  { metric: "最大回撤", category: "risk", baseline: 0.286, candidateA: 0.192, candidateB: 0.185, candidateC: 0.169 },
  { metric: "Calmar", category: "risk", baseline: 0.75, candidateA: 1.78, candidateB: 1.79, candidateC: 1.87 },
  { metric: "年化换手", category: "trade", baseline: 0.44, candidateA: 0.29, candidateB: 0.27, candidateC: 0.25 },
  { metric: "胜率", category: "trade", baseline: 0.49, candidateA: 0.624, candidateB: 0.612, candidateC: 0.598 },
];

export const rebalancePlanRows: RebalancePlanRow[] = [
  { symbol: "113063", name: "赛轮转债", action: "buy", currentWeight: 0.0, targetWeight: 0.075, diffWeight: 0.075, estAmountWan: 82.6, priority: "high" },
  { symbol: "110085", name: "通22转债", action: "buy", currentWeight: 0.021, targetWeight: 0.068, diffWeight: 0.047, estAmountWan: 51.7, priority: "medium" },
  { symbol: "123107", name: "温氏转债", action: "hold", currentWeight: 0.064, targetWeight: 0.062, diffWeight: -0.002, estAmountWan: 0.0, priority: "low" },
  { symbol: "127089", name: "晶澳转债", action: "sell", currentWeight: 0.083, targetWeight: 0.0, diffWeight: -0.083, estAmountWan: 91.2, priority: "high" },
  { symbol: "113059", name: "福莱转债", action: "buy", currentWeight: 0.0, targetWeight: 0.061, diffWeight: 0.061, estAmountWan: 67.4, priority: "medium" },
  { symbol: "127084", name: "柳工转2", action: "sell", currentWeight: 0.057, targetWeight: 0.02, diffWeight: -0.037, estAmountWan: 40.8, priority: "medium" },
  { symbol: "113061", name: "拓普转债", action: "buy", currentWeight: 0.0, targetWeight: 0.055, diffWeight: 0.055, estAmountWan: 60.7, priority: "medium" },
  { symbol: "123176", name: "精测转2", action: "hold", currentWeight: 0.044, targetWeight: 0.043, diffWeight: -0.001, estAmountWan: 0.0, priority: "low" },
];

export const orderBlotterRows: OrderBlotterRow[] = [
  { orderId: "OD-11001", symbol: "113063", side: "buy", price: 128.48, volume: 800, filled: 800, status: "filled", slippageBp: 2.1, submitTime: "09:36:10" },
  { orderId: "OD-11002", symbol: "127089", side: "sell", price: 109.31, volume: 1200, filled: 700, status: "part_filled", slippageBp: 5.4, submitTime: "09:36:22" },
  { orderId: "OD-11003", symbol: "110085", side: "buy", price: 117.70, volume: 600, filled: 0, status: "new", slippageBp: 0, submitTime: "09:36:30" },
  { orderId: "OD-11004", symbol: "127084", side: "sell", price: 116.20, volume: 500, filled: 500, status: "filled", slippageBp: 1.8, submitTime: "09:37:02" },
  { orderId: "OD-11005", symbol: "113061", side: "buy", price: 122.19, volume: 400, filled: 0, status: "rejected", slippageBp: 0, submitTime: "09:37:18" },
  { orderId: "OD-11006", symbol: "113059", side: "buy", price: 132.15, volume: 500, filled: 0, status: "canceled", slippageBp: 0, submitTime: "09:38:10" },
  { orderId: "OD-11007", symbol: "123107", side: "sell", price: 121.06, volume: 300, filled: 300, status: "filled", slippageBp: 1.2, submitTime: "09:38:40" },
];

export const executionLogs: ExecutionLogRow[] = [
  { time: "09:35:58", level: "info", source: "router", message: "生成调仓批次 EXE-20260221-01，待执行 8 条指令" },
  { time: "09:36:12", level: "info", source: "gateway.xtp", message: "OD-11001 成交完成，均价 128.48" },
  { time: "09:36:35", level: "warn", source: "risk", message: "OD-11002 成交率低于阈值，触发二次报价" },
  { time: "09:37:20", level: "error", source: "gateway.xtp", message: "OD-11005 拒单：账户可用资金不足" },
  { time: "09:38:15", level: "warn", source: "execution", message: "OD-11006 超时未成交，已执行撤单" },
  { time: "09:38:55", level: "info", source: "position", message: "仓位同步完成，当前持仓 11 只" },
];

export const attributionRows: AttributionRow[] = [
  { strategy: "双低稳健A", period: "weekly", pnlWan: 42.8, stockContribution: 0.27, bondContribution: 0.53, timingContribution: 0.14, costContribution: -0.06 },
  { strategy: "双低+评级", period: "weekly", pnlWan: 38.2, stockContribution: 0.24, bondContribution: 0.56, timingContribution: 0.13, costContribution: -0.07 },
  { strategy: "双低回撤保护", period: "weekly", pnlWan: 31.4, stockContribution: 0.2, bondContribution: 0.58, timingContribution: 0.17, costContribution: -0.08 },
  { strategy: "双低稳健A", period: "monthly", pnlWan: 166.0, stockContribution: 0.29, bondContribution: 0.5, timingContribution: 0.16, costContribution: -0.05 },
  { strategy: "双低+评级", period: "monthly", pnlWan: 149.5, stockContribution: 0.25, bondContribution: 0.55, timingContribution: 0.14, costContribution: -0.06 },
  { strategy: "低价低溢价轮动", period: "monthly", pnlWan: 121.8, stockContribution: 0.34, bondContribution: 0.43, timingContribution: 0.18, costContribution: -0.11 },
];

export const deviationRows: DeviationRow[] = [
  { orderId: "OD-11002", symbol: "127089", expectedPrice: 109.28, filledPrice: 109.31, slippageBp: 2.7, reason: "liquidity", resolved: false, time: "09:36:33" },
  { orderId: "OD-11005", symbol: "113061", expectedPrice: 122.17, filledPrice: 0, slippageBp: 0, reason: "rejected", resolved: true, time: "09:37:19" },
  { orderId: "OD-11006", symbol: "113059", expectedPrice: 132.09, filledPrice: 0, slippageBp: 0, reason: "delay", resolved: true, time: "09:38:15" },
  { orderId: "OD-10997", symbol: "123143", expectedPrice: 130.36, filledPrice: 130.49, slippageBp: 9.9, reason: "manual", resolved: false, time: "09:28:11" },
  { orderId: "OD-10990", symbol: "110090", expectedPrice: 136.44, filledPrice: 136.52, slippageBp: 5.8, reason: "liquidity", resolved: true, time: "09:11:42" },
];

export const ticketRows: TicketRow[] = [
  { ticketId: "ISS-231", type: "execution", severity: "high", status: "open", owner: "ops_a", summary: "盘中拒单率超阈值 3%", updatedAt: "09:40" },
  { ticketId: "ISS-230", type: "data", severity: "medium", status: "in_progress", owner: "data_b", summary: "jsl 部分字段空值回填", updatedAt: "09:22" },
  { ticketId: "ISS-229", type: "risk", severity: "high", status: "open", owner: "risk_c", summary: "单券仓位超过预警线", updatedAt: "09:15" },
  { ticketId: "ISS-228", type: "execution", severity: "low", status: "closed", owner: "ops_d", summary: "撤单回报延迟排查", updatedAt: "08:55" },
  { ticketId: "ISS-227", type: "data", severity: "medium", status: "closed", owner: "data_b", summary: "历史快照缺交易日修复", updatedAt: "昨天" },
];

export const triggerRows: TriggerRow[] = [
  { rule: "近3月跑输基准 > 8%", status: "fired", threshold: "-8%", currentValue: "-9.4%", hitCount: 2, lastTriggered: "今天 09:12", action: "触发参数重搜" },
  { rule: "组合回撤 > 18%", status: "armed", threshold: "18%", currentValue: "11.7%", hitCount: 0, lastTriggered: "--", action: "保持监控" },
  { rule: "滑点均值 > 12bp", status: "fired", threshold: "12bp", currentValue: "14.1bp", hitCount: 1, lastTriggered: "今天 09:35", action: "执行降频" },
  { rule: "拒单率 > 2%", status: "armed", threshold: "2%", currentValue: "1.6%", hitCount: 0, lastTriggered: "--", action: "保持监控" },
  { rule: "数据缺口 > 5 字段", status: "muted", threshold: "5", currentValue: "2", hitCount: 0, lastTriggered: "昨天 10:20", action: "手动解除" },
];

export const strategyPoolRows: StrategyPoolRow[] = [
  { strategy: "双低稳健A", stage: "prod", robustScore: 92.2, cagr: 0.342, mdd: 0.192, recent3m: 0.082, nextAction: "保持实盘", owner: "quant_a" },
  { strategy: "双低+评级", stage: "prod", robustScore: 90.9, cagr: 0.331, mdd: 0.185, recent3m: 0.077, nextAction: "保持实盘", owner: "quant_c" },
  { strategy: "双低回撤保护", stage: "watch", robustScore: 89.8, cagr: 0.316, mdd: 0.169, recent3m: 0.061, nextAction: "灰度一周", owner: "quant_b" },
  { strategy: "流动性优先", stage: "watch", robustScore: 85.2, cagr: 0.288, mdd: 0.141, recent3m: 0.055, nextAction: "补充样本", owner: "quant_e" },
  { strategy: "低溢价动量", stage: "out", robustScore: 77.5, cagr: 0.278, mdd: 0.236, recent3m: -0.012, nextAction: "回测重构", owner: "quant_b" },
  { strategy: "小盘债容量版", stage: "watch", robustScore: 82.9, cagr: 0.301, mdd: 0.201, recent3m: 0.019, nextAction: "观察流动性", owner: "quant_f" },
];

export const rolloutRows: RolloutRow[] = [
  { version: "RLS-1.8.0", from: "watch", to: "prod", result: "success", startAt: "2026-02-20 14:00", endAt: "2026-02-20 15:20", operator: "ops_a" },
  { version: "RLS-1.7.4", from: "prod", to: "watch", result: "rollback", startAt: "2026-02-18 10:00", endAt: "2026-02-18 10:35", operator: "ops_b" },
  { version: "RLS-1.8.1", from: "watch", to: "prod", result: "running", startAt: "2026-02-21 09:30", endAt: "--", operator: "ops_c" },
  { version: "RLS-1.7.0", from: "watch", to: "out", result: "success", startAt: "2026-02-15 16:10", endAt: "2026-02-15 16:40", operator: "ops_d" },
];

export const pipelineRows: PipelineRow[] = [
  { stage: "信息挖掘", status: "ready", updatedAt: "09:35", owner: "data_b", note: "快照完整，字段覆盖 98.4%" },
  { stage: "策略生成", status: "running", updatedAt: "09:36", owner: "quant_a", note: "模板 TPL-005 参数调整中" },
  { stage: "回测评估", status: "running", updatedAt: "09:37", owner: "quant_c", note: "2 个任务运行，1 个排队" },
  { stage: "自动执行", status: "blocked", updatedAt: "09:38", owner: "ops_a", note: "1 笔拒单待资金回补" },
  { stage: "反馈复盘", status: "ready", updatedAt: "09:20", owner: "risk_c", note: "昨日日志归因已生成" },
  { stage: "持续迭代", status: "running", updatedAt: "09:33", owner: "quant_b", note: "触发器命中，准备重跑" },
];

export const alertRows: AlertRow[] = [
  { id: "ALT-101", level: "high", module: "execution", message: "拒单率 3.2% 超阈值", impact: "影响调仓完成率", action: "补资金后重发", updatedAt: "09:38" },
  { id: "ALT-102", level: "medium", module: "data", message: "jsl premium_rt 缺失 6 条", impact: "部分策略候选偏差", action: "启用昨日回退", updatedAt: "09:34" },
  { id: "ALT-103", level: "low", module: "risk", message: "单券权重接近上限", impact: "可能触发减仓", action: "继续观察", updatedAt: "09:30" },
  { id: "ALT-104", level: "medium", module: "backtest", message: "BT-004 任务失败", impact: "排行榜样本减少", action: "重试任务", updatedAt: "09:26" },
];

export const actionRows: ActionRow[] = [
  { time: "09:36:00", operator: "ops_a", action: "提交回测任务", target: "BT-20260221-007", result: "success" },
  { time: "09:36:52", operator: "quant_b", action: "更新参数模板", target: "TPL-007", result: "success" },
  { time: "09:37:19", operator: "ops_a", action: "发送委托", target: "OD-11005", result: "failed" },
  { time: "09:38:12", operator: "ops_a", action: "批量撤单", target: "EXE-20260221-01", result: "running" },
  { time: "09:38:40", operator: "risk_c", action: "创建问题单", target: "ISS-231", result: "success" },
];
