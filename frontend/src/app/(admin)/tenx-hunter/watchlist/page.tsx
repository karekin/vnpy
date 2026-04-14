import Link from "next/link";
import StatusTag from "@/components/cb-quant/StatusTag";
import { getTenxErrorMessage, loadTenxWorkspaceSnapshot } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { TenxSectionCard, getRiskTone } from "@/components/tenx-hunter/TenxCards";
import type { TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";

export default async function TenxHunterWatchlistPage() {
  let snapshot: TenxWorkspaceSnapshot;
  try {
    snapshot = await loadTenxWorkspaceSnapshot();
  } catch (error) {
    return (
      <TenxPageShell
        title="TenX Hunter · Watchlist"
        subtitle="观察池是 TenX Hunter 的留存核心：不是一次性推荐，而是不断解释为什么逻辑在加强、变弱，或需要人工复核。"
      >
        <TenxDataStateCard
          title="Watchlist 实时数据暂不可用"
          message="观察池已经停止显示 mock 条目。请检查 TenX 后端 API、PostgreSQL，以及真实数据 pipeline 的运行状态。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }

  return (
    <TenxPageShell
      title="TenX Hunter · Watchlist"
      subtitle="观察池是 TenX Hunter 的留存核心：不是一次性推荐，而是不断解释为什么逻辑在加强、变弱，或需要人工复核。"
    >
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.4fr_1fr]">
        <TenxSectionCard title="Watchlist Center" description="聚焦已经值得持续跟踪的标的，按逻辑状态而不是按涨幅排序。">
          <div className="space-y-4">
            {snapshot.watchlist.map((item) => (
              <div key={item.symbol} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="max-w-2xl">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link href={`/tenx-hunter/research/${item.symbol}`} className="text-lg font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300">
                        {item.symbol}
                      </Link>
                      <span className="text-sm text-gray-500 dark:text-gray-400">{item.name}</span>
                      <StatusTag label={item.thesisStatus} tone={item.thesisStatus === "strengthening" ? "green" : item.thesisStatus === "needs-review" ? "yellow" : "red"} />
                    </div>
                    <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.lastEvent}</p>
                    <div className="mt-3 text-sm text-gray-500 dark:text-gray-400">下一观察点：{item.nextCheck}</div>
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

        <TenxSectionCard title="建议动作" description="当前阶段只保留研究相关动作：加入观察、创建提醒、导出摘要、标记复核。">
          <div className="space-y-3 text-sm text-gray-600 dark:text-gray-300">
            <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
              <div className="font-semibold text-gray-800 dark:text-white/90">1. 逻辑增强</div>
              <p className="mt-2">优先刷新研究卡片和晨会摘要，而不是立即引入交易动作。</p>
            </div>
            <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
              <div className="font-semibold text-gray-800 dark:text-white/90">2. 需要复核</div>
              <p className="mt-2">当证据不足、引用冲突或叙事拥挤时，前台应显式降级为“建议人工复核”。</p>
            </div>
            <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
              <div className="font-semibold text-gray-800 dark:text-white/90">3. 高风险观察</div>
              <p className="mt-2">只保留提醒和追踪，不开放下单、调仓、自动交易类动作。</p>
            </div>
          </div>
        </TenxSectionCard>
      </div>
    </TenxPageShell>
  );
}
