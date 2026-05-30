"use client";

import StatusTag from "@/components/cb-quant/StatusTag";
import {
  buildHotStockRows,
  formatCompactNumber,
  formatSignedNumber,
  formatSignedPercent,
  type TenxHotStockRow,
} from "@/components/tenx-hunter/hotMonitor";
import { getSocialHotErrorMessage, loadSocialHotStocks, type SocialHotStocksResponse } from "@/components/tenx-hunter/socialHotApi";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, ExternalLink, Flame, RefreshCw, Search, TrendingDown, TrendingUp } from "lucide-react";
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

function DesktopHotTable({ rows }: { rows: TenxHotStockRow[] }) {
  return (
    <div className="hidden overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03] xl:block">
      <table className="min-w-full table-fixed divide-y divide-gray-200 dark:divide-gray-800">
        <thead className="bg-gray-50 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">
          <tr>
            <th className="w-20 px-5 py-4 text-left">排名</th>
            <th className="w-[28%] px-5 py-4 text-left">股票名称</th>
            <th className="w-24 px-5 py-4 text-left">代码</th>
            <th className="w-32 px-5 py-4 text-right">提及次数</th>
            <th className="w-36 px-5 py-4 text-right">24h 变化</th>
            <th className="w-32 px-5 py-4 text-right">点赞数</th>
            <th className="w-32 px-5 py-4 text-right">排名变化</th>
            <th className="w-36 px-5 py-4 text-right">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {rows.map((row) => (
            <tr key={row.symbol} className="transition hover:bg-gray-50/80 dark:hover:bg-white/[0.04]">
              <td className="px-5 py-4">
                <HotRankBadge rank={row.rank} />
              </td>
              <td className="px-5 py-4">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-gray-900 dark:text-white">{row.name}</div>
                  <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">ApeWisdom · Reddit 股票社区</div>
                </div>
              </td>
              <td className="px-5 py-4 text-sm font-semibold text-gray-900 dark:text-white">{row.symbol}</td>
              <td className="px-5 py-4 text-right">
                <div className="text-lg font-semibold text-gray-900 dark:text-white">{formatCompactNumber(row.mentions)}</div>
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">前值 {row.mentions24hAgo ?? "N/A"}</div>
              </td>
              <td className={`px-5 py-4 text-right text-sm font-semibold ${changeTone(row.mentionChange)}`}>
                <div>{formatSignedNumber(row.mentionChange)}</div>
                <div className="mt-1 text-xs">{formatSignedPercent(row.mentionChangePct)}</div>
              </td>
              <td className="px-5 py-4 text-right text-sm font-semibold text-gray-900 dark:text-white">
                {formatCompactNumber(row.upvotes)}
              </td>
              <td className={`px-5 py-4 text-right text-sm font-semibold ${changeTone(row.rankChange)}`}>
                {formatSignedNumber(row.rankChange)}
              </td>
              <td className="px-5 py-4 text-right">
                <Link
                  href={`/tenx-hunter/us/research/${row.symbol}`}
                  className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
                >
                  <Search className="h-4 w-4" aria-hidden="true" />
                  研究
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MobileHotList({ rows }: { rows: TenxHotStockRow[] }) {
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
        </div>

        <div className="p-5 xl:p-6">
          {rows.length ? (
            <>
              <DesktopHotTable rows={rows} />
              <MobileHotList rows={rows} />
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
