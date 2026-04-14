import { notFound } from "next/navigation";
import StatusTag from "@/components/cb-quant/StatusTag";
import { getTenxErrorMessage, getTimelineForSymbol, loadTenxResearchCard, loadTenxWorkspaceSnapshot } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { TenxSectionCard, getStageTone } from "@/components/tenx-hunter/TenxCards";
import type { TenxResearchCard, TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";

export default async function TenxHunterResearchDetailPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;

  let card: TenxResearchCard | null;
  try {
    card = await loadTenxResearchCard(symbol);
  } catch (error) {
    return (
      <TenxPageShell
        title={`Research Card · ${symbol.toUpperCase()}`}
        subtitle="研究卡片必须区分事实、推断和风险。这里的内容面向研究辅助，不构成投资建议。"
        marketLabel="TenX research"
      >
        <TenxDataStateCard
          title="Research Card 实时数据暂不可用"
          message="研究页已经停止显示 mock 研究卡。请确认 vnpy.web API、PostgreSQL，以及 TenX 真实数据 pipeline 都已经就绪。"
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
    snapshot = await loadTenxWorkspaceSnapshot();
  } catch (error) {
    workspaceErrorMessage = getTenxErrorMessage(error);
  }

  const timeline = snapshot ? getTimelineForSymbol(card.symbol, snapshot) : [];

  return (
    <TenxPageShell
      title={`Research Card · ${card.symbol}`}
      subtitle="研究卡片必须区分事实、推断和风险。这里的内容面向研究辅助，不构成投资建议。"
      marketLabel={snapshot ? `${snapshot.universe} · ${card.theme}` : card.theme}
    >
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.5fr_1fr]">
        <TenxSectionCard
          title={`${card.name} (${card.symbol})`}
          description={card.thesisSummary}
          action={<StatusTag label={card.stage} tone={getStageTone(card.stage)} />}
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

        <TenxSectionCard title="Risk & Checkpoints" description="风险必须被显式展示，而不是藏在结论后面。">
          <div className="space-y-4">
            <div>
              <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">主要风险</div>
              <div className="mt-3 space-y-3">
                {card.risks.map((item) => (
                  <div key={item} className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-200">
                    {item}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">下一观察点</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {card.nextCheckpoints.map((item) => (
                  <StatusTag key={item} label={item} tone="blue" />
                ))}
              </div>
            </div>
          </div>
        </TenxSectionCard>
      </div>

      <TenxSectionCard title="Selection Logic" description="这一层明确回答：为什么它进主候选池，为什么不是那只更热门的大票。">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
            <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">为什么入选</div>
            <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{card.selectionReason ?? card.thesisSummary}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
            <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">阶段原因</div>
            <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{card.stageReason ?? card.theme}</p>
          </div>
          <div className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
            <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">为什么不是更热门的大票</div>
            <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{card.crowdingNote ?? "当前未命中更明确的拥挤说明。"}</p>
          </div>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          {(card.scoreDrivers ?? []).map((item) => (
            <StatusTag key={item} label={item} tone="blue" />
          ))}
        </div>
      </TenxSectionCard>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr_1fr]">
        <TenxSectionCard title="Evidence" description="证据链保留来源和时间戳，防止 AI 变成不可追溯的黑盒。">
          <div className="space-y-4">
            {card.evidence.map((item) => (
              <div key={`${item.source}-${item.publishedAt}`} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold text-gray-900 dark:text-white">{item.source}</div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">{item.publishedAt}</div>
                </div>
                <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.note}</p>
              </div>
            ))}
          </div>
        </TenxSectionCard>

        <TenxSectionCard title="Timeline" description="最近发生了什么，决定我们是继续跟踪、升级观察，还是要求人工复核。">
          {workspaceErrorMessage ? (
            <TenxDataStateCard
              tone="warning"
              title="Timeline 暂不可用"
              message="研究卡主体已经来自真实 API，但工作台快照暂时拉取失败，因此最近事件时间线未能展示。请检查 TenX API、数据库和 pipeline 状态。"
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
                <div className="rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">暂无最近事件，建议在下一财报或产业链更新后重新评估。</div>
              )}
            </div>
          )}
        </TenxSectionCard>
      </div>
    </TenxPageShell>
  );
}
