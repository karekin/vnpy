"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import type { ApexOptions } from "apexcharts";

const ReactApexChart = dynamic(() => import("react-apexcharts"), { ssr: false });
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import { createDiscoverCandidate, createWatchlistEntry, getTenxErrorMessage, loadTenxStrategyBacktest, uploadTenxResearchReport } from "@/components/tenx-hunter/api";
import { CandidateFlowTag } from "@/components/tenx-hunter/TenxFlowStatus";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { getRiskTone, getStageTone, TenxSectionCard } from "@/components/tenx-hunter/TenxCards";
import type { TenxEarningsLens, TenxEarningsOptionItem, TenxEarningsShortlineItem, TenxFlowStatus, TenxStrategyBacktestData, TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";
import { BellRing, Binoculars, BookOpen, ChevronDown, ChevronRight, FileUp, Plus, Search } from "lucide-react";

const stageOptions = ["all", "discovery", "validation", "acceleration", "crowded", "falsified"] as const;
const flowOptions: Array<"all" | TenxFlowStatus> = ["all", "candidate", "watch-ready", "watching", "alerting", "blocked"];
const pageSizeOptions = [5, 10];

type Props = {
  snapshot: TenxWorkspaceSnapshot;
  earningsLens?: TenxEarningsLens | null;
  earningsLensError?: string | null;
};

/* ── 财报/期权工具函数（来自 TenxDiscoverEarningsDesk） ── */

type ForecastTone = "green" | "yellow" | "red" | "blue" | "slate";

function normalizeVol(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  return Math.abs(value) > 2 ? value / 100 : value;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function fmtNum(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function fmtCompact(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  if (Math.abs(value) >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return fmtNum(value);
}

function fmtCurrency(value: number | null | undefined, currency = "USD") {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  const prefix = currency === "CNY" ? "¥" : "$";
  return `${prefix}${fmtCompact(value)}`;
}

function fmtPercent(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  return `${(value * 100).toFixed(digits)}%`;
}

function fmtSignedPercent(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
}

function fmtStrike(value: number | null | undefined, currency = "USD") {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  const prefix = currency === "CNY" ? "¥" : "$";
  return `${prefix}${value >= 100 ? value.toFixed(0) : value.toFixed(1)}`;
}

function dayLabel(days?: number | null) {
  if (days === null || days === undefined) return "未知";
  if (days < 0) return "已过";
  if (days === 0) return "TODAY";
  return `T-${days}`;
}

function dayTone(days?: number | null): ForecastTone {
  if (days === null || days === undefined || days < 0) return "slate";
  if (days <= 3) return "red";
  if (days <= 10) return "yellow";
  return "blue";
}

function roundStrike(price: number) {
  if (price >= 500) return Math.round(price / 5) * 5;
  if (price >= 100) return Math.round(price / 2.5) * 2.5;
  if (price >= 20) return Math.round(price);
  return Math.round(price * 2) / 2;
}

type EventForecast = {
  directionLabel: string;
  directionTone: ForecastTone;
  optionSide: "CALL" | "PUT" | "VOL";
  expectedMove: number | null;
  winProbability: number | null;
  strike: number | null;
  sellStrike: number | null;
  premium: number | null;
  spreadDebit: number | null;
};

function buildForecast(shortline: TenxEarningsShortlineItem, option?: TenxEarningsOptionItem): EventForecast {
  if (!option || option.dataQualityFlag !== "ok") {
    return { directionLabel: "待补", directionTone: "slate", optionSide: "VOL", expectedMove: null, winProbability: null, strike: null, sellStrike: null, premium: null, spreadDebit: null };
  }
  let ds = 0;
  if (option.flowSentiment === "bullish") ds += 2;
  if (option.flowSentiment === "bearish") ds -= 2;
  if ((option.callPutVolumeRatio ?? 1) >= 1.25) ds += 1;
  if ((option.callPutVolumeRatio ?? 1) <= 0.8) ds -= 1;
  if (shortline.scoreChange >= 2) ds += 1;
  if (shortline.scoreChange <= -2) ds -= 1;

  const iv = normalizeVol(option.avgImpliedVolatility);
  const horizon = clamp(shortline.daysToEarnings ?? 7, 1, 30);
  const em = iv === null ? null : iv * Math.sqrt(horizon / 365);
  const sel = option.optionSelectionScore ?? option.liquidityScore ?? null;
  const liqAdj = option.liquidityScore ? clamp((option.liquidityScore - 50) / 5, -6, 8) : 0;
  const dirAdj = Math.abs(ds) >= 2 ? 4 : 0;
  const wp = sel === null ? null : clamp(43 + sel * 0.34 + liqAdj + dirAdj, 35, 86);

  const u = option.underlyingPrice ?? null;
  const side: EventForecast["optionSide"] = ds >= 2 ? "CALL" : ds <= -2 ? "PUT" : "VOL";
  const mfs = em ?? 0.08;
  const strike = u === null ? option.maxPainStrike ?? null : side === "PUT" ? roundStrike(u * (1 - mfs * 0.45)) : side === "CALL" ? roundStrike(u * (1 + mfs * 0.45)) : roundStrike(u);
  const sellStrike = u === null || strike === null ? null : side === "PUT" ? roundStrike(strike * (1 - mfs * 0.85)) : roundStrike(strike * (1 + mfs * 0.85));
  const premium = u === null ? null : u * mfs * (side === "VOL" ? 0.32 : 0.22);
  const spreadDebit = u === null ? null : u * mfs * 0.09;

  const tone: ForecastTone = ds >= 2 ? "green" : ds <= -2 ? "red" : "yellow";
  const label = ds >= 2 ? "偏多" : ds <= -2 ? "偏空" : "波动";
  return { directionLabel: label, directionTone: tone, optionSide: side, expectedMove: em, winProbability: wp, strike, sellStrike, premium, spreadDebit };
}

/* ── 小组件 ── */

function ScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? "#16a34a" : score >= 65 ? "#d97706" : "#64748b";
  return (
    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full" style={{ background: `conic-gradient(${color} ${clamp(score, 0, 100) * 3.6}deg, #e5e7eb 0deg)` }} aria-label={`score ${score}`}>
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-sm font-bold text-gray-900 dark:bg-gray-950 dark:text-white">{score}</div>
    </div>
  );
}

function StrategyRow({ label, values, muted }: { label: string; values: string[]; muted?: boolean }) {
  return (
    <div className={`grid grid-cols-[80px_repeat(5,minmax(0,1fr))] border-b border-gray-200 text-xs last:border-b-0 dark:border-gray-800 ${muted ? "bg-gray-50/80 dark:bg-gray-900/40" : ""}`}>
      <div className="flex items-center border-r border-gray-200 px-2 py-1.5 font-semibold text-gray-700 dark:border-gray-800 dark:text-gray-200">{label}</div>
      {values.map((v, i) => (
        <div key={`${label}-${i}`} className="min-w-0 border-r border-gray-200 px-2 py-1.5 text-gray-600 last:border-r-0 dark:border-gray-800 dark:text-gray-300">
          <span className="block truncate">{v}</span>
        </div>
      ))}
    </div>
  );
}

function ForecastCell({ label, value, tone = "slate" }: { label: string; value: string; tone?: ForecastTone }) {
  const cls = tone === "green" ? "text-green-600 dark:text-green-300" : tone === "red" ? "text-red-600 dark:text-red-300" : tone === "yellow" ? "text-yellow-600 dark:text-yellow-300" : "text-gray-900 dark:text-white";
  return (
    <div className="min-w-0 rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-900/60">
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`mt-0.5 truncate text-sm font-semibold ${cls}`}>{value}</div>
    </div>
  );
}

/* ── 期权策略引擎 ── */

/* ── 期权策略 Payoff 参数（纯数值，用于到期盈亏图计算） ── */

type StrategyPayoffParams = {
  S: number;           // 标的现价
  iv: number;          // 隐含波动率（年化，如 0.40）
  days: number;        // 到期天数
  sigma1: number;      // 1σ 价格变动 = S * iv * sqrt(days/365)
  legs: Array<{
    type: "call" | "put" | "stock";
    strike: number;     // 行权价（stock 时为入场价）
    premium: number;    // 权利金（买入为正，卖出为负净值）
    qty: number;        // +1=long, -1=short
  }>;
  breakevenPoints: number[];
  maxProfitValue: number | null;  // null=无限
  maxLossValue: number | null;
};

type OptionStrategy = {
  key: string;
  name: string;
  nameEn: string;
  direction: string;
  directionTone: ForecastTone;
  winProb: number;
  maxProfit: string;
  maxLoss: string;
  breakeven: string;
  strikes: string;
  premium: string;
  logic: string;
  rank: number;
  /* 回测数据（懒加载） */
  backtestWinRate?: number | null;
  backtestTotalTrades?: number | null;
  backtestLogic?: string | null;
  backtestProfitFactor?: number | null;
  backtestStreak?: string | null;
  /* LLM 增强分析 */
  llmRecommendation?: string | null;
  llmConfidence?: string | null;
  llmLogic?: string | null;
  llmKeyRisks?: string[] | null;
  /* Payoff 参数（用于到期盈亏图） */
  payoffParams: StrategyPayoffParams;
};

/** 正态分布累积函数近似（Abramowitz & Stegun） */
function normalCDF(x: number): number {
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const sign = x < 0 ? -1 : 1;
  const t = 1 / (1 + p * Math.abs(x));
  const y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x / 2);
  return 0.5 * (1 + sign * y);
}

/** 估算策略胜率：P(价格落在盈利区间) */
function estWinProb(S: number, K_be: number, profitable_above: boolean, iv: number, days: number): number {
  if (iv <= 0 || days <= 0) return 50;
  const sigma = S * iv * Math.sqrt(days / 365);
  if (sigma <= 0) return 50;
  const d = (K_be - S) / sigma;
  return profitable_above
    ? Math.round((1 - normalCDF(d)) * 100)
    : Math.round(normalCDF(d) * 100);
}

function buildStrategies(opt: TenxEarningsOptionItem | undefined): OptionStrategy[] {
  // 无期权数据时返回空
  if (!opt || opt.dataQualityFlag !== "ok" || !opt.underlyingPrice) return [];

  const S = opt.underlyingPrice;
  const iv = normalizeVol(opt.avgImpliedVolatility) ?? 0.40; // 默认 40% IV
  const cpRatio = opt.callPutVolumeRatio ?? 1;
  const cpOI = opt.callPutOpenInterestRatio ?? 1;
  const flow = opt.flowSentiment ?? "unknown";
  const sel = opt.optionSelectionScore ?? 50;
  const liq = opt.liquidityScore ?? 50;
  const days = 30; // 默认 30 天到期
  const currency = "USD";
  const sigma1 = S * iv * Math.sqrt(days / 365); // 1σ 价格变动

  // 经验修正：selectionScore 高 → 方向性策略胜率 +3~5%
  const selBonus = sel >= 80 ? 5 : sel >= 70 ? 3 : 0;
  // 资金流方向修正
  const flowBonus = flow === "bullish" ? 3 : flow === "bearish" ? 3 : 0;

  // Strike 辅助函数
  const atm = S;
  const otm_call = S + sigma1 * 0.5;    // ATM + 0.5σ
  const otm_call2 = S + sigma1;          // ATM + 1σ
  const otm_put = S - sigma1 * 0.5;      // ATM - 0.5σ
  const otm_put2 = S - sigma1;           // ATM - 1σ
  const mid = (S + (opt.maxPainStrike || S)) / 2; // 蝴蝶中点

  // Premium 估算（BSM 简化）
  const callATM = S * iv * Math.sqrt(days / 365) * 0.4;  // ATM call ≈ 0.4 × S × σ√T
  const putATM = callATM * (cpRatio < 0.9 ? 1.1 : 0.95);
  const callOTM = callATM * 0.45;
  const putOTM = putATM * 0.45;
  const callOTM2 = callATM * 0.18;
  const putOTM2 = putATM * 0.18;

  // IV 水平判断
  const ivHigh = iv > 0.45;
  const ivLow = iv < 0.25;
  const ivMid = !ivHigh && !ivLow;

  const strategies: OptionStrategy[] = [];

  // ── 1. 看涨价差 Bull Call Spread ──
  {
    const be = atm + (callATM - callOTM);
    const maxP = otm_call - atm - (callATM - callOTM);
    const maxL = callATM - callOTM;
    let wp = estWinProb(S, be, true, iv, days) + selBonus + flowBonus;
    const bullish = flow === "bullish" || cpRatio >= 1.2;
    const rank = (bullish && ivMid) ? 1 : (bullish ? 3 : 6);
    wp = Math.min(85, Math.max(30, wp + (bullish ? 5 : -3)));
    strategies.push({
      key: "bull_call_spread", name: "看涨价差", nameEn: "Bull Call Spread",
      direction: "偏多", directionTone: "green", winProb: wp, rank,
      maxProfit: `有限 (+${fmtCurrency(maxP, currency)})`, maxLoss: `有限 (-${fmtCurrency(maxL, currency)})`,
      breakeven: fmtStrike(be, currency),
      strikes: `Buy ${fmtStrike(atm, currency)}C / Sell ${fmtStrike(otm_call, currency)}C`,
      premium: `净支出 ${fmtCurrency(callATM - callOTM, currency)}`,
      logic: `资金流偏多(${flow})且 Call/Put ${cpRatio.toFixed(2)}，看涨价差限定风险${ivMid ? "，IV 适中定价合理" : ivHigh ? "，但 IV 偏高注意时间衰减" : "，IV 偏低权利金便宜"}。`,
      payoffParams: { S, iv, days, sigma1, legs: [
        { type: "call", strike: atm, premium: callATM, qty: 1 },
        { type: "call", strike: otm_call, premium: callOTM, qty: -1 },
      ], breakevenPoints: [be], maxProfitValue: maxP, maxLossValue: -maxL },
    });
  }

  // ── 2. 看跌价差 Bear Put Spread ──
  {
    const be = atm - (putATM - putOTM);
    const maxP = atm - otm_put - (putATM - putOTM);
    const maxL = putATM - putOTM;
    let wp = estWinProb(S, be, false, iv, days) + selBonus + flowBonus;
    const bearish = flow === "bearish" || cpRatio <= 0.85;
    const rank = (bearish && ivMid) ? 1 : (bearish ? 3 : 7);
    wp = Math.min(85, Math.max(30, wp + (bearish ? 5 : -3)));
    strategies.push({
      key: "bear_put_spread", name: "看跌价差", nameEn: "Bear Put Spread",
      direction: "偏空", directionTone: "red", winProb: wp, rank,
      maxProfit: `有限 (+${fmtCurrency(maxP, currency)})`, maxLoss: `有限 (-${fmtCurrency(maxL, currency)})`,
      breakeven: fmtStrike(be, currency),
      strikes: `Buy ${fmtStrike(atm, currency)}P / Sell ${fmtStrike(otm_put, currency)}P`,
      premium: `净支出 ${fmtCurrency(putATM - putOTM, currency)}`,
      logic: `资金流偏空(${flow})且 Call/Put ${cpRatio.toFixed(2)}，看跌价差限定下行风险${ivMid ? "，IV 适中" : ""}。`,
      payoffParams: { S, iv, days, sigma1, legs: [
        { type: "put", strike: atm, premium: putATM, qty: 1 },
        { type: "put", strike: otm_put, premium: putOTM, qty: -1 },
      ], breakevenPoints: [be], maxProfitValue: maxP, maxLossValue: -maxL },
    });
  }

  // ── 3. 买入看涨 Long Call ──
  {
    const cost = callATM;
    const be = atm + cost;
    let wp = Math.round((1 - normalCDF((be - S) / sigma1)) * 100);
    const bullish = flow === "bullish" || cpRatio >= 1.2;
    const rank = bullish ? 2 : 5;
    wp = Math.min(80, Math.max(25, wp + (bullish ? 5 : -3) + selBonus));
    strategies.push({
      key: "long_call", name: "买入看涨", nameEn: "Long Call",
      direction: "看多", directionTone: "green", winProb: wp, rank,
      maxProfit: `理论无限`, maxLoss: `有限 (-${fmtCurrency(cost, currency)})`,
      breakeven: fmtStrike(be, currency),
      strikes: `Buy ${fmtStrike(atm, currency)}C`,
      premium: `净支出 ${fmtCurrency(cost, currency)}`,
      logic: `买入 ATM Call 做多，理论收益无限，风险仅限权利金${bullish ? `。资金流偏多(${flow})支持看多判断` : ""}。${ivLow ? "IV 偏低权利金便宜" : ivHigh ? "IV 偏高注意时间衰减" : "IV 适中"}。`,
      payoffParams: { S, iv, days, sigma1, legs: [
        { type: "call", strike: atm, premium: callATM, qty: 1 },
      ], breakevenPoints: [be], maxProfitValue: null, maxLossValue: -cost },
    });
  }

  // ── 4. 买入看跌 Long Put ──
  {
    const cost = putATM;
    const be = atm - cost;
    let wp = Math.round(normalCDF((be - S) / sigma1) * 100);
    const bearish = flow === "bearish" || cpRatio <= 0.85;
    const rank = bearish ? 2 : 5;
    wp = Math.min(80, Math.max(25, wp + (bearish ? 5 : -3) + selBonus));
    strategies.push({
      key: "long_put", name: "买入看跌", nameEn: "Long Put",
      direction: "看空", directionTone: "red", winProb: wp, rank,
      maxProfit: `有限 (标的归零时 +${fmtCurrency(atm - cost, currency)})`, maxLoss: `有限 (-${fmtCurrency(cost, currency)})`,
      breakeven: fmtStrike(be, currency),
      strikes: `Buy ${fmtStrike(atm, currency)}P`,
      premium: `净支出 ${fmtCurrency(cost, currency)}`,
      logic: `买入 ATM Put 做空，收益在标的归零时最大，风险仅限权利金${bearish ? `。资金流偏空(${flow})支持看空判断` : ""}。${ivLow ? "IV 偏低权利金便宜" : ivHigh ? "IV 偏高注意时间衰减" : "IV 适中"}。`,
      payoffParams: { S, iv, days, sigma1, legs: [
        { type: "put", strike: atm, premium: putATM, qty: 1 },
      ], breakevenPoints: [be], maxProfitValue: atm - cost, maxLossValue: -cost },
    });
  }

  // ── 5. 买入跨式 Long Straddle ──
  {
    const cost = callATM + putATM;
    const be_up = atm + cost;
    const be_dn = atm - cost;
    const wp_up = (1 - normalCDF((be_up - S) / sigma1)) * 100;
    const wp_dn = normalCDF((be_dn - S) / sigma1) * 100;
    let wp = Math.round(wp_up + wp_dn);
    const rank = ivLow ? 2 : (ivHigh ? 7 : 5);
    wp = Math.min(70, Math.max(20, wp + (ivLow ? 8 : -5)));
    strategies.push({
      key: "long_straddle", name: "买入跨式", nameEn: "Long Straddle",
      direction: "波动", directionTone: "yellow", winProb: wp, rank,
      maxProfit: `理论无限`, maxLoss: `有限 (-${fmtCurrency(cost, currency)})`,
      breakeven: `${fmtStrike(be_dn, currency)} / ${fmtStrike(be_up, currency)}`,
      strikes: `Buy ${fmtStrike(atm, currency)}C + Buy ${fmtStrike(atm, currency)}P`,
      premium: `净支出 ${fmtCurrency(cost, currency)}`,
      logic: `买入同价 Call+Put，押注大幅突破${ivLow ? "。IV 偏低(${(iv * 100).toFixed(0)}%)，权利金便宜，波动性价比高" : "。IV ${(iv * 100).toFixed(0)}%，需要足够大的方向性突破才能盈利"}。`,
      payoffParams: { S, iv, days, sigma1, legs: [
        { type: "call", strike: atm, premium: callATM, qty: 1 },
        { type: "put", strike: atm, premium: putATM, qty: 1 },
      ], breakevenPoints: [be_dn, be_up], maxProfitValue: null, maxLossValue: -cost },
    });
  }

  // ── 6. 卖出跨式 Short Straddle ──
  {
    const credit = callATM + putATM;
    const be_up = atm + credit;
    const be_dn = atm - credit;
    const wp_up = (1 - normalCDF((be_up - S) / sigma1)) * 100;
    const wp_dn = normalCDF((be_dn - S) / sigma1) * 100;
    let wp = Math.round(100 - wp_up - wp_dn);
    const rank = ivHigh ? 1 : (ivMid ? 4 : 8);
    wp = Math.min(80, Math.max(35, wp + (ivHigh ? 8 : -5)));
    strategies.push({
      key: "short_straddle", name: "卖出跨式", nameEn: "Short Straddle",
      direction: "中性", directionTone: "blue", winProb: wp, rank,
      maxProfit: `有限 (+${fmtCurrency(credit, currency)})`, maxLoss: `理论无限`,
      breakeven: `${fmtStrike(be_dn, currency)} / ${fmtStrike(be_up, currency)}`,
      strikes: `Sell ${fmtStrike(atm, currency)}C + Sell ${fmtStrike(atm, currency)}P`,
      premium: `净收入 ${fmtCurrency(credit, currency)}`,
      logic: `卖出同价 Call+Put 收权利金，押注横盘${ivHigh ? "。IV 偏高(${(iv * 100).toFixed(0)}%)，权利金丰厚，卖方优势明显" : "。IV 适中，需确信短期无大幅波动"}。风险无限需严格止损。`,
      payoffParams: { S, iv, days, sigma1, legs: [
        { type: "call", strike: atm, premium: callATM, qty: -1 },
        { type: "put", strike: atm, premium: putATM, qty: -1 },
      ], breakevenPoints: [be_dn, be_up], maxProfitValue: credit, maxLossValue: null },
    });
  }

  // ── 7. 买入宽跨式 Long Strangle ──
  {
    const cost = callOTM + putOTM;
    const be_up = otm_call + cost;
    const be_dn = otm_put - cost;
    const wp_up = (1 - normalCDF((be_up - S) / sigma1)) * 100;
    const wp_dn = normalCDF((be_dn - S) / sigma1) * 100;
    let wp = Math.round(wp_up + wp_dn);
    const rank = ivLow ? 3 : (ivMid ? 6 : 8);
    wp = Math.min(60, Math.max(15, wp + (ivLow ? 5 : -3)));
    strategies.push({
      key: "long_strangle", name: "买入宽跨式", nameEn: "Long Strangle",
      direction: "突破", directionTone: "yellow", winProb: wp, rank,
      maxProfit: `理论无限`, maxLoss: `有限 (-${fmtCurrency(cost, currency)})`,
      breakeven: `${fmtStrike(be_dn, currency)} / ${fmtStrike(be_up, currency)}`,
      strikes: `Buy ${fmtStrike(otm_call, currency)}C + Buy ${fmtStrike(otm_put, currency)}P`,
      premium: `净支出 ${fmtCurrency(cost, currency)}`,
      logic: `虚值 Call+Put 成本更低(${fmtCurrency(cost, currency)})，需要更大的突破幅度。${ivLow ? "IV 偏低，买入波动率性价比好" : "IV 偏高，买入成本较大"}。`,
      payoffParams: { S, iv, days, sigma1, legs: [
        { type: "call", strike: otm_call, premium: callOTM, qty: 1 },
        { type: "put", strike: otm_put, premium: putOTM, qty: 1 },
      ], breakevenPoints: [be_dn, be_up], maxProfitValue: null, maxLossValue: -cost },
    });
  }

  // ── 8. 铁鹰 Iron Condor ──
  {
    const credit = putOTM + callOTM - putOTM2 - callOTM2;
    const be_put = otm_put - credit;
    const be_call = otm_call + credit;
    let wp = Math.round(normalCDF((otm_put - be_put) / (sigma1 * 0.5)) * 50 + normalCDF((be_call - otm_call) / (sigma1 * 0.5)) * 50);
    const rank = (ivHigh || flow === "neutral") ? 2 : (ivMid ? 4 : 7);
    wp = Math.min(78, Math.max(40, wp + (ivHigh ? 6 : 0) + (flow === "neutral" ? 4 : 0)));
    strategies.push({
      key: "iron_condor", name: "铁鹰", nameEn: "Iron Condor",
      direction: "中性", directionTone: "blue", winProb: wp, rank,
      maxProfit: `有限 (+${fmtCurrency(Math.max(0, credit), currency)})`, maxLoss: `有限 (-${fmtCurrency(Math.abs(otm_put - otm_put2 - credit), currency)})`,
      breakeven: `${fmtStrike(be_put, currency)} / ${fmtStrike(be_call, currency)}`,
      strikes: `Sell ${fmtStrike(otm_put, currency)}P/${fmtStrike(otm_put2, currency)}P + Sell ${fmtStrike(otm_call, currency)}C/${fmtStrike(otm_call2, currency)}C`,
      premium: `净收入 ${fmtCurrency(Math.max(0, credit), currency)}`,
      logic: `四腿组合卖 Put价差+Call价差收权利金，押注区间震荡${ivHigh ? "。IV 偏高，卖方优势大" : ""}${flow === "neutral" ? "。资金流中性，方向不明" : ""}。盈亏比有限但胜率高。`,
      payoffParams: { S, iv, days, sigma1, legs: [
        { type: "put", strike: otm_put, premium: putOTM, qty: -1 },
        { type: "put", strike: otm_put2, premium: putOTM2, qty: 1 },
        { type: "call", strike: otm_call, premium: callOTM, qty: -1 },
        { type: "call", strike: otm_call2, premium: callOTM2, qty: 1 },
      ], breakevenPoints: [be_put, be_call], maxProfitValue: Math.max(0, credit), maxLossValue: -(Math.abs(otm_put - otm_put2 - credit)) },
    });
  }

  // ── 9. 蝴蝶 Call Butterfly ──
  {
    const midStrike = roundStrike(mid);
    const lower = roundStrike(midStrike - sigma1 * 0.5);
    const upper = roundStrike(midStrike + sigma1 * 0.5);
    const cost_bf = callOTM * 0.3; // 简化估算
    const maxP_bf = upper - midStrike - cost_bf;
    const be_low = lower + cost_bf;
    const be_high = upper - cost_bf;
    let wp = Math.round(normalCDF((midStrike - be_low) / (sigma1 * 0.3)) * 100 * 0.6);
    const rank = (flow === "neutral" && ivMid) ? 3 : 5;
    wp = Math.min(55, Math.max(20, wp + (flow === "neutral" ? 5 : 0)));
    strategies.push({
      key: "call_butterfly", name: "蝴蝶", nameEn: "Call Butterfly",
      direction: "收敛", directionTone: "blue", winProb: wp, rank,
      maxProfit: `有限 (+${fmtCurrency(Math.max(0, maxP_bf), currency)})`, maxLoss: `有限 (-${fmtCurrency(cost_bf, currency)})`,
      breakeven: `${fmtStrike(be_low, currency)} / ${fmtStrike(be_high, currency)}`,
      strikes: `Buy ${fmtStrike(lower, currency)}C / Sell 2×${fmtStrike(midStrike, currency)}C / Buy ${fmtStrike(upper, currency)}C`,
      premium: `净支出 ${fmtCurrency(cost_bf, currency)}`,
      logic: `三腿组合押注价格收敛到中点(${fmtStrike(midStrike, currency)})${flow === "neutral" ? "，资金流中性支持收敛判断" : ""}。低成本有限风险，适合高确信度的区间判断。`,
      payoffParams: { S, iv, days, sigma1, legs: [
        { type: "call", strike: lower, premium: callOTM * 0.3, qty: 1 },
        { type: "call", strike: midStrike, premium: callOTM * 0.3, qty: -2 },
        { type: "call", strike: upper, premium: callOTM * 0.3, qty: 1 },
      ], breakevenPoints: [be_low, be_high], maxProfitValue: Math.max(0, maxP_bf), maxLossValue: -cost_bf },
    });
  }

  // ── 10. 备兑看涨 Covered Call ──
  {
    const strike_cc = roundStrike(otm_call);
    const credit_cc = callOTM;
    const be_cc = S - credit_cc;
    let wp = Math.round(normalCDF((strike_cc - S) / sigma1) * 100);
    const rank = (flow === "bullish" || flow === "neutral") ? 4 : 6;
    wp = Math.min(75, Math.max(50, wp + 10)); // 备兑天然胜率高
    strategies.push({
      key: "covered_call", name: "备兑看涨", nameEn: "Covered Call",
      direction: "偏多", directionTone: "green", winProb: wp, rank,
      maxProfit: `有限 (+${fmtCurrency(strike_cc - S + credit_cc, currency)})`, maxLoss: `${fmtCurrency(S - credit_cc, currency)} (标的大跌)`,
      breakeven: fmtStrike(be_cc, currency),
      strikes: `持有股票 + Sell ${fmtStrike(strike_cc, currency)}C`,
      premium: `收入 ${fmtCurrency(credit_cc, currency)}`,
      logic: `持有标的卖 OTM Call 增强收益，降低持仓成本${liq >= 80 ? "。流动性充足，滑点风险小" : ""}。适合看好标的但认为短期涨幅有限的情况。`,
      payoffParams: { S, iv, days, sigma1, legs: [
        { type: "stock", strike: S, premium: 0, qty: 1 },
        { type: "call", strike: strike_cc, premium: credit_cc, qty: -1 },
      ], breakevenPoints: [be_cc], maxProfitValue: strike_cc - S + credit_cc, maxLossValue: -(S - credit_cc) },
    });
  }

  // 按 rank 排序
  strategies.sort((a, b) => a.rank - b.rank || b.winProb - a.winProb);
  return strategies;
}

/* ── Payoff 计算函数 ── */

/** 单腿到期收益计算 */
function legPayoff(
  legType: "call" | "put" | "stock",
  strike: number,
  premium: number,
  qty: number,
  ST: number,
): number {
  if (legType === "stock") {
    // stock: profit = qty * (ST - entryPrice)，entryPrice 存在 strike 中
    return qty * (ST - strike);
  }
  const intrinsic = legType === "call"
    ? Math.max(0, ST - strike)
    : Math.max(0, strike - ST);
  return qty * intrinsic - qty * premium;
}

/** 生成 Payoff 曲线数据点（S ± 2σ 范围） */
function generatePayoffData(
  params: StrategyPayoffParams,
  numPoints = 200,
): { prices: number[]; payoffs: number[] } {
  const { S, sigma1, legs } = params;
  const xMin = S - 2 * sigma1;
  const xMax = S + 2 * sigma1;
  const step = (xMax - xMin) / (numPoints - 1);
  const prices: number[] = [];
  const payoffs: number[] = [];
  for (let i = 0; i < numPoints; i++) {
    const ST = xMin + i * step;
    let total = 0;
    for (const leg of legs) {
      total += legPayoff(leg.type, leg.strike, leg.premium, leg.qty, ST);
    }
    prices.push(ST);
    payoffs.push(total);
  }
  return { prices, payoffs };
}

/** 特定价格点的 P&L */
function scenarioPayoff(params: StrategyPayoffParams, targetPrice: number): number {
  let total = 0;
  for (const leg of params.legs) {
    total += legPayoff(leg.type, leg.strike, leg.premium, leg.qty, targetPrice);
  }
  return total;
}

/* ── 场景分析小单元格 ── */

function ScenarioCell({ label, price, pnl }: { label: string; price: number; pnl: number }) {
  const tone = pnl >= 0 ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400";
  return (
    <div className="rounded-lg bg-gray-50 px-3 py-2 text-center dark:bg-gray-900/60">
      <div className="text-[10px] text-gray-500 dark:text-gray-400">{label}</div>
      <div className="text-xs text-gray-400">${price.toFixed(1)}</div>
      <div className={`text-sm font-bold ${tone}`}>
        {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}
      </div>
    </div>
  );
}

/* ── 策略 Payoff 详情面板 ── */

function StrategyPayoffPanel({ params }: { params: StrategyPayoffParams }) {
  const { S, sigma1, legs, breakevenPoints } = params;

  const chartData = useMemo(() => generatePayoffData(params), [params]);

  // 场景分析
  const pnlAtS = scenarioPayoff(params, S);
  const pnlAtPlus1S = scenarioPayoff(params, S + sigma1);
  const pnlAtMinus1S = scenarioPayoff(params, S - sigma1);

  // 双系列：盈利线 + 亏损线（实现绿涨红跌视觉效果）
  const profitData = chartData.payoffs.map((v) => (v >= 0 ? v : null));
  const lossData = chartData.payoffs.map((v) => (v < 0 ? v : null));

  const xaxisLabels = chartData.prices.map((p) => +p.toFixed(2));

  // 标注：当前价格 + 盈亏平衡点
  const xAnnotations: Array<{ x: number; strokeDashArray: number; borderColor: string; label: { text: string; style: { background: string; color: string; fontSize: string } } }> = [
    {
      x: S,
      strokeDashArray: 4,
      borderColor: "#6366f1",
      label: { text: `现价 $${S.toFixed(1)}`, style: { background: "#6366f1", color: "#fff", fontSize: "10px" } },
    },
    ...breakevenPoints.map((be) => ({
      x: be,
      strokeDashArray: 2,
      borderColor: "#eab308",
      label: { text: `BE $${be.toFixed(1)}`, style: { background: "#eab308", color: "#000", fontSize: "10px" } },
    })),
  ];

  const options: ApexOptions = {
    chart: {
      fontFamily: "Outfit, sans-serif",
      type: "area",
      height: 280,
      toolbar: { show: false },
      background: "transparent",
      animations: { enabled: true, speed: 300 },
    },
    stroke: { width: [2, 2], curve: "straight" },
    colors: ["#10b981", "#ef4444"],
    fill: {
      type: "gradient",
      gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.02, type: "vertical" },
    },
    series: [
      { name: "盈利", data: profitData },
      { name: "亏损", data: lossData },
    ],
    annotations: {
      xaxis: xAnnotations,
      yaxis: [
        { y: 0, strokeDashArray: 0, borderColor: "#6b7280", borderWidth: 1 },
      ],
    },
    xaxis: {
      categories: xaxisLabels,
      tickAmount: 8,
      axisBorder: { show: false },
      axisTicks: { show: false },
      labels: {
        style: { fontSize: "9px", colors: "#9ca3af" },
        formatter: (val: string) => {
          const num = parseFloat(val);
          const pct = ((num - S) / S * 100);
          if (Math.abs(num - S) < sigma1 * 0.05) return `$${num.toFixed(0)}`;
          if (Math.abs(num - (S + sigma1)) < sigma1 * 0.05) return `+${pct.toFixed(0)}%`;
          if (Math.abs(num - (S - sigma1)) < sigma1 * 0.05) return `${pct.toFixed(0)}%`;
          return "";
        },
        rotate: 0,
        hideOverlappingLabels: true,
      },
      title: { text: "到期标的价格", style: { fontSize: "10px", color: "#6b7280" } },
    },
    yaxis: {
      labels: {
        style: { fontSize: "9px", colors: "#9ca3af" },
        formatter: (val: number) => `$${val.toFixed(1)}`,
      },
      title: { text: "P&L", style: { fontSize: "10px", color: "#6b7280" } },
    },
    grid: {
      borderColor: "#e5e7eb30",
      strokeDashArray: 3,
      xaxis: { lines: { show: false } },
      yaxis: { lines: { show: true } },
    },
    dataLabels: { enabled: false },
    legend: { show: false },
    tooltip: {
      enabled: true,
      x: { formatter: (val: number) => `价格: $${val.toFixed(2)}` },
      y: {
        formatter: (val: number | null) => val !== null ? `${val >= 0 ? "+" : ""}$${val.toFixed(2)}` : "-",
      },
    },
    theme: { mode: "light" },
  };

  return (
    <div className="mt-3 space-y-3">
      {/* Payoff 曲线 */}
      <div className="rounded-lg border border-gray-200 bg-white p-2 dark:border-gray-700 dark:bg-gray-800/50">
        <ReactApexChart options={options} series={options.series!} type="area" height={280} />
      </div>

      {/* 场景分析 */}
      <div className="grid grid-cols-3 gap-2">
        <ScenarioCell label={`-1σ (${((S - sigma1 - S) / S * 100).toFixed(0)}%)`} price={S - sigma1} pnl={pnlAtMinus1S} />
        <ScenarioCell label="当前价" price={S} pnl={pnlAtS} />
        <ScenarioCell label={`+1σ (+${((S + sigma1 - S) / S * 100).toFixed(0)}%)`} price={S + sigma1} pnl={pnlAtPlus1S} />
      </div>

      {/* 持仓明细 */}
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-2 dark:border-gray-700 dark:bg-gray-900/40">
        <div className="mb-1 text-[10px] font-medium text-gray-500 dark:text-gray-400">持仓明细</div>
        <div className="space-y-0.5">
          {legs.map((leg, i) => (
            <div key={i} className="flex items-center justify-between text-[11px]">
              <span className={leg.qty > 0 ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400"}>
                {leg.qty > 0 ? "Buy" : "Sell"} {leg.type === "stock" ? "股票" : leg.type === "call" ? "Call" : "Put"} ${leg.strike.toFixed(1)}
              </span>
              <span className="text-gray-500 dark:text-gray-400">
                权利金 ${leg.premium.toFixed(2)} × {Math.abs(leg.qty)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── 策略卡片组件 ── */

function StrategyCard({ s, isExpanded, onToggleExpand }: { s: OptionStrategy; isExpanded: boolean; onToggleExpand: () => void }) {
  const hasBacktest = s.backtestWinRate != null && s.backtestTotalTrades != null && s.backtestTotalTrades > 0;
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50/50 p-3 dark:border-gray-800 dark:bg-gray-900/40">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onToggleExpand}
          className="flex items-center gap-1.5 group cursor-pointer"
          title="点击查看 Payoff 详情"
        >
          <span className="text-sm font-bold text-gray-900 group-hover:text-brand-600 dark:text-white dark:group-hover:text-brand-300 transition-colors">{s.name}</span>
          <span className="text-xs text-gray-400 dark:text-gray-500">{s.nameEn}</span>
          <ChevronRight className={`h-3.5 w-3.5 text-gray-400 transition-transform duration-200 ${isExpanded ? "rotate-90" : ""}`} />
        </button>
        <StatusTag label={s.direction} tone={s.directionTone} />
      </div>

      {/* 理论胜率条 */}
      <div className="mt-2 flex items-center gap-2">
        <span className="w-12 shrink-0 text-xs text-gray-500 dark:text-gray-400">理论</span>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
          <div
            className={`h-full rounded-full transition-all ${s.winProb >= 60 ? "bg-green-500" : s.winProb >= 45 ? "bg-yellow-500" : "bg-red-400"}`}
            style={{ width: `${Math.min(100, s.winProb)}%` }}
          />
        </div>
        <span className={`text-xs font-bold ${s.winProb >= 60 ? "text-green-600 dark:text-green-400" : s.winProb >= 45 ? "text-yellow-600 dark:text-yellow-400" : "text-red-500"}`}>
          {s.winProb}%
        </span>
      </div>

      {/* 回测胜率条 */}
      {hasBacktest && (() => {
        const btWin = s.backtestWinRate!;
        const btTotal = s.backtestTotalTrades!;
        return (
          <div className="mt-1 flex items-center gap-2">
            <span className="w-12 shrink-0 text-xs text-indigo-500 dark:text-indigo-400">回测</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
              <div
                className={`h-full rounded-full transition-all ${btWin >= 60 ? "bg-indigo-500" : btWin >= 45 ? "bg-amber-500" : "bg-rose-400"}`}
                style={{ width: `${Math.min(100, btWin)}%` }}
              />
            </div>
            <span className={`text-xs font-bold ${btWin >= 60 ? "text-indigo-600 dark:text-indigo-400" : btWin >= 45 ? "text-amber-600 dark:text-amber-400" : "text-rose-500"}`}>
              {btWin}%<span className="font-normal text-gray-400 dark:text-gray-500"> ({btTotal}笔)</span>
            </span>
          </div>
        );
      })()}

      {/* 关键指标 */}
      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div><span className="text-gray-400 dark:text-gray-500">最大盈利 </span><span className="font-medium text-gray-700 dark:text-gray-200">{s.maxProfit}</span></div>
        <div><span className="text-gray-400 dark:text-gray-500">最大亏损 </span><span className="font-medium text-gray-700 dark:text-gray-200">{s.maxLoss}</span></div>
        <div><span className="text-gray-400 dark:text-gray-500">盈亏平衡 </span><span className="font-medium text-gray-700 dark:text-gray-200">{s.breakeven}</span></div>
        <div><span className="text-gray-400 dark:text-gray-500">权利金 </span><span className="font-medium text-gray-700 dark:text-gray-200">{s.premium}</span></div>
      </div>

      <div className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">{s.strikes}</div>

      {/* 逻辑 */}
      <p className="mt-2 text-xs leading-5 text-gray-600 dark:text-gray-300">{s.logic}</p>
      {s.backtestLogic && (
        <p className="mt-1 text-xs leading-5 text-indigo-600 dark:text-indigo-400">{s.backtestLogic}</p>
      )}

      {/* LLM AI 分析 */}
      {s.llmLogic && (
        <div className="mt-2 rounded-md border border-purple-200 bg-purple-50/50 p-2 dark:border-purple-800/50 dark:bg-purple-950/20">
          <div className="flex items-center gap-2">
            {s.llmRecommendation && (() => {
              const rec = s.llmRecommendation!;
              const tone = rec === "strong_buy" ? "text-emerald-700 dark:text-emerald-400" : rec === "buy" ? "text-green-600 dark:text-green-400" : rec === "hold" ? "text-amber-600 dark:text-amber-400" : "text-red-500 dark:text-red-400";
              const label = rec === "strong_buy" ? "强烈看多" : rec === "buy" ? "看多" : rec === "hold" ? "观望" : rec === "avoid" ? "回避" : "强烈回避";
              return <span className={`text-xs font-bold ${tone}`}>{label}</span>;
            })()}
            {s.llmConfidence && <span className="text-xs text-gray-400">置信度 {s.llmConfidence}</span>}
          </div>
          <p className="mt-1 text-xs leading-5 text-purple-700 dark:text-purple-300">{s.llmLogic}</p>
          {s.llmKeyRisks && s.llmKeyRisks.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {s.llmKeyRisks.map((r, i) => (
                <span key={i} className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] text-red-600 dark:bg-red-900/30 dark:text-red-400">{r}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Payoff 详情面板（点击展开） */}
      {isExpanded && <StrategyPayoffPanel params={s.payoffParams} />}
    </div>
  );
}

/* ── 主组件 ── */

export default function TenxHunterDiscoverClient({ snapshot, earningsLens, earningsLensError }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const marketPath = snapshot.market.toLowerCase();
  const [search, setSearch] = useState(searchParams.get("symbol") || "");
  const [stage, setStage] = useState<string>("all");
  const [flow, setFlow] = useState<"all" | TenxFlowStatus>("all");
  const [theme, setTheme] = useState<string>(searchParams.get("theme") || "all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);
  const [pendingSymbol, setPendingSymbol] = useState<string | null>(null);
  const [pendingIntake, setPendingIntake] = useState(false);
  const [manualSymbol, setManualSymbol] = useState(searchParams.get("symbol") || "");
  const [manualName, setManualName] = useState("");
  const [manualTheme, setManualTheme] = useState("Manual");
  const [manualNote, setManualNote] = useState("");
  const [manualReport, setManualReport] = useState<File | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [backtestCache, setBacktestCache] = useState<Map<string, TenxStrategyBacktestData>>(new Map());
  const [backtestLoading, setBacktestLoading] = useState<string | null>(null);
  const [expandedStrategy, setExpandedStrategy] = useState<string | null>(null);

  const keyword = search.trim().toLowerCase();

  // 构建 earnings/option 查找表
  const earningsBySymbol = useMemo(() => {
    const shortline = new Map((earningsLens?.shortline ?? []).map((item) => [item.symbol.toUpperCase(), item]));
    const options = new Map((earningsLens?.options ?? []).map((item) => [item.symbol.toUpperCase(), item]));
    return { shortline, options };
  }, [earningsLens]);

  const filteredCandidates = useMemo(() => {
    return snapshot.candidates.filter((item) => {
      const hitKeyword = !keyword || [item.symbol, item.name, item.theme, item.sector, item.keySignal].some((f) => f.toLowerCase().includes(keyword));
      const hitStage = stage === "all" || item.stage === stage;
      const hitTheme = theme === "all" || item.theme === theme;
      const hitFlow = flow === "all" || item.flowStatus === flow;
      return hitKeyword && hitStage && hitTheme && hitFlow;
    });
  }, [flow, keyword, stage, theme, snapshot.candidates]);

  const themeOptions = useMemo(() => {
    const dynamicThemes = Array.from(new Set(snapshot.candidates.map((item) => item.theme))).sort((a, b) => a.localeCompare(b));
    return ["all", ...dynamicThemes];
  }, [snapshot.candidates]);

  const totalPages = Math.max(1, Math.ceil(filteredCandidates.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pagedCandidates = filteredCandidates.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  async function promoteToWatchlist(symbol: string) {
    setPendingSymbol(symbol);
    setActionMessage(null);
    try {
      const result = await createWatchlistEntry(snapshot.market, symbol, "watch");
      setActionMessage(result.message);
      router.refresh();
    } catch (error) {
      setActionMessage(getTenxErrorMessage(error));
    } finally {
      setPendingSymbol(null);
    }
  }

  async function submitManualCandidate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const symbol = manualSymbol.trim().toUpperCase();
    if (!symbol) { setActionMessage("请输入股票代码。"); return; }
    setPendingIntake(true);
    setActionMessage(null);
    try {
      const candidateResult = await createDiscoverCandidate(snapshot.market, {
        symbol, name: manualName.trim() || undefined, source: "manual", theme: manualTheme.trim() || "Manual",
        thesis: manualNote.trim() || `${symbol} 从热点线索手动纳入发现池，等待补投研报告和可复核证据。`,
        note: manualNote.trim() || undefined, triggerScene: "discover-manual-intake",
      });
      let nextMessage = candidateResult.message;
      if (manualReport) {
        const reportResult = await uploadTenxResearchReport(snapshot.market, symbol, manualReport);
        nextMessage = `${nextMessage} ${reportResult.message}`;
      }
      setActionMessage(nextMessage);
      setSearch(symbol);
      setManualReport(null);
      router.refresh();
    } catch (error) {
      setActionMessage(getTenxErrorMessage(error));
    } finally {
      setPendingIntake(false);
    }
  }

  function toggleExpand(symbol: string) {
    const nextExpanded = expandedSymbol === symbol ? null : symbol;
    setExpandedSymbol(nextExpanded);
    // 展开时懒加载回测数据
    if (nextExpanded && !backtestCache.has(nextExpanded) && snapshot.market === "US") {
      setBacktestLoading(nextExpanded);
      loadTenxStrategyBacktest(snapshot.market, nextExpanded)
        .then((data) => {
          setBacktestCache((prev) => new Map(prev).set(nextExpanded, data));
        })
        .catch(() => { /* 静默降级，策略卡片只显示理论胜率 */ })
        .finally(() => setBacktestLoading(null));
    }
  }

  return (
    <TenxPageShell
      market={snapshot.market}
      title="TenX Hunter · Discover"
      subtitle="候选池 + 财报期权事件看板，按行展开查看策略详情。"
      pipelineStage="discover"
    >
      <TenxSectionCard
        title="Candidate Pool"
        description="个股优先的研究入口。加入 discover 的股票自动聚合财报日历和期权策略。"
      >
        {/* 手动添加候选 */}
        <form onSubmit={(event) => void submitManualCandidate(event)} className="mb-5 rounded-xl border border-dashed border-brand-200 bg-brand-50/40 p-4 dark:border-brand-500/30 dark:bg-brand-500/10">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-end">
            <div className="grid flex-1 grid-cols-1 gap-3 md:grid-cols-[0.8fr_1.2fr_1fr]">
              <label className="block">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">股票代码</span>
                <input type="text" value={manualSymbol} onChange={(e) => setManualSymbol(e.target.value.toUpperCase())} placeholder="ASTS" className="mt-1 h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm font-semibold uppercase text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90" />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">公司名称</span>
                <input type="text" value={manualName} onChange={(e) => setManualName(e.target.value)} placeholder="AST SpaceMobile Inc" className="mt-1 h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90" />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">主题</span>
                <input type="text" value={manualTheme} onChange={(e) => setManualTheme(e.target.value)} placeholder="Satellite Connectivity" className="mt-1 h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90" />
              </label>
            </div>
            <label className="block min-w-0 xl:w-64">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">投研报告</span>
              <span className="mt-1 flex h-10 items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
                <FileUp className="h-4 w-4 shrink-0" />
                <span className="min-w-0 flex-1 truncate">{manualReport?.name ?? "可选 Markdown"}</span>
                <input type="file" accept=".md,.markdown,.txt,text/markdown,text/plain" onChange={(e) => setManualReport(e.target.files?.[0] ?? null)} className="sr-only" />
              </span>
            </label>
            <button type="submit" disabled={pendingIntake} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60">
              <Plus className="h-4 w-4" />{pendingIntake ? "纳入中" : "加入发现池"}
            </button>
          </div>
          <textarea value={manualNote} onChange={(e) => setManualNote(e.target.value)} placeholder="记录为什么值得从热点线索进入发现池。" className="mt-3 min-h-20 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm leading-6 text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90" />
        </form>

        {actionMessage && <div className="mb-4 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">{actionMessage}</div>}

        {/* 搜索/筛选 */}
        <div className="mb-5 grid grid-cols-1 gap-3 lg:grid-cols-[1.6fr_repeat(4,minmax(0,1fr))]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input type="text" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Symbol / company / signal" className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-10 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90" />
          </div>
          <select value={stage} onChange={(e) => { setStage(e.target.value); setPage(1); }} className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90">
            {stageOptions.map((o) => <option key={o} value={o}>{o === "all" ? "全部阶段" : o}</option>)}
          </select>
          <select value={flow} onChange={(e) => { setFlow(e.target.value as "all" | TenxFlowStatus); setPage(1); }} className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90">
            {flowOptions.map((o) => <option key={o} value={o}>{o === "all" ? "全部流转" : o}</option>)}
          </select>
          <select value={theme} onChange={(e) => { setTheme(e.target.value); setPage(1); }} className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90">
            {themeOptions.map((o) => <option key={o} value={o}>{o === "all" ? "全部主题" : o}</option>)}
          </select>
          <select value={String(pageSize)} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }} className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90">
            {pageSizeOptions.map((s) => <option key={s} value={s}>{`每页 ${s}`}</option>)}
          </select>
        </div>

        {/* 错误/提示 */}
        {earningsLensError && <div className="mb-4 rounded-lg bg-yellow-50 px-3 py-2 text-sm text-yellow-700 dark:bg-yellow-500/10 dark:text-yellow-300">{earningsLensError}</div>}
        {earningsLens?.notes.length ? <div className="mb-4 rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">{earningsLens.notes.join(" ")}</div> : null}

        {/* 候选卡片列表 */}
        <div className="space-y-2">
          {pagedCandidates.length === 0 ? (
            <div className="rounded-xl border border-gray-200 bg-white px-4 py-8 text-center text-sm text-gray-400 dark:border-gray-800 dark:bg-gray-950/50 dark:text-gray-500">当前筛选条件下没有候选标的。</div>
          ) : pagedCandidates.map((row) => {
            const symbol = row.symbol.toUpperCase();
            const sl = earningsBySymbol.shortline.get(symbol);
            const opt = earningsBySymbol.options.get(symbol);
            const forecast = sl ? buildForecast(sl, opt) : null;
            const expanded = expandedSymbol === symbol;
            const canPromote = row.flowStatus === "watch-ready";
            const isTracked = row.flowStatus === "watching" || row.flowStatus === "alerting";
            const currency = sl?.currency || "USD";
            const optionReady = opt?.dataQualityFlag === "ok";

            return (
              <div key={symbol} className={`rounded-xl border bg-white transition dark:bg-gray-950/50 ${expanded ? "border-brand-300 shadow-sm dark:border-brand-500/40" : "border-gray-200 dark:border-gray-800"}`}>
                {/* 摘要行 */}
                <button type="button" onClick={() => toggleExpand(symbol)} className="flex w-full items-center gap-3 px-4 py-3 text-left lg:gap-4">
                  <ScoreRing score={row.score} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link href={`/tenx-hunter/${marketPath}/research/${symbol}`} onClick={(e) => e.stopPropagation()} className="text-base font-bold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300">{row.symbol}</Link>
                      <span className="text-sm text-gray-500 dark:text-gray-400">{row.name}</span>
                      <CandidateFlowTag candidate={row} />
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      <StatusTag label={row.stage} tone={getStageTone(row.stage)} />
                      <StatusTag label={row.riskLevel} tone={getRiskTone(row.riskLevel)} />
                      <span className="text-xs text-gray-400 dark:text-gray-500">{row.theme}</span>
                      {sl && (
                        <>
                          <span className="text-gray-300 dark:text-gray-600">·</span>
                          <StatusTag label={dayLabel(sl.daysToEarnings)} tone={dayTone(sl.daysToEarnings)} />
                          {forecast && <StatusTag label={forecast.directionLabel} tone={forecast.directionTone} />}
                          {sl.epsEstimate !== null && sl.epsEstimate !== undefined && <span className="text-xs text-gray-500 dark:text-gray-400">EPS ${sl.epsEstimate.toFixed(2)}</span>}
                        </>
                      )}
                    </div>
                    {row.promotionSummary && <p className="mt-1 max-w-[400px] truncate text-xs text-gray-400 dark:text-gray-500">{row.promotionSummary}</p>}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {/* 行动按钮 */}
                    <span onClick={(e) => e.stopPropagation()}>
                      {isTracked ? (
                        <Link href={`/tenx-hunter/${marketPath}/${row.flowStatus === "alerting" ? "alerts" : "watchlist"}`} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400">
                          {row.flowStatus === "alerting" ? <BellRing className="h-3.5 w-3.5" /> : <Binoculars className="h-3.5 w-3.5" />}查看
                        </Link>
                      ) : (
                        <button type="button" onClick={() => void promoteToWatchlist(row.symbol)} disabled={!canPromote || pendingSymbol === row.symbol} title={canPromote ? "加入观察池" : "晋级条件未满足"} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400">
                          <Binoculars className="h-3.5 w-3.5" />{pendingSymbol === row.symbol ? "处理中" : "观察"}
                        </button>
                      )}
                    </span>
                    <span onClick={(e) => e.stopPropagation()}>
                      <Link href={`/tenx-hunter/${marketPath}/research/${symbol}/report`} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400">
                        <BookOpen className="h-3.5 w-3.5" />报告
                      </Link>
                    </span>
                    {expanded ? <ChevronDown className="h-4 w-4 text-gray-400" /> : <ChevronRight className="h-4 w-4 text-gray-400" />}
                  </div>
                </button>

                {/* 展开详情：晋级检查 + 财报 + 期权策略 */}
                {expanded && (
                  <div className="border-t border-gray-100 px-4 py-4 dark:border-gray-800">
                    {/* 晋级检查 */}
                    <div className="mb-4">
                      <div className="text-xs font-semibold text-gray-500 dark:text-gray-400">晋级门槛</div>
                      <div className="mt-1.5 grid max-w-lg grid-cols-2 gap-1.5">
                        {row.promotionChecks.map((check) => (
                          <div key={`${symbol}-${check.key}`} className="flex items-start gap-1.5 text-xs text-gray-600 dark:text-gray-300">
                            <span className={`mt-0.5 inline-block h-2 w-2 shrink-0 rounded-full ${check.passed ? "bg-green-500" : "bg-gray-300 dark:bg-gray-600"}`} />
                            <span>{check.label}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* 财报数据（如有） */}
                    {sl && (
                      <div className="mb-4">
                        <div className="text-xs font-semibold text-gray-500 dark:text-gray-400">财报预期</div>
                        <div className="mt-1.5 grid grid-cols-2 gap-2 sm:grid-cols-4">
                          <ForecastCell label="营收预期" value={fmtCurrency(sl.revenueEstimate, currency)} />
                          <ForecastCell label="EPS 预期" value={sl.epsEstimate !== null && sl.epsEstimate !== undefined ? `$${sl.epsEstimate.toFixed(2)}` : "N/A"} />
                          <ForecastCell label="财报日" value={sl.nextEarningsDate || "N/A"} tone={dayTone(sl.daysToEarnings)} />
                          <ForecastCell label="倒计时" value={sl.daysToEarnings !== null && sl.daysToEarnings !== undefined ? dayLabel(sl.daysToEarnings) : "N/A"} tone={dayTone(sl.daysToEarnings)} />
                        </div>
                        {sl.shortlineSignal && <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{sl.shortlineSignal}</p>}
                      </div>
                    )}

                    {/* 期权策略（不依赖财报） */}
                    {(() => {
                      const strats = buildStrategies(opt);
                      if (strats.length === 0) {
                        return <div className="text-sm text-gray-400 dark:text-gray-500">期权数据待补，运行 refresh-options 后查看策略分析。</div>;
                      }
                      // 合并回测数据
                      const btData = backtestCache.get(symbol);
                      const merged = strats.map((s) => {
                        if (!btData) return s;
                        const bt = btData.strategies.find((b) => b.key === s.key);
                        if (!bt || bt.totalTrades === 0) return s;
                        return {
                          ...s,
                          backtestWinRate: Math.round(bt.winRate * 100),
                          backtestTotalTrades: bt.totalTrades,
                          backtestLogic: bt.backtestLogic,
                          backtestProfitFactor: bt.profitFactor,
                          backtestStreak: bt.currentStreak,
                          llmRecommendation: bt.llmRecommendation ?? null,
                          llmConfidence: bt.llmConfidence ?? null,
                          llmLogic: bt.llmLogic ?? null,
                          llmKeyRisks: bt.llmKeyRisks ?? null,
                        };
                      });
                      return (
                        <div>
                          <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-gray-500 dark:text-gray-400">
                            <span>期权策略分析</span>
                            <span className="text-gray-300 dark:text-gray-600">·</span>
                            <span>IV {fmtPercent(normalizeVol(opt?.avgImpliedVolatility))}</span>
                            <span className="text-gray-300 dark:text-gray-600">·</span>
                            <span>Call/Put {fmtNum(opt?.callPutVolumeRatio)}</span>
                            <span className="text-gray-300 dark:text-gray-600">·</span>
                            <span>Max pain {fmtStrike(opt?.maxPainStrike, currency)}</span>
                            {backtestLoading === symbol && (
                              <>
                                <span className="text-gray-300 dark:text-gray-600">·</span>
                                <span className="animate-pulse text-indigo-400">回测加载中…</span>
                              </>
                            )}
                          </div>
                          <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
                            {merged.map((s) => (
                              <StrategyCard
                                key={s.key}
                                s={s}
                                isExpanded={expandedStrategy === `${symbol}::${s.key}`}
                                onToggleExpand={() => {
                                  const k = `${symbol}::${s.key}`;
                                  setExpandedStrategy((prev) => prev === k ? null : k);
                                }}
                              />
                            ))}
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {filteredCandidates.length > pageSize && (
          <TablePaginationBar totalItems={filteredCandidates.length} currentPage={currentPage} totalPages={totalPages} onPageChange={setPage} />
        )}
      </TenxSectionCard>
    </TenxPageShell>
  );
}
