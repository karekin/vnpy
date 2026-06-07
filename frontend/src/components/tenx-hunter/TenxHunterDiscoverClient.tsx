"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import { createDiscoverCandidate, createWatchlistEntry, getTenxErrorMessage, uploadTenxResearchReport } from "@/components/tenx-hunter/api";
import { CandidateFlowTag } from "@/components/tenx-hunter/TenxFlowStatus";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { getRiskTone, getStageTone, TenxSectionCard } from "@/components/tenx-hunter/TenxCards";
import type { TenxEarningsLens, TenxEarningsOptionItem, TenxEarningsShortlineItem, TenxFlowStatus, TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";
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
    setExpandedSymbol((prev) => (prev === symbol ? null : symbol));
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

                {/* 展开详情：财报 + 期权策略 */}
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

                    {sl ? (
                      <>
                        {/* 财报指标 */}
                        <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                          <ForecastCell label="营收预期" value={fmtCurrency(sl.revenueEstimate, currency)} />
                          <ForecastCell label="EPS 预期" value={sl.epsEstimate !== null && sl.epsEstimate !== undefined ? `$${sl.epsEstimate.toFixed(2)}` : "N/A"} />
                          <ForecastCell label="预期波动" value={fmtPercent(forecast?.expectedMove ?? null)} tone="red" />
                          <ForecastCell label="模型胜率" value={forecast?.winProbability === null ? "N/A" : `${forecast?.winProbability?.toFixed(0)}%`} tone={forecast?.directionTone} />
                        </div>

                        {/* 期权策略 */}
                        <div className="mb-3 overflow-hidden rounded-lg border border-gray-200 dark:border-gray-800">
                          <StrategyRow
                            label="单腿期权"
                            values={optionReady && forecast ? [
                              forecast.optionSide,
                              opt?.nearestExpiration ?? "N/A",
                              fmtStrike(forecast.strike, currency),
                              fmtCurrency(forecast.premium, currency),
                              forecast.optionSide === "PUT" ? "下行保护" : forecast.optionSide === "CALL" ? "上行弹性" : "双向波动",
                            ] : ["待补链", "N/A", "N/A", "N/A", "刷新期权链"]}
                          />
                          <StrategyRow
                            label="垂直价差"
                            values={optionReady && forecast ? [
                              forecast.optionSide === "PUT" ? "PUT spread" : forecast.optionSide === "CALL" ? "CALL spread" : "VOL spread",
                              `${fmtStrike(forecast.strike, currency)} / ${fmtStrike(forecast.sellStrike, currency)}`,
                              fmtCurrency(forecast.spreadDebit, currency),
                              fmtSignedPercent(forecast.expectedMove ? forecast.expectedMove * 0.85 : null),
                              fmtSignedPercent(forecast.spreadDebit && opt?.underlyingPrice ? -(forecast.spreadDebit / opt.underlyingPrice) : null),
                            ] : ["待补链", "N/A", "N/A", "N/A", "刷新期权链"]}
                            muted
                          />
                        </div>

                        {/* 辅助指标 + 信号 */}
                        <div className="flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
                          <span>IV {fmtPercent(normalizeVol(opt?.avgImpliedVolatility))}</span>
                          <span>Call/Put {fmtNum(opt?.callPutVolumeRatio)}</span>
                          <span>Max pain {fmtStrike(opt?.maxPainStrike, currency)}</span>
                          {sl.shortlineSignal && <span className="text-gray-600 dark:text-gray-300">· {sl.shortlineSignal}</span>}
                        </div>
                      </>
                    ) : (
                      <div className="text-sm text-gray-400 dark:text-gray-500">暂无财报日历数据，先补 earnings lens。</div>
                    )}
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
