import StatusTag from "@/components/cb-quant/StatusTag";
import type { TenxMarketSentiment, TenxMarketSentimentMetric, TenxMarketSentimentTone } from "@/components/tenx-hunter/types";
import { Activity, AlertTriangle, BarChart3, Gauge, ShieldCheck, TrendingUp } from "lucide-react";

const toneStyles: Record<TenxMarketSentimentTone, { badge: "red" | "yellow" | "green" | "blue" | "slate"; text: string; bar: string; bg: string }> = {
  "extreme-fear": {
    badge: "red",
    text: "text-red-700 dark:text-red-300",
    bar: "bg-red-500",
    bg: "bg-red-50 dark:bg-red-500/10",
  },
  fear: {
    badge: "yellow",
    text: "text-amber-700 dark:text-amber-300",
    bar: "bg-amber-500",
    bg: "bg-amber-50 dark:bg-amber-500/10",
  },
  neutral: {
    badge: "slate",
    text: "text-gray-700 dark:text-gray-200",
    bar: "bg-gray-500",
    bg: "bg-gray-50 dark:bg-gray-900/60",
  },
  greed: {
    badge: "green",
    text: "text-green-700 dark:text-green-300",
    bar: "bg-green-500",
    bg: "bg-green-50 dark:bg-green-500/10",
  },
  "extreme-greed": {
    badge: "blue",
    text: "text-brand-700 dark:text-brand-300",
    bar: "bg-brand-500",
    bg: "bg-brand-50 dark:bg-brand-500/10",
  },
  unavailable: {
    badge: "slate",
    text: "text-gray-500 dark:text-gray-400",
    bar: "bg-gray-300",
    bg: "bg-gray-50 dark:bg-gray-900/60",
  },
};

function formatChange(value: number | null) {
  if (value === null) return "N/A";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(Math.abs(value) >= 10 ? 0 : 1)}`;
}

function metricIcon(category: string) {
  if (category === "volatility") return <Activity className="h-4 w-4" aria-hidden="true" />;
  if (category === "credit") return <ShieldCheck className="h-4 w-4" aria-hidden="true" />;
  if (category === "trend") return <TrendingUp className="h-4 w-4" aria-hidden="true" />;
  if (category === "cross-asset") return <BarChart3 className="h-4 w-4" aria-hidden="true" />;
  return <Gauge className="h-4 w-4" aria-hidden="true" />;
}

function SentimentSparkline({ metric }: { metric: TenxMarketSentimentMetric }) {
  const values = metric.history.map((point) => point.value).filter((value) => Number.isFinite(value));
  if (values.length < 2) {
    return <div className="h-12 rounded-lg bg-gray-50 dark:bg-gray-900/60" />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(1, max - min);
  const width = 180;
  const height = 48;
  const step = width / Math.max(1, values.length - 1);
  const points = values
    .map((value, index) => {
      const x = index * step;
      const y = height - ((value - min) / range) * (height - 8) - 4;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-12 w-full" role="img" aria-label={`${metric.label} trend`}>
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="text-brand-500 dark:text-brand-300" />
    </svg>
  );
}

function ScoreBar({ score, tone }: { score: number | null; tone: TenxMarketSentimentTone }) {
  const value = Math.max(0, Math.min(100, score ?? 0));
  return (
    <div className="h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
      <div className={`h-full rounded-full ${toneStyles[tone].bar}`} style={{ width: `${value}%` }} />
    </div>
  );
}

function MetricCard({ metric }: { metric: TenxMarketSentimentMetric }) {
  const tone = toneStyles[metric.tone];

  return (
    <article className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
            <span className={`inline-flex h-8 w-8 items-center justify-center rounded-lg ${tone.bg} ${tone.text}`}>
              {metricIcon(metric.category)}
            </span>
            <span className="truncate">{metric.label}</span>
          </div>
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-gray-500 dark:text-gray-400">{metric.detail}</p>
        </div>
        <StatusTag label={metric.statusLabel} tone={tone.badge} />
      </div>

      <div className="mt-4 flex items-end justify-between gap-4">
        <div>
          <div className={`text-3xl font-semibold ${tone.text}`}>{metric.displayValue}</div>
          <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            变化 <span className={metric.change !== null && metric.change < 0 ? "text-red-600 dark:text-red-300" : "text-green-600 dark:text-green-300"}>{formatChange(metric.change)}</span>
          </div>
        </div>
        <div className="min-w-28 flex-1">
          <SentimentSparkline metric={metric} />
        </div>
      </div>

      <div className="mt-4 space-y-2">
        <ScoreBar score={metric.score} tone={metric.tone} />
        <div className="flex items-center justify-between gap-3 text-xs text-gray-500 dark:text-gray-400">
          <span>{metric.source}</span>
          <span>{metric.updatedAt || "等待更新"}</span>
        </div>
      </div>
    </article>
  );
}

export default function TenxMarketSentimentDashboard({ snapshot }: { snapshot: TenxMarketSentiment }) {
  const regimeTone = toneStyles[snapshot.regime];
  const score = snapshot.compositeScore ?? 0;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="grid grid-cols-1 gap-0 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="border-b border-gray-200 p-5 dark:border-gray-800 lg:border-b-0 lg:border-r xl:p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Composite Score</p>
                <div className={`mt-2 text-6xl font-semibold ${regimeTone.text}`}>{snapshot.compositeScore?.toFixed(0) ?? "N/A"}</div>
              </div>
              <div className={`flex h-24 w-24 items-center justify-center rounded-full ${regimeTone.bg}`}>
                <Gauge className={`h-11 w-11 ${regimeTone.text}`} aria-hidden="true" />
              </div>
            </div>
            <div className="mt-5 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <StatusTag label={snapshot.regimeLabel} tone={regimeTone.badge} />
                <StatusTag label={snapshot.dataQuality} tone="slate" />
              </div>
              <ScoreBar score={score} tone={snapshot.regime} />
              <p className="text-sm leading-6 text-gray-600 dark:text-gray-300">{snapshot.summary}</p>
            </div>
          </div>

          <div className="p-5 xl:p-6">
            <div className="flex items-start gap-3">
              <span className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${regimeTone.bg} ${regimeTone.text}`}>
                <AlertTriangle className="h-5 w-5" aria-hidden="true" />
              </span>
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">风险偏好纪律</h2>
                <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{snapshot.riskPosture}</p>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">
                <div className="text-xs text-gray-500 dark:text-gray-400">刷新时间</div>
                <div className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{snapshot.snapshotAt}</div>
              </div>
              <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">
                <div className="text-xs text-gray-500 dark:text-gray-400">覆盖</div>
                <div className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{snapshot.metrics.length} sources</div>
              </div>
              <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">
                <div className="text-xs text-gray-500 dark:text-gray-400">市场</div>
                <div className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{snapshot.market}</div>
              </div>
            </div>

            {snapshot.notes.length ? (
              <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
                {snapshot.notes[0]}
              </div>
            ) : null}
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {snapshot.metrics.map((metric) => (
          <MetricCard key={metric.key} metric={metric} />
        ))}
      </section>
    </div>
  );
}
