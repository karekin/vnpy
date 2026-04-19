import { notFound } from "next/navigation";
import StatusTag from "@/components/cb-quant/StatusTag";
import TenxActionDrawer from "@/components/tenx-hunter/TenxActionDrawer";
import TenxCopilotPanel from "@/components/tenx-hunter/TenxCopilotPanel";
import { fromMarketSlug, getTenxErrorMessage, getTimelineForSymbol, loadTenxResearchCard, loadTenxWorkspaceSnapshot, marketLabel } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { TenxSectionCard, getStageTone } from "@/components/tenx-hunter/TenxCards";
import type { TenxResearchCard, TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";

export default async function TenxHunterResearchDetailMarketPage({
  params,
}: {
  params: Promise<{ market: string; symbol: string }>;
}) {
  const { market: marketSlug, symbol } = await params;
  const market = fromMarketSlug(marketSlug);

  let card: TenxResearchCard | null;
  try {
    card = await loadTenxResearchCard(market, symbol);
  } catch (error) {
    return (
      <TenxPageShell
        market={market}
        title={`Research Card · ${symbol.toUpperCase()}`}
        subtitle="研究卡片必须区分事实、推断和风险。"
        marketLabel={marketLabel(market)}
      >
        <TenxDataStateCard
          title="Research Card 实时数据暂不可用"
          message="请确认 vnpy.web API、PostgreSQL，以及对应市场的真实数据 pipeline 都已经就绪。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }

  if (!card) {
    notFound();
  }

  let snapshot: TenxWorkspaceSnapshot | null = null;
  let workspaceErrorMessage: string | null = null;
  try {
    snapshot = await loadTenxWorkspaceSnapshot(market);
  } catch (error) {
    workspaceErrorMessage = getTenxErrorMessage(error);
  }

  const timeline = snapshot ? getTimelineForSymbol(card.symbol, snapshot) : [];

  return (
    <TenxCopilotPanel market={market} workspace={snapshot} researchCard={card}>
      <TenxPageShell
        market={market}
        title={`Research Card · ${card.symbol}`}
        subtitle="研究卡片必须区分事实、推断和风险。这里的内容面向研究辅助，不构成投资建议。"
        marketLabel={`${marketLabel(market)} · ${card.theme}`}
      >
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.5fr_1fr]">
          <TenxSectionCard
            title={`${card.name} (${card.symbol})`}
            description={card.thesisSummary}
            action={<StatusTag label={card.lifecycleStage.label} tone={getStageTone(card.stage)} />}
          >
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200">Facts</h4>
                <ul className="mt-3 space-y-3 text-sm leading-6 text-gray-600 dark:text-gray-300">
                  {card.facts.map((item) => (
                    <li key={item} className="rounded-xl bg-gray-50 px-4 py-3 dark:bg-gray-900/60">{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200">Thesis</h4>
                <ul className="mt-3 space-y-3 text-sm leading-6 text-gray-600 dark:text-gray-300">
                  {card.thesisPoints.map((item) => (
                    <li key={item} className="rounded-xl bg-gray-50 px-4 py-3 dark:bg-gray-900/60">{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          </TenxSectionCard>

          <div className="space-y-6">
            <TenxSectionCard title="Risk & Checkpoints" description="风险必须被显式展示。">
              <div className="space-y-4">
                <div>
                  <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">主要风险</div>
                  <div className="mt-3 space-y-3">
                    {card.riskItems.map((item) => (
                      <div key={item.title} className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
                        <div className="font-semibold">{item.title}</div>
                        <div className="mt-1">{item.note}</div>
                        <div className="mt-1 text-xs">触发条件：{item.trigger}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">下一观察点</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {card.nextWatchPoints.map((item) => (
                      <StatusTag key={item} label={item} tone="blue" />
                    ))}
                  </div>
                </div>
              </div>
            </TenxSectionCard>
            <TenxActionDrawer market={market} symbol={card.symbol} />
          </div>
        </div>

        <TenxSectionCard title="Selection Logic" description="明确回答为什么它进入候选池。">
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
              <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">为什么入选</div>
              <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{card.whySelected.summary}</p>
            </div>
            <div className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
              <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">生命周期阶段</div>
              <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{card.lifecycleStage.summary}</p>
            </div>
            <div className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
              <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">拥挤度提示</div>
              <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{card.crowdingNote}</p>
            </div>
          </div>
        </TenxSectionCard>

        <TenxSectionCard title="Score Breakdown" description="分数必须拆解成可复核的结构。">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {card.scoreBreakdown.map((item) => (
              <div key={item.key} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold text-gray-900 dark:text-white">{item.label}</div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">{item.weight}%</div>
                </div>
                <div className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{item.score.toFixed(1)}</div>
                <div className="mt-2 text-sm text-gray-600 dark:text-gray-300">{item.summary}</div>
              </div>
            ))}
          </div>
        </TenxSectionCard>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr_1fr]">
          <TenxSectionCard title="Evidence" description="证据链保留来源和时间戳。">
            <div className="space-y-4">
              {card.evidenceItems.map((item) => (
                <div key={item.id} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-semibold text-gray-900 dark:text-white">{item.source}</div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">{item.publishedAt}</div>
                  </div>
                  <div className="mt-2 text-sm font-medium text-gray-800 dark:text-white/90">{item.title}</div>
                  <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.note}</p>
                </div>
              ))}
            </div>
          </TenxSectionCard>

          <TenxSectionCard title="Timeline" description="最近发生了什么，决定我们是继续跟踪还是要求人工复核。">
            {workspaceErrorMessage ? (
              <TenxDataStateCard
                tone="warning"
                title="Timeline 暂不可用"
                message="研究卡主体已经来自真实 API，但工作台快照暂时拉取失败，因此最近事件时间线未能展示。"
                detail={workspaceErrorMessage}
              />
            ) : (
              <div className="space-y-4">
                {timeline.length ? timeline.map((event) => (
                  <div key={event.id} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                    <div className="flex items-center justify-between gap-3">
                      <StatusTag label={event.type} tone="blue" />
                      <div className="text-sm text-gray-500 dark:text-gray-400">{event.date}</div>
                    </div>
                    <div className="mt-2 font-semibold text-gray-900 dark:text-white">{event.title}</div>
                    <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{event.summary}</p>
                  </div>
                )) : (
                  <div className="rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">暂无最近事件，建议在下一次财报或主题变化后重新评估。</div>
                )}
              </div>
            )}
          </TenxSectionCard>
        </div>
      </TenxPageShell>
    </TenxCopilotPanel>
  );
}
