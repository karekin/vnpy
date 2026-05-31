import StatusTag from "@/components/cb-quant/StatusTag";
import type { TenxPoliticalEvidenceGrade, TenxPoliticalMention, TenxPoliticalSignal, TenxPoliticalSignalStatus } from "@/components/tenx-hunter/types";
import { BadgeCheck, ExternalLink, FileSearch, Megaphone, ShieldAlert, Vote } from "lucide-react";

function formatNumber(value: number | null) {
  if (value === null) return "N/A";
  return new Intl.NumberFormat("en-US").format(value);
}

function statusTone(status: TenxPoliticalSignalStatus): "green" | "yellow" | "red" | "blue" | "slate" {
  if (status === "confirmed") return "green";
  if (status === "watching") return "blue";
  if (status === "needs-verification") return "yellow";
  if (status === "discarded") return "red";
  return "slate";
}

function statusLabel(status: TenxPoliticalSignalStatus) {
  return {
    confirmed: "已确认",
    watching: "跟踪中",
    "needs-verification": "待核实",
    discarded: "剔除",
  }[status];
}

function gradeTone(grade: TenxPoliticalEvidenceGrade) {
  return {
    A: "border-green-200 bg-green-50 text-green-700 dark:border-green-500/30 dark:bg-green-500/10 dark:text-green-300",
    B: "border-brand-200 bg-brand-50 text-brand-700 dark:border-brand-500/30 dark:bg-brand-500/10 dark:text-brand-300",
    C: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300",
    D: "border-gray-200 bg-gray-50 text-gray-600 dark:border-gray-700 dark:bg-gray-900/60 dark:text-gray-300",
  }[grade];
}

function sourceLink(sourceUrl: string) {
  if (!sourceUrl) return null;
  return (
    <a href={sourceUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700 dark:text-brand-300">
      来源
      <ExternalLink className="h-3 w-3" aria-hidden="true" />
    </a>
  );
}

function MentionRow({ mention }: { mention: TenxPoliticalMention }) {
  return (
    <article className="grid gap-4 border-t border-gray-100 px-4 py-4 first:border-t-0 dark:border-gray-800 lg:grid-cols-[0.8fr_1.5fr_1fr]">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-lg font-semibold text-gray-900 dark:text-white">{mention.symbol}</span>
          <StatusTag label={statusLabel(mention.status)} tone={statusTone(mention.status)} />
          <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${gradeTone(mention.evidenceGrade)}`}>证据 {mention.evidenceGrade}</span>
        </div>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{mention.name}</p>
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{mention.eventDate} · {mention.eventType}</p>
      </div>

      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{mention.headline}</h3>
        <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{mention.summary}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
          <span>{mention.source}</span>
          {sourceLink(mention.sourceUrl)}
        </div>
      </div>

      <div className="rounded-lg bg-gray-50 p-3 text-sm leading-6 text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
        <div className="font-semibold text-gray-900 dark:text-white">下一步</div>
        <p className="mt-1">{mention.nextAction}</p>
        <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{mention.watchlistRule}</p>
      </div>
    </article>
  );
}

export default function TenxPoliticalSignalsDashboard({ snapshot }: { snapshot: TenxPoliticalSignal }) {
  const disclosure = snapshot.disclosure;
  const confirmedCount = snapshot.mentions.filter((item) => item.status === "confirmed" || item.status === "watching").length;
  const needsVerificationCount = snapshot.mentions.filter((item) => item.status === "needs-verification").length;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="border-b border-gray-200 p-5 dark:border-gray-800 xl:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-4xl">
              <div className="flex items-center gap-2 text-sm font-semibold text-brand-700 dark:text-brand-300">
                <Vote className="h-4 w-4" aria-hidden="true" />
                Trump Political Signal Monitor
              </div>
              <h2 className="mt-2 text-xl font-semibold text-gray-900 dark:text-white">持仓披露、公开声援和政策受益分层跟踪</h2>
              <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{snapshot.thesis}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusTag label={`${confirmedCount} 条已确认/跟踪`} tone="blue" />
              <StatusTag label={`${needsVerificationCount} 条待核实`} tone="yellow" />
              <StatusTag label={snapshot.freshness.dataComplete ? "披露源可用" : "披露源降级"} tone={snapshot.freshness.dataComplete ? "green" : "red"} />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-0 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="border-b border-gray-200 p-5 dark:border-gray-800 lg:border-b-0 lg:border-r xl:p-6">
            <div className="flex items-start gap-3">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
                <FileSearch className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">披露交易底座</h3>
                  {sourceLink(disclosure.sourceUrl)}
                </div>
                <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{disclosure.detail}</p>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
              <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">
                <div className="text-xs text-gray-500 dark:text-gray-400">总交易</div>
                <div className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">{formatNumber(disclosure.totalTrades)}</div>
              </div>
              <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">
                <div className="text-xs text-gray-500 dark:text-gray-400">买入</div>
                <div className="mt-1 text-lg font-semibold text-green-600 dark:text-green-300">{formatNumber(disclosure.purchases)}</div>
              </div>
              <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">
                <div className="text-xs text-gray-500 dark:text-gray-400">卖出</div>
                <div className="mt-1 text-lg font-semibold text-red-600 dark:text-red-300">{formatNumber(disclosure.sales)}</div>
              </div>
              <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">
                <div className="text-xs text-gray-500 dark:text-gray-400">延迟披露</div>
                <div className="mt-1 text-lg font-semibold text-amber-600 dark:text-amber-300">
                  {disclosure.lateFilingPct === null ? "N/A" : `${disclosure.lateFilingPct.toFixed(1)}%`}
                </div>
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-gray-200 px-4 py-3 text-sm text-gray-600 dark:border-gray-800 dark:text-gray-300">
              <div className="font-semibold text-gray-900 dark:text-white">最新披露</div>
              <div className="mt-1">{disclosure.latestFilingDate || "等待数据"} · {disclosure.transactionWindow || "交易窗口待确认"}</div>
            </div>
          </div>

          <div className="p-5 xl:p-6">
            <div className="flex items-start gap-3">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-300">
                <ShieldAlert className="h-5 w-5" aria-hidden="true" />
              </span>
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">持续监控规则</h3>
                <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">
                  这组规则决定线索能否从“热度/传闻”进入 Discover，再进入 Watchlist 和 Alerts。
                </p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
              {snapshot.monitoringRules.map((rule) => (
                <div key={rule} className="rounded-lg bg-gray-50 px-3 py-2 text-sm leading-6 text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
                  {rule}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="flex flex-col gap-3 border-b border-gray-200 p-5 dark:border-gray-800 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
              <Megaphone className="h-4 w-4 text-brand-600 dark:text-brand-300" aria-hidden="true" />
              声援/点名股票队列
            </div>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">截图和社群传闻默认 D 级，只能做待核实线索。</p>
          </div>
          <StatusTag label={`${snapshot.mentions.length} symbols`} tone="slate" />
        </div>
        <div>
          {snapshot.mentions.map((mention) => (
            <MentionRow key={`${mention.symbol}-${mention.eventDate}`} mention={mention} />
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="flex items-center justify-between gap-3 border-b border-gray-200 p-5 dark:border-gray-800">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-white">
              <BadgeCheck className="h-4 w-4 text-green-600 dark:text-green-300" aria-hidden="true" />
              最新披露交易样本
            </div>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">用于发现新增披露，不代表实时持仓。</p>
          </div>
          <div className="text-xs text-gray-500 dark:text-gray-400">{snapshot.snapshotAt}</div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-100 text-sm dark:divide-gray-800">
            <thead className="bg-gray-50 text-xs uppercase text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">
              <tr>
                <th className="px-4 py-3 text-left font-semibold">Date</th>
                <th className="px-4 py-3 text-left font-semibold">Symbol</th>
                <th className="px-4 py-3 text-left font-semibold">Description</th>
                <th className="px-4 py-3 text-left font-semibold">Type</th>
                <th className="px-4 py-3 text-left font-semibold">Amount</th>
                <th className="px-4 py-3 text-left font-semibold">Flag</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {snapshot.recentTrades.map((trade) => (
                <tr key={`${trade.date}-${trade.description}-${trade.amount}`} className="align-top">
                  <td className="whitespace-nowrap px-4 py-3 text-gray-600 dark:text-gray-300">{trade.date}</td>
                  <td className="whitespace-nowrap px-4 py-3 font-semibold text-gray-900 dark:text-white">{trade.symbol || "-"}</td>
                  <td className="min-w-72 px-4 py-3 text-gray-600 dark:text-gray-300">{trade.description}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-gray-600 dark:text-gray-300">{trade.tradeType}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-gray-600 dark:text-gray-300">{trade.amount}</td>
                  <td className="whitespace-nowrap px-4 py-3">{trade.isLate ? <StatusTag label="late" tone="yellow" /> : <StatusTag label="on-time" tone="slate" />}</td>
                </tr>
              ))}
              {!snapshot.recentTrades.length ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                    暂未拉取到交易样本，请直接查看 OGE/Open Cabinet 源文件。
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
