import Link from "next/link";
import StatusTag from "@/components/cb-quant/StatusTag";
import { fromMarketSlug, getTenxErrorMessage, loadTenxWorkspaceSnapshot, marketLabel } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { TenxPriceSnapshotStrip, TenxSectionCard, getRiskTone } from "@/components/tenx-hunter/TenxCards";
import type { TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";
import WatchlistRulesDrawer from "@/components/tenx-hunter/WatchlistRulesDrawer";
import { BellRing, Binoculars, FileText } from "lucide-react";

export default async function TenxHunterWatchlistMarketPage({ params }: { params: Promise<{ market: string }> }) {
  const { market: marketSlug } = await params;
  const market = fromMarketSlug(marketSlug);
  let snapshot: TenxWorkspaceSnapshot;
  try {
    snapshot = await loadTenxWorkspaceSnapshot(market);
  } catch (error) {
    return (
      <TenxPageShell
        market={market}
        title="TenX Hunter · Watchlist"
        subtitle="观察池只保留已经确认持续跟踪的股票。"
        marketLabel={marketLabel(market)}
        pipelineStage="watchlist"
      >
        <TenxDataStateCard
          title="Watchlist 实时数据暂不可用"
          message="观察池已经停止显示 mock 条目。请检查 TenX 后端 API、数据库，以及真实数据 pipeline 的运行状态。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }

  const pathMarket = market.toLowerCase();
  const activeAlertCount = snapshot.watchlist.reduce((sum, item) => sum + item.activeAlertCount, 0);
  return (
    <TenxPageShell
      market={market}
      title="TenX Hunter · Watchlist"
      subtitle="按逻辑状态而不是按涨幅管理正在跟踪的股票。系统建议停留在 Discover，确认跟踪后才进入这里。"
      marketLabel={`${marketLabel(market)} · Watchlist`}
      pipelineStage="watchlist"
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex items-center justify-between">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
              <Binoculars className="h-4 w-4" aria-hidden="true" />
            </span>
            <StatusTag label="confirmed" tone="green" />
          </div>
          <div className="mt-3 text-2xl font-semibold text-gray-900 dark:text-white">{snapshot.watchlist.length}</div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">已确认观察标的</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex items-center justify-between">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-300">
              <BellRing className="h-4 w-4" aria-hidden="true" />
            </span>
            <StatusTag label="tracking" tone="red" />
          </div>
          <div className="mt-3 text-2xl font-semibold text-gray-900 dark:text-white">{activeAlertCount}</div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">挂接提醒规则</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex items-center justify-between">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-gray-50 text-gray-600 dark:bg-gray-900 dark:text-gray-300">
              <FileText className="h-4 w-4" aria-hidden="true" />
            </span>
            <StatusTag label="source" tone="blue" />
          </div>
          <div className="mt-3 text-2xl font-semibold text-gray-900 dark:text-white">Discover</div>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">唯一晋级入口</p>
        </div>
      </div>

      <TenxSectionCard
        title="Watchlist Center"
        description="观察池只显示已确认跟踪的股票，并默认绑定事件追踪。"
        action={<WatchlistRulesDrawer />}
      >
        {snapshot.watchlist.length ? (
          <div className="space-y-4">
            {snapshot.watchlist.map((item) => (
              <article key={item.symbol} className="min-w-0 overflow-hidden rounded-xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="min-w-0">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Link href={`/tenx-hunter/${pathMarket}/research/${item.symbol}`} className="text-lg font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300">
                          {item.symbol}
                        </Link>
                        <span className="min-w-0 text-sm text-gray-500 [overflow-wrap:anywhere] dark:text-gray-400">{item.name}</span>
                        <StatusTag label={item.thesisStatus} tone={item.thesisStatus === "strengthening" ? "green" : item.thesisStatus === "needs-review" ? "yellow" : "red"} />
                      </div>
                      <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.lastEvent}</p>
                      <div className="mt-3 flex flex-wrap gap-2 text-sm text-gray-500 dark:text-gray-400">
                        <span>下一观察点：{item.nextCheck}</span>
                        {item.nextAlertDue ? <span>提醒复核：{item.nextAlertDue}</span> : null}
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2 lg:max-w-56 lg:justify-end">
                      <StatusTag label={item.trackingStatus} tone={item.activeAlertCount > 0 ? "red" : "blue"} />
                      <StatusTag label={`${item.activeAlertCount} alerts`} tone={item.activeAlertCount > 0 ? "red" : "slate"} />
                      <StatusTag label={item.riskLevel} tone={getRiskTone(item.riskLevel)} />
                      <StatusTag label={`Score ${item.score}`} tone="slate" />
                    </div>
                  </div>
                  <TenxPriceSnapshotStrip snapshot={item.priceSnapshot} market={market} />
                  <div className="mt-4 flex flex-wrap justify-end gap-2">
                    <Link
                      href={`/tenx-hunter/${pathMarket}/alerts`}
                      className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
                    >
                      <BellRing className="h-4 w-4" aria-hidden="true" />
                      事件提醒
                    </Link>
                    <Link
                      href={`/tenx-hunter/${pathMarket}/research/${item.symbol}/report`}
                      className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
                    >
                      <FileText className="h-4 w-4" aria-hidden="true" />
                      投研报告
                    </Link>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="rounded-xl bg-gray-50 px-4 py-5 text-sm leading-6 text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
            当前没有已确认观察标的。请在 Discover 中筛选“可晋级观察”，通过阶段、证据、风险和动量门槛后再加入观察池。
          </div>
        )}
      </TenxSectionCard>
    </TenxPageShell>
  );
}
