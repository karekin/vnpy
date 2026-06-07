"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import StatusTag from "@/components/cb-quant/StatusTag";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import type { TenxEarningsDeskData } from "@/components/tenx-hunter/types";
import { CalendarClock, ChevronRight, ShieldCheck, Target, TrendingUp } from "lucide-react";

type Props = {
  data: TenxEarningsDeskData;
  error?: string | null;
};

type TimeBucket = "all" | "this-week" | "next-week" | "two-weeks";

/* ── 工具函数 ── */

function formatCompact(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  if (Math.abs(value) >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  const normalized = Math.abs(value) > 2 ? value / 100 : value;
  return `${(normalized * 100).toFixed(1)}%`;
}

function dayLabel(days: number | null | undefined) {
  if (days === null || days === undefined) return "日期未知";
  if (days < 0) return "已过";
  if (days === 0) return "TODAY";
  return `T-${days}`;
}

function dayTone(days: number | null | undefined): "red" | "blue" | "slate" {
  if (days === null || days === undefined) return "slate";
  if (days <= 3 && days >= 0) return "red";
  return "blue";
}

function priorityTone(priority: string): "red" | "yellow" | "slate" {
  if (priority === "P1") return "red";
  if (priority === "P2") return "yellow";
  return "slate";
}

function flowTone(sentiment: string): "green" | "red" | "yellow" | "slate" {
  if (sentiment === "bullish") return "green";
  if (sentiment === "bearish") return "red";
  if (sentiment === "neutral") return "yellow";
  return "slate";
}

function inBucket(days: number | null | undefined, bucket: TimeBucket): boolean {
  if (bucket === "all") return true;
  if (days === null || days === undefined || days < 0) return false;
  if (bucket === "this-week") return days <= 7;
  if (bucket === "next-week") return days > 7 && days <= 14;
  if (bucket === "two-weeks") return days <= 14;
  return true;
}

/* ── 统计卡片 ── */

type MetricCardProps = {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  tone?: "blue" | "green" | "red" | "slate";
};

function MetricCard({ icon, label, value, tone = "blue" }: MetricCardProps) {
  const toneClasses = {
    blue: "border-brand-200 bg-brand-50/40 dark:border-brand-500/20 dark:bg-brand-500/5",
    green: "border-green-200 bg-green-50/40 dark:border-green-500/20 dark:bg-green-500/5",
    red: "border-red-200 bg-red-50/40 dark:border-red-500/20 dark:bg-red-500/5",
    slate: "border-gray-200 bg-gray-50/40 dark:border-gray-700 dark:bg-gray-900/40",
  }[tone];

  return (
    <div className={`rounded-lg border p-3 ${toneClasses}`}>
      <div className="flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-lg font-bold text-gray-900 dark:text-white">{value}</div>
    </div>
  );
}

/* ── 事件行卡片 ── */

function EventRow({ ev, market }: { ev: TenxEarningsDeskData["events"][number]; market: string }) {
  const isP1 = ev.priority === "P1";
  const borderClass = isP1
    ? "border-l-4 border-l-red-400 dark:border-l-red-500"
    : "border-l-4 border-l-transparent";

  return (
    <Link
      href={`/tenx-hunter/${market.toLowerCase()}/research/${ev.symbol}`}
      className={`group block rounded-xl border border-gray-200 bg-white p-4 transition hover:border-brand-300 hover:shadow-sm dark:border-gray-800 dark:bg-gray-950/50 dark:hover:border-brand-500/40 ${borderClass}`}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-6">
        {/* 左：Symbol + 公司信息 */}
        <div className="min-w-[140px] shrink-0 lg:w-[180px]">
          <div className="flex items-center gap-2">
            <span className="text-base font-bold text-gray-900 group-hover:text-brand-600 dark:text-white dark:group-hover:text-brand-300">
              {ev.symbol}
            </span>
            <StatusTag label={ev.priority} tone={priorityTone(ev.priority)} />
          </div>
          <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{ev.name || "—"}</div>
          {ev.sector && (
            <div className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{ev.sector}</div>
          )}
        </div>

        {/* 中：财报日历 */}
        <div className="flex flex-wrap items-center gap-3 lg:min-w-[220px]">
          <div className="flex items-center gap-2">
            <StatusTag label={dayLabel(ev.daysToEarnings)} tone={dayTone(ev.daysToEarnings)} />
          </div>
          <div className="text-sm">
            <div className="text-gray-700 dark:text-gray-300">{ev.nextEarningsDate || "—"}</div>
            {(ev.timeOfDay || ev.fiscalPeriod) && (
              <div className="text-xs text-gray-400 dark:text-gray-500">
                {[ev.timeOfDay, ev.fiscalPeriod].filter(Boolean).join(" · ")}
              </div>
            )}
          </div>
        </div>

        {/* EPS / Revenue */}
        <div className="flex items-center gap-4 text-sm lg:min-w-[180px]">
          <div>
            <span className="text-xs text-gray-400 dark:text-gray-500">EPS</span>
            <div className="font-semibold text-gray-700 dark:text-gray-300">
              {ev.epsEstimate !== null && ev.epsEstimate !== undefined ? `$${ev.epsEstimate.toFixed(2)}` : "N/A"}
            </div>
          </div>
          <div>
            <span className="text-xs text-gray-400 dark:text-gray-500">Rev</span>
            <div className="font-semibold text-gray-700 dark:text-gray-300">
              {formatCompact(ev.revenueEstimate)}
            </div>
          </div>
        </div>

        {/* 期权信号 */}
        <div className="flex flex-1 items-center gap-3">
          {ev.optionSignal ? (
            <>
              <StatusTag
                label={
                  ev.flowSentiment === "bullish" ? "偏多" :
                  ev.flowSentiment === "bearish" ? "偏空" :
                  ev.flowSentiment === "neutral" ? "波动" : "无数据"
                }
                tone={flowTone(ev.flowSentiment)}
              />
              {ev.optionSelectionScore !== null && ev.optionSelectionScore !== undefined && (
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                  分 {ev.optionSelectionScore.toFixed(1)}
                </span>
              )}
              <span className="hidden text-sm text-gray-600 dark:text-gray-300 xl:inline">
                {ev.optionSignal}
              </span>
            </>
          ) : (
            <span className="text-xs text-gray-400 dark:text-gray-500">期权待补</span>
          )}
        </div>

        {/* 右：行动建议 + 箭头 */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm text-gray-500 dark:text-gray-400">{ev.actionLabel || "—"}</span>
          <ChevronRight className="h-4 w-4 text-gray-300 transition group-hover:text-brand-500 dark:text-gray-600 dark:group-hover:text-brand-400" />
        </div>
      </div>
    </Link>
  );
}

/* ── 主组件 ── */

export default function TenxEarningsDeskClient({ data, error }: Props) {
  const [bucket, setBucket] = useState<TimeBucket>("all");

  const filtered = useMemo(
    () => data.events.filter((ev) => inBucket(ev.daysToEarnings, bucket)),
    [data.events, bucket],
  );

  const sorted = useMemo(
    () =>
      [...filtered].sort((a, b) => {
        const da = a.daysToEarnings ?? 9999;
        const db = b.daysToEarnings ?? 9999;
        return da - db || a.symbol.localeCompare(b.symbol);
      }),
    [filtered],
  );

  const { metrics } = data;

  return (
    <TenxPageShell
      market={data.market}
      title="TenX Hunter · Earnings Event Desk"
      subtitle="市场全量财报事件看板：即将到来的财报日、期权信号和行动建议。"
      pipelineStage="earnings"
    >
      {/* 指标卡片 */}
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard
          icon={<CalendarClock className="h-3.5 w-3.5" />}
          label="近期财报"
          value={metrics.totalEvents}
          tone="blue"
        />
        <MetricCard
          icon={<Target className="h-3.5 w-3.5" />}
          label="P1 高优先"
          value={metrics.p1Count}
          tone={metrics.p1Count > 0 ? "red" : "slate"}
        />
        <MetricCard
          icon={<ShieldCheck className="h-3.5 w-3.5" />}
          label="期权可读"
          value={metrics.optionReadableCount}
          tone="green"
        />
        <MetricCard
          icon={<TrendingUp className="h-3.5 w-3.5" />}
          label="平均预期波动"
          value={formatPercent(metrics.avgExpectedMove)}
          tone="blue"
        />
      </div>

      {/* 时间桶过滤器 */}
      <div className="mb-4 inline-flex rounded-lg bg-gray-100 p-1 dark:bg-gray-900">
        {(
          [
            { key: "all", label: "全部" },
            { key: "this-week", label: "本周 (T-7)" },
            { key: "next-week", label: "下周 (T-14)" },
            { key: "two-weeks", label: "两周内" },
          ] as const
        ).map((opt) => (
          <button
            key={opt.key}
            type="button"
            onClick={() => setBucket(opt.key)}
            className={`rounded-md px-3 py-2 text-sm font-medium transition ${
              bucket === opt.key
                ? "bg-white text-gray-900 shadow dark:bg-gray-800 dark:text-white"
                : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* 提示信息 */}
      {error && (
        <div className="mb-4 rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-sm text-yellow-700 dark:border-yellow-500/30 dark:bg-yellow-500/10 dark:text-yellow-300">
          {error}
        </div>
      )}
      {data.notes.length > 0 && (
        <div className="mb-4 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">
          {data.notes.join(" ")}
        </div>
      )}

      {/* 事件列表：一行一个卡片 */}
      <div className="space-y-2">
        {sorted.length === 0 ? (
          <div className="rounded-xl border border-gray-200 bg-white px-4 py-8 text-center text-sm text-gray-400 dark:border-gray-800 dark:bg-gray-950/50 dark:text-gray-500">
            当前时间窗口内没有即将到来的财报事件。
          </div>
        ) : (
          sorted.map((ev) => (
            <EventRow key={`${ev.symbol}-${ev.nextEarningsDate}`} ev={ev} market={data.market} />
          ))
        )}
      </div>
    </TenxPageShell>
  );
}
