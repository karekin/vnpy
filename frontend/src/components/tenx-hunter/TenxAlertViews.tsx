import StatusTag from "@/components/cb-quant/StatusTag";
import type { TenxAlertItem } from "@/components/tenx-hunter/types";
import { CalendarClock, ChartLine, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";

export function severityTone(severity: "P1" | "P2" | "P3") {
  if (severity === "P1") return "red" as const;
  if (severity === "P2") return "yellow" as const;
  return "slate" as const;
}

function confidenceTone(confidence: string) {
  if (confidence === "high") return "green" as const;
  if (confidence === "medium") return "blue" as const;
  return "slate" as const;
}

function severityRank(severity: TenxAlertItem["severity"]) {
  if (severity === "P1") return 0;
  if (severity === "P2") return 1;
  return 2;
}

function extractSummaryList(summary: string, label: string) {
  const labelStart = [`${label}：`, `${label}:`]
    .map((candidate) => summary.indexOf(candidate))
    .find((index) => index >= 0);
  if (labelStart === undefined) return [];

  const contentStart = labelStart + label.length + 1;
  const nextLabelStart = ["事件层", "结构层", "执行层", "反证"]
    .filter((candidate) => candidate !== label)
    .map((candidate) => {
      const chinese = summary.indexOf(`${candidate}：`, contentStart);
      const ascii = summary.indexOf(`${candidate}:`, contentStart);
      return [chinese, ascii].filter((index) => index >= 0);
    })
    .flat()
    .sort((a, b) => a - b)[0];
  const segment = summary.slice(contentStart, nextLabelStart ?? summary.length);

  return segment
    .split(/[;；、]/)
    .map((item) => item.trim())
    .map((item) => item.replace(/[。.]$/, ""))
    .filter(Boolean);
}

function getEventLayer(item: TenxAlertItem) {
  return item.eventLayer.length ? item.eventLayer : extractSummaryList(item.summary, "事件层");
}

function getStructureLayer(item: TenxAlertItem) {
  return item.structureLayer.length ? item.structureLayer : extractSummaryList(item.summary, "结构层");
}

function getExecutionLayer(item: TenxAlertItem) {
  return item.executionLayer.length ? item.executionLayer : extractSummaryList(item.summary, "执行层");
}

function getInvalidationSignals(item: TenxAlertItem) {
  return item.invalidationSignals.length ? item.invalidationSignals : extractSummaryList(item.summary, "反证");
}

function AlertChecklist({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="min-w-0 rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
      <div className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">{title}</div>
      {items.length ? (
        <ul className="mt-3 space-y-2 text-sm leading-6 text-gray-700 dark:text-gray-300">
          {items.map((item) => (
            <li key={item} className="flex gap-2">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
              <span className="min-w-0 [overflow-wrap:anywhere]">{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-3 text-sm text-gray-500 dark:text-gray-400">待补充</div>
      )}
    </div>
  );
}

type DisciplineCardProps = {
  step: string;
  title: string;
  intent: string;
  checks: string[];
  icon: LucideIcon;
  accentClass: string;
  iconClass: string;
  chipClass: string;
};

const disciplineCards: DisciplineCardProps[] = [
  {
    step: "01",
    title: "事件层",
    intent: "先确认催化和预期差。",
    checks: ["主线足够大", "未完全 price in", "高于社群线索"],
    icon: CalendarClock,
    accentClass: "bg-brand-500",
    iconClass: "border-brand-200 bg-brand-50 text-brand-700 dark:border-brand-500/20 dark:bg-brand-500/10 dark:text-brand-200",
    chipClass: "border-brand-100 bg-brand-50/70 text-brand-700 dark:border-brand-500/15 dark:bg-brand-500/10 dark:text-brand-200",
  },
  {
    step: "02",
    title: "结构层",
    intent: "把观点落到可观察点位。",
    checks: ["支撑/阻力", "OI / Max Pain", "IV / VIX"],
    icon: ChartLine,
    accentClass: "bg-amber-500",
    iconClass: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200",
    chipClass: "border-amber-100 bg-amber-50/70 text-amber-700 dark:border-amber-500/15 dark:bg-amber-500/10 dark:text-amber-200",
  },
  {
    step: "03",
    title: "执行层",
    intent: "先定义输法，再考虑表达。",
    checks: ["最大亏损", "止盈止损", "证伪空仓"],
    icon: ShieldCheck,
    accentClass: "bg-emerald-500",
    iconClass: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200",
    chipClass: "border-emerald-100 bg-emerald-50/70 text-emerald-700 dark:border-emerald-500/15 dark:bg-emerald-500/10 dark:text-emerald-200",
  },
];

function DisciplineCard({ step, title, intent, checks, icon: Icon, accentClass, iconClass, chipClass }: DisciplineCardProps) {
  return (
    <div className="relative min-h-[84px] overflow-hidden rounded-lg border border-gray-200 bg-white px-3 py-3 dark:border-gray-800 dark:bg-white/[0.03]">
      <div className={`absolute left-0 top-0 h-full w-1 ${accentClass}`} />
      <div className="flex min-w-0 items-center gap-2 pl-1">
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${iconClass}`}>
          <Icon className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <div className="flex min-w-0 items-baseline gap-2">
            <div className="min-w-0 truncate text-sm font-semibold text-gray-900 dark:text-white">{title}</div>
            <span className="shrink-0 text-[11px] font-medium uppercase tracking-[0] text-gray-400 dark:text-gray-500">
              {step}
            </span>
          </div>
          <p className="mt-1 truncate text-xs text-gray-500 dark:text-gray-400">{intent}</p>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5 pl-1">
        {checks.map((check) => (
          <span
            key={check}
            className={`rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-4 [overflow-wrap:anywhere] ${chipClass}`}
          >
            {check}
          </span>
        ))}
      </div>
    </div>
  );
}

export function EventFrameworkStrip({ updatedAt }: { updatedAt: string }) {
  return (
    <section>
      <div className="mb-2 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900 dark:text-white">Event Framework</h2>
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">事件、结构、执行三层纪律。</p>
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400">最新刷新：{updatedAt}</div>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {disciplineCards.map((card) => (
          <DisciplineCard key={card.title} {...card} />
        ))}
      </div>
    </section>
  );
}

export function sortAlerts(items: TenxAlertItem[]) {
  return [...items].sort((left, right) => {
    const rankDelta = severityRank(left.severity) - severityRank(right.severity);
    if (rankDelta !== 0) return rankDelta;
    return right.createdAt.localeCompare(left.createdAt);
  });
}

export function findAlertById(items: TenxAlertItem[], alertId: string) {
  return items.find((item) => item.id === alertId) ?? null;
}

export function getSearchParamValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export type AlertFilter = "all" | "priority" | "low-evidence" | "draft";

export function normalizeAlertFilter(value: string | string[] | undefined): AlertFilter {
  const filter = getSearchParamValue(value);
  if (filter === "priority" || filter === "low-evidence" || filter === "draft") return filter;
  return "all";
}

export function buildAlertFilterCounts(items: TenxAlertItem[]) {
  return {
    all: items.length,
    priority: items.filter((item) => item.severity !== "P3").length,
    "low-evidence": items.filter((item) => item.evidenceGrade === "D").length,
    draft: items.filter((item) => item.status === "draft").length,
  };
}

export function filterAlerts(items: TenxAlertItem[], filter: AlertFilter) {
  if (filter === "priority") return items.filter((item) => item.severity !== "P3");
  if (filter === "low-evidence") return items.filter((item) => item.evidenceGrade === "D");
  if (filter === "draft") return items.filter((item) => item.status === "draft");
  return items;
}

const filterLabels: Record<AlertFilter, string> = {
  all: "全部",
  priority: "优先复核",
  "low-evidence": "低证据",
  draft: "草稿",
};

export function AlertList({
  items,
  marketSlug,
  activeFilter = "all",
  counts = buildAlertFilterCounts(items),
}: {
  items: TenxAlertItem[];
  marketSlug: string;
  activeFilter?: AlertFilter;
  counts?: Record<AlertFilter, number>;
}) {
  const filters: AlertFilter[] = ["all", "priority", "low-evidence", "draft"];

  return (
    <div className="min-w-0 overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
      <div className="space-y-3 border-b border-gray-200 px-4 py-3 dark:border-gray-800">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-gray-800 dark:text-white/90">事件列表</div>
            <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">用标签快速收拢需要复核的事件。</div>
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">{items.length} 条</div>
        </div>
        <div className="flex flex-wrap gap-2">
          {filters.map((filter) => {
            const active = filter === activeFilter;
            const href = filter === "all"
              ? `/tenx-hunter/${marketSlug}/alerts`
              : `/tenx-hunter/${marketSlug}/alerts?filter=${filter}`;
            return (
              <Link
                key={filter}
                href={href}
                className={`rounded-lg border px-2.5 py-1.5 text-xs font-medium transition ${
                  active
                    ? "border-brand-500 bg-brand-50 text-brand-700 dark:border-brand-400 dark:bg-brand-500/10 dark:text-brand-200"
                    : "border-gray-200 bg-white text-gray-600 hover:border-brand-200 hover:text-brand-600 dark:border-gray-800 dark:bg-white/[0.03] dark:text-gray-300 dark:hover:border-brand-500/40 dark:hover:text-brand-200"
                }`}
              >
                {filterLabels[filter]} <span className="ml-1 text-gray-400 dark:text-gray-500">{counts[filter]}</span>
              </Link>
            );
          })}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
          <span className="font-medium text-gray-600 dark:text-gray-300">纪律</span>
          {["事件层", "结构层", "执行层"].map((label) => (
            <span
              key={label}
              className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 font-medium text-gray-600 dark:border-gray-800 dark:bg-gray-900/60 dark:text-gray-300"
            >
              {label}
            </span>
          ))}
        </div>
      </div>
      <div className="divide-y divide-gray-200 dark:divide-gray-800">
        {items.length ? (
          items.map((item) => (
            <Link
              key={item.id}
              href={`/tenx-hunter/${marketSlug}/alerts/${encodeURIComponent(item.id)}`}
              className="block px-4 py-4 transition hover:bg-gray-50 dark:hover:bg-white/[0.03]"
            >
              <div className="flex min-w-0 items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusTag label={item.severity} tone={severityTone(item.severity)} />
                    <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{item.status}</span>
                  </div>
                  <div className="mt-2 flex min-w-0 items-baseline gap-2">
                    <span className="shrink-0 text-sm font-semibold text-gray-900 dark:text-white">{item.symbol}</span>
                    <span className="min-w-0 truncate text-sm font-medium text-gray-700 dark:text-gray-200">
                      {item.title}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
                    <span>{item.alertType}</span>
                    <span>证据 {item.evidenceGrade}</span>
                    <span>{item.confidence}</span>
                  </div>
                </div>
                <div className="shrink-0 text-right text-xs text-gray-500 dark:text-gray-400">
                  <div>{item.createdAt}</div>
                  {item.dueAt ? <div className="mt-1">复核 {item.dueAt}</div> : null}
                  <div className="mt-2 font-medium text-brand-600 dark:text-brand-300">查看明细</div>
                </div>
              </div>
            </Link>
          ))
        ) : (
          <div className="px-4 py-8 text-sm text-gray-500 dark:text-gray-400">当前筛选下暂无事件。</div>
        )}
      </div>
    </div>
  );
}

export function AlertDetail({ item }: { item: TenxAlertItem }) {
  const eventLayer = getEventLayer(item);
  const structureLayer = getStructureLayer(item);
  const executionLayer = getExecutionLayer(item);
  const invalidationSignals = getInvalidationSignals(item);

  return (
    <article className="min-w-0 rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusTag label={item.severity} tone={severityTone(item.severity)} />
            <StatusTag label={item.alertType} tone="blue" />
            <StatusTag label={`证据 ${item.evidenceGrade}`} tone={item.evidenceGrade === "D" ? "slate" : "green"} />
            <StatusTag label={item.confidence} tone={confidenceTone(item.confidence)} />
            <span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-300">
              {item.status}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <div className="text-xl font-semibold text-gray-900 dark:text-white">
              {item.symbol}
            </div>
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">{item.title}</h3>
          </div>
          <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.summary}</p>
          {item.sourceNote ? (
            <div className="mt-3 rounded-xl border border-dashed border-gray-200 px-4 py-3 text-sm leading-6 text-gray-600 dark:border-gray-800 dark:text-gray-300">
              {item.sourceNote}
            </div>
          ) : null}
        </div>
        <div className="shrink-0 text-sm text-gray-500 dark:text-gray-400 xl:text-right">
          <div>{item.createdAt}</div>
          {item.dueAt ? <div className="mt-2">复核：{item.dueAt}</div> : null}
          <div className="mt-2">{item.source}</div>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-3 xl:grid-cols-3">
        <AlertChecklist title="事件层" items={eventLayer} />
        <AlertChecklist title="结构层" items={structureLayer} />
        <AlertChecklist title="执行层" items={executionLayer} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-[1fr_1fr]">
        <AlertChecklist title="反证 / 降风险触发" items={invalidationSignals} />
        <div className="rounded-xl bg-brand-50 px-4 py-3 text-sm leading-6 text-brand-800 dark:bg-brand-500/10 dark:text-brand-200">
          下一步：{item.nextAction}
        </div>
      </div>
    </article>
  );
}
