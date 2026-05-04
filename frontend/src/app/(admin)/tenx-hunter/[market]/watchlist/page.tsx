import Link from "next/link";
import StatusTag from "@/components/cb-quant/StatusTag";
import { fromMarketSlug, getTenxErrorMessage, loadTenxWorkspaceSnapshot, marketLabel } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { TenxPriceSnapshotStrip, TenxSectionCard, getRiskTone } from "@/components/tenx-hunter/TenxCards";
import type { TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";

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
        subtitle="观察池是研究留存的核心。"
        marketLabel={marketLabel(market)}
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
  return (
    <TenxPageShell
      market={market}
      title="TenX Hunter · Watchlist"
      subtitle="按逻辑状态而不是按涨幅管理正在跟踪的股票。"
      marketLabel={`${marketLabel(market)} · Watchlist`}
    >
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.4fr_1fr]">
        <TenxSectionCard title="Watchlist Center" description="聚焦已经值得持续跟踪的标的，按逻辑状态分组。">
          <div className="space-y-4">
            {snapshot.watchlist.map((item) => (
              <div key={item.symbol} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="max-w-2xl">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link href={`/tenx-hunter/${pathMarket}/research/${item.symbol}`} className="text-lg font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300">
                        {item.symbol}
                      </Link>
                      <span className="text-sm text-gray-500 dark:text-gray-400">{item.name}</span>
                      <StatusTag label={item.thesisStatus} tone={item.thesisStatus === "strengthening" ? "green" : item.thesisStatus === "needs-review" ? "yellow" : "red"} />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.lastEvent}</p>
                    <div className="mt-3 text-sm text-gray-500 dark:text-gray-400">下一观察点：{item.nextCheck}</div>
                    <TenxPriceSnapshotStrip snapshot={item.priceSnapshot} market={market} />
                  </div>
                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    <StatusTag label={item.alertType} tone="blue" />
                    <StatusTag label={item.riskLevel} tone={getRiskTone(item.riskLevel)} />
                    <StatusTag label={`Score ${item.score}`} tone="slate" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </TenxSectionCard>

        <TenxSectionCard title="观察池规则" description="首期只保留研究动作，不开放交易动作。">
          <div className="space-y-3 text-sm text-gray-600 dark:text-gray-300">
            <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
              <div className="font-semibold text-gray-800 dark:text-white/90">逻辑增强</div>
              <p className="mt-2">优先刷新研究卡片和提醒，不把 UI 做成交易终端。</p>
            </div>
            <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
              <div className="font-semibold text-gray-800 dark:text-white/90">需要复核</div>
              <p className="mt-2">证据不足、分歧增大或风险上升时，显式降级为人工复核。</p>
            </div>
          </div>
        </TenxSectionCard>
      </div>
    </TenxPageShell>
  );
}
