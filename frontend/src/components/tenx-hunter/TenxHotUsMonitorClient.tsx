"use client";

import StatusTag from "@/components/cb-quant/StatusTag";
import {
  buildHotStockRows,
  formatCompactNumber,
  formatSignedNumber,
  formatSignedPercent,
  type TenxHotStockRow,
} from "@/components/tenx-hunter/hotMonitor";
import { createDiscoverCandidate, getTenxErrorMessage } from "@/components/tenx-hunter/api";
import { getSocialHotErrorMessage, loadSocialHotStocks, type SocialHotStocksResponse } from "@/components/tenx-hunter/socialHotApi";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, ExternalLink, Flame, GitBranch, Plus, RefreshCw, Search, TrendingDown, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

const pageSizeOptions = [25, 50, 100, 200];

function changeTone(value: number | null | undefined) {
  if (value === null || value === undefined) return "text-gray-500 dark:text-gray-400";
  if (value > 0) return "text-green-600 dark:text-green-300";
  if (value < 0) return "text-red-600 dark:text-red-300";
  return "text-gray-600 dark:text-gray-300";
}

function updatedAtLabel(response: SocialHotStocksResponse | null) {
  return response?.generatedAt || "等待 ApeWisdom 数据";
}

function HotRankBadge({ rank }: { rank: number }) {
  const className =
    rank === 1
      ? "bg-orange-500 text-white"
      : rank === 2
        ? "bg-gray-800 text-white dark:bg-gray-100 dark:text-gray-900"
        : rank === 3
          ? "bg-brand-500 text-white"
          : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300";

  return (
    <span className={`inline-flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${className}`}>
      {rank}
    </span>
  );
}

function HeatSparkline({ row }: { row: TenxHotStockRow }) {
  const bars = [
    row.mentions24hAgo ?? 0,
    row.mentions,
    row.upvotes / 8,
    Math.max(0, row.mentionChange ?? 0) * 2,
    row.heatScore,
  ].map((value) => Math.max(12, Math.min(64, value / 4)));

  return (
    <div className="flex h-14 items-end gap-1.5" aria-label={`${row.symbol} social heat trend`}>
      {bars.map((height, index) => (
        <span
          key={`${row.symbol}-${index}`}
          className="block w-2 rounded-full bg-orange-400/85 dark:bg-orange-300/75"
          style={{ height }}
        />
      ))}
    </div>
  );
}

function HotRowActions({
  row,
  onAddCandidate,
  pendingSymbol,
}: {
  row: TenxHotStockRow;
  onAddCandidate: (row: TenxHotStockRow) => void;
  pendingSymbol: string | null;
}) {
  const isPending = pendingSymbol === row.symbol;

  return (
    <div className="inline-flex h-10 items-center overflow-hidden rounded-lg border border-gray-200 bg-white shadow-xs dark:border-gray-700 dark:bg-gray-900">
      <Link
        href={`/tenx-hunter/us/discover?symbol=${encodeURIComponent(row.symbol)}`}
        aria-label={`${row.symbol} 进入候选验证`}
        title="进入候选验证"
        className="inline-flex h-10 items-center gap-1.5 px-3 text-sm font-medium text-gray-600 transition hover:bg-brand-50 hover:text-brand-600 dark:text-gray-300 dark:hover:bg-brand-500/15 dark:hover:text-brand-300"
      >
        <GitBranch className="h-4 w-4" aria-hidden="true" />
        <span className="hidden 2xl:inline">验证</span>
      </Link>
      <button
        type="button"
        onClick={() => onAddCandidate(row)}
        disabled={isPending}
        aria-label={`${row.symbol} 加入发现池`}
        title="加入发现池"
        className="inline-flex h-10 min-w-[104px] items-center justify-center gap-1.5 border-x border-gray-200 bg-brand-500 px-3 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-brand-300 dark:border-gray-700 dark:bg-brand-500 dark:hover:bg-brand-400 dark:disabled:bg-brand-500/45"
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
        <span className="whitespace-nowrap">{isPending ? "加入中" : "加入发现"}</span>
      </button>
      <Link
        href={`/tenx-hunter/us/research/${row.symbol}`}
        aria-label={`打开 ${row.symbol} 研究卡`}
        title="打开研究卡"
        className="inline-flex h-10 items-center gap-1.5 px-3 text-sm font-medium text-gray-600 transition hover:bg-brand-50 hover:text-brand-600 dark:text-gray-300 dark:hover:bg-brand-500/15 dark:hover:text-brand-300"
      >
        <Search className="h-4 w-4" aria-hidden="true" />
        <span className="hidden 2xl:inline">研究</span>
      </Link>
    </div>
  );
}

function DesktopHotTable({
  rows,
  onAddCandidate,
  pendingSymbol,
}: {
  rows: TenxHotStockRow[];
  onAddCandidate: (row: TenxHotStockRow) => void;
  pendingSymbol: string | null;
}) {
  return (
    <div className="hidden overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03] xl:block">
      <table className="min-w-full table-fixed divide-y divide-gray-200 dark:divide-gray-800">
        <thead className="bg-gray-50 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">
          <tr>
            <th className="w-[42%] px-5 py-4 text-left">股票</th>
            <th className="w-32 px-4 py-4 text-right">提及</th>
            <th className="w-32 px-4 py-4 text-right">24h</th>
            <th className="w-36 px-4 py-4 text-right">互动 / 排名</th>
            <th className="w-64 px-5 py-4 text-right">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {rows.map((row) => (
            <tr key={row.symbol} className="transition hover:bg-gray-50/80 dark:hover:bg-white/[0.04]">
              <td className="px-5 py-4">
                <div className="flex min-w-0 items-center gap-3">
                  <HotRankBadge rank={row.rank} />
                  <div className="min-w-0">
                    <div className="flex min-w-0 items-center gap-2">
                      <Link
                        href={`/tenx-hunter/us/research/${row.symbol}`}
                        className="shrink-0 text-sm font-semibold text-gray-900 transition hover:text-brand-600 dark:text-white dark:hover:text-brand-300"
                      >
                        {row.symbol}
                      </Link>
                      <span className="truncate text-sm font-medium text-gray-700 dark:text-gray-200">{row.name}</span>
                    </div>
                    <div className="mt-1 truncate text-xs text-gray-500 dark:text-gray-400">ApeWisdom · Reddit 股票社区</div>
                  </div>
                </div>
              </td>
              <td className="px-4 py-4 text-right">
                <div className="text-lg font-semibold text-gray-900 dark:text-white">{formatCompactNumber(row.mentions)}</div>
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">前值 {row.mentions24hAgo ?? "N/A"}</div>
              </td>
              <td className={`px-4 py-4 text-right text-sm font-semibold ${changeTone(row.mentionChange)}`}>
                <div>{formatSignedNumber(row.mentionChange)}</div>
                <div className="mt-1 text-xs">{formatSignedPercent(row.mentionChangePct)}</div>
              </td>
              <td className="px-4 py-4 text-right">
                <div className="text-sm font-semibold text-gray-900 dark:text-white">{formatCompactNumber(row.upvotes)}</div>
                <div className={`mt-1 text-xs font-semibold ${changeTone(row.rankChange)}`}>排名 {formatSignedNumber(row.rankChange)}</div>
              </td>
              <td className="px-5 py-4">
                <div className="flex justify-end">
                  <HotRowActions row={row} onAddCandidate={onAddCandidate} pendingSymbol={pendingSymbol} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MobileHotList({
  rows,
  onAddCandidate,
  pendingSymbol,
}: {
  rows: TenxHotStockRow[];
  onAddCandidate: (row: TenxHotStockRow) => void;
  pendingSymbol: string | null;
}) {
  return (
    <div className="space-y-3 xl:hidden">
      {rows.map((row) => (
        <div key={row.symbol} className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex items-start gap-3">
            <HotRankBadge rank={row.rank} />
            <div className="min-w-0 flex-1">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <Link href={`/tenx-hunter/us/research/${row.symbol}`} className="text-base font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300">
                  {row.symbol}
                </Link>
                <span className="min-w-0 text-sm text-gray-500 [overflow-wrap:anywhere] dark:text-gray-400">{row.name}</span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                <StatusTag label={`${row.mentions} mentions`} tone="blue" />
                <StatusTag label={`${row.upvotes} upvotes`} tone="slate" />
              </div>
            </div>
            <div className="text-right">
              <div className="text-lg font-semibold text-gray-900 dark:text-white">{row.heatScore}</div>
              <div className={`text-xs font-medium ${changeTone(row.mentionChange)}`}>{formatSignedNumber(row.mentionChange)}</div>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
            <div>
              <div className="text-xs text-gray-500 dark:text-gray-400">24h 变化</div>
              <div className={`mt-1 font-semibold ${changeTone(row.mentionChange)}`}>{formatSignedPercent(row.mentionChangePct)}</div>
              <div className="text-xs text-gray-500 dark:text-gray-400">{formatSignedNumber(row.mentionChange)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 dark:text-gray-400">点赞数</div>
              <div className="mt-1 font-semibold text-gray-900 dark:text-white">{formatCompactNumber(row.upvotes)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 dark:text-gray-400">排名变化</div>
              <div className={`mt-1 font-semibold ${changeTone(row.rankChange)}`}>{formatSignedNumber(row.rankChange)}</div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={() => onAddCandidate(row)}
              disabled={pendingSymbol === row.symbol}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              {pendingSymbol === row.symbol ? "加入中" : "加入发现"}
            </button>
            <Link
              href={`/tenx-hunter/us/discover?symbol=${encodeURIComponent(row.symbol)}`}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
            >
              <GitBranch className="h-4 w-4" aria-hidden="true" />
              进入候选验证
            </Link>
          </div>
        </div>
      ))}
    </div>
  );
}

function buildVisiblePages(currentPage: number, totalPages: number) {
  const maxVisible = 5;
  let start = Math.max(1, currentPage - Math.floor(maxVisible / 2));
  const end = Math.min(totalPages, start + maxVisible - 1);
  if (end - start + 1 < maxVisible) {
    start = Math.max(1, end - maxVisible + 1);
  }
  return Array.from({ length: end - start + 1 }, (_, index) => start + index);
}

function PaginationIconButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-600 transition hover:border-brand-300 hover:text-brand-600 disabled:cursor-not-allowed disabled:opacity-45 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
    >
      {children}
    </button>
  );
}

function HotPaginationBar({
  response,
  isLoading,
  onPageChange,
  onPageSizeChange,
}: {
  response: SocialHotStocksResponse;
  isLoading: boolean;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}) {
  const currentPage = Math.max(1, response.page);
  const totalPages = Math.max(1, response.totalPages);
  const visiblePages = buildVisiblePages(currentPage, totalPages);
  const firstItem = response.returnedCount > 0 ? (currentPage - 1) * response.pageSize + 1 : 0;
  const lastItem = response.returnedCount > 0 ? firstItem + response.returnedCount - 1 : 0;
  const canGoPrevious = currentPage > 1 && !isLoading;
  const canGoNext = currentPage < totalPages && !isLoading;

  return (
    <div className="mt-5 flex flex-col gap-4 border-t border-gray-100 pt-5 dark:border-gray-800 xl:flex-row xl:items-center xl:justify-between">
      <div className="text-sm text-gray-500 dark:text-gray-400">
        显示 <span className="font-semibold text-gray-900 dark:text-white">{firstItem || 0}</span>
        {" - "}
        <span className="font-semibold text-gray-900 dark:text-white">{lastItem || 0}</span>
        {" / "}
        <span className="font-semibold text-gray-900 dark:text-white">{response.count}</span>
        {" · "}
        第 <span className="font-semibold text-gray-900 dark:text-white">{currentPage}</span> /{" "}
        <span className="font-semibold text-gray-900 dark:text-white">{totalPages}</span> 页
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between xl:justify-end">
        <label className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
          <span className="shrink-0">每页</span>
          <select
            value={String(response.pageSize)}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            disabled={isLoading}
            className="h-10 rounded-lg border border-gray-200 bg-white px-3 text-sm font-medium text-gray-700 outline-none transition focus:border-brand-300 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:focus:border-brand-400"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>{`${size} 条`}</option>
            ))}
          </select>
        </label>

        <div className="flex items-center gap-2">
          <PaginationIconButton label="第一页" disabled={!canGoPrevious} onClick={() => onPageChange(1)}>
            <ChevronsLeft className="h-4 w-4" aria-hidden="true" />
          </PaginationIconButton>
          <PaginationIconButton label="上一页" disabled={!canGoPrevious} onClick={() => onPageChange(currentPage - 1)}>
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </PaginationIconButton>

          <div className="hidden items-center gap-1 sm:flex">
            {visiblePages.map((page) => (
              <button
                key={page}
                type="button"
                onClick={() => onPageChange(page)}
                disabled={isLoading || page === currentPage}
                className={`inline-flex h-10 min-w-10 items-center justify-center rounded-lg px-3 text-sm font-semibold transition disabled:cursor-not-allowed ${
                  page === currentPage
                    ? "bg-brand-500 text-white"
                    : "text-gray-600 hover:bg-brand-50 hover:text-brand-600 dark:text-gray-300 dark:hover:bg-brand-500/15 dark:hover:text-brand-300"
                }`}
              >
                {page}
              </button>
            ))}
          </div>

          <span className="min-w-20 text-center text-sm font-medium text-gray-600 sm:hidden dark:text-gray-300">
            {currentPage} / {totalPages}
          </span>

          <PaginationIconButton label="下一页" disabled={!canGoNext} onClick={() => onPageChange(currentPage + 1)}>
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </PaginationIconButton>
          <PaginationIconButton label="最后一页" disabled={!canGoNext} onClick={() => onPageChange(totalPages)}>
            <ChevronsRight className="h-4 w-4" aria-hidden="true" />
          </PaginationIconButton>
        </div>
      </div>
    </div>
  );
}

export default function TenxHotUsMonitorClient({
  initialResponse,
  initialError = null,
}: {
  initialResponse: SocialHotStocksResponse | null;
  initialError?: string | null;
}) {
  const [response, setResponse] = useState<SocialHotStocksResponse | null>(initialResponse);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(initialError);
  const [pendingCandidateSymbol, setPendingCandidateSymbol] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const rows = useMemo(() => (response ? buildHotStockRows(response) : []), [response]);
  const topRow = rows[0];
  const risingCount = rows.filter((row) => (row.mentionChange ?? 0) > 0).length;
  const coolingCount = rows.filter((row) => (row.mentionChange ?? 0) < 0).length;
  const currentPage = response?.page ?? 1;
  const currentPageSize = response?.pageSize ?? 50;

  const loadPage = useCallback(async (page: number, pageSize: number, refreshFromProvider = false) => {
    setIsRefreshing(true);
    try {
      const nextResponse = await loadSocialHotStocks({ page, pageSize, refresh: refreshFromProvider });
      setResponse(nextResponse);
      setError(null);
    } catch (loadError) {
      setError(getSocialHotErrorMessage(loadError));
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  const refresh = useCallback(() => {
    void loadPage(currentPage, currentPageSize, true);
  }, [currentPage, currentPageSize, loadPage]);

  const changePage = useCallback((page: number) => {
    void loadPage(page, currentPageSize);
  }, [currentPageSize, loadPage]);

  const changePageSize = useCallback((pageSize: number) => {
    void loadPage(1, pageSize);
  }, [loadPage]);

  const addToDiscover = useCallback(async (row: TenxHotStockRow) => {
    setPendingCandidateSymbol(row.symbol);
    setActionMessage(null);
    try {
      const result = await createDiscoverCandidate("US", {
        symbol: row.symbol,
        name: row.name,
        source: "hot-monitor",
        theme: "Social Heat",
        thesis: `${row.symbol} 从 ApeWisdom 热点监控进入发现池，先验证热度是否对应基本面或事件催化。`,
        note: `当前提及 ${row.mentions}，24h 变化 ${formatSignedNumber(row.mentionChange)}，点赞 ${row.upvotes}。`,
        triggerScene: "hot-monitor-row-action",
        sourcePayload: {
          rank: row.rank,
          mentions: row.mentions,
          mentions24hAgo: row.mentions24hAgo,
          mentionChange: row.mentionChange,
          mentionChangePct: row.mentionChangePct,
          upvotes: row.upvotes,
          rankChange: row.rankChange,
          heatScore: row.heatScore,
        },
      });
      setActionMessage(result.message);
    } catch (candidateError) {
      setActionMessage(getTenxErrorMessage(candidateError));
    } finally {
      setPendingCandidateSymbol(null);
    }
  }, []);

  useEffect(() => {
    const intervalMs = Math.max(60, response?.refreshSeconds ?? 300) * 1000;
    const interval = window.setInterval(refresh, intervalMs);
    return () => {
      window.clearInterval(interval);
    };
  }, [refresh, response?.refreshSeconds]);

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="border-b border-gray-200 px-5 py-5 dark:border-gray-800 xl:px-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-orange-500 text-white">
                  <Flame className="h-5 w-5" aria-hidden="true" />
                </span>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900 dark:text-white">热门美股监控</h2>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    ApeWisdom · 过去 24 小时 Reddit 股票社区提及热度
                  </p>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="rounded-lg bg-gray-50 px-3 py-2 text-xs font-medium text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
                每 {Math.round((response?.refreshSeconds ?? 300) / 60)} 分钟自动刷新
              </div>
              <button
                type="button"
                onClick={refresh}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
                disabled={isRefreshing}
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} aria-hidden="true" />
                刷新
              </button>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400">当前页榜首</div>
              <div className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{topRow?.symbol ?? "N/A"}</div>
              <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{topRow?.name ?? "暂无数据"}</div>
            </div>
            <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400">ApeWisdom 总覆盖</div>
              <div className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{response?.count ?? rows.length}</div>
              <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                当前显示 {response ? `第 ${response.page}/${response.totalPages} 页 · ${rows.length} 条` : "Top 50"}
              </div>
            </div>
            <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400">升温标的</div>
              <div className="mt-2 flex items-center gap-2 text-2xl font-semibold text-green-600 dark:text-green-300">
                <TrendingUp className="h-5 w-5" aria-hidden="true" />
                {risingCount}
              </div>
              <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">当前页提及次数高于前 24h</div>
            </div>
            <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400">降温标的</div>
              <div className="mt-2 flex items-center gap-2 text-2xl font-semibold text-red-600 dark:text-red-300">
                <TrendingDown className="h-5 w-5" aria-hidden="true" />
                {coolingCount}
              </div>
              <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">当前页提及次数低于前 24h</div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-xs text-gray-500 dark:text-gray-400">
            <span>最新数据：{updatedAtLabel(response)}</span>
            <span>{response ? `${response.sourceLabel} · ${response.windowHours}h window` : "等待 ApeWisdom API"}</span>
          </div>
          {error ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800/60 dark:bg-red-500/10 dark:text-red-300">
              刷新失败：{error}
            </div>
          ) : null}
          {actionMessage ? (
            <div className="mt-4 rounded-xl border border-brand-100 bg-brand-50 px-4 py-3 text-sm text-brand-700 dark:border-brand-500/20 dark:bg-brand-500/10 dark:text-brand-200">
              {actionMessage}
            </div>
          ) : null}
        </div>

        <div className="p-5 xl:p-6">
          {rows.length ? (
            <>
              <DesktopHotTable rows={rows} onAddCandidate={(row) => void addToDiscover(row)} pendingSymbol={pendingCandidateSymbol} />
              <MobileHotList rows={rows} onAddCandidate={(row) => void addToDiscover(row)} pendingSymbol={pendingCandidateSymbol} />
              {response ? (
                <HotPaginationBar
                  response={response}
                  isLoading={isRefreshing}
                  onPageChange={changePage}
                  onPageSizeChange={changePageSize}
                />
              ) : null}
            </>
          ) : (
            <div className="rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
              暂无 ApeWisdom 热股数据。请检查外部网络或 ApeWisdom API 状态。
            </div>
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.4fr_1fr]">
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-gray-900 dark:text-white">社交热度走势</h3>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">提及前值、当前提及、点赞、提及增量和综合热度的压缩视图。</p>
            </div>
            <StatusTag label="ApeWisdom" tone="green" />
          </div>
          <div className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
            {rows.slice(0, 10).map((row) => (
              <div key={row.symbol} className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-gray-900 dark:text-white">{row.symbol}</div>
                    <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{formatCompactNumber(row.mentions)}</div>
                  </div>
                  <HeatSparkline row={row} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-gray-900 dark:text-white">重点跟踪</h3>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">榜首标的的研究入口和社交变化。</p>
            </div>
            <ExternalLink className="h-5 w-5 text-gray-400" aria-hidden="true" />
          </div>
          <div className="mt-4 space-y-3">
            {rows.slice(0, 5).map((row) => (
              <Link
                key={row.symbol}
                href={`/tenx-hunter/us/research/${row.symbol}`}
                className="flex items-center justify-between gap-3 rounded-xl bg-gray-50 px-4 py-3 transition hover:bg-brand-50 dark:bg-gray-900/60 dark:hover:bg-brand-500/15"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-gray-900 dark:text-white">{row.symbol}</div>
                  <div className="mt-1 truncate text-xs text-gray-500 dark:text-gray-400">{row.name}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold text-gray-900 dark:text-white">{formatCompactNumber(row.mentions)}</div>
                  <div className={`text-xs ${changeTone(row.mentionChange)}`}>{formatSignedNumber(row.mentionChange)}</div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
