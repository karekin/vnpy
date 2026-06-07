"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import StatusTag from "@/components/cb-quant/StatusTag";
import { TenxSectionCard, getRiskTone, getStageTone } from "@/components/tenx-hunter/TenxCards";
import type { TenxEarningsLens, TenxEarningsOptionItem, TenxEarningsShortlineItem } from "@/components/tenx-hunter/types";
import { CalendarClock, Gauge, ShieldCheck, Target } from "lucide-react";

type TenxDiscoverEarningsDeskProps = {
  lens?: TenxEarningsLens | null;
  error?: string | null;
  marketPath: string;
};

type ForecastTone = "green" | "yellow" | "red" | "blue" | "slate";

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

type EarningsSetup = {
  shortline: TenxEarningsShortlineItem;
  option?: TenxEarningsOptionItem;
  forecast: EventForecast;
};

const dateFormatter = new Intl.DateTimeFormat("zh-CN", {
  month: "numeric",
  day: "numeric",
});

const weekdayFormatter = new Intl.DateTimeFormat("zh-CN", {
  weekday: "short",
});

function normalizeVol(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  return Math.abs(value) > 2 ? value / 100 : value;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function formatNumber(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function formatCompact(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  if (Math.abs(value) >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return formatNumber(value);
}

function formatCurrency(value: number | null | undefined, currency = "USD") {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  const prefix = currency === "CNY" ? "¥" : "$";
  return `${prefix}${formatCompact(value)}`;
}

function formatPercent(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  return `${(value * 100).toFixed(digits)}%`;
}

function formatSignedPercent(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
}

function formatStrike(value: number | null | undefined, currency = "USD") {
  if (value === null || value === undefined || !Number.isFinite(value)) return "N/A";
  const prefix = currency === "CNY" ? "¥" : "$";
  return `${prefix}${value >= 100 ? value.toFixed(0) : value.toFixed(1)}`;
}

function parseDate(value?: string | null) {
  if (!value) return null;
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function dateLabel(value?: string | null) {
  const date = parseDate(value);
  if (!date) return "未知";
  return dateFormatter.format(date);
}

function weekdayLabel(value?: string | null) {
  const date = parseDate(value);
  if (!date) return "TBD";
  return weekdayFormatter.format(date);
}

function dayLabel(days?: number | null) {
  if (days === null || days === undefined) return "未知";
  if (days < 0) return "已过";
  if (days === 0) return "今天";
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

function buildForecast(shortline: TenxEarningsShortlineItem, option?: TenxEarningsOptionItem): EventForecast {
  if (!option || option.dataQualityFlag !== "ok") {
    return {
      directionLabel: "待补",
      directionTone: "slate",
      optionSide: "VOL",
      expectedMove: null,
      winProbability: null,
      strike: null,
      sellStrike: null,
      premium: null,
      spreadDebit: null,
    };
  }

  let directionalScore = 0;
  if (option.flowSentiment === "bullish") directionalScore += 2;
  if (option.flowSentiment === "bearish") directionalScore -= 2;
  if ((option.callPutVolumeRatio ?? 1) >= 1.25) directionalScore += 1;
  if ((option.callPutVolumeRatio ?? 1) <= 0.8) directionalScore -= 1;
  if (shortline.scoreChange >= 2) directionalScore += 1;
  if (shortline.scoreChange <= -2) directionalScore -= 1;

  const iv = normalizeVol(option.avgImpliedVolatility);
  const horizonDays = clamp(shortline.daysToEarnings ?? 7, 1, 30);
  const expectedMove = iv === null ? null : iv * Math.sqrt(horizonDays / 365);
  const selectionScore = option.optionSelectionScore ?? option.liquidityScore ?? null;
  const liquidityAdjustment = option.liquidityScore ? clamp((option.liquidityScore - 50) / 5, -6, 8) : 0;
  const directionalAdjustment = Math.abs(directionalScore) >= 2 ? 4 : 0;
  const winProbability = selectionScore === null ? null : clamp(43 + selectionScore * 0.34 + liquidityAdjustment + directionalAdjustment, 35, 86);

  const underlying = option?.underlyingPrice ?? null;
  const side: EventForecast["optionSide"] = directionalScore >= 2 ? "CALL" : directionalScore <= -2 ? "PUT" : "VOL";
  const moveForStrike = expectedMove ?? 0.08;
  const strike =
    underlying === null
      ? option?.maxPainStrike ?? null
      : side === "PUT"
        ? roundStrike(underlying * (1 - moveForStrike * 0.45))
        : side === "CALL"
          ? roundStrike(underlying * (1 + moveForStrike * 0.45))
          : roundStrike(underlying);
  const sellStrike =
    underlying === null || strike === null
      ? null
      : side === "PUT"
        ? roundStrike(strike * (1 - moveForStrike * 0.85))
        : roundStrike(strike * (1 + moveForStrike * 0.85));
  const premium = underlying === null ? null : underlying * moveForStrike * (side === "VOL" ? 0.32 : 0.22);
  const spreadDebit = underlying === null ? null : underlying * moveForStrike * 0.09;

  if (directionalScore >= 2) {
    return {
      directionLabel: "偏多",
      directionTone: "green",
      optionSide: side,
      expectedMove,
      winProbability,
      strike,
      sellStrike,
      premium,
      spreadDebit,
    };
  }
  if (directionalScore <= -2) {
    return {
      directionLabel: "偏空",
      directionTone: "red",
      optionSide: side,
      expectedMove,
      winProbability,
      strike,
      sellStrike,
      premium,
      spreadDebit,
    };
  }
  return {
    directionLabel: "波动",
    directionTone: "yellow",
    optionSide: side,
    expectedMove,
    winProbability,
    strike,
    sellStrike,
    premium,
    spreadDebit,
  };
}

function buildSetups(lens: TenxEarningsLens | null | undefined): EarningsSetup[] {
  if (!lens) return [];
  const optionsBySymbol = new Map(lens.options.map((item) => [item.symbol.toUpperCase(), item]));
  return lens.shortline
    .map((shortline) => {
      const option = optionsBySymbol.get(shortline.symbol.toUpperCase());
      return {
        shortline,
        option,
        forecast: buildForecast(shortline, option),
      };
    })
    .sort((left, right) => {
      const leftDays = left.shortline.daysToEarnings ?? 9999;
      const rightDays = right.shortline.daysToEarnings ?? 9999;
      if ((leftDays >= 0) !== (rightDays >= 0)) return leftDays >= 0 ? -1 : 1;
      if (leftDays !== rightDays) return leftDays - rightDays;
      return right.shortline.score - left.shortline.score;
    });
}

function buildDateBuckets(items: TenxEarningsShortlineItem[]) {
  const counts = new Map<string, number>();
  items.forEach((item) => {
    if (!item.nextEarningsDate) return;
    counts.set(item.nextEarningsDate, (counts.get(item.nextEarningsDate) ?? 0) + 1);
  });
  return Array.from(counts.entries())
    .map(([date, count]) => ({ date, count }))
    .sort((left, right) => left.date.localeCompare(right.date))
    .slice(0, 5);
}

export default function TenxDiscoverEarningsDesk({ lens, error, marketPath }: TenxDiscoverEarningsDeskProps) {
  const [dateFilter, setDateFilter] = useState("all");
  const setups = useMemo(() => buildSetups(lens), [lens]);
  const dateBuckets = useMemo(() => buildDateBuckets(lens?.shortline ?? []), [lens]);
  const filteredSetups = dateFilter === "all" ? setups : setups.filter((item) => item.shortline.nextEarningsDate === dateFilter);
  const topSetups = filteredSetups.slice(0, 3);

  const metrics = useMemo(() => {
    const upcoming = setups.filter((item) => {
      const days = item.shortline.daysToEarnings;
      return days !== null && days !== undefined && days >= 0 && days <= 14;
    });
    const optionReady = setups.filter((item) => item.option?.dataQualityFlag === "ok");
    const moves = optionReady
      .map((item) => item.forecast.expectedMove)
      .filter((value): value is number => value !== null && Number.isFinite(value));
    const avgMove = moves.length ? moves.reduce((sum, value) => sum + value, 0) / moves.length : null;
    return {
      upcoming: upcoming.length,
      priority: upcoming.filter((item) => item.shortline.score >= 70).length,
      optionReady: optionReady.length,
      avgMove,
    };
  }, [setups]);

  return (
    <TenxSectionCard
      title="Earnings Event Desk"
      description="按财报日期聚合候选池，合并营收/EPS预期、预期波动、期权流向和结构化表达。"
      action={<StatusTag label={lens?.snapshotAt ? `更新 ${lens.snapshotAt}` : "Earnings Lens"} tone={lens ? "blue" : "slate"} />}
    >
      {error ? (
        <div className="mb-4 rounded-lg bg-yellow-50 px-4 py-3 text-sm leading-6 text-yellow-800 dark:bg-yellow-500/10 dark:text-yellow-200">
          {error}
        </div>
      ) : null}

      {!lens ? (
        <div className="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
          Earnings Lens 暂不可用，Discover 仍保留候选池评分和晋级检查。
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <MetricTile icon={<CalendarClock className="h-4 w-4" />} label="14D 财报" value={String(metrics.upcoming)} />
            <MetricTile icon={<Target className="h-4 w-4" />} label="短线优先" value={String(metrics.priority)} />
            <MetricTile icon={<ShieldCheck className="h-4 w-4" />} label="期权可读" value={String(metrics.optionReady)} />
            <MetricTile icon={<Gauge className="h-4 w-4" />} label="平均预期波动" value={formatPercent(metrics.avgMove)} />
          </div>

          <div className="flex gap-2 overflow-x-auto pb-1">
            <button
              type="button"
              onClick={() => setDateFilter("all")}
              className={`min-h-14 min-w-28 rounded-lg border px-3 text-left text-sm transition ${
                dateFilter === "all"
                  ? "border-gray-900 bg-gray-900 text-white dark:border-white dark:bg-white dark:text-gray-900"
                  : "border-gray-200 text-gray-600 hover:border-brand-200 hover:text-brand-700 dark:border-gray-800 dark:text-gray-300"
              }`}
            >
              <span className="block text-xs opacity-70">全部窗口</span>
              <span className="mt-1 block font-semibold">{setups.length} 只</span>
            </button>
            {dateBuckets.map((bucket) => (
              <button
                key={bucket.date}
                type="button"
                onClick={() => setDateFilter(bucket.date)}
                className={`min-h-14 min-w-28 rounded-lg border px-3 text-left text-sm transition ${
                  dateFilter === bucket.date
                    ? "border-gray-900 bg-gray-900 text-white dark:border-white dark:bg-white dark:text-gray-900"
                    : "border-gray-200 text-gray-600 hover:border-brand-200 hover:text-brand-700 dark:border-gray-800 dark:text-gray-300"
                }`}
              >
                <span className="block text-xs opacity-70">{weekdayLabel(bucket.date)}</span>
                <span className="mt-1 block font-semibold">{dateLabel(bucket.date)} · {bucket.count} 只</span>
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            {topSetups.map((setup, index) => (
              <EarningsSetupCard key={setup.shortline.symbol} setup={setup} rank={index + 1} marketPath={marketPath} />
            ))}
          </div>

          {!topSetups.length ? (
            <div className="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
              当前日期筛选下暂无财报候选。
            </div>
          ) : null}

          {lens.notes.length ? (
            <div className="rounded-lg bg-gray-50 px-4 py-3 text-xs leading-5 text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">
              {lens.notes.join(" ")}
            </div>
          ) : null}
        </div>
      )}
    </TenxSectionCard>
  );
}

function MetricTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
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

function ScoreRing({ score }: { score: number }) {
  const tone = score >= 80 ? "#16a34a" : score >= 65 ? "#d97706" : "#64748b";
  return (
    <div
      className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full"
      style={{ background: `conic-gradient(${tone} ${clamp(score, 0, 100) * 3.6}deg, #e5e7eb 0deg)` }}
      aria-label={`score ${score}`}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-lg font-semibold text-gray-900 dark:bg-gray-950 dark:text-white">
        {score}
      </div>
    </div>
  );
}

function EarningsSetupCard({ setup, rank, marketPath }: { setup: EarningsSetup; rank: number; marketPath: string }) {
  const { shortline, option, forecast } = setup;
  const currency = shortline.currency || "USD";
  const optionReady = option?.dataQualityFlag === "ok";
  const maxProfitMove =
    forecast.expectedMove === null
      ? null
      : forecast.optionSide === "VOL"
        ? forecast.expectedMove * 1.35
        : forecast.expectedMove * 0.85;
  const maxLossMove = forecast.spreadDebit && option?.underlyingPrice ? -(forecast.spreadDebit / option.underlyingPrice) : null;

  return (
    <article className="rounded-lg border border-gray-200 bg-white p-4 shadow-xs dark:border-gray-800 dark:bg-gray-950/20">
      <div className="flex items-start gap-3">
        <ScoreRing score={shortline.score} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-brand-50 px-2 py-1 text-xs font-semibold text-brand-700 dark:bg-brand-500/15 dark:text-brand-200">
              {String(rank).padStart(2, "0")}
            </span>
            <Link
              href={`/tenx-hunter/${marketPath}/research/${shortline.symbol}`}
              className="text-lg font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300"
            >
              {shortline.symbol}
            </Link>
            <StatusTag label={dayLabel(shortline.daysToEarnings)} tone={dayTone(shortline.daysToEarnings)} />
            <StatusTag label={forecast.directionLabel} tone={forecast.directionTone} />
          </div>
          <div className="mt-1 truncate text-sm text-gray-500 dark:text-gray-400">{shortline.name}</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <StatusTag label={shortline.stage} tone={getStageTone(shortline.stage)} />
            <StatusTag label={shortline.riskLevel} tone={getRiskTone(shortline.riskLevel)} />
            <StatusTag label={shortline.timeOfDay || shortline.fiscalPeriod || "TBD"} tone="slate" />
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <ForecastCell label="营收预期" value={formatCurrency(shortline.revenueEstimate, currency)} />
        <ForecastCell label="EPS 预期" value={shortline.epsEstimate === null || shortline.epsEstimate === undefined ? "N/A" : shortline.epsEstimate.toFixed(2)} />
        <ForecastCell label="预期波动" value={formatPercent(forecast.expectedMove)} tone="red" />
        <ForecastCell label="模型胜率" value={forecast.winProbability === null ? "N/A" : `${forecast.winProbability.toFixed(0)}%`} tone={forecast.directionTone} />
      </div>

      <div className="mt-4 overflow-hidden rounded-lg border border-gray-200 dark:border-gray-800">
        <StrategyRow
          label="单腿期权"
          values={optionReady ? [
            forecast.optionSide,
            option?.nearestExpiration ?? "N/A",
            formatStrike(forecast.strike, currency),
            formatCurrency(forecast.premium, currency),
            forecast.optionSide === "PUT" ? "下行保护/回撤表达" : forecast.optionSide === "CALL" ? "上行弹性表达" : "双向波动表达",
          ] : ["待补链", "N/A", "N/A", "N/A", "刷新期权链"]}
        />
        <StrategyRow
          label="垂直价差"
          values={optionReady ? [
            forecast.optionSide === "PUT" ? "PUT spread" : forecast.optionSide === "CALL" ? "CALL spread" : "VOL spread",
            `${formatStrike(forecast.strike, currency)} / ${formatStrike(forecast.sellStrike, currency)}`,
            formatCurrency(forecast.spreadDebit, currency),
            formatSignedPercent(maxProfitMove),
            formatSignedPercent(maxLossMove),
          ] : ["待补链", "N/A", "N/A", "N/A", "刷新期权链"]}
          muted
        />
      </div>

      <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{shortline.shortlineSignal}</p>
      <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
        <span>IV {formatPercent(normalizeVol(option?.avgImpliedVolatility))}</span>
        <span>Call/Put {formatNumber(option?.callPutVolumeRatio)}</span>
        <span>Max pain {formatStrike(option?.maxPainStrike, currency)}</span>
      </div>
    </article>
  );
}

function ForecastCell({ label, value, tone = "slate" }: { label: string; value: string; tone?: ForecastTone }) {
  const valueClass =
    tone === "green"
      ? "text-green-600 dark:text-green-300"
      : tone === "red"
        ? "text-red-600 dark:text-red-300"
        : tone === "yellow"
          ? "text-yellow-600 dark:text-yellow-300"
          : "text-gray-900 dark:text-white";
  return (
    <div className="min-w-0 rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-900/60">
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`mt-1 truncate text-sm font-semibold ${valueClass}`}>{value}</div>
    </div>
  );
}

function StrategyRow({ label, values, muted }: { label: string; values: string[]; muted?: boolean }) {
  return (
    <div className={`grid grid-cols-[96px_repeat(5,minmax(0,1fr))] border-b border-gray-200 text-xs last:border-b-0 dark:border-gray-800 ${muted ? "bg-gray-50/80 dark:bg-gray-900/40" : "bg-white dark:bg-gray-950/10"}`}>
      <div className="flex items-center border-r border-gray-200 px-3 py-2 font-semibold text-gray-700 dark:border-gray-800 dark:text-gray-200">
        {label}
      </div>
      {values.map((value, index) => (
        <div key={`${label}-${index}`} className="min-w-0 border-r border-gray-200 px-3 py-2 text-gray-600 last:border-r-0 dark:border-gray-800 dark:text-gray-300">
          <span className="block truncate">{value}</span>
        </div>
      ))}
    </div>
  );
}
