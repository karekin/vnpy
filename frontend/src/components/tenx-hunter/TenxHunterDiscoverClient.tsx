"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import { createDiscoverCandidate, createWatchlistEntry, getTenxErrorMessage, uploadTenxResearchReport } from "@/components/tenx-hunter/api";
import { CandidateFlowTag, TenxFlowRail, getFlowTone } from "@/components/tenx-hunter/TenxFlowStatus";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { getRiskTone, getStageTone, TenxSectionCard } from "@/components/tenx-hunter/TenxCards";
import type { TenxFlowStatus, TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";
import { TableCell, TableRow } from "@/components/ui/table";
import { BellRing, Binoculars, BookOpen, CalendarClock, CheckCircle2, Circle, FileUp, Plus, Search } from "lucide-react";

const stageOptions = ["all", "discovery", "validation", "acceleration", "crowded", "falsified"] as const;
const flowOptions: Array<"all" | TenxFlowStatus> = ["all", "candidate", "watch-ready", "watching", "alerting", "blocked"];
const pageSizeOptions = [5, 10];

type TenxHunterDiscoverClientProps = {
  snapshot: TenxWorkspaceSnapshot;
};

export default function TenxHunterDiscoverClient({ snapshot }: TenxHunterDiscoverClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const marketPath = snapshot.market.toLowerCase();
  const [search, setSearch] = useState(searchParams.get("symbol") || "");
  const [stage, setStage] = useState<string>("all");
  const [flow, setFlow] = useState<"all" | TenxFlowStatus>("all");
  const [theme, setTheme] = useState<string>(searchParams.get("theme") || "all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [showTimeline, setShowTimeline] = useState(false);
  const [pendingSymbol, setPendingSymbol] = useState<string | null>(null);
  const [pendingIntake, setPendingIntake] = useState(false);
  const [manualSymbol, setManualSymbol] = useState(searchParams.get("symbol") || "");
  const [manualName, setManualName] = useState("");
  const [manualTheme, setManualTheme] = useState("Manual");
  const [manualNote, setManualNote] = useState("");
  const [manualReport, setManualReport] = useState<File | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const keyword = search.trim().toLowerCase();

  const filteredCandidates = useMemo(() => {
    return snapshot.candidates.filter((item) => {
      const hitKeyword =
        !keyword ||
        [item.symbol, item.name, item.theme, item.sector, item.keySignal].some((field) =>
          field.toLowerCase().includes(keyword),
        );
      const hitStage = stage === "all" || item.stage === stage;
      const hitTheme = theme === "all" || item.theme === theme;
      const hitFlow = flow === "all" || item.flowStatus === flow;
      return hitKeyword && hitStage && hitTheme && hitFlow;
    });
  }, [flow, keyword, stage, theme, snapshot.candidates]);

  const themeOptions = useMemo(() => {
    const dynamicThemes = Array.from(new Set(snapshot.candidates.map((item) => item.theme))).sort((a, b) =>
      a.localeCompare(b),
    );
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
    if (!symbol) {
      setActionMessage("请输入股票代码。");
      return;
    }

    setPendingIntake(true);
    setActionMessage(null);
    try {
      const candidateResult = await createDiscoverCandidate(snapshot.market, {
        symbol,
        name: manualName.trim() || undefined,
        source: "manual",
        theme: manualTheme.trim() || "Manual",
        thesis: manualNote.trim() || `${symbol} 从热点线索手动纳入发现池，等待补投研报告和可复核证据。`,
        note: manualNote.trim() || undefined,
        triggerScene: "discover-manual-intake",
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

  return (
    <TenxPageShell
      market={snapshot.market}
      title="TenX Hunter · Discover"
      subtitle={snapshot.market === "CN" ? "候选池只负责发现和验证，主题归因去 Themes，确认跟踪后再进入 Watchlist。" : "候选池只负责发现和验证，主题归因去 Themes，确认跟踪后再进入 Watchlist。"}
    >
      <TenxFlowRail snapshot={snapshot} />

      <TenxSectionCard
        title="Earnings Node"
        description="财报日历已提升为独立主流程节点，Discover 只负责候选发现和验证。"
        action={
          <Link
            href={`/tenx-hunter/${marketPath}/earnings`}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-gray-200 px-3 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
          >
            <CalendarClock className="h-4 w-4" aria-hidden="true" />
            打开财报节点
          </Link>
        }
      >
        <div className="grid grid-cols-1 gap-3 text-sm leading-6 text-gray-600 dark:text-gray-300 lg:grid-cols-3">
          <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">财报短线集中查看下一次财报日、EPS / Rev 预期和事件窗口。</div>
          <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">财报期权集中查看期权链摘要、流动性、结构评分和方向提示。</div>
          <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">通过财报事件验证后，再回到 Discover / Watchlist 做候选晋级和持续跟踪。</div>
        </div>
      </TenxSectionCard>

      <TenxSectionCard
        title="Candidate Pool"
        description="个股优先的研究入口。这里判断是否具备进入观察池的资格，不承载主题页的主线叙事。"
        action={
          <div className="inline-flex rounded-lg bg-gray-100 p-1 dark:bg-gray-900">
            <button
              type="button"
              onClick={() => setShowTimeline(false)}
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                !showTimeline
                  ? "bg-white text-gray-900 shadow dark:bg-gray-800 dark:text-white"
                  : "text-gray-500 dark:text-gray-400"
              }`}
            >
              候选
            </button>
            <button
              type="button"
              onClick={() => setShowTimeline(true)}
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                showTimeline
                  ? "bg-white text-gray-900 shadow dark:bg-gray-800 dark:text-white"
                  : "text-gray-500 dark:text-gray-400"
              }`}
            >
              事件
            </button>
          </div>
        }
      >
        <form
          onSubmit={(event) => void submitManualCandidate(event)}
          className="mb-5 rounded-xl border border-dashed border-brand-200 bg-brand-50/40 p-4 dark:border-brand-500/30 dark:bg-brand-500/10"
        >
          <div className="flex flex-col gap-3 xl:flex-row xl:items-end">
            <div className="grid flex-1 grid-cols-1 gap-3 md:grid-cols-[0.8fr_1.2fr_1fr]">
              <label className="block">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">股票代码</span>
                <input
                  type="text"
                  value={manualSymbol}
                  onChange={(event) => setManualSymbol(event.target.value.toUpperCase())}
                  placeholder="ASTS"
                  className="mt-1 h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm font-semibold uppercase text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">公司名称</span>
                <input
                  type="text"
                  value={manualName}
                  onChange={(event) => setManualName(event.target.value)}
                  placeholder="AST SpaceMobile Inc"
                  className="mt-1 h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">主题</span>
                <input
                  type="text"
                  value={manualTheme}
                  onChange={(event) => setManualTheme(event.target.value)}
                  placeholder="Satellite Connectivity"
                  className="mt-1 h-10 w-full rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                />
              </label>
            </div>
            <label className="block min-w-0 xl:w-64">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">投研报告</span>
              <span className="mt-1 flex h-10 items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
                <FileUp className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="min-w-0 flex-1 truncate">{manualReport?.name ?? "可选 Markdown"}</span>
                <input
                  type="file"
                  accept=".md,.markdown,.txt,text/markdown,text/plain"
                  onChange={(event) => setManualReport(event.target.files?.[0] ?? null)}
                  className="sr-only"
                />
              </span>
            </label>
            <button
              type="submit"
              disabled={pendingIntake}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              {pendingIntake ? "纳入中" : "加入发现池"}
            </button>
          </div>
          <textarea
            value={manualNote}
            onChange={(event) => setManualNote(event.target.value)}
            placeholder="记录为什么值得从热点线索进入发现池，例如 Falcon 9 发射节奏、卫星数量假设、待验证证据。"
            className="mt-3 min-h-20 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm leading-6 text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          />
        </form>
        {actionMessage ? (
          <div className="mb-4 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">{actionMessage}</div>
        ) : null}
        <div className="mb-5 grid grid-cols-1 gap-3 lg:grid-cols-[1.6fr_repeat(4,minmax(0,1fr))]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden="true" />
            <input
              type="text"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Symbol / company / signal"
              className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-10 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            />
          </div>
          <select
            value={stage}
            onChange={(event) => {
              setStage(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          >
            {stageOptions.map((option) => (
              <option key={option} value={option}>
                {option === "all" ? "全部阶段" : option}
              </option>
            ))}
          </select>
          <select
            value={flow}
            onChange={(event) => {
              setFlow(event.target.value as "all" | TenxFlowStatus);
              setPage(1);
            }}
            className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          >
            {flowOptions.map((option) => (
              <option key={option} value={option}>
                {option === "all" ? "全部流转" : option}
              </option>
            ))}
          </select>
          <select
            value={theme}
            onChange={(event) => {
              setTheme(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          >
            {themeOptions.map((option) => (
              <option key={option} value={option}>
                {option === "all" ? "全部主题" : option}
              </option>
            ))}
          </select>
          <select
            value={String(pageSize)}
            onChange={(event) => {
              setPageSize(Number(event.target.value));
              setPage(1);
            }}
            className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>{`每页 ${size}`}</option>
            ))}
          </select>
        </div>

        {!showTimeline ? (
          <>
            <ScrollableDataTable
              headers={["Symbol", "Flow", "Stage", "Score", "Risk", "Promotion Gate", "Next", "Action"]}
              minTableWidthClass="min-w-[1180px]"
              colSpan={8}
              isEmpty={!pagedCandidates.length}
            >
              {pagedCandidates.map((row) => {
                const canPromote = row.flowStatus === "watch-ready";
                const isTracked = row.flowStatus === "watching" || row.flowStatus === "alerting";
                return (
                  <TableRow key={row.symbol} className="border-b border-gray-100 last:border-b-0 dark:border-gray-800">
                    <TableCell className="px-4 py-3 align-top">
                      <Link
                        href={`/tenx-hunter/${marketPath}/research/${row.symbol}`}
                        className="font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300"
                      >
                        {row.symbol}
                      </Link>
                      <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{row.name}</div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <StatusTag label={row.theme} tone="blue" />
                        <StatusTag label={`${row.evidenceCount} 证据`} tone="slate" />
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3 align-top">
                      <CandidateFlowTag candidate={row} />
                      <p className="mt-2 max-w-[200px] text-xs leading-5 text-gray-500 dark:text-gray-400">{row.promotionSummary}</p>
                    </TableCell>
                    <TableCell className="px-4 py-3 align-top">
                      <StatusTag label={row.stage} tone={getStageTone(row.stage)} />
                      <div className="mt-2 max-w-[190px] text-xs leading-5 text-gray-500 dark:text-gray-400">
                        {row.stageReason || row.lifecycleStage.summary}
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3 align-top">
                      <div className="font-semibold text-gray-900 dark:text-white">{row.score}</div>
                      <div className={`text-xs ${row.scoreChange >= 0 ? "text-green-600 dark:text-green-300" : "text-red-600 dark:text-red-300"}`}>
                        {row.scoreChange >= 0 ? "+" : ""}
                        {row.scoreChange.toFixed(1)}
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3 align-top">
                      <StatusTag label={row.riskLevel} tone={getRiskTone(row.riskLevel)} />
                      <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">{row.momentum}</div>
                    </TableCell>
                    <TableCell className="px-4 py-3 align-top">
                      <div className="grid max-w-[260px] grid-cols-2 gap-2">
                        {row.promotionChecks.map((check) => (
                          <div key={`${row.symbol}-${check.key}`} className="flex items-start gap-1.5 text-xs leading-5 text-gray-600 dark:text-gray-300" title={check.detail}>
                            {check.passed ? (
                              <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-green-500" aria-hidden="true" />
                            ) : (
                              <Circle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400" aria-hidden="true" />
                            )}
                            <span>{check.label}</span>
                          </div>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="px-4 py-3 text-sm leading-6 text-gray-600 dark:text-gray-300">
                      <div className="max-w-[220px]">{row.nextEvent}</div>
                    </TableCell>
                    <TableCell className="px-4 py-3 align-top">
                      <div className="flex flex-col gap-2">
                        {isTracked ? (
                          <Link
                            href={`/tenx-hunter/${marketPath}/${row.flowStatus === "alerting" ? "alerts" : "watchlist"}`}
                            className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
                          >
                            {row.flowStatus === "alerting" ? <BellRing className="h-4 w-4" aria-hidden="true" /> : <Binoculars className="h-4 w-4" aria-hidden="true" />}
                            查看
                          </Link>
                        ) : (
                          <button
                            type="button"
                            onClick={() => void promoteToWatchlist(row.symbol)}
                            disabled={!canPromote || pendingSymbol === row.symbol}
                            title={canPromote ? "加入观察池" : "晋级条件未满足"}
                            className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
                          >
                            <Binoculars className="h-4 w-4" aria-hidden="true" />
                            {pendingSymbol === row.symbol ? "处理中" : "观察"}
                          </button>
                        )}
                        <Link
                          href={`/tenx-hunter/${marketPath}/research/${row.symbol}/report`}
                          className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
                        >
                          <BookOpen className="h-4 w-4" aria-hidden="true" />
                          报告
                        </Link>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredCandidates.length}
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </>
        ) : (
          <div className="space-y-4">
            {snapshot.timeline.map((event) => (
              <div key={event.id} className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">{event.date}</div>
                    <div className="mt-1 text-base font-semibold text-gray-900 dark:text-white">{event.title}</div>
                    <div className="mt-1 text-sm text-gray-600 dark:text-gray-300">{event.summary}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusTag label={event.type} tone="blue" />
                    <Link
                      href={`/tenx-hunter/${marketPath}/research/${event.symbol}`}
                      className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-300 dark:hover:text-brand-200"
                    >
                      {event.symbol}
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </TenxSectionCard>

      <TenxSectionCard title="Flow Exceptions" description="不让页面概念互相覆盖。">
        <div className="grid grid-cols-1 gap-3 text-sm leading-6 text-gray-600 dark:text-gray-300 lg:grid-cols-3">
          <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
            <StatusTag label="Hot Monitor" tone={getFlowTone("hot-lead")} />
            <p className="mt-3">只负责捕捉社交热度线索，不能自动代表基本面候选。</p>
          </div>
          <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
            <StatusTag label="Themes" tone="blue" />
            <p className="mt-3">只负责主线归因和主题热度，不重复展示完整候选池。</p>
          </div>
          <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
            <StatusTag label="Watchlist" tone={getFlowTone("watching")} />
            <p className="mt-3">只显示已确认跟踪的股票，不再混入系统兜底候选。</p>
          </div>
        </div>
      </TenxSectionCard>
    </TenxPageShell>
  );
}
