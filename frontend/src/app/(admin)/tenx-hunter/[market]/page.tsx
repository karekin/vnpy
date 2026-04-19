import Link from "next/link";
import StatusTag from "@/components/cb-quant/StatusTag";
import { fromMarketSlug, getOverviewMetrics, getTenxErrorMessage, loadTenxWorkspaceSnapshot, marketLabel } from "@/components/tenx-hunter/api";
import TenxCopilotPanel from "@/components/tenx-hunter/TenxCopilotPanel";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { TenxMetricCard, TenxSectionCard, getRiskTone, getStageTone } from "@/components/tenx-hunter/TenxCards";
import type { TenxMarket, TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";

export default async function TenxHunterMarketHomePage({ params }: { params: Promise<{ market: string }> }) {
  const { market: marketSlug } = await params;
  const market = fromMarketSlug(marketSlug);

  let snapshot: TenxWorkspaceSnapshot;
  try {
    snapshot = await loadTenxWorkspaceSnapshot(market);
  } catch (error) {
    return (
      <TenxPageShell
        market={market}
        title="TenX Hunter"
        subtitle={market === "CN" ? "AI 原生 A 股研究工作台，围绕发现、理解、跟踪、复盘构建日常研究闭环。" : "AI 原生美股研究工作台，围绕发现、理解、跟踪、复盘构建日常研究闭环。"}
        marketLabel={marketLabel(market)}
      >
        <TenxDataStateCard
          title="TenX 首页实时数据暂不可用"
          message="首页已经停止显示 mock 数据。请先启动 vnpy.web API、PostgreSQL，并运行对应市场的真实数据 pipeline。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }

  const metrics = getOverviewMetrics(snapshot);
  const topCandidates = snapshot.candidates.slice(0, 4);
  const hotThemes = snapshot.themes.slice(0, 3);
  const watchlist = snapshot.watchlist.slice(0, 3);
  const pathMarket = snapshot.market.toLowerCase();

  return (
    <TenxCopilotPanel market={market} workspace={snapshot}>
      <TenxPageShell
        market={market as TenxMarket}
        title="TenX Hunter"
        subtitle={market === "CN" ? "如果今天只有 15 分钟，这里应该先告诉你哪几只 A 股值得研究、哪些观察对象发生了变化。" : "如果今天只有 15 分钟，这里应该先告诉你哪几只美股值得研究、哪些观察对象发生了变化。"}
        marketLabel={`${marketLabel(market)} · ${snapshot.universe}`}
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => (
            <TenxMetricCard key={metric.label} label={metric.label} value={metric.value} delta={metric.delta} />
          ))}
        </div>

        <TenxSectionCard
          title="Workspace"
          description="先回答今天最该看什么，再进入研究卡片。"
          action={
            <Link
              href={`/tenx-hunter/${pathMarket}/discover`}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-600 hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
            >
              查看完整候选池
            </Link>
          }
        >
          <div className="grid gap-4 lg:grid-cols-2">
            {topCandidates.map((candidate) => (
              <div key={candidate.symbol} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Link href={`/tenx-hunter/${pathMarket}/research/${candidate.symbol}`} className="text-lg font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300">
                        {candidate.symbol}
                      </Link>
                      <StatusTag label={candidate.lifecycleStage.label} tone={getStageTone(candidate.stage)} />
                    </div>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{candidate.name} · {candidate.theme}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-semibold text-gray-900 dark:text-white">{candidate.score}</div>
                    <div className="text-sm text-green-600 dark:text-green-300">
                      {candidate.scoreChange >= 0 ? "+" : ""}
                      {candidate.scoreChange.toFixed(1)} 5日
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{candidate.whySelected.summary}</p>
                <div className="mt-4 flex flex-wrap gap-2 text-xs">
                  <StatusTag label={candidate.riskLevel} tone={getRiskTone(candidate.riskLevel)} />
                  <StatusTag label={`${candidate.evidenceCount} 条证据`} tone="slate" />
                  <StatusTag label={candidate.nextEvent} tone="blue" />
                </div>
                <div className="mt-4 rounded-xl bg-gray-50 p-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
                  <span className="font-medium text-gray-800 dark:text-white/90">阶段原因：</span> {candidate.lifecycleStage.summary}
                </div>
              </div>
            ))}
          </div>
        </TenxSectionCard>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <TenxSectionCard title="Theme Radar" description="先看主线，再看个股。">
            <div className="space-y-4">
            {hotThemes.length ? hotThemes.map((theme) => (
              <div key={theme.slug} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-base font-semibold text-gray-900 dark:text-white">{theme.name}</div>
                    <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{theme.driver}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-semibold text-gray-900 dark:text-white">{theme.heat}</div>
                    <StatusTag label={theme.trend} tone={theme.trend === "rising" ? "green" : theme.trend === "stable" ? "blue" : "yellow"} />
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {theme.relatedSymbols.map((symbol) => (
                    <Link key={symbol} href={`/tenx-hunter/${pathMarket}/research/${symbol}`} className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-brand-50 hover:text-brand-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-brand-500/15 dark:hover:text-brand-300">
                      {symbol}
                    </Link>
                  ))}
                </div>
              </div>
            )) : (
              <div className="rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
                暂无主题数据，请先补跑对应市场的数据链路。
              </div>
            )}
          </div>
        </TenxSectionCard>

        <TenxSectionCard title="Watchlist Alerts" description="观察池不是一次性推荐，而是持续验证逻辑是否成立。">
          <div className="space-y-4">
            {watchlist.length ? watchlist.map((item) => (
              <div key={item.symbol} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Link href={`/tenx-hunter/${pathMarket}/research/${item.symbol}`} className="text-base font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300">
                        {item.symbol}
                      </Link>
                      <StatusTag label={item.thesisStatus} tone={item.thesisStatus === "strengthening" ? "green" : item.thesisStatus === "needs-review" ? "yellow" : "red"} />
                    </div>
                    <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{item.name}</div>
                  </div>
                  <StatusTag label={item.alertType} tone="blue" />
                </div>
                <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.lastEvent}</p>
                <div className="mt-3 text-sm text-gray-500 dark:text-gray-400">下一检查点：{item.nextCheck}</div>
              </div>
            )) : (
              <div className="rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
                观察池提醒暂时为空。你可以先把候选加入观察池，系统也会在后续根据重点候选生成默认跟踪建议。
              </div>
            )}
          </div>
        </TenxSectionCard>
        </div>
      </TenxPageShell>
    </TenxCopilotPanel>
  );
}
