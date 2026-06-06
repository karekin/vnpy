"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import { getRiskTone, getStageTone, TenxSectionCard } from "@/components/tenx-hunter/TenxCards";
import type { TenxEarningsLens, TenxEarningsOptionItem, TenxEarningsShortlineItem } from "@/components/tenx-hunter/types";
import { TableCell, TableRow } from "@/components/ui/table";
import { Activity, BarChart3, CalendarClock, Database, ExternalLink, Gauge, LineChart, ShieldCheck } from "lucide-react";

type TenxEarningsLensPanelProps = {
  lens?: TenxEarningsLens | null;
  error?: string | null;
};

type LensMode = "shortline" | "options";

function formatCompactNumber(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  const number = Number(value);
  if (Math.abs(number) >= 1_000_000_000) return `${(number / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(number) >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}M`;
  if (Math.abs(number) >= 1_000) return `${(number / 1_000).toFixed(1)}K`;
  return number.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function formatCurrency(value: number | null | undefined, currency?: string) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  const prefix = currency === "CNY" ? "¥" : "$";
  return `${prefix}${formatCompactNumber(value)}`;
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  const scaled = Math.abs(Number(value)) <= 1 ? Number(value) * 100 : Number(value);
  return `${scaled.toFixed(1)}%`;
}

function formatSigned(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(1)}`;
}

function dayLabel(days?: number | null) {
  if (days === null || days === undefined) return "未知";
  if (days < 0) return "已过";
  if (days === 0) return "今天";
  return `T-${days}`;
}

function dayTone(days?: number | null) {
  if (days === null || days === undefined) return "slate" as const;
  if (days < 0) return "slate" as const;
  if (days <= 3) return "red" as const;
  if (days <= 10) return "yellow" as const;
  return "blue" as const;
}

function optionTone(row: TenxEarningsOptionItem) {
  if (row.dataQualityFlag !== "ok") return "slate" as const;
  if ((row.optionSelectionScore ?? 0) >= 70) return "green" as const;
  if ((row.liquidityScore ?? 0) >= 50) return "blue" as const;
  return "yellow" as const;
}

function sentimentTone(value: string) {
  if (value === "bullish") return "green" as const;
  if (value === "bearish") return "red" as const;
  if (value === "neutral") return "blue" as const;
  return "slate" as const;
}

function average(values: Array<number | null | undefined>) {
  const valid = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!valid.length) return null;
  return valid.reduce((sum, value) => sum + value, 0) / valid.length;
}

export default function TenxEarningsLensPanel({ lens, error }: TenxEarningsLensPanelProps) {
  const [mode, setMode] = useState<LensMode>("shortline");
  const metrics = useMemo(() => {
    const shortline = lens?.shortline ?? [];
    const options = lens?.options ?? [];
    return {
      upcoming: shortline.filter((item) => item.daysToEarnings !== null && item.daysToEarnings !== undefined && item.daysToEarnings >= 0 && item.daysToEarnings <= 14).length,
      priority: shortline.filter((item) => (item.daysToEarnings ?? 999) >= 0 && (item.daysToEarnings ?? 999) <= 10 && item.score >= 70).length,
      optionReady: options.filter((item) => item.dataQualityFlag === "ok").length,
      avgIv: average(options.filter((item) => item.dataQualityFlag === "ok").map((item) => item.avgImpliedVolatility)),
    };
  }, [lens]);

  return (
    <TenxSectionCard
      title="Earnings Lens"
      description="财报窗口、预期和期权链摘要均来自 TenX 已采集数据。"
      action={
        <div className="inline-flex rounded-lg bg-gray-100 p-1 dark:bg-gray-900" aria-label="Earnings lens mode">
          <button
            type="button"
            onClick={() => setMode("shortline")}
            className={`inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium ${
              mode === "shortline"
                ? "bg-white text-gray-900 shadow dark:bg-gray-800 dark:text-white"
                : "text-gray-500 dark:text-gray-400"
            }`}
          >
            <CalendarClock className="h-4 w-4" aria-hidden="true" />
            财报短线
          </button>
          <button
            type="button"
            onClick={() => setMode("options")}
            className={`inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium ${
              mode === "options"
                ? "bg-white text-gray-900 shadow dark:bg-gray-800 dark:text-white"
                : "text-gray-500 dark:text-gray-400"
            }`}
          >
            <Activity className="h-4 w-4" aria-hidden="true" />
            财报期权
          </button>
        </div>
      }
    >
      {error ? (
        <div className="mb-4 rounded-lg bg-yellow-50 px-4 py-3 text-sm leading-6 text-yellow-800 dark:bg-yellow-500/10 dark:text-yellow-200">
          {error}
        </div>
      ) : null}

      <DataSourceNote />

      <div className="mb-5 grid grid-cols-1 gap-3 md:grid-cols-4">
        <MetricPill icon={<CalendarClock className="h-4 w-4" />} label="14D 财报" value={String(metrics.upcoming)} />
        <MetricPill icon={<Gauge className="h-4 w-4" />} label="优先复核" value={String(metrics.priority)} />
        <MetricPill icon={<ShieldCheck className="h-4 w-4" />} label="期权可读" value={String(metrics.optionReady)} />
        <MetricPill icon={<LineChart className="h-4 w-4" />} label="平均 IV" value={formatPercent(metrics.avgIv)} />
      </div>

      {!lens ? (
        <div className="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
          Earnings Lens 暂不可用。
        </div>
      ) : mode === "shortline" ? (
        <ShortlineTable items={lens.shortline} marketPath={lens.market.toLowerCase()} />
      ) : (
        <OptionsTable items={lens.options} marketPath={lens.market.toLowerCase()} />
      )}

      {lens?.notes.length ? (
        <div className="mt-4 rounded-lg bg-gray-50 px-4 py-3 text-sm leading-6 text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
          {lens.notes.join(" ")}
        </div>
      ) : null}
    </TenxSectionCard>
  );
}

function DataSourceNote() {
  return (
    <div
      className="mb-5 grid gap-3 rounded-lg border border-gray-100 bg-gray-50/70 p-3 text-sm leading-6 text-gray-600 dark:border-gray-800 dark:bg-gray-900/35 dark:text-gray-300 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]"
      aria-label="Earnings Lens data sources"
    >
      <div className="flex min-w-0 gap-3">
        <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-brand-600 shadow-xs dark:bg-gray-800 dark:text-brand-300">
          <Database className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <div className="font-semibold text-gray-900 dark:text-white">当前数据链路</div>
          <p className="mt-1">
            财报短线读取 <code className="break-all rounded bg-white px-1.5 py-0.5 text-xs dark:bg-gray-800">dwd.security_earnings_calendar_current</code>；
            财报期权读取 <code className="break-all rounded bg-white px-1.5 py-0.5 text-xs dark:bg-gray-800">dws.security_option_chain_summary_daily</code>。
            0 / N/A 表示候选标的尚未补齐下一次财报日或可用期权链摘要。
          </p>
        </div>
      </div>
      <div className="min-w-0">
        <div className="font-semibold text-gray-900 dark:text-white">可接入公开源</div>
        <div className="mt-2 flex flex-wrap gap-2">
          <SourceLink href="https://www.sec.gov/search-filings/edgar-application-programming-interfaces" label="SEC EDGAR" />
          <SourceLink href="https://www.alphavantage.co/documentation/" label="Alpha Vantage" />
          <SourceLink href="https://ranaroussi.github.io/yfinance/" label="yfinance" />
          <SourceLink href="https://docs.openbb.co/platform/reference/derivatives/options/chains" label="OpenBB" />
        </div>
        <p className="mt-2 text-xs leading-5 text-gray-500 dark:text-gray-400">
          SEC 适合财报事实与 filings；财报日历/期权链更适合用 Alpha Vantage、yfinance 或 OpenBB 接入后缓存落库，并复核授权边界。
        </p>
      </div>
    </div>
  );
}

function SourceLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex h-8 items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 text-xs font-semibold text-gray-700 transition hover:border-brand-200 hover:text-brand-700 dark:border-gray-700 dark:bg-gray-950/30 dark:text-gray-300 dark:hover:border-brand-400/50 dark:hover:text-brand-200"
    >
      {label}
      <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
    </a>
  );
}

function MetricPill({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center gap-3 rounded-lg bg-gray-50 px-4 py-3 dark:bg-gray-900/60">
      <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-brand-600 shadow-xs dark:bg-gray-800 dark:text-brand-300">
        {icon}
      </span>
      <div className="min-w-0">
        <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
        <div className="mt-0.5 truncate text-lg font-semibold text-gray-900 dark:text-white">{value}</div>
      </div>
    </div>
  );
}

function ShortlineTable({ items, marketPath }: { items: TenxEarningsShortlineItem[]; marketPath: string }) {
  return (
    <ScrollableDataTable
      headers={["Symbol", "Window", "Score", "Stage", "Estimate", "Signal", "Flow", "Action"]}
      minTableWidthClass="min-w-[1160px]"
      colSpan={8}
      isEmpty={!items.length}
    >
      {items.slice(0, 12).map((row) => (
        <TableRow key={row.symbol} className="border-b border-gray-100 last:border-b-0 dark:border-gray-800">
          <TableCell className="px-4 py-3 align-top">
            <Link
              href={`/tenx-hunter/${marketPath}/research/${row.symbol}`}
              className="font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300"
            >
              {row.symbol}
            </Link>
            <div className="mt-1 max-w-[180px] truncate text-sm text-gray-500 dark:text-gray-400">{row.name}</div>
            <div className="mt-2">
              <StatusTag label={row.theme} tone="blue" />
            </div>
          </TableCell>
          <TableCell className="px-4 py-3 align-top">
            <StatusTag label={dayLabel(row.daysToEarnings)} tone={dayTone(row.daysToEarnings)} />
            <div className="mt-2 text-sm font-medium text-gray-800 dark:text-white/90">{row.nextEarningsDate ?? "N/A"}</div>
            <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{row.timeOfDay || row.fiscalPeriod || "TBD"}</div>
          </TableCell>
          <TableCell className="px-4 py-3 align-top">
            <div className="text-base font-semibold text-gray-900 dark:text-white">{row.score}</div>
            <div className={`text-xs ${row.scoreChange >= 0 ? "text-green-600 dark:text-green-300" : "text-red-600 dark:text-red-300"}`}>
              {formatSigned(row.scoreChange)}
            </div>
          </TableCell>
          <TableCell className="px-4 py-3 align-top">
            <StatusTag label={row.stage} tone={getStageTone(row.stage)} />
            <div className="mt-2">
              <StatusTag label={row.riskLevel} tone={getRiskTone(row.riskLevel)} />
            </div>
          </TableCell>
          <TableCell className="px-4 py-3 text-sm leading-6 text-gray-600 dark:text-gray-300">
            <div>EPS {row.epsEstimate === null || row.epsEstimate === undefined ? "N/A" : row.epsEstimate.toFixed(2)}</div>
            <div>Rev {formatCurrency(row.revenueEstimate, row.currency)}</div>
          </TableCell>
          <TableCell className="px-4 py-3 align-top">
            <div className="max-w-[260px] text-sm leading-6 text-gray-600 dark:text-gray-300">{row.shortlineSignal}</div>
            <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{row.sourceVendor || row.earningsQuality}</div>
          </TableCell>
          <TableCell className="px-4 py-3 align-top">
            <StatusTag label={row.flowStatusLabel} tone={row.flowStatus === "blocked" ? "red" : row.flowStatus === "watch-ready" ? "green" : "slate"} />
          </TableCell>
          <TableCell className="px-4 py-3 align-top">
            <Link
              href={`/tenx-hunter/${marketPath}/research/${row.symbol}`}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
            >
              <BarChart3 className="h-4 w-4" aria-hidden="true" />
              {row.actionLabel}
            </Link>
          </TableCell>
        </TableRow>
      ))}
    </ScrollableDataTable>
  );
}

function OptionsTable({ items, marketPath }: { items: TenxEarningsOptionItem[]; marketPath: string }) {
  return (
    <ScrollableDataTable
      headers={["Symbol", "Score", "IV / Flow", "Call / Put", "Liquidity", "Max Pain", "Signal", "Action"]}
      minTableWidthClass="min-w-[1240px]"
      colSpan={8}
      isEmpty={!items.length}
    >
      {items.slice(0, 12).map((row) => (
        <TableRow key={row.symbol} className="border-b border-gray-100 last:border-b-0 dark:border-gray-800">
          <TableCell className="px-4 py-3 align-top">
            <Link
              href={`/tenx-hunter/${marketPath}/research/${row.symbol}`}
              className="font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300"
            >
              {row.symbol}
            </Link>
            <div className="mt-1 max-w-[180px] truncate text-sm text-gray-500 dark:text-gray-400">{row.name}</div>
            <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">{row.nextEarningsDate ?? "N/A"} · {dayLabel(row.daysToEarnings)}</div>
          </TableCell>
          <TableCell className="px-4 py-3 align-top">
            <StatusTag label={formatCompactNumber(row.optionSelectionScore)} tone={optionTone(row)} />
            <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">TenX {row.score}</div>
          </TableCell>
          <TableCell className="px-4 py-3 align-top">
            <div className="font-semibold text-gray-900 dark:text-white">{formatPercent(row.avgImpliedVolatility)}</div>
            <div className="mt-2">
              <StatusTag label={row.flowSentiment} tone={sentimentTone(row.flowSentiment)} />
            </div>
          </TableCell>
          <TableCell className="px-4 py-3 text-sm leading-6 text-gray-600 dark:text-gray-300">
            <div>Vol {formatCompactNumber(row.callPutVolumeRatio)}</div>
            <div>OI {formatCompactNumber(row.callPutOpenInterestRatio)}</div>
          </TableCell>
          <TableCell className="px-4 py-3 text-sm leading-6 text-gray-600 dark:text-gray-300">
            <div>{formatCompactNumber(row.liquidityScore)}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">{row.contractCount} contracts</div>
          </TableCell>
          <TableCell className="px-4 py-3 text-sm leading-6 text-gray-600 dark:text-gray-300">
            <div>{formatCurrency(row.maxPainStrike)}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">{row.nearestExpiration ?? "No expiry"}</div>
          </TableCell>
          <TableCell className="px-4 py-3 align-top">
            <div className="max-w-[260px] text-sm leading-6 text-gray-600 dark:text-gray-300">{row.optionSignal}</div>
            <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{row.updatedAt || row.dataQualityFlag}</div>
          </TableCell>
          <TableCell className="px-4 py-3 align-top">
            <Link
              href={`/tenx-hunter/${marketPath}/research/${row.symbol}`}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
            >
              <Activity className="h-4 w-4" aria-hidden="true" />
              {row.actionLabel}
            </Link>
          </TableCell>
        </TableRow>
      ))}
    </ScrollableDataTable>
  );
}
