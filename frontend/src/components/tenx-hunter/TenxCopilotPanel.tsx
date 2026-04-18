"use client";

import { CopilotKit, useCopilotAction, useCopilotReadable } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { createAlertDraft, createWatchlistEntry, toMarketSlug } from "@/components/tenx-hunter/api";
import type { TenxMarket, TenxResearchCard, TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

type Props = {
  market: TenxMarket;
  workspace: TenxWorkspaceSnapshot;
  researchCard?: TenxResearchCard | null;
};

function ActionCard({
  title,
  body,
  status,
}: {
  title: string;
  body: string;
  status: "inProgress" | "executing" | "complete";
}) {
  const tone =
    status === "complete"
      ? "border-green-200 bg-green-50 text-green-800"
      : "border-gray-200 bg-gray-50 text-gray-700";
  return (
    <div className={`rounded-lg border px-3 py-2 text-sm ${tone}`}>
      <div className="font-semibold">{title}</div>
      <div className="mt-1 leading-6">{body}</div>
    </div>
  );
}

function TenxCopilotBindings({
  market,
  workspace,
  researchCard,
}: {
  market: TenxMarket;
  workspace: TenxWorkspaceSnapshot;
  researchCard?: TenxResearchCard | null;
}) {
  const router = useRouter();

  useCopilotReadable({
    description: "当前 TenX 工作台摘要，包括市场、研究范围、更新时间和数据来源。",
    value: {
      market,
      universe: workspace.universe,
      snapshotAt: workspace.snapshotAt,
      freshness: workspace.freshness,
    },
  });

  useCopilotReadable({
    description: "当前页面最值得优先研究的候选股列表。",
    value: workspace.candidates.slice(0, 8).map((item) => ({
      symbol: item.symbol,
      name: item.name,
      theme: item.theme,
      stage: item.lifecycleStage.label,
      score: item.score,
      evidenceCount: item.evidenceCount,
      nextEvent: item.nextEvent,
      selectionReason: item.selectionReason,
    })),
  });

  useCopilotReadable({
    description: "当前主线主题列表，包含热度、趋势和代表股。",
    value: workspace.themes.map((item) => ({
      name: item.name,
      heat: item.heat,
      trend: item.trend,
      driver: item.driver,
      relatedSymbols: item.relatedSymbols,
    })),
  });

  useCopilotReadable({
    description: "当前观察池与提醒摘要。",
    value: workspace.watchlist.map((item) => ({
      symbol: item.symbol,
      thesisStatus: item.thesisStatus,
      alertType: item.alertType,
      riskLevel: item.riskLevel,
      nextCheck: item.nextCheck,
    })),
  });

  if (researchCard) {
    useCopilotReadable({
      description: "当前正在查看的研究卡片。",
      value: {
        symbol: researchCard.symbol,
        name: researchCard.name,
        theme: researchCard.theme,
        stage: researchCard.lifecycleStage.label,
        score: researchCard.score,
        thesisSummary: researchCard.thesisSummary,
        nextWatchPoints: researchCard.nextWatchPoints,
        risks: researchCard.riskItems.map((item) => ({
          title: item.title,
          severity: item.severity,
          trigger: item.trigger,
        })),
      },
    });
  }

  useCopilotAction({
    name: "openResearchCard",
    description: "打开某只股票的研究卡片页面。",
    parameters: [
      { name: "symbol", type: "string", description: "股票代码，例如 300750.SZ", required: true },
      { name: "market", type: "string", description: "市场代码，CN 或 US", required: false },
    ],
    handler: async ({ symbol, market: actionMarket }) => {
      const nextMarket = (actionMarket || market).toUpperCase() === "US" ? "US" : "CN";
      router.push(`/tenx-hunter/${toMarketSlug(nextMarket)}/research/${symbol}`);
      return { ok: true, message: `已打开 ${symbol} 的研究卡片。` };
    },
    render: ({ args, status, result }) => (
      <ActionCard
        status={status}
        title="打开研究卡片"
        body={
          status === "complete"
            ? result?.message || `已打开 ${args.symbol}`
            : `正在跳转到 ${args.symbol} 的研究卡片…`
        }
      />
    ),
  });

  useCopilotAction({
    name: "addToWatchlist",
    description: "把标的加入观察池。",
    parameters: [
      { name: "symbol", type: "string", description: "股票代码", required: true },
      { name: "market", type: "string", description: "市场代码，CN 或 US", required: false },
    ],
    handler: async ({ symbol, market: actionMarket }) => {
      const nextMarket = (actionMarket || market).toUpperCase() === "US" ? "US" : "CN";
      const result = await createWatchlistEntry(nextMarket, symbol, "watch");
      router.refresh();
      return { ok: true, message: result.message };
    },
    render: ({ args, status, result }) => (
      <ActionCard
        status={status}
        title="加入观察池"
        body={
          status === "complete"
            ? result?.message || `${args.symbol} 已加入观察池。`
            : `正在把 ${args.symbol} 加入观察池…`
        }
      />
    ),
  });

  useCopilotAction({
    name: "removeFromWatchlist",
    description: "把标的从观察池移除。",
    parameters: [
      { name: "symbol", type: "string", description: "股票代码", required: true },
      { name: "market", type: "string", description: "市场代码，CN 或 US", required: false },
    ],
    handler: async ({ symbol, market: actionMarket }) => {
      const nextMarket = (actionMarket || market).toUpperCase() === "US" ? "US" : "CN";
      const result = await createWatchlistEntry(nextMarket, symbol, "unwatch");
      router.refresh();
      return { ok: true, message: result.message };
    },
    render: ({ args, status, result }) => (
      <ActionCard
        status={status}
        title="移出观察池"
        body={
          status === "complete"
            ? result?.message || `${args.symbol} 已移出观察池。`
            : `正在把 ${args.symbol} 从观察池移除…`
        }
      />
    ),
  });

  useCopilotAction({
    name: "createAlert",
    description: "为指定标的创建提醒草稿。",
    parameters: [
      { name: "symbol", type: "string", description: "股票代码", required: true },
      { name: "market", type: "string", description: "市场代码，CN 或 US", required: false },
      { name: "title", type: "string", description: "提醒标题", required: true },
      { name: "note", type: "string", description: "提醒内容", required: true },
      { name: "severity", type: "string", description: "提醒等级，P1/P2/P3", required: false },
    ],
    handler: async ({ symbol, market: actionMarket, title, note }) => {
      const nextMarket = (actionMarket || market).toUpperCase() === "US" ? "US" : "CN";
      const result = await createAlertDraft(nextMarket, symbol, title, note);
      router.refresh();
      return { ok: true, message: result.message };
    },
    render: ({ args, status, result }) => (
      <ActionCard
        status={status}
        title="创建提醒"
        body={
          status === "complete"
            ? result?.message || `${args.symbol} 的提醒草稿已创建。`
            : `正在为 ${args.symbol} 创建提醒：${args.title}`
        }
      />
    ),
  });

  return null;
}

export default function TenxCopilotPanel({ market, workspace, researchCard }: Props) {
  const suggestions = useMemo(
    () =>
      workspace.copilotPrompts.map((prompt) => ({
        title: prompt,
        message: prompt,
      })),
    [workspace.copilotPrompts],
  );

  const instructions = useMemo(() => {
    const lines = [
      "你是 TenX Hunter 的应用内研究 Copilot。",
      "你只能基于当前页面可读状态回答，不得捏造来源。",
      "你可以执行页面动作：打开研究卡、加入/移出观察池、创建提醒。",
      "不要给买卖建议；只做研究、比较、复核、提醒和下一步行动建议。",
      `当前市场：${market}`,
      `当前范围：${workspace.universe}`,
    ];
    if (researchCard) {
      lines.push(`当前研究卡：${researchCard.symbol} / ${researchCard.theme}`);
    }
    return lines.join("\n");
  }, [market, workspace.universe, researchCard]);

  return (
    <CopilotKit runtimeUrl="/api/copilotkit" showDevConsole={false} useSingleEndpoint>
      <TenxCopilotBindings market={market} workspace={workspace} researchCard={researchCard} />
      <div className="rounded-2xl border border-gray-200 bg-white p-0 dark:border-gray-800 dark:bg-white/[0.03]">
        <CopilotChat
          className="h-[760px]"
          instructions={instructions}
          suggestions={suggestions}
          labels={{
            title: "TenX Copilot",
            initial: [
              "我已经接入当前 TenX 工作台上下文。",
              "你可以让我解释候选逻辑、比较主题、打开研究卡，或者帮你把标的加入观察池与创建提醒。",
            ],
            placeholder: "问研究问题，或直接要求我执行 TenX 动作…",
          }}
        />
      </div>
    </CopilotKit>
  );
}
