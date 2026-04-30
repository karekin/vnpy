"use client";

import React, { useEffect, useMemo, useState } from "react";
import { ArrowRight, CheckCircle2, CircleDollarSign, ClipboardCheck, Plus, RefreshCw, RotateCcw, ShieldCheck, Sparkles, Trash2 } from "lucide-react";
import {
  loadSmartAllocationCashflowEvents,
  loadSmartAllocationDashboard,
  loadSmartAllocationLeapsCandidates,
  loadSmartAllocationWheelCandidates,
  loadSmartAllocationWheelDailyRecommendation,
  recordSmartAllocationCashflow,
  refreshSmartAllocationSnapshot,
  updateSmartAllocationProfile,
  updateSmartAllocationRecommendation,
} from "@/components/smart-allocation/api";
import type {
  SmartAllocationDashboard,
  SmartAllocationCashflowEvent,
  SmartAllocationGuardrail,
  SmartAllocationLeapsCandidate,
  SmartAllocationRecommendation,
  SmartAllocationRiskLevel,
  SmartAllocationWaterfallTransfer,
  SmartAllocationWheelCandidate,
  SmartAllocationWheelDailyRecommendation,
} from "@/components/smart-allocation/types";

export type SmartAllocationView =
  | "overview"
  | "profile"
  | "waterfall"
  | "rebalance"
  | "leaps"
  | "wheel"
  | "wheelRecommendations"
  | "guardrails"
  | "review";

type SingleStockRow = {
  id: string;
  symbol: string;
  value: string;
};

const DEFAULT_SINGLE_STOCK_ROWS: SingleStockRow[] = [
  { id: "stock-nvda", symbol: "NVDA.US", value: "1043.10" },
  { id: "stock-dram", symbol: "DRAM.US", value: "111.90" },
  { id: "stock-uco", symbol: "UCO.US", value: "427.90" },
];

const DEFAULT_CNY_USD_RATE = 7.2;

function money(value: number) {
  return `$${value.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function yuan(value: number) {
  return `¥${value.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
}

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function num(value: string) {
  const parsed = Number(value.replace(/,/g, "").trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

function amount(value: number) {
  return Number.isFinite(value) ? value.toFixed(2) : "0.00";
}

function riskTone(level: SmartAllocationRiskLevel) {
  if (level === "red") return "border-red-200 bg-red-50 text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300";
  if (level === "orange") return "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900/60 dark:bg-orange-950/30 dark:text-orange-300";
  if (level === "yellow") return "border-yellow-200 bg-yellow-50 text-yellow-700 dark:border-yellow-900/60 dark:bg-yellow-950/30 dark:text-yellow-300";
  return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-300";
}

function statusCardTone(status: "normal" | "warning" | "abnormal") {
  if (status === "abnormal") return "border-red-200 bg-red-50 text-red-700 dark:border-red-900/60 dark:bg-red-950/25 dark:text-red-300";
  if (status === "warning") return "border-yellow-200 bg-yellow-50 text-yellow-700 dark:border-yellow-900/60 dark:bg-yellow-950/25 dark:text-yellow-300";
  return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/25 dark:text-emerald-300";
}

function statusText(status: "normal" | "warning" | "abnormal") {
  if (status === "abnormal") return "异常";
  if (status === "warning") return "警告";
  return "正常";
}

function wheelStatusTone(status: string) {
  if (status === "candidate") return "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300";
  if (status === "watch") return "bg-yellow-50 text-yellow-700 dark:bg-yellow-950/30 dark:text-yellow-300";
  return "bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300";
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
        {description ? <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{description}</p> : null}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function BucketRow({
  name,
  actual,
  target,
  ratio,
}: {
  name: string;
  actual: number;
  target: number;
  ratio: number;
}) {
  const width = target > 0 ? Math.min(140, Math.max(2, (actual / target) * 100)) : 0;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="font-medium text-gray-800 dark:text-gray-100">{name}</span>
        <span className="text-gray-500 dark:text-gray-400">
          实际 {money(actual)} / 目标 {money(target)} / {pct(ratio)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
        <div className="h-full rounded-full bg-brand-500" style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}

function GuardrailRow({ item }: { item: SmartAllocationGuardrail }) {
  return (
    <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-gray-900 dark:text-white">{item.message}</p>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{item.recommended_action}</p>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${riskTone(item.risk_level)}`}>
          {item.risk_level}
        </span>
      </div>
      <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
        实际 {money(item.actual_value)} / 红线 {money(item.limit_value)}
      </p>
    </div>
  );
}

function RecommendationRow({ item }: { item: SmartAllocationRecommendation }) {
  return (
    <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-gray-900 dark:text-white">{item.recommendation_type}</p>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{item.reason}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-gray-100 px-3 py-1 text-sm font-semibold text-gray-700 dark:bg-gray-800 dark:text-gray-200">
            {money(item.amount)}
          </span>
          <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700 dark:bg-brand-500/15 dark:text-brand-300">
            {item.status}
          </span>
        </div>
      </div>
      {item.user_note ? <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">备注：{item.user_note}</p> : null}
    </div>
  );
}

function splitSymbols(value: string) {
  return value
    .split(/[,\n，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseNumberMap(value: string) {
  const result: Record<string, number> = {};
  for (const raw of value.split(/[,\n，]/)) {
    const [symbol, numberValue] = raw.split(":").map((item) => item.trim());
    if (!symbol || !numberValue) continue;
    const parsed = Number(numberValue);
    if (Number.isFinite(parsed)) result[symbol] = parsed;
  }
  return result;
}

function singleStockRowsToValue(rows: SingleStockRow[]) {
  return rows
    .map((row) => {
      const symbol = row.symbol.trim();
      const value = row.value.trim();
      return symbol && value ? `${symbol}:${value}` : "";
    })
    .filter(Boolean)
    .join(",");
}

function incomeStatusText(value: "stable" | "unstable" | "retired") {
  if (value === "stable") return "有稳定收入";
  if (value === "retired") return "退休";
  return "无稳定收入";
}

function compareText(actual: number, target: number, unitName: string) {
  const diff = actual - target;
  const absDiff = Math.abs(diff);
  if (target <= 0 && actual <= 0) return `${unitName}暂无目标缺口。`;
  if (absDiff <= Math.max(target * 0.05, 1)) return `${unitName}接近目标，暂不需要为了比例做动作。`;
  return diff > 0 ? `${unitName}高于目标约 ${money(absDiff)}。` : `${unitName}低于目标约 ${money(absDiff)}。`;
}

const WHEEL_RECORD_FIELDS = ["cycle_id", "symbol", "phase", "strike", "premium", "cash_reserved", "assigned", "adjusted_cost", "realized_pnl"];

const WHEEL_CHECKLIST_ITEMS = [
  "只在愿意长期持有的股票或 ETF 上卖 Put。",
  "Put 被指派后，单一标的不能超过账户上限。",
  "Covered Call 行权价优先高于调整后成本。",
  "权利金浮盈 50%-80% 可优先释放风险。",
  "基本面破坏时允许止损，不用无限滚动掩盖亏损。",
];

const WHEEL_OPERATION_SOP = [
  "刷新每日推荐，先看 status：blocked 只观察，candidate 才进入下一步。",
  "核验账户约束：一张 Put 的现金担保不能超过 Wheel 可用额度和单股上限。",
  "核验期权链：优先 30-45 DTE、Delta 0.20-0.30，并检查 IV、成交量、未平仓量和 bid/ask 价差。",
  "核验事件风险：财报、除息、重大新闻前不机械开仓。",
  "下单后记录 cycle、strike、premium、cash_reserved；权利金只按已实现现金流入账。",
];

function cashflowAuditText(value: string) {
  if (value === "snapshot_waterfall_audit") return "系统快照审计";
  if (value === "wheel_premium_received") return "Wheel 权利金";
  if (value === "leaps_profit_realized") return "LEAPS 盈利";
  if (value === "cash_bucket_topup") return "临时入金";
  if (value === "dca_injection") return "工资定投";
  return "人工调整";
}

function calculateTargets(ageValue: string, incomeStatus: "stable" | "unstable" | "retired", totalEquity: number) {
  const age = Math.max(0, Math.min(120, Math.trunc(num(ageValue))));
  const dcaRatio = Math.min(age + 20, 70) / 100;
  const cashRatio = incomeStatus === "stable" ? 0.05 : 0.1;
  const optionsRatio = Math.max(0, 1 - dcaRatio - cashRatio);
  const dcaValue = totalEquity * dcaRatio;
  const cashValue = totalEquity * cashRatio;
  const optionsValue = totalEquity * optionsRatio;
  return {
    dca_ratio: dcaRatio,
    cash_ratio: cashRatio,
    options_ratio: optionsRatio,
    dca_value: dcaValue,
    cash_value: cashValue,
    options_value: optionsValue,
    qqqm_value: dcaValue * 0.3,
    voo_value: dcaValue * 0.3,
    quality_stock_value: dcaValue * 0.4,
    single_stock_limit: dcaValue * 0.1,
    wheel_value: optionsValue * 0.8,
    leaps_value: optionsValue * 0.2,
    margin_limit: totalEquity * 0.25,
  };
}

export default function SmartAllocationDashboard({
  dashboard: initialDashboard,
  activeView = "overview",
}: {
  dashboard: SmartAllocationDashboard;
  activeView?: SmartAllocationView;
}) {
  const [dashboard, setDashboard] = useState(initialDashboard);
  const [profileAge, setProfileAge] = useState(String(initialDashboard.profile.age));
  const [incomeStatus, setIncomeStatus] = useState(initialDashboard.profile.income_status);
  const [qualitySymbols, setQualitySymbols] = useState(initialDashboard.profile.quality_stock_symbols.join(", "));
  const [wheelSymbols, setWheelSymbols] = useState(initialDashboard.profile.wheel_symbols.join(", "));
  const [leapsSymbols, setLeapsSymbols] = useState(initialDashboard.profile.leaps_symbols.join(", "));
  const [snapshotForm, setSnapshotForm] = useState({
    total_equity: String(initialDashboard.snapshot.total_equity),
    cash_value: String(initialDashboard.snapshot.cash_value),
    dca_value: String(initialDashboard.snapshot.dca_value),
    options_value: String(initialDashboard.snapshot.options_value),
    wheel_value: String(initialDashboard.snapshot.wheel_value),
    leaps_value: String(initialDashboard.snapshot.leaps_value),
    margin_used: String(initialDashboard.snapshot.margin_used),
    unclassified_value: String(initialDashboard.snapshot.unclassified_value),
    single_stock_values: "",
    latest_rsi_by_symbol: "",
    open_leaps_symbols: initialDashboard.snapshot.open_leaps_symbols.join(", "),
  });
  const [singleStockRows, setSingleStockRows] = useState<SingleStockRow[]>(DEFAULT_SINGLE_STOCK_ROWS);
  const [snapshotSourceForm, setSnapshotSourceForm] = useState({
    hkdUsdRate: "7.8",
    hsbcTotalHkd: "74378.54",
    hsbcInvestmentHkd: "61790",
    schwabNetLiquidationUsd: "3014.85",
    schwabCashSweepUsd: "1431.95",
    schwabStockValueUsd: "1582.90",
    wheelValueUsd: "0",
    leapsValueUsd: "0",
    marginUsedUsd: "0",
  });
  const [externalIncomeForm, setExternalIncomeForm] = useState({
    incomeCny: "10000",
  });
  const [cashflowAmount, setCashflowAmount] = useState("");
  const [cashflowType, setCashflowType] = useState("cash_bucket_topup");
  const [cashflowTransfers, setCashflowTransfers] = useState<SmartAllocationWaterfallTransfer[]>([]);
  const [cashflowEvents, setCashflowEvents] = useState<SmartAllocationCashflowEvent[]>([]);
  const [leapsCandidates, setLeapsCandidates] = useState<SmartAllocationLeapsCandidate[]>([]);
  const [wheelCandidates, setWheelCandidates] = useState<SmartAllocationWheelCandidate[]>([]);
  const [wheelDailyRecommendation, setWheelDailyRecommendation] = useState<SmartAllocationWheelDailyRecommendation | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [isSnapshotSaving, setIsSnapshotSaving] = useState(false);
  const [snapshotSaveFeedback, setSnapshotSaveFeedback] = useState<{
    tone: "success" | "error";
    message: string;
  } | null>(null);

  const { snapshot, targets } = dashboard;
  const shouldShow = (...views: SmartAllocationView[]) => views.includes(activeView);
  const derivedSnapshot = useMemo(() => {
    const hkdUsdRate = num(snapshotSourceForm.hkdUsdRate) || 7.8;
    const hsbcTotalUsd = num(snapshotSourceForm.hsbcTotalHkd) / hkdUsdRate;
    const hsbcInvestmentUsd = num(snapshotSourceForm.hsbcInvestmentHkd) / hkdUsdRate;
    const hsbcCashUsd = Math.max(hsbcTotalUsd - hsbcInvestmentUsd, 0);
    const schwabNetLiquidationUsd = num(snapshotSourceForm.schwabNetLiquidationUsd);
    const schwabCashUsd = num(snapshotSourceForm.schwabCashSweepUsd);
    const schwabStockUsd = num(snapshotSourceForm.schwabStockValueUsd);
    const wheelValue = num(snapshotSourceForm.wheelValueUsd);
    const leapsValue = num(snapshotSourceForm.leapsValueUsd);
    const optionsValue = wheelValue + leapsValue;
    const totalEquity = hsbcTotalUsd + schwabNetLiquidationUsd;
    const cashValue = hsbcCashUsd + schwabCashUsd;
    const dcaValue = hsbcInvestmentUsd + schwabStockUsd;
    const classified = cashValue + dcaValue + optionsValue;
    return {
      hsbcTotalUsd,
      hsbcInvestmentUsd,
      hsbcCashUsd,
      totalEquity,
      cashValue,
      dcaValue,
      optionsValue,
      wheelValue,
      leapsValue,
      marginUsed: num(snapshotSourceForm.marginUsedUsd),
      unclassifiedValue: Math.max(totalEquity - classified, 0),
    };
  }, [snapshotSourceForm]);
  const profileSummary = useMemo(
    () => `${dashboard.profile.age} 岁 / ${dashboard.profile.income_status} / 阈值 ${(dashboard.profile.rebalance_threshold * 100).toFixed(1)}%`,
    [dashboard.profile],
  );
  const draftSnapshot = useMemo(
    () => ({
      total_equity: derivedSnapshot.totalEquity,
      cash_value: derivedSnapshot.cashValue,
      dca_value: derivedSnapshot.dcaValue,
      options_value: derivedSnapshot.optionsValue,
      wheel_value: derivedSnapshot.wheelValue,
      leaps_value: derivedSnapshot.leapsValue,
      margin_used: derivedSnapshot.marginUsed,
      unclassified_value: derivedSnapshot.unclassifiedValue,
    }),
    [derivedSnapshot],
  );
  const previewTargets = useMemo(
    () => calculateTargets(profileAge, incomeStatus, draftSnapshot.total_equity),
    [draftSnapshot.total_equity, incomeStatus, profileAge],
  );
  const displaySnapshot = activeView === "profile" ? draftSnapshot : snapshot;
  const displayTargets = activeView === "profile" ? previewTargets : targets;
  const displayOpenLeapsSymbols = activeView === "profile" ? splitSymbols(snapshotForm.open_leaps_symbols) : snapshot.open_leaps_symbols;
  const isDedicatedWaterfallView = activeView === "waterfall";
  const singleStockValuesText = useMemo(() => singleStockRowsToValue(singleStockRows), [singleStockRows]);
  const ageNumber = Math.max(0, Math.min(120, Math.trunc(num(profileAge))));
  const blockingGuardrailCount = dashboard.guardrails.filter((item) => item.blocking).length;
  const targetFormulaItems = [
    `定投 = min(${ageNumber} + 20, 70)% = ${pct(displayTargets.dca_ratio)}`,
    `现金 = ${incomeStatus === "stable" ? "5%" : "10%"}（${incomeStatusText(incomeStatus)}）`,
    `期权 = 100% - 定投 - 现金 = ${pct(displayTargets.options_ratio)}`,
  ];
  const guardrailFormulaItems = [
    "单股上限 = 定投仓位 x 10%",
    "保证金上限 = 总权益 x 25%",
    "Wheel 目标 = 期权仓位 x 80%",
    "LEAPS 目标 = 期权仓位 x 20%",
    `仓位偏离 >= ${pct(dashboard.profile.rebalance_threshold)} 触发再平衡`,
  ];
  const healthRuleText = "max(0, 100 - 红线数 x 15 - 阻断红线数 x 20)";
  const healthCalcText = `100 - ${dashboard.guardrails.length} x 15 - ${blockingGuardrailCount} x 20 = ${dashboard.health_score}`;
  const aiInsightParagraphs = useMemo(() => {
    const bucketInsights = [
      compareText(displaySnapshot.cash_value, displayTargets.cash_value, "现金仓位"),
      compareText(displaySnapshot.dca_value, displayTargets.dca_value, "定投仓位"),
      compareText(displaySnapshot.options_value, displayTargets.options_value, "期权仓位"),
    ];
    const riskInsights: string[] = [];
    const oversizedStocks = singleStockRows
      .map((row) => ({ symbol: row.symbol.trim(), value: num(row.value) }))
      .filter((row) => row.symbol && row.value > displayTargets.single_stock_limit);
    if (oversizedStocks.length) {
      riskInsights.push(`${oversizedStocks.map((row) => row.symbol).join("、")} 超过单股上限，新增买入应先阻断。`);
    } else {
      riskInsights.push("当前录入的单股市值未超过单股集中度上限。");
    }
    if (displaySnapshot.margin_used > displayTargets.margin_limit) {
      riskInsights.push("保证金已经超过 25% 红线，应停止新增保证金 Sell Put。");
    } else if (displaySnapshot.margin_used > displayTargets.margin_limit * 0.8) {
      riskInsights.push("保证金接近红线，后续 Sell Put 需要保守处理。");
    } else {
      riskInsights.push("保证金距离红线仍有缓冲。");
    }
    const primaryAction =
      displaySnapshot.options_value < displayTargets.options_value * 0.2
        ? "当前期权仓位明显低于目标，但 LEAPS 仍应等待 RSI 纪律，不需要为了填满目标而强行入场。"
        : "优先按现金流瀑布处理期权利润，避免把收益继续滚入期权池。";
    return [`${primaryAction} ${bucketInsights.join(" ")}`, riskInsights.join(" ")];
  }, [displaySnapshot, displayTargets, singleStockRows]);
  const realizedOptionProfit = useMemo(
    () =>
      cashflowEvents
        .filter((item) => ["wheel_premium_received", "leaps_profit_realized"].includes(item.event_type))
        .reduce((total, item) => total + Math.max(0, item.amount), 0),
    [cashflowEvents],
  );
  const wheelPremiumRealized = useMemo(
    () =>
      cashflowEvents
        .filter((item) => item.event_type === "wheel_premium_received")
        .reduce((total, item) => total + Math.max(0, item.amount), 0),
    [cashflowEvents],
  );
  const waterfallPreview = useMemo(() => {
    const amountValue = Math.max(0, realizedOptionProfit);
    const cashGap = Math.max(displayTargets.cash_value - displaySnapshot.cash_value, 0);
    const cashTopup = Math.min(amountValue, cashGap);
    const dcaOverflow = Math.max(amountValue - cashTopup, 0);
    return {
      amountValue,
      cashGap,
      cashTopup,
      dcaOverflow,
      qqqm: dcaOverflow * 0.3,
      voo: dcaOverflow * 0.3,
      quality: dcaOverflow * 0.4,
    };
  }, [displaySnapshot.cash_value, displayTargets.cash_value, realizedOptionProfit]);
  const externalIncomePlan = useMemo(() => {
    const incomeCny = Math.max(0, num(externalIncomeForm.incomeCny));
    const cnyUsdRate = DEFAULT_CNY_USD_RATE;
    const incomeUsd = incomeCny / cnyUsdRate;
    const nextTotalEquity = displaySnapshot.total_equity + incomeUsd;
    const nextTargets = calculateTargets(String(dashboard.profile.age), dashboard.profile.income_status, nextTotalEquity);
    const cashGap = Math.max(nextTargets.cash_value - displaySnapshot.cash_value, 0);
    const cashTopup = Math.min(incomeUsd, cashGap);
    const afterCash = Math.max(incomeUsd - cashTopup, 0);
    const dcaGap = Math.max(nextTargets.dca_value - displaySnapshot.dca_value, 0);
    const dcaTopup = Math.min(afterCash, dcaGap);
    const optionsWaiting = Math.max(afterCash - dcaTopup, 0);
    const cashAfter = displaySnapshot.cash_value + cashTopup;
    const dcaAfter = displaySnapshot.dca_value + dcaTopup;
    const optionsAfter = displaySnapshot.options_value + optionsWaiting;
    return {
      incomeCny,
      cnyUsdRate,
      incomeUsd,
      nextTotalEquity,
      nextTargets,
      cashGap,
      dcaGap,
      cashTopup,
      dcaTopup,
      optionsWaiting,
      wheelWaiting: optionsWaiting * 0.8,
      leapsWaiting: optionsWaiting * 0.2,
      rows: [
        {
          bucket: "现金池",
          amountUsd: cashTopup,
          amountCny: cashTopup * cnyUsdRate,
          afterValue: cashAfter,
          afterRatio: nextTotalEquity > 0 ? cashAfter / nextTotalEquity : 0,
          targetValue: nextTargets.cash_value,
          rule: cashTopup > 0 ? "先补足新总权益下的现金安全垫。" : "现金已高于新目标，本次不补。",
        },
        {
          bucket: "定投池",
          amountUsd: dcaTopup,
          amountCny: dcaTopup * cnyUsdRate,
          afterValue: dcaAfter,
          afterRatio: nextTotalEquity > 0 ? dcaAfter / nextTotalEquity : 0,
          targetValue: nextTargets.dca_value,
          rule: dcaTopup > 0 ? "现金达标后补定投目标，可再拆成 QQQM / VOO / 优质个股。" : "定投已高于新目标，本次不加。",
        },
        {
          bucket: "期权策略待机资金",
          amountUsd: optionsWaiting,
          amountCny: optionsWaiting * cnyUsdRate,
          afterValue: optionsAfter,
          afterRatio: nextTotalEquity > 0 ? optionsAfter / nextTotalEquity : 0,
          targetValue: nextTargets.options_value,
          rule: optionsWaiting > 0 ? "进入 Wheel / LEAPS 候选等待区，不计入期权利润池。" : "无剩余额度进入期权策略。",
        },
      ],
    };
  }, [dashboard.profile.age, dashboard.profile.income_status, displaySnapshot, externalIncomeForm]);
  const hasWheelStarted = displaySnapshot.wheel_value > 0 || cashflowEvents.some((item) => item.event_type === "wheel_premium_received");
  const hasLeapsStarted = displaySnapshot.leaps_value > 0 || displayOpenLeapsSymbols.length > 0 || cashflowEvents.some((item) => item.event_type === "leaps_profit_realized");
  const optionIncomeStage = hasWheelStarted ? "策略已启动，等待权利金流水" : "未启动 Wheel";
  const leapsStage = hasLeapsStarted ? "策略已启动，等待退出纪律" : "未启动 LEAPS";
  const cashStage = displaySnapshot.cash_value >= displayTargets.cash_value ? "现金已补满" : "现金待补足";
  const dcaStage = waterfallPreview.dcaOverflow > 0 ? "可生成定投注入草案" : "暂无期权利润溢出";
  const optionBucketMismatch = Math.abs(displaySnapshot.options_value - displaySnapshot.wheel_value - displaySnapshot.leaps_value) > 1;
  const optionProfitStatus: "normal" | "warning" | "abnormal" = optionBucketMismatch
    ? "abnormal"
    : hasWheelStarted || hasLeapsStarted
      ? "warning"
      : "normal";
  const cashBucketStatus: "normal" | "warning" | "abnormal" =
    displaySnapshot.cash_value >= displayTargets.cash_value
      ? "normal"
      : displaySnapshot.cash_value < displayTargets.cash_value * 0.8
        ? "abnormal"
        : "warning";
  const dcaBucketDeviation =
    displaySnapshot.total_equity > 0
      ? Math.abs(displaySnapshot.dca_value / displaySnapshot.total_equity - displayTargets.dca_ratio)
      : 0;
  const hasBlockingSingleStock = dashboard.guardrails.some((item) => item.rule_code === "single_stock_limit" && item.blocking);
  const dcaBucketStatus: "normal" | "warning" | "abnormal" = hasBlockingSingleStock
    ? "abnormal"
    : dcaBucketDeviation >= dashboard.profile.rebalance_threshold
      ? "warning"
      : "normal";
  const wheelUsageRatio = displayTargets.wheel_value > 0 ? displaySnapshot.wheel_value / displayTargets.wheel_value : 0;
  const wheelAvailableCash = Math.max(displayTargets.wheel_value - displaySnapshot.wheel_value, 0);
  const wheelDisciplineState =
    displaySnapshot.wheel_value > displayTargets.wheel_value
      ? "Wheel 已超目标，暂停新开仓"
      : displaySnapshot.cash_value < displayTargets.cash_value
        ? "现金池未满，权利金先补现金"
        : "可按候选池逐笔评估";
  const wheelActionHint =
    displaySnapshot.wheel_value > displayTargets.wheel_value
      ? "先减小 Wheel 占用或等待合约自然结束，不把新权利金继续滚入期权池。"
      : !hasWheelStarted
        ? "先用候选池做纸面模拟，确认被指派后愿意持有，再小仓位实盘。"
        : displaySnapshot.cash_value < displayTargets.cash_value
          ? "已实现权利金应进入现金流瀑布，优先补现金安全垫。"
          : "下一笔开仓仍按现金担保、单标的上限和事件风险逐项检查。";
  const candidateWheelCount = wheelCandidates.filter((item) => item.status === "candidate").length;
  const topWheelCandidates = wheelCandidates.slice(0, 8);
  const wheelPoolSources = wheelDailyRecommendation?.pool_sources ?? [];
  const mrvlCandidate = wheelDailyRecommendation?.candidates.find((item) => item.symbol === "MRVL.US") ?? wheelCandidates.find((item) => item.symbol === "MRVL.US");
  const mrvlAccountText = mrvlCandidate
    ? mrvlCandidate.status === "candidate"
      ? `按当前账户规模，MRVL 可进入候选池；下一步仍要核验期权链流动性、财报日期、IV、Delta 和 bid/ask 价差。预计一张现金担保约 ${money(mrvlCandidate.estimated_cash_required)}。`
      : `按当前账户规模，MRVL 不适合实盘 Wheel，只保留观察：预计一张现金担保约 ${money(mrvlCandidate.estimated_cash_required)}，当前 Wheel 可用额度 ${money(wheelDailyRecommendation?.wheel_available ?? wheelAvailableCash)}。`
    : "MRVL 已加入系统 AI/半导体观察池，刷新每日推荐后会按账户规模给出可做、观察或阻断状态。";
  const wheelCandidateText = wheelCandidates.length
    ? `${candidateWheelCount} 个可核验 / ${wheelCandidates.length} 个观察候选`
    : "等待候选推荐刷新";
  const wheelFlowItems = [
    {
      title: "现金担保 Put",
      subtitle: "用期权仓位现金承诺按目标价买入",
      detail: "现金预留 = strike x 100 x 合约数；盈亏平衡 = strike - 每股权利金。",
    },
    {
      title: "未指派或被指派",
      subtitle: "没指派就保留权利金；被指派就进入持股",
      detail: "滚动只是延期风险，基本面破坏时优先平仓止损。",
    },
    {
      title: "Covered Call",
      subtitle: "持有 100 股后卖 Call 管理退出价",
      detail: "Call strike 优先高于调整后成本，除非明确标记为止损减仓。",
    },
    {
      title: "回到现金",
      subtitle: "股票被叫走后完成一轮循环",
      detail: "Put/Call 权利金和股票差价计入已实现结果，再进入现金流瀑布。",
    },
  ];
  const wheelRiskItems = [
    {
      label: "标的资格",
      text: "不做看不懂、流动性差、只因权利金高而动心的标的。",
    },
    {
      label: "集中度",
      text: `单股上限 ${money(displayTargets.single_stock_limit)}，被指派后仍要能承受。`,
    },
    {
      label: "保证金",
      text: `已用保证金 ${money(displaySnapshot.margin_used)} / 红线 ${money(displayTargets.margin_limit)}，接近红线时停止 Sell Put。`,
    },
    {
      label: "事件风险",
      text: "财报、除息、诉讼、并购等事件前，必须先确认是否愿意承受跳空和提前指派。",
    },
  ];

  useEffect(() => {
    void refreshCashflowEvents();
    void refreshWheelCandidates();
    void refreshWheelDailyRecommendation();
  }, []);

  async function refreshCashflowEvents() {
    try {
      const events = await loadSmartAllocationCashflowEvents();
      setCashflowEvents(events);
    } catch {
      setCashflowEvents([]);
    }
  }

  async function reloadDashboard() {
    const next = await loadSmartAllocationDashboard();
    setDashboard(next);
    return next;
  }

  async function saveCashflow() {
    const cashflowValue = Number(cashflowAmount);
    if (!Number.isFinite(cashflowValue) || cashflowValue <= 0) {
      setStatusMessage("请输入大于 0 的实际外部资金金额。");
      return;
    }
    const targetBucket = cashflowType === "dca_injection" ? "dca" : "cash";
    const transfers = await recordSmartAllocationCashflow({
      event_type: cashflowType,
      amount: cashflowValue,
      source_bucket: "external",
      target_bucket: targetBucket,
      note: "人工补录外部资金流入",
    });
    setCashflowTransfers(transfers);
    await reloadDashboard();
    await refreshCashflowEvents();
    await refreshWheelCandidates();
    await refreshWheelDailyRecommendation();
    setStatusMessage("现金流事件已记录。");
  }

  async function refreshLeaps() {
    const candidates = await loadSmartAllocationLeapsCandidates();
    setLeapsCandidates(candidates);
    setStatusMessage("LEAPS 候选已刷新。");
  }

  async function refreshWheelCandidates() {
    try {
      const candidates = await loadSmartAllocationWheelCandidates();
      setWheelCandidates(candidates);
    } catch {
      setWheelCandidates([]);
    }
  }

  async function refreshWheelDailyRecommendation() {
    try {
      const recommendation = await loadSmartAllocationWheelDailyRecommendation();
      setWheelDailyRecommendation(recommendation);
    } catch {
      setWheelDailyRecommendation(null);
    }
  }

  async function updateRecommendation(id: string, action: "ignore" | "mark-executed") {
    const recommendations = await updateSmartAllocationRecommendation(id, action, action === "ignore" ? "本轮手动忽略" : "已在线下处理");
    setDashboard((current) => ({ ...current, recommendations }));
  }

  async function applyDerivedSnapshot() {
    if (isSnapshotSaving) return;
    setIsSnapshotSaving(true);
    setSnapshotSaveFeedback(null);
    const nextSnapshotForm = {
      total_equity: amount(derivedSnapshot.totalEquity),
      cash_value: amount(derivedSnapshot.cashValue),
      dca_value: amount(derivedSnapshot.dcaValue),
      options_value: amount(derivedSnapshot.optionsValue),
      wheel_value: amount(derivedSnapshot.wheelValue),
      leaps_value: amount(derivedSnapshot.leapsValue),
      margin_used: amount(derivedSnapshot.marginUsed),
      unclassified_value: amount(derivedSnapshot.unclassifiedValue),
      single_stock_values: singleStockValuesText,
      latest_rsi_by_symbol: snapshotForm.latest_rsi_by_symbol,
      open_leaps_symbols: snapshotForm.open_leaps_symbols,
    };
    try {
      setSnapshotForm((current) => ({
        ...current,
        ...nextSnapshotForm,
      }));
      await updateSmartAllocationProfile(dashboard.profile.id, {
        age: Number(profileAge),
        income_status: incomeStatus,
        name: "智能仓位方案",
        rebalance_threshold: 0.05,
        allow_bull_market_leaps_relaxation: false,
        quality_stock_symbols: splitSymbols(qualitySymbols),
        wheel_symbols: splitSymbols(wheelSymbols),
        leaps_symbols: splitSymbols(leapsSymbols),
      });
      const next = await refreshSmartAllocationSnapshot({
        total_equity: num(nextSnapshotForm.total_equity),
        cash_value: num(nextSnapshotForm.cash_value),
        dca_value: num(nextSnapshotForm.dca_value),
        options_value: num(nextSnapshotForm.options_value),
        wheel_value: num(nextSnapshotForm.wheel_value),
        leaps_value: num(nextSnapshotForm.leaps_value),
        margin_used: num(nextSnapshotForm.margin_used),
        unclassified_value: num(nextSnapshotForm.unclassified_value),
        single_stock_values: parseNumberMap(nextSnapshotForm.single_stock_values),
        latest_rsi_by_symbol: parseNumberMap(nextSnapshotForm.latest_rsi_by_symbol),
        open_leaps_symbols: splitSymbols(nextSnapshotForm.open_leaps_symbols),
      });
      setDashboard(next);
      await refreshCashflowEvents();
      await refreshWheelCandidates();
      await refreshWheelDailyRecommendation();
      const savedAt = new Date(next.snapshot.snapshot_at).toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      const message = `已保存 ${savedAt}，账户快照已更新。`;
      setStatusMessage("已按汇丰 + 嘉信截图口径生成并刷新快照，账户结构和关键红线已联动更新。");
      setSnapshotSaveFeedback({ tone: "success", message });
    } catch (error) {
      const message = error instanceof Error ? error.message : "保存失败，请稍后重试。";
      setStatusMessage(`保存账户快照失败：${message}`);
      setSnapshotSaveFeedback({ tone: "error", message: `保存失败：${message}` });
    } finally {
      setIsSnapshotSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">智能仓位管理</h1>
            <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">
              面向 vnpy 主系统的账户级仓位纪律：定投底仓、现金池、期权现金流、LEAPS 爆发力和风控红线统一管理。
            </p>
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{profileSummary}</p>
          </div>
          <div className={`rounded-2xl border px-5 py-4 ${riskTone(dashboard.risk_level)} lg:min-w-[520px]`}>
            <div className="grid gap-4 sm:grid-cols-[auto_1fr] sm:items-center">
              <div className="text-center">
                <p className="text-xs font-medium">健康分</p>
                <p className="mt-1 text-3xl font-semibold">{dashboard.health_score}</p>
                <p className="mt-1 text-xs">{dashboard.risk_level}</p>
              </div>
              <div className="space-y-1 text-xs leading-5">
                <p>规则：{healthRuleText}</p>
                <p>当前：{healthCalcText}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {statusMessage ? (
        <div className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-700 dark:border-brand-900/60 dark:bg-brand-950/30 dark:text-brand-300">
          {statusMessage}
        </div>
      ) : null}

      {shouldShow("wheel", "wheelRecommendations") ? (
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-gray-900 dark:text-white">Wheel 操作 SOP</p>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">每天只按候选、账户约束、期权链和事件风险逐步推进，不把观察池当下单信号。</p>
            </div>
            <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-600 dark:bg-gray-800 dark:text-gray-300">
              {money(wheelAvailableCash)} 可用
            </span>
          </div>
          <div className="mt-3 grid gap-2 text-xs leading-5 md:grid-cols-5">
            {WHEEL_OPERATION_SOP.map((item, index) => (
              <div key={item} className="rounded-lg bg-gray-50 p-3 text-gray-600 dark:bg-gray-900/50 dark:text-gray-300">
                <p className="mb-1 font-semibold text-gray-900 dark:text-white">Step {index + 1}</p>
                {item}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="grid gap-6">
        {shouldShow("profile") ? (
        <Section title="账户快照录入" description="录入基本情况和外部账户事实数据；内部仓位、目标配置和红线由系统自动转换。">
          <div className="mb-4 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/40">
            <div className="mb-4">
              <div>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">1. 基本情况</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">年龄和收入状态决定目标比例；白名单只用于资产归类和风控。</p>
              </div>
            </div>
            <div className="grid gap-3 text-sm md:grid-cols-2">
              <label className="space-y-1">
                <span className="text-gray-500 dark:text-gray-400">年龄</span>
                <input className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-transparent" value={profileAge} onChange={(event) => setProfileAge(event.target.value)} />
              </label>
              <label className="space-y-1">
                <span className="text-gray-500 dark:text-gray-400">收入状态</span>
                <select className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-transparent" value={incomeStatus} onChange={(event) => setIncomeStatus(event.target.value as typeof incomeStatus)}>
                  <option value="stable">有稳定收入</option>
                  <option value="unstable">无稳定收入</option>
                  <option value="retired">退休</option>
                </select>
              </label>
              <label className="space-y-1 md:col-span-2">
                <span className="text-gray-500 dark:text-gray-400">优质个股白名单</span>
                <input className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-transparent" value={qualitySymbols} onChange={(event) => setQualitySymbols(event.target.value)} placeholder="NVDA.US, MSFT.US" />
              </label>
              <label className="space-y-1">
                <span className="text-gray-500 dark:text-gray-400">Wheel 标的</span>
                <input className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-transparent" value={wheelSymbols} onChange={(event) => setWheelSymbols(event.target.value)} />
              </label>
              <label className="space-y-1">
                <span className="text-gray-500 dark:text-gray-400">LEAPS 标的</span>
                <input className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-transparent" value={leapsSymbols} onChange={(event) => setLeapsSymbols(event.target.value)} />
              </label>
            </div>
          </div>
          <div className="mb-4 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/40">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">2. 外部账户数据</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">按截图抄数即可，目标配置不需要手填。</p>
              </div>
            </div>
            <div className="grid gap-3 text-sm md:grid-cols-3">
              {[
                ["hkdUsdRate", "港币兑美元，例 7.8"],
                ["hsbcTotalHkd", "汇丰总资产 HKD"],
                ["hsbcInvestmentHkd", "汇丰投资市值 HKD"],
                ["schwabNetLiquidationUsd", "嘉信净清仓价值 USD"],
                ["schwabCashSweepUsd", "嘉信现金转存账户 USD"],
                ["schwabStockValueUsd", "嘉信股票市值 USD"],
                ["wheelValueUsd", "Wheel 占用 USD"],
                ["leapsValueUsd", "LEAPS 市值 USD"],
                ["marginUsedUsd", "已用保证金 USD"],
              ].map(([key, label]) => (
                <label key={key} className="space-y-1">
                  <span className="text-gray-500 dark:text-gray-400">{label}</span>
                  <input
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-transparent"
                    value={snapshotSourceForm[key as keyof typeof snapshotSourceForm]}
                    onChange={(event) => setSnapshotSourceForm((current) => ({ ...current, [key]: event.target.value }))}
                  />
                </label>
              ))}
            </div>
          </div>
          <div className="mb-4 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/40">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">3. 单股持仓市值</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">每行录入一只股票，系统用来检查单股集中度上限。</p>
              </div>
              <button
                type="button"
                onClick={() => setSingleStockRows((current) => [...current, { id: `stock-${current.length + 1}-${Date.now()}`, symbol: "", value: "" }])}
                className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-900"
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                添加
              </button>
            </div>
            <div className="space-y-2">
              {singleStockRows.map((row, index) => (
                <div key={row.id} className="grid gap-2 md:grid-cols-[1.1fr_1fr_auto]">
                  <label className="space-y-1">
                    <span className="text-xs text-gray-500 dark:text-gray-400">代码</span>
                    <input
                      className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-transparent"
                      value={row.symbol}
                      onChange={(event) =>
                        setSingleStockRows((current) => current.map((item) => (item.id === row.id ? { ...item, symbol: event.target.value } : item)))
                      }
                      placeholder="NVDA.US"
                    />
                  </label>
                  <label className="space-y-1">
                    <span className="text-xs text-gray-500 dark:text-gray-400">市值 USD</span>
                    <input
                      className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-transparent"
                      value={row.value}
                      onChange={(event) =>
                        setSingleStockRows((current) => current.map((item) => (item.id === row.id ? { ...item, value: event.target.value } : item)))
                      }
                      placeholder="1043.10"
                    />
                  </label>
                  <button
                    type="button"
                    aria-label="删除单股市值"
                    onClick={() => setSingleStockRows((current) => (current.length > 1 ? current.filter((item) => item.id !== row.id) : current.map((item, itemIndex) => (itemIndex === index ? { ...item, symbol: "", value: "" } : item))))}
                    className="self-end rounded-lg border border-gray-200 p-2 text-gray-500 hover:bg-gray-50 hover:text-red-600 dark:border-gray-800 dark:hover:bg-gray-900"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              ))}
            </div>
          </div>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-100 bg-brand-50 p-4 dark:border-brand-900/60 dark:bg-brand-950/20">
            <div>
              <p className="text-sm font-semibold text-gray-900 dark:text-white">保存后会同时更新基本情况和账户快照</p>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">目标仓位、关键红线、AI 解读和再平衡建议会基于保存后的快照重新计算。</p>
            </div>
            <div className="flex flex-col items-start gap-2 sm:items-end">
              <button
                type="button"
                onClick={applyDerivedSnapshot}
                disabled={isSnapshotSaving}
                aria-busy={isSnapshotSaving}
                className="inline-flex min-w-[132px] items-center justify-center gap-2 rounded-lg bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isSnapshotSaving ? <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" /> : <CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
                {isSnapshotSaving ? "保存中" : "保存账户快照"}
              </button>
              <div
                role="status"
                aria-live="polite"
                className={`min-h-5 text-xs font-medium ${
                  snapshotSaveFeedback?.tone === "error"
                    ? "text-red-600 dark:text-red-400"
                    : snapshotSaveFeedback?.tone === "success"
                    ? "text-emerald-700 dark:text-emerald-300"
                    : "text-gray-500 dark:text-gray-400"
                }`}
              >
                {snapshotSaveFeedback?.message || "点击后会写入后端快照"}
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/40">
            <div>
              <p className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">4. 自动转换预览</p>
              <div className="grid gap-3 text-sm md:grid-cols-4">
                <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">汇丰现金</p>
                  <p className="font-semibold text-gray-900 dark:text-white">{money(derivedSnapshot.hsbcCashUsd)}</p>
                </div>
                <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">总权益</p>
                  <p className="font-semibold text-gray-900 dark:text-white">{money(derivedSnapshot.totalEquity)}</p>
                </div>
                <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">现金仓位</p>
                  <p className="font-semibold text-gray-900 dark:text-white">{money(derivedSnapshot.cashValue)}</p>
                </div>
                <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">定投仓位</p>
                  <p className="font-semibold text-gray-900 dark:text-white">{money(derivedSnapshot.dcaValue)}</p>
                </div>
              </div>
            </div>
            <p className="mt-3 text-xs leading-5 text-gray-500 dark:text-gray-400">
              口径：汇丰现金 = 汇丰总资产 - 汇丰投资市值；嘉信现金使用“现金转存计划账户”，不是“期权购买力/股票购买力”。截图里没有期权持仓时，Wheel 和 LEAPS 填 0。
            </p>
          </div>
        </Section>
        ) : null}
      </div>

      {shouldShow("overview", "profile") ? (
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Section title="账户结构" description="目标比例由年龄、收入状态和技术方案公式自动计算。">
          <div className="mb-5 flex flex-wrap gap-2 rounded-xl bg-gray-50 p-3 text-sm leading-6 text-gray-600 dark:bg-gray-900/50 dark:text-gray-300">
            {targetFormulaItems.map((item, index) => (
              <span key={item} className="rounded-lg bg-white px-3 py-1 dark:bg-gray-950/40">
                {index + 1}. {item}
              </span>
            ))}
          </div>
          <div className="space-y-5">
            <BucketRow name="定投仓位" actual={displaySnapshot.dca_value} target={displayTargets.dca_value} ratio={displayTargets.dca_ratio} />
            <BucketRow name="现金仓位" actual={displaySnapshot.cash_value} target={displayTargets.cash_value} ratio={displayTargets.cash_ratio} />
            <BucketRow name="期权仓位" actual={displaySnapshot.options_value} target={displayTargets.options_value} ratio={displayTargets.options_ratio} />
          </div>
        </Section>

        <Section title="关键红线" description="硬红线默认阻断高风险自动交易。">
          <div className="mb-4 flex flex-wrap gap-2 rounded-xl bg-gray-50 p-3 text-sm leading-6 text-gray-600 dark:bg-gray-900/50 dark:text-gray-300">
            {guardrailFormulaItems.map((item, index) => (
              <span key={item} className="rounded-lg bg-white px-3 py-1 dark:bg-gray-950/40">
                {index + 1}. {item}
              </span>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/50">
              <p className="text-gray-500 dark:text-gray-400">单股上限</p>
              <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(displayTargets.single_stock_limit)}</p>
            </div>
            <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/50">
              <p className="text-gray-500 dark:text-gray-400">保证金上限</p>
              <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(displayTargets.margin_limit)}</p>
            </div>
            <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/50">
              <p className="text-gray-500 dark:text-gray-400">Wheel 目标</p>
              <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(displayTargets.wheel_value)}</p>
            </div>
            <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/50">
              <p className="text-gray-500 dark:text-gray-400">LEAPS 目标</p>
              <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(displayTargets.leaps_value)}</p>
            </div>
          </div>
        </Section>
      </div>
      ) : null}

      {shouldShow("overview", "profile", "review") ? (
      <Section title="AI 解读" description="基于当前快照、目标仓位和关键红线生成的执行提示。">
        <div className="grid gap-4 xl:grid-cols-[0.7fr_1.3fr]">
          <div className={`rounded-xl border p-4 ${riskTone(dashboard.risk_level)}`}>
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              <p className="text-sm font-semibold">组合状态</p>
            </div>
            <p className="mt-3 text-2xl font-semibold">{dashboard.health_score}</p>
            <div className="mt-2 space-y-1 text-xs leading-5">
              <p>规则：{healthRuleText}</p>
              <p>当前：{healthCalcText}</p>
            </div>
          </div>
          <div className="space-y-2">
            {aiInsightParagraphs.map((item, index) => (
              <div key={`${index}-${item}`} className="rounded-xl bg-gray-50 p-3 text-sm leading-6 text-gray-700 dark:bg-gray-900/50 dark:text-gray-200">
                {item}
              </div>
            ))}
          </div>
        </div>
      </Section>
      ) : null}

      {shouldShow("wheel") ? (
        <Section title="Wheel 现金流" description="把 Cash-Secured Put 和 Covered Call 纳入账户纪律：只做愿意持有的标的，权利金先沉淀到现金流瀑布。">
          <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/40">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-gray-900 dark:text-white">当前 Wheel 状态</p>
                  <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
                    Wheel 不是稳定工资，而是一套“愿意买入、愿意持有、愿意按目标价卖出”的现金流流程。
                  </p>
                </div>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-gray-700 dark:bg-gray-950/40 dark:text-gray-200">
                  {wheelDisciplineState}
                </span>
              </div>
              <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">Wheel 上限</p>
                  <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(displayTargets.wheel_value)}</p>
                </div>
                <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">当前占用</p>
                  <p className="mt-1 font-semibold text-gray-900 dark:text-white">
                    {money(displaySnapshot.wheel_value)} / {pct(wheelUsageRatio)}
                  </p>
                </div>
                <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">可用额度</p>
                  <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(wheelAvailableCash)}</p>
                </div>
              </div>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-white dark:bg-gray-950/40">
                <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, Math.max(0, wheelUsageRatio * 100))}%` }} />
              </div>
              <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{wheelActionHint}</p>
            </div>

            <div className="rounded-xl border border-brand-200 bg-brand-50 p-4 dark:border-brand-900/60 dark:bg-brand-950/20">
              <div className="flex items-center gap-2">
                <CircleDollarSign className="h-4 w-4 text-brand-600 dark:text-brand-300" aria-hidden="true" />
                <p className="text-sm font-semibold text-gray-900 dark:text-white">已实现现金流</p>
              </div>
              <p className="mt-4 text-2xl font-semibold text-gray-900 dark:text-white">{money(wheelPremiumRealized)}</p>
              <div className="mt-3 space-y-2 text-xs leading-5 text-gray-500 dark:text-gray-400">
                <p>推荐流：{wheelCandidateText}</p>
                <p>记录口径：只统计已落地的 Wheel 权利金，不把期权占用当作利润。</p>
                <p>落地纪律：权利金先补现金仓位，现金已满后再注入定投仓位。</p>
              </div>
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/40">
            <div className="mb-4">
              <p className="text-sm font-semibold text-gray-900 dark:text-white">人工补录 / 审计 SOP</p>
              <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
                只补录工资定投、临时入金和线下修正；Wheel 与 LEAPS 流水应由券商流水或策略模块自动生成。
              </p>
            </div>
            <div className="grid gap-3 text-sm md:grid-cols-[1fr_1fr_auto]">
              <label className="space-y-1">
                <span className="text-gray-500 dark:text-gray-400">现金流事件</span>
                <select className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-transparent" value={cashflowType} onChange={(event) => setCashflowType(event.target.value)}>
                  <option value="cash_bucket_topup">临时入金</option>
                  <option value="dca_injection">工资定投</option>
                  <option value="manual_adjustment">人工调整</option>
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-gray-500 dark:text-gray-400">金额 USD</span>
                <input className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 dark:border-gray-800 dark:bg-transparent" value={cashflowAmount} onChange={(event) => setCashflowAmount(event.target.value)} placeholder="输入实际入金金额" />
              </label>
              <button type="button" onClick={saveCashflow} className="self-end rounded-lg bg-brand-500 px-5 py-2.5 font-semibold text-white hover:bg-brand-600">
                记录外部资金
              </button>
            </div>
            <div className="mt-4 grid gap-3 text-sm lg:grid-cols-4">
              {[
                ["1", "确认类型", "外部资金或线下修正"],
                ["2", "填写金额", "按 USD 记账口径录入"],
                ["3", "生成审计", "进入现金流事件记录"],
                ["4", "刷新快照", "在再平衡页复核偏离"],
              ].map(([step, title, state]) => (
                <div key={step} className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-950/30">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-500 text-xs font-semibold text-white">{step}</span>
                    <p className="font-semibold text-gray-900 dark:text-white">{title}</p>
                  </div>
                  <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{state}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-gray-200 p-4 dark:border-gray-800">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">Wheel 候选推荐</p>
                <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
                  入池逻辑：手动 Wheel 候选池优先，其次是优质个股白名单、当前持仓反向观察和系统内置观察池；再按账户可用 Wheel 额度、单股上限、保证金和集中度筛掉不适合实盘的标的。
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={async () => {
                    await refreshWheelCandidates();
                    await refreshWheelDailyRecommendation();
                    setStatusMessage("Wheel 候选推荐已刷新。");
                  }}
                  className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-900"
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  刷新推荐
                </button>
                <a
                  href="/smart-allocation/wheel/recommendations"
                  className="inline-flex items-center rounded-lg border border-gray-200 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-900"
                >
                  每日推荐页
                </a>
              </div>
            </div>
            {wheelPoolSources.length ? (
              <div className="mb-4 grid gap-2 text-xs md:grid-cols-2 xl:grid-cols-4">
                {wheelPoolSources.map((source) => (
                  <div key={source.name} className="rounded-lg bg-gray-50 p-3 text-gray-600 dark:bg-gray-900/50 dark:text-gray-300">
                    <p className="font-semibold text-gray-900 dark:text-white">{source.name} · {source.count}</p>
                    <p className="mt-1 leading-5">{source.rule}</p>
                  </div>
                ))}
              </div>
            ) : null}
            <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
              <div className="grid min-w-[900px] grid-cols-[1fr_90px_1fr_1fr_1.3fr] bg-gray-50 px-4 py-3 text-xs font-semibold text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">
                <span>标的</span>
                <span>评分</span>
                <span>预计现金担保</span>
                <span>状态</span>
                <span>推荐依据</span>
              </div>
              {topWheelCandidates.map((item) => (
                <div key={item.symbol} className="grid min-w-[900px] grid-cols-[1fr_90px_1fr_1fr_1.3fr] gap-3 border-t border-gray-200 px-4 py-3 text-sm text-gray-700 dark:border-gray-800 dark:text-gray-200">
                  <div>
                    <p className="font-semibold text-gray-900 dark:text-white">{item.symbol}</p>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{item.source}</p>
                  </div>
                  <span className="font-semibold text-gray-900 dark:text-white">{item.score}</span>
                  <div>
                    <p>{money(item.estimated_cash_required)}</p>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">可做 {item.max_contracts} 张</p>
                  </div>
                  <span className={`self-start rounded-full px-2.5 py-1 text-xs font-semibold ${wheelStatusTone(item.status)}`}>
                    {item.status}
                  </span>
                  <div className="text-xs leading-5 text-gray-500 dark:text-gray-400">
                    <p>{item.reason}</p>
                    {item.blockers.length ? <p className="mt-1 text-red-600 dark:text-red-300">{item.blockers[0]}</p> : null}
                  </div>
                </div>
              ))}
              {topWheelCandidates.length === 0 ? (
                <p className="border-t border-gray-200 px-4 py-3 text-sm text-gray-500 dark:border-gray-800 dark:text-gray-400">
                  暂无候选数据。点击刷新推荐，系统会先基于规则观察池生成一批待核验标的。
                </p>
              ) : null}
            </div>
          </div>

          <div className="mt-5 grid gap-3 text-sm lg:grid-cols-4">
            {wheelFlowItems.map((item, index) => (
              <div key={item.title} className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-500 text-xs font-semibold text-white">{index + 1}</span>
                  {index < wheelFlowItems.length - 1 ? <ArrowRight className="h-4 w-4 text-gray-400" aria-hidden="true" /> : <RotateCcw className="h-4 w-4 text-gray-400" aria-hidden="true" />}
                </div>
                <p className="font-semibold text-gray-900 dark:text-white">{item.title}</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{item.subtitle}</p>
                <p className="mt-3 text-xs leading-5 text-gray-600 dark:text-gray-300">{item.detail}</p>
              </div>
            ))}
          </div>

          <div className="mt-5 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
              <div className="mb-3 flex items-center gap-2">
                <ClipboardCheck className="h-4 w-4 text-gray-500 dark:text-gray-400" aria-hidden="true" />
                <p className="text-sm font-semibold text-gray-900 dark:text-white">交易前检查</p>
              </div>
              <div className="space-y-3 text-sm">
                {WHEEL_CHECKLIST_ITEMS.map((item) => (
                  <div key={item} className="flex gap-2 text-gray-600 dark:text-gray-300">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-300" aria-hidden="true" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
              <div className="mb-3 flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-gray-500 dark:text-gray-400" aria-hidden="true" />
                <p className="text-sm font-semibold text-gray-900 dark:text-white">风险阻断</p>
              </div>
              <div className="grid gap-3 text-sm md:grid-cols-2">
                {wheelRiskItems.map((item) => (
                  <div key={item.label} className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/50">
                    <p className="font-semibold text-gray-900 dark:text-white">{item.label}</p>
                    <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">{item.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-5 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
              <p className="text-sm font-semibold text-gray-900 dark:text-white">开仓与平仓参数</p>
              <div className="mt-3 grid gap-3 text-sm md:grid-cols-3">
                <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/50">
                  <p className="text-gray-500 dark:text-gray-400">Cash-Secured Put</p>
                  <p className="mt-1 font-semibold text-gray-900 dark:text-white">30-45 DTE / Delta 0.20-0.30</p>
                </div>
                <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/50">
                  <p className="text-gray-500 dark:text-gray-400">Covered Call</p>
                  <p className="mt-1 font-semibold text-gray-900 dark:text-white">优先高于调整后成本</p>
                </div>
                <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/50">
                  <p className="text-gray-500 dark:text-gray-400">盈利处理</p>
                  <p className="mt-1 font-semibold text-gray-900 dark:text-white">50%-80% 浮盈可平仓</p>
                </div>
              </div>
              <p className="mt-3 text-xs leading-5 text-gray-500 dark:text-gray-400">
                这些是保守起点，不是自动下单信号；真正的前置条件是愿意以 strike 买入、被指派后仓位仍可承受、且事件风险已被确认。
              </p>
            </div>

            <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
              <p className="text-sm font-semibold text-gray-900 dark:text-white">Wheel 记录字段</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {WHEEL_RECORD_FIELDS.map((item) => (
                  <span key={item} className="rounded-lg bg-gray-50 px-3 py-1.5 text-xs font-semibold text-gray-600 dark:bg-gray-900/50 dark:text-gray-300">
                    {item}
                  </span>
                ))}
              </div>
              <p className="mt-3 text-xs leading-5 text-gray-500 dark:text-gray-400">
                重点维护 adjusted_cost：Put 权利金、Call 权利金、指派和费用都要进入同一轮 cycle，避免误判真实盈亏。
              </p>
            </div>
          </div>
        </Section>
      ) : null}

      {shouldShow("wheelRecommendations") ? (
        <Section title="每日 Wheel 推荐" description="每日任务先做账户级候选过滤，再等待真实期权链扫描接入后补全可交易信号。">
          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/40">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-gray-900 dark:text-white">今日扫描</p>
                  <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
                    扫描日期 {wheelDailyRecommendation?.scan_date ?? "待刷新"}；当前账户权益 {money(wheelDailyRecommendation?.account_equity ?? displaySnapshot.total_equity)}。
                  </p>
                </div>
                <button
                  type="button"
                  onClick={async () => {
                    await refreshWheelDailyRecommendation();
                    await refreshWheelCandidates();
                    setStatusMessage("每日 Wheel 推荐已刷新。");
                  }}
                  className="inline-flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600"
                >
                  <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  刷新扫描
                </button>
              </div>
              <div className="mt-4 grid gap-3 text-sm sm:grid-cols-4">
                <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">Wheel 目标</p>
                  <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(wheelDailyRecommendation?.wheel_target ?? displayTargets.wheel_value)}</p>
                </div>
                <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">可用额度</p>
                  <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(wheelDailyRecommendation?.wheel_available ?? wheelAvailableCash)}</p>
                </div>
                <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">可核验</p>
                  <p className="mt-1 font-semibold text-gray-900 dark:text-white">{wheelDailyRecommendation?.actionable_count ?? candidateWheelCount}</p>
                </div>
                <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">观察候选</p>
                  <p className="mt-1 font-semibold text-gray-900 dark:text-white">{wheelDailyRecommendation?.candidate_count ?? wheelCandidates.length}</p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-brand-200 bg-brand-50 p-4 dark:border-brand-900/60 dark:bg-brand-950/20">
              <p className="text-sm font-semibold text-gray-900 dark:text-white">MRVL 专项判断</p>
              <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{mrvlAccountText}</p>
              {mrvlCandidate?.blockers.length ? (
                <div className="mt-3 space-y-1 text-xs leading-5 text-red-600 dark:text-red-300">
                  {mrvlCandidate.blockers.map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className="mt-5 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
            {(wheelDailyRecommendation?.pool_sources ?? wheelPoolSources).map((source) => (
              <div key={source.name} className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
                <p className="font-semibold text-gray-900 dark:text-white">{source.name}</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{source.count} 个标的</p>
                <p className="mt-3 text-xs leading-5 text-gray-600 dark:text-gray-300">{source.rule}</p>
                <p className="mt-3 line-clamp-2 text-xs text-gray-500 dark:text-gray-400">{source.symbols.join(", ") || "暂无"}</p>
              </div>
            ))}
          </div>

          <div className="mt-5 overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
            <div className="grid min-w-[980px] grid-cols-[1fr_90px_1fr_1fr_1.4fr] bg-gray-50 px-4 py-3 text-xs font-semibold text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">
              <span>标的</span>
              <span>评分</span>
              <span>预计现金担保</span>
              <span>状态</span>
              <span>账户级结论</span>
            </div>
            {(wheelDailyRecommendation?.candidates ?? wheelCandidates).map((item) => (
              <div key={item.symbol} className="grid min-w-[980px] grid-cols-[1fr_90px_1fr_1fr_1.4fr] gap-3 border-t border-gray-200 px-4 py-3 text-sm text-gray-700 dark:border-gray-800 dark:text-gray-200">
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">{item.symbol}</p>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{item.source}</p>
                </div>
                <span className="font-semibold text-gray-900 dark:text-white">{item.score}</span>
                <div>
                  <p>{money(item.estimated_cash_required)}</p>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">可做 {item.max_contracts} 张</p>
                </div>
                <span className={`self-start rounded-full px-2.5 py-1 text-xs font-semibold ${wheelStatusTone(item.status)}`}>
                  {item.status}
                </span>
                <div className="text-xs leading-5 text-gray-500 dark:text-gray-400">
                  <p>{item.reason}</p>
                  {item.blockers.map((blocker) => (
                    <p key={blocker} className="mt-1 text-red-600 dark:text-red-300">{blocker}</p>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-5 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/40">
            <p className="text-sm font-semibold text-gray-900 dark:text-white">每日任务链路</p>
            <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
              {(wheelDailyRecommendation?.methodology ?? []).map((item) => (
                <div key={item} className="rounded-lg bg-white p-3 text-gray-600 dark:bg-gray-950/40 dark:text-gray-300">
                  {item}
                </div>
              ))}
            </div>
          </div>
        </Section>
      ) : null}

      {shouldShow("waterfall", "overview", "guardrails", "review") ? (
      <div className={isDedicatedWaterfallView ? "grid gap-6" : "grid gap-6 xl:grid-cols-2"}>
        {shouldShow("waterfall") ? (
        <Section title="现金流瀑布" description="基于真实账户快照判断现金安全垫；只有已发生的 Wheel 权利金和 LEAPS 已实现盈利才进入瀑布分配。">
          <div className="grid gap-4 xl:grid-cols-3">
            <div className={`rounded-xl border p-4 ${statusCardTone(optionProfitStatus)}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">期权利润池</p>
                  <p className="mt-1 text-xs opacity-80">只统计已发生的 Wheel 权利金 / LEAPS 已实现盈利</p>
                </div>
                <span className="rounded-full bg-white/70 px-2.5 py-1 text-xs font-semibold dark:bg-gray-950/30">{statusText(optionProfitStatus)}</span>
              </div>
              <p className="mt-4 text-2xl font-semibold">{money(waterfallPreview.amountValue)}</p>
              <div className="mt-4 space-y-2 text-xs opacity-80">
                <p>Wheel：{money(displaySnapshot.wheel_value)}，{optionIncomeStage}</p>
                <p>LEAPS：{money(displaySnapshot.leaps_value)}，{leapsStage}</p>
                <p>账户期权仓位：{money(displaySnapshot.options_value)}，不等于可分配利润</p>
              </div>
            </div>
            <div className={`rounded-xl border p-4 ${statusCardTone(cashBucketStatus)}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">现金池</p>
                  <p className="mt-1 text-xs opacity-80">安全垫 / LEAPS 等待区</p>
                </div>
                <span className="rounded-full bg-white/70 px-2.5 py-1 text-xs font-semibold dark:bg-gray-950/30">{statusText(cashBucketStatus)}</span>
              </div>
              <p className="mt-4 text-2xl font-semibold">{money(displaySnapshot.cash_value)}</p>
              <div className="mt-4 space-y-2 text-xs opacity-80">
                <p>目标：{money(displayTargets.cash_value)}，{cashStage}</p>
                <p>缺口：{money(waterfallPreview.cashGap)}</p>
                <p>本次可补：{money(waterfallPreview.cashTopup)}</p>
              </div>
            </div>
            <div className={`rounded-xl border p-4 ${statusCardTone(dcaBucketStatus)}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">定投池</p>
                  <p className="mt-1 text-xs opacity-80">QQQM / VOO / 优质个股</p>
                </div>
                <span className="rounded-full bg-white/70 px-2.5 py-1 text-xs font-semibold dark:bg-gray-950/30">{statusText(dcaBucketStatus)}</span>
              </div>
              <p className="mt-4 text-2xl font-semibold">{money(displaySnapshot.dca_value)}</p>
              <div className="mt-4 space-y-2 text-xs opacity-80">
                <p>目标：{money(displayTargets.dca_value)}，{dcaStage}</p>
                <p>期权利润溢出：{money(waterfallPreview.dcaOverflow)}</p>
                {hasBlockingSingleStock ? <p>单股集中度触发阻断，先处理超限标的。</p> : null}
              </div>
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/40">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">外部收入分配 SOP</p>
                <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
                  工资、奖金和临时入金先按新总权益重算目标：补现金缺口，再补定投缺口，剩余才进入期权策略待机资金。
                </p>
              </div>
              <div className="grid gap-2 text-sm sm:grid-cols-2">
                <label className="space-y-1">
                  <span className="text-xs text-gray-500 dark:text-gray-400">本次收入 CNY</span>
                  <input
                    className="h-10 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-brand-500 dark:border-gray-800 dark:bg-gray-950/40 dark:text-white"
                    value={externalIncomeForm.incomeCny}
                    onChange={(event) => setExternalIncomeForm((current) => ({ ...current, incomeCny: event.target.value }))}
                  />
                </label>
                <div className="space-y-1">
                  <span className="text-xs text-gray-500 dark:text-gray-400">系统汇率</span>
                  <div className="flex h-10 w-full items-center rounded-lg border border-gray-200 bg-white px-3 text-sm font-medium text-gray-500 dark:border-gray-800 dark:bg-gray-950/40 dark:text-gray-400">
                    1 USD = {externalIncomePlan.cnyUsdRate.toFixed(2)} CNY
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-4 grid gap-3 text-sm md:grid-cols-4">
              <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                <p className="text-gray-500 dark:text-gray-400">折算金额</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(externalIncomePlan.incomeUsd)}</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{yuan(externalIncomePlan.incomeCny)}</p>
              </div>
              <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                <p className="text-gray-500 dark:text-gray-400">入金后总权益</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(externalIncomePlan.nextTotalEquity)}</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">现金目标 {money(externalIncomePlan.nextTargets.cash_value)}</p>
              </div>
              <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                <p className="text-gray-500 dark:text-gray-400">定投目标</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(externalIncomePlan.nextTargets.dca_value)}</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">当前 {money(displaySnapshot.dca_value)}</p>
              </div>
              <div className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                <p className="text-gray-500 dark:text-gray-400">期权目标</p>
                <p className="mt-1 font-semibold text-gray-900 dark:text-white">{money(externalIncomePlan.nextTargets.options_value)}</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">当前 {money(displaySnapshot.options_value)}</p>
              </div>
            </div>

            <div className="mt-4 overflow-x-auto rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950/30">
              <div className="grid min-w-[980px] grid-cols-[150px_1fr_1fr_1fr_1.5fr] bg-gray-50 px-4 py-3 text-xs font-semibold text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">
                <span>去向</span>
                <span>美元金额</span>
                <span>人民币金额</span>
                <span>变动后仓位</span>
                <span>纪律说明</span>
              </div>
              {externalIncomePlan.rows.map((row) => (
                <div key={row.bucket} className="grid min-w-[980px] grid-cols-[150px_1fr_1fr_1fr_1.5fr] gap-3 border-t border-gray-200 px-4 py-3 text-sm text-gray-700 dark:border-gray-800 dark:text-gray-200">
                  <span className="font-semibold text-gray-900 dark:text-white">{row.bucket}</span>
                  <span>{money(row.amountUsd)}</span>
                  <span>{yuan(row.amountCny)}</span>
                  <span>{money(row.afterValue)} / {pct(row.afterRatio)}，目标 {money(row.targetValue)}</span>
                  <span className="text-gray-500 dark:text-gray-400">{row.rule}</span>
                </div>
              ))}
            </div>

            <div className="mt-4 grid gap-3 text-sm lg:grid-cols-5">
              {[
                ["1", "记录入金", `${yuan(externalIncomePlan.incomeCny)} / ${money(externalIncomePlan.incomeUsd)}`],
                ["2", "补现金", externalIncomePlan.cashTopup > 0 ? money(externalIncomePlan.cashTopup) : "跳过"],
                ["3", "补定投", externalIncomePlan.dcaTopup > 0 ? money(externalIncomePlan.dcaTopup) : "跳过"],
                ["4", "策略待机", money(externalIncomePlan.optionsWaiting)],
                ["5", "再核验", `Wheel ${money(externalIncomePlan.wheelWaiting)} / LEAPS ${money(externalIncomePlan.leapsWaiting)}`],
              ].map(([step, title, state]) => (
                <div key={step} className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-950/30">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-500 text-xs font-semibold text-white">{step}</span>
                    <p className="font-semibold text-gray-900 dark:text-white">{title}</p>
                  </div>
                  <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{state}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/40">
            <div>
              <p className="text-sm font-semibold text-gray-900 dark:text-white">期权利润分配 SOP</p>
              <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
                只处理已实现的 Wheel 权利金和 LEAPS 已实现盈利；没有已实现利润时，只展示状态，不生成补现金或定投注入动作。
              </p>
            </div>
            <div className="mt-4 grid gap-3 text-sm md:grid-cols-4">
              {[
                ["已实现利润", money(waterfallPreview.amountValue), waterfallPreview.amountValue > 0 ? "可分配" : "暂无可分配利润"],
                ["现金缺口", money(waterfallPreview.cashGap), waterfallPreview.cashGap > 0 ? "优先补现金" : "现金已达标"],
                ["本次补现金", money(waterfallPreview.cashTopup), waterfallPreview.cashTopup > 0 ? "先补安全垫" : "跳过"],
                ["可注入定投", money(waterfallPreview.dcaOverflow), waterfallPreview.dcaOverflow > 0 ? "再拆 QQQM/VOO/个股" : "暂无溢出"],
              ].map(([label, value, hint]) => (
                <div key={label} className="rounded-lg bg-white p-3 dark:bg-gray-950/40">
                  <p className="text-gray-500 dark:text-gray-400">{label}</p>
                  <p className="mt-1 font-semibold text-gray-900 dark:text-white">{value}</p>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{hint}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 grid gap-3 text-sm lg:grid-cols-6">
              {[
                ["1", "确认来源", "Wheel / LEAPS 已实现"],
                ["2", "先进现金池", cashStage],
                ["3", "等待纪律", "满足 RSI 才买 LEAPS"],
                ["4", "LEAPS 持仓", leapsStage],
                ["5", "盈利退出", "先回现金池"],
                ["6", "定投注入", dcaStage],
              ].map(([step, title, state]) => (
                <div key={step} className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-950/30">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-500 text-xs font-semibold text-white">{step}</span>
                    <p className="font-semibold text-gray-900 dark:text-white">{title}</p>
                  </div>
                  <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{state}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950/30">
              <div className="grid grid-cols-[80px_1.1fr_1fr_1fr] bg-gray-50 px-4 py-3 text-xs font-semibold text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">
                <span>顺序</span>
                <span>触发条件</span>
                <span>本次动作</span>
                <span>落地账户/纪律</span>
              </div>
              {[
                {
                  step: "1",
                  condition: "系统存在已发生的 Wheel 权利金或 LEAPS 已实现盈利",
                  action: `补现金 ${money(waterfallPreview.cashTopup)}`,
                  target: waterfallPreview.cashGap > 0 ? "先补满现金仓位，避免被迫卖资产" : "现金已达标，本步骤跳过",
                },
                {
                  step: "2",
                  condition: "现金仓位已补满后仍有溢出",
                  action: `可注入定投 ${money(waterfallPreview.dcaOverflow)}`,
                  target: "期权利润不回流期权池，避免风险滚大",
                },
                {
                  step: "3",
                  condition: "定投注入按技术方案拆分",
                  action: `QQQM ${money(waterfallPreview.qqqm)} / VOO ${money(waterfallPreview.voo)} / 优质个股 ${money(waterfallPreview.quality)}`,
                  target: "个股买入前检查单股上限和白名单",
                },
              ].map((item) => (
                <div key={item.step} className="grid grid-cols-[80px_1.1fr_1fr_1fr] gap-3 border-t border-gray-200 px-4 py-3 text-sm text-gray-700 dark:border-gray-800 dark:text-gray-200">
                  <span className="font-semibold text-gray-900 dark:text-white">{item.step}</span>
                  <span>{item.condition}</span>
                  <span>{item.action}</span>
                  <span>{item.target}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/40">
            <div className="mb-4">
              <p className="text-sm font-semibold text-gray-900 dark:text-white">人工补录 / 审计 SOP</p>
              <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
                只补录工资定投、临时入金和线下修正；Wheel 与 LEAPS 流水应由券商流水或策略模块自动生成。
              </p>
            </div>
            <div className="grid gap-3 text-sm md:grid-cols-[1fr_1fr_auto]">
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400">
                现金流事件
                <select
                  value={cashflowType}
                  onChange={(event) => setCashflowType(event.target.value)}
                  className="mt-1 h-11 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-brand-500 dark:border-gray-800 dark:bg-gray-950 dark:text-white"
                >
                  <option value="external_deposit">临时入金</option>
                  <option value="salary_dca">工资定投</option>
                  <option value="manual_adjustment">线下修正</option>
                </select>
              </label>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400">
                金额 USD
                <input
                  value={cashflowAmount}
                  onChange={(event) => setCashflowAmount(event.target.value)}
                  placeholder="输入实际入金金额"
                  className="mt-1 h-11 w-full rounded-lg border border-gray-200 bg-white px-3 text-sm text-gray-900 outline-none focus:border-brand-500 dark:border-gray-800 dark:bg-gray-950 dark:text-white"
                />
              </label>
              <button
                type="button"
                onClick={saveCashflow}
                className="h-11 self-end rounded-lg bg-brand-500 px-4 text-sm font-semibold text-white hover:bg-brand-600"
              >
                记录外部资金
              </button>
            </div>
            <div className="mt-4 grid gap-3 text-sm lg:grid-cols-4">
              {[
                ["1", "确认类型", "外部资金或线下修正"],
                ["2", "填写金额", "按 USD 记账口径录入"],
                ["3", "生成审计", "进入现金流事件记录"],
                ["4", "刷新快照", "在再平衡页复核偏离"],
              ].map(([step, title, state]) => (
                <div key={step} className="rounded-xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-gray-950/30">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-500 text-xs font-semibold text-white">{step}</span>
                    <p className="font-semibold text-gray-900 dark:text-white">{title}</p>
                  </div>
                  <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{state}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-5 rounded-xl border border-gray-200 p-4 dark:border-gray-800">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">审计记录</p>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">保存账户快照会自动产生瀑布审计；人工补录也会进入这里。</p>
              </div>
              <button type="button" onClick={refreshCashflowEvents} className="rounded-lg border border-gray-200 px-3 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-900">
                刷新审计
              </button>
            </div>
            <div className="space-y-2">
              {cashflowEvents.slice(0, 6).map((item) => (
                <div key={`${item.created_at}-${item.event_type}`} className="grid gap-2 rounded-xl bg-gray-50 p-3 text-sm text-gray-700 dark:bg-gray-900/50 dark:text-gray-200 md:grid-cols-[160px_120px_1fr]">
                  <span className="font-semibold text-gray-900 dark:text-white">{cashflowAuditText(item.event_type)}</span>
                  <span>{money(item.amount)}</span>
                  <span>{item.note || `${item.source_bucket} -> ${item.target_bucket}`}</span>
                </div>
              ))}
              {cashflowEvents.length === 0 ? (
                <p className="rounded-xl bg-gray-50 p-3 text-sm text-gray-500 dark:bg-gray-900/50 dark:text-gray-400">
                  暂无审计记录。保存一次账户快照后，系统会自动生成第一条瀑布审计。
                </p>
              ) : null}
            </div>
          </div>

          {cashflowTransfers.length ? (
            <div className="mt-5 space-y-2 text-sm">
              <p className="font-semibold text-gray-900 dark:text-white">已生成流水</p>
              {cashflowTransfers.map((item) => (
                <div key={`${item.target_bucket}-${item.target_sub_bucket ?? "cash"}`} className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/50">
                  {money(item.amount)} {"->"} {item.target_bucket}{item.target_sub_bucket ? ` / ${item.target_sub_bucket}` : ""}：{item.reason}
                </div>
              ))}
            </div>
          ) : null}
        </Section>
        ) : null}

        {shouldShow("overview", "guardrails", "review") ? (
        <Section title="风控巡检" description="当前账户快照触发的规则。">
          <div className="space-y-3">
            {dashboard.guardrails.length ? (
              dashboard.guardrails.map((item) => <GuardrailRow key={`${item.rule_code}-${item.message}`} item={item} />)
            ) : (
              <p className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">
                当前快照未触发风控红线。
              </p>
            )}
          </div>
        </Section>
        ) : null}
      </div>
      ) : null}

      {shouldShow("overview", "rebalance", "review") ? (
      <Section title="再平衡建议" description="偏离目标仓位达到阈值后生成。">
        <div className="space-y-3">
          {dashboard.recommendations.length ? (
            dashboard.recommendations.map((item) => (
              <div key={item.id} className="space-y-2">
                <RecommendationRow item={item} />
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => updateRecommendation(item.id, "ignore")} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-900">
                    忽略
                  </button>
                  <button type="button" onClick={() => updateRecommendation(item.id, "mark-executed")} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-gray-700 dark:bg-white dark:text-gray-900">
                    标记已执行
                  </button>
                </div>
              </div>
            ))
          ) : (
            <p className="rounded-xl bg-gray-50 p-4 text-sm text-gray-600 dark:bg-gray-900/50 dark:text-gray-300">
              当前无需再平衡。下一步可接入真实券商快照和 Wheel/LEAPS 流水。
            </p>
          )}
        </div>
      </Section>
      ) : null}

      {shouldShow("leaps") ? (
      <Section title="LEAPS 候选池" description="默认 RSI < 35 才进入可研究；牛市放宽时 RSI < 40 仅观察。">
        <button type="button" onClick={refreshLeaps} className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600">
          刷新候选
        </button>
        <div className="mt-4 space-y-2">
          {leapsCandidates.map((item) => (
            <div key={item.symbol} className="rounded-xl border border-gray-200 p-3 text-sm dark:border-gray-800">
              <span className="font-semibold text-gray-900 dark:text-white">{item.symbol}</span>
              <span className="ml-3 text-gray-500 dark:text-gray-400">RSI {item.rsi}</span>
              <span className="ml-3 text-brand-600 dark:text-brand-300">{item.status}</span>
              <p className="mt-1 text-gray-500 dark:text-gray-400">{item.reason}</p>
            </div>
          ))}
        </div>
      </Section>
      ) : null}

      {shouldShow("review") ? (
        <Section title="季度复盘" description="每三个月检查一次，偏离目标超过 5% 就进入再平衡处理。">
          <div className="grid gap-3 text-sm md:grid-cols-2">
            {[
              "确认总资产、现金、定投、期权口径是否一致。",
              "检查现金仓位是否低于目标。",
              "检查期权利润是否仍滞留在期权池。",
              "检查单股是否超过定投仓位 10%。",
              "检查保证金是否触碰 25% 红线。",
              "检查 LEAPS 是否只在 RSI 纪律区间内新增。",
            ].map((item) => (
              <div key={item} className="rounded-xl border border-gray-200 p-3 text-gray-600 dark:border-gray-800 dark:text-gray-300">
                {item}
              </div>
            ))}
          </div>
        </Section>
      ) : null}
    </div>
  );
}
