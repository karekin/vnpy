import Link from "next/link";
import StatusTag from "@/components/cb-quant/StatusTag";
import { fromMarketSlug, getRelatedCandidatesForTheme, getTenxErrorMessage, loadTenxWorkspaceSnapshot, marketLabel } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { TenxSectionCard } from "@/components/tenx-hunter/TenxCards";
import type { TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";

export default async function TenxHunterThemesMarketPage({ params }: { params: Promise<{ market: string }> }) {
  const { market: marketSlug } = await params;
  const market = fromMarketSlug(marketSlug);
  let snapshot: TenxWorkspaceSnapshot;
  try {
    snapshot = await loadTenxWorkspaceSnapshot(market);
  } catch (error) {
    return (
      <TenxPageShell
        market={market}
        title="TenX Hunter · Themes"
        subtitle="主题页只回答主线和归因，个股晋级交给 Discover。"
        marketLabel={marketLabel(market)}
      >
        <TenxDataStateCard
          title="Theme Radar 实时数据暂不可用"
          message="主题页已经停止显示 mock 主题。请确认 API、数据库和真实数据 pipeline 都已就绪。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }

  const pathMarket = market.toLowerCase();
  return (
    <TenxPageShell
      market={market}
      title="TenX Hunter · Themes"
      subtitle="主题页是主线雷达，不再重复做候选列表。需要看个股状态时跳回 Discover。"
      marketLabel={`${marketLabel(market)} · Theme Radar`}
    >
      <TenxSectionCard
        title="Theme Radar"
        description="主线优先：热度、驱动、证据和相关候选数量。"
        action={<StatusTag label={`${snapshot.themes.length} themes`} tone="blue" />}
      >
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {snapshot.themes.map((theme) => {
            const related = getRelatedCandidatesForTheme(theme.slug, snapshot);
            const topSymbols = related.slice(0, 5).map((candidate) => candidate.symbol);
            return (
              <article key={theme.slug} className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-semibold text-gray-900 dark:text-white">{theme.name}</h3>
                      <StatusTag label={theme.trend} tone={theme.trend === "rising" ? "green" : theme.trend === "stable" ? "blue" : "yellow"} />
                    </div>
                    <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{theme.driver}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-2xl font-semibold text-gray-900 dark:text-white">{theme.heat}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">heat</div>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-1 gap-3 text-sm md:grid-cols-[1.3fr_1fr]">
                  <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">
                    <div className="text-xs font-semibold text-gray-500 dark:text-gray-400">主题证据</div>
                    <ul className="mt-2 space-y-1.5 text-gray-600 dark:text-gray-300">
                      {theme.evidence.slice(0, 3).map((point) => (
                        <li key={point}>{point}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-xs font-semibold text-gray-500 dark:text-gray-400">相关候选</div>
                      <StatusTag label={`${related.length}`} tone="slate" />
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {topSymbols.length ? topSymbols.map((symbol) => (
                        <StatusTag key={`${theme.slug}-${symbol}`} label={symbol} tone="blue" />
                      )) : (
                        <span className="text-sm text-gray-500 dark:text-gray-400">暂无候选</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex justify-end">
                  <Link
                    href={`/tenx-hunter/${pathMarket}/discover?theme=${encodeURIComponent(theme.name)}`}
                    className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-300 dark:hover:text-brand-200"
                  >
                    查看候选状态
                  </Link>
                </div>
              </article>
            );
          })}
        </div>
      </TenxSectionCard>
    </TenxPageShell>
  );
}
