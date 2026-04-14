import Link from "next/link";
import StatusTag from "@/components/cb-quant/StatusTag";
import {
  getTenxErrorMessage,
  getCopilotContext,
  getOverviewMetrics,
  loadTenxWorkspaceSnapshot,
} from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import { CopilotPanel, TenxMetricCard, TenxSectionCard, getRiskTone, getStageTone } from "@/components/tenx-hunter/TenxCards";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import type { TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";

export default async function TenxHunterHomePage() {
  let snapshot: TenxWorkspaceSnapshot;
  try {
    snapshot = await loadTenxWorkspaceSnapshot();
  } catch (error) {
    return (
      <TenxPageShell
        title="TenX Hunter"
        subtitle="AI 原生美股研究工作台。MVP 先聚焦美股成长科技，通过候选池、研究卡片、观察池和主题雷达，帮助用户更快发现并跟踪高成长标的。"
      >
        <TenxDataStateCard
          title="TenX 首页实时数据暂不可用"
          message="首页已经停止显示 mock 候选池。请先启动 vnpy.web API、PostgreSQL，并运行 TenX 真实数据 pipeline。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }

  const metrics = getOverviewMetrics(snapshot);
  const topCandidates = snapshot.candidates.slice(0, 4);
  const hotThemes = snapshot.themes.slice(0, 3);
  const watchlist = snapshot.watchlist.slice(0, 3);
  const context = getCopilotContext(snapshot);

  return (
    <TenxPageShell
      title="TenX Hunter"
      subtitle="AI 原生美股研究工作台。MVP 先聚焦美股成长科技，通过候选池、研究卡片、观察池和主题雷达，帮助用户更快发现并跟踪高成长标的。"
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <TenxMetricCard key={metric.label} label={metric.label} value={metric.value} delta={metric.delta} />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.6fr_1fr]">
        <TenxSectionCard
          title="Today Workspace"
          description="这里默认只展示主候选池里优先级最高的 4 个名字。它代表今天最值得先研究谁，而不是谁最适合立刻交易。"
          action={
            <Link
              href="/tenx-hunter/discover"
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
                      <Link href={`/tenx-hunter/research/${candidate.symbol}`} className="text-lg font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300">
                        {candidate.symbol}
                      </Link>
                      <StatusTag label={candidate.stage} tone={getStageTone(candidate.stage)} />
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
                <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{candidate.selectionReason ?? candidate.thesis}</p>
                <div className="mt-4 flex flex-wrap gap-2 text-xs">
                  <StatusTag label={candidate.riskLevel} tone={getRiskTone(candidate.riskLevel)} />
                  <StatusTag label={`${candidate.evidenceCount} 条证据`} tone="slate" />
                  <StatusTag label={candidate.nextEvent} tone="blue" />
                </div>
                <div className="mt-4 rounded-xl bg-gray-50 p-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
                  <span className="font-medium text-gray-800 dark:text-white/90">阶段原因：</span> {candidate.stageReason ?? candidate.keySignal}
                </div>
              </div>
            ))}
          </div>
        </TenxSectionCard>

        <CopilotPanel context={context} prompts={snapshot.copilotPrompts} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <TenxSectionCard title="Theme Radar" description="先看主线，再看个股。主题升温是否已经进入业绩验证，是判断赔率的关键。">
          <div className="space-y-4">
            {hotThemes.map((theme) => (
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
                    <Link key={symbol} href={`/tenx-hunter/research/${symbol}`} className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-brand-50 hover:text-brand-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-brand-500/15 dark:hover:text-brand-300">
                      {symbol}
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </TenxSectionCard>

        <TenxSectionCard title="Watchlist Alerts" description="观察池不是一次性推荐，而是不断验证逻辑是否仍成立。">
          <div className="space-y-4">
            {watchlist.map((item) => (
              <div key={item.symbol} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Link href={`/tenx-hunter/research/${item.symbol}`} className="text-base font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300">
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
            ))}
          </div>
        </TenxSectionCard>
      </div>
    </TenxPageShell>
  );
}
