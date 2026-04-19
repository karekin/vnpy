"use client";

import {
  AssistantRuntimeProvider,
  Suggestions,
  Tools,
  type Toolkit,
  useAssistantInstructions,
  useAui,
  useAuiState,
} from "@assistant-ui/react";
import {
  AssistantChatTransport,
  useChatRuntime,
} from "@assistant-ui/react-ai-sdk";
import { cn } from "@/utils/index";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  createAlertDraft,
  createWatchlistEntry,
  loadTenxDeerFlowState,
  toMarketSlug,
} from "@/components/tenx-hunter/api";
import TenxAssistantProcessPanel from "@/components/tenx-hunter/TenxAssistantProcessPanel";
import TenxAssistantThread, {
  type UploadedThreadFileMeta,
} from "@/components/tenx-hunter/TenxAssistantThread";
import type {
  TenxMarket,
  TenxResearchCard,
  TenxWorkspaceSnapshot,
} from "@/components/tenx-hunter/types";
import {
  lastAssistantMessageIsCompleteWithToolCalls,
  type JSONSchema7,
  type UIMessage,
} from "ai";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

type Props = {
  market: TenxMarket;
  workspace?: TenxWorkspaceSnapshot | null;
  researchCard?: TenxResearchCard | null;
  children: ReactNode;
};

type TenxAssistantToolStatus =
  | { type: "running" }
  | { type: "complete" }
  | { type: "requires-action" }
  | { type: "incomplete"; reason?: string; error?: unknown };

type TenxToolRenderProps<TArgs, TResult> = {
  args?: TArgs;
  result?: TResult;
  status?: TenxAssistantToolStatus;
};

type OpenResearchCardArgs = {
  symbol: string;
  market?: string;
};

type OpenResearchCardResult = {
  ok: boolean;
  href: string;
  message: string;
};

type WatchlistToolArgs = {
  symbol: string;
  market?: string;
};

type WatchlistToolResult = {
  ok: boolean;
  message: string;
};

type CreateAlertArgs = {
  symbol: string;
  market?: string;
  title: string;
  note: string;
  severity?: string;
};

type CreateAlertResult = {
  ok: boolean;
  message: string;
};

const openResearchCardSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    symbol: {
      type: "string",
      description: "股票代码，例如 300750.SZ 或 DUOL",
    },
    market: {
      type: "string",
      description: "市场代码，CN 或 US。缺省时沿用当前页面市场。",
      enum: ["CN", "US"],
    },
  },
  required: ["symbol"],
} satisfies JSONSchema7;

const watchlistToolSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    symbol: {
      type: "string",
      description: "股票代码。",
    },
    market: {
      type: "string",
      description: "市场代码，CN 或 US。缺省时沿用当前页面市场。",
      enum: ["CN", "US"],
    },
  },
  required: ["symbol"],
} satisfies JSONSchema7;

const createAlertSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    symbol: {
      type: "string",
      description: "股票代码。",
    },
    market: {
      type: "string",
      description: "市场代码，CN 或 US。缺省时沿用当前页面市场。",
      enum: ["CN", "US"],
    },
    title: {
      type: "string",
      description: "提醒标题。",
    },
    note: {
      type: "string",
      description: "提醒说明内容。",
    },
    severity: {
      type: "string",
      description: "提醒等级，可选。",
      enum: ["P1", "P2", "P3"],
    },
  },
  required: ["symbol", "title", "note"],
} satisfies JSONSchema7;

function normalizeMarket(currentMarket: TenxMarket, actionMarket?: string): TenxMarket {
  return (actionMarket || currentMarket).toUpperCase() === "US" ? "US" : "CN";
}

function formatList(items: string[]): string {
  if (items.length === 0) {
    return "无";
  }

  return items.map((item) => `- ${item}`).join("\n");
}

function buildWorkspaceSummary(workspace?: TenxWorkspaceSnapshot | null): string {
  if (!workspace) {
    return "当前工作台快照不可用，只能基于当前页面和用户输入回答。";
  }

  const topCandidates = workspace.candidates.slice(0, 6).map((item) => {
    return `${item.symbol} | ${item.name} | ${item.theme} | ${item.lifecycleStage.label} | score ${item.score.toFixed(1)} | next ${item.nextEvent} | why ${item.whySelected.summary}`;
  });

  const topThemes = workspace.themes.slice(0, 4).map((item) => {
    return `${item.name} | heat ${item.heat} | trend ${item.trend} | driver ${item.driver} | symbols ${item.relatedSymbols.join(", ")}`;
  });

  const watchlist = workspace.watchlist.slice(0, 4).map((item) => {
    return `${item.symbol} | ${item.name} | thesis ${item.thesisStatus} | alert ${item.alertType} | next ${item.nextCheck}`;
  });

  return [
    `工作台市场：${workspace.market}`,
    `工作台范围：${workspace.universe}`,
    `工作台策略：${workspace.universeStrategy}`,
    `数据更新时间：${workspace.snapshotAt}`,
    `数据覆盖：${workspace.freshness.coverage}`,
    "优先候选：",
    formatList(topCandidates),
    "主题雷达：",
    formatList(topThemes),
    "观察池：",
    formatList(watchlist),
  ].join("\n");
}

function buildResearchSummary(researchCard?: TenxResearchCard | null): string {
  if (!researchCard) {
    return "当前未打开研究卡。";
  }

  const risks = researchCard.riskItems.slice(0, 4).map((item) => {
    return `${item.title} | severity ${item.severity} | trigger ${item.trigger}`;
  });

  return [
    `当前研究卡：${researchCard.symbol} | ${researchCard.name}`,
    `主题：${researchCard.theme}`,
    `阶段：${researchCard.lifecycleStage.label}`,
    `摘要：${researchCard.thesisSummary}`,
    `下一观察点：${researchCard.nextWatchPoints.join("；") || "无"}`,
    "主要风险：",
    formatList(risks),
  ].join("\n");
}

function buildAssistantInstructions({
  market,
  workspace,
  researchCard,
}: {
  market: TenxMarket;
  workspace?: TenxWorkspaceSnapshot | null;
  researchCard?: TenxResearchCard | null;
}): string {
  return [
    "你是 TenX Hunter 的应用内研究助手。",
    "你只能基于当前页面上下文、当前工作台快照和工具执行结果回答，不得虚构来源或数据。",
    "不要给明确买卖建议；只做研究总结、比较、复核、提醒和下一步行动建议。",
    "优先给出简洁、结构化、可执行的回答。",
    "当执行动作能明显提升回答质量时，可以主动调用工具。",
    "高风险动作只有 removeFromWatchlist，它只能在用户明确要求移除观察池时才调用。",
    "低风险动作包括 openResearchCard、addToWatchlist、createAlert，可以在合适时直接调用。",
    `当前页面市场：${market}`,
    "",
    "[当前工作台]",
    buildWorkspaceSummary(workspace),
    "",
    "[当前研究卡]",
    buildResearchSummary(researchCard),
  ].join("\n");
}

function getSuggestionEntries(workspace?: TenxWorkspaceSnapshot | null) {
  const prompts = workspace?.copilotPrompts ?? [];
  if (prompts.length > 0) {
    return prompts.slice(0, 4).map((prompt) => ({
      title: prompt,
      label: "快速开始",
      prompt,
    }));
  }

  return [
    {
      title: "比较候选",
      label: "优先级判断",
      prompt: "比较当前最值得优先研究的两只候选股，并说明为什么。",
    },
    {
      title: "梳理主线",
      label: "主题与驱动",
      prompt: "总结当前最热主题、核心驱动和对应代表股。",
    },
    {
      title: "观察池更新",
      label: "跟踪变化",
      prompt: "告诉我观察池里哪些标的最需要今天复核，以及原因。",
    },
  ];
}

function TenxAssistantOrb() {
  return (
    <svg
      viewBox="0 0 72 72"
      className="h-14 w-14"
      aria-hidden="true"
    >
      <circle cx="36" cy="37" r="25" fill="#FCFCFD" />
      <circle
        cx="36"
        cy="37"
        r="25"
        fill="none"
        stroke="rgba(15,23,42,0.14)"
        strokeWidth="2.4"
      />
      <path
        d="M36 13c4.8-5.4 11.8-7 18.8-4.2 1.3.5 1.7 2.1.8 3.1-3.8 4.4-8.2 6.8-13.1 7.2-3.9.3-7.1-.9-9.7-3.7l-.8-.9.6-.7c.4-.4 1.1-.9 2.4-.8Z"
        fill="#90D2A3"
        stroke="#1F2937"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="M40.8 15.2c2 2.1 3.4 4.5 4.2 7.2"
        fill="none"
        stroke="#1F2937"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M26.8 30.5c2.1-2 4.6-2.8 7.5-2.2"
        fill="none"
        stroke="#111827"
        strokeWidth="2.8"
        strokeLinecap="round"
      />
      <path
        d="M37.7 28.6c2.6-1.4 5.2-1.4 7.7.1"
        fill="none"
        stroke="#111827"
        strokeWidth="2.8"
        strokeLinecap="round"
      />
      <path
        d="M27.8 38.4c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2Z"
        fill="#111827"
      />
      <path
        d="M43.7 38.4c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2Z"
        fill="#111827"
      />
      <path
        d="M36.1 31.8 31.6 49h9.2"
        fill="none"
        stroke="#111827"
        strokeWidth="3.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M26.2 52.6c6.2 3.4 13.3 3.5 21.1.4"
        fill="none"
        stroke="#111827"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <circle cx="55.5" cy="54.8" r="4.6" fill="#2563EB" />
      <path
        d="M53.7 54.8h3.6M55.5 53v3.6"
        fill="none"
        stroke="#fff"
        strokeWidth="1.9"
        strokeLinecap="round"
      />
    </svg>
  );
}

function TenxAssistantLauncher({
  onOpenChange,
}: {
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onOpenChange(true)}
      className="fixed bottom-6 right-6 z-40 inline-flex h-18 w-18 items-center justify-center rounded-full bg-transparent shadow-[0_18px_44px_rgba(15,23,42,0.16)] transition duration-200 hover:-translate-y-0.5 hover:scale-[1.03] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-500/20"
      aria-label="Open TenX assistant"
      title="Open TenX assistant"
    >
      <span className="absolute inset-1 rounded-full bg-[radial-gradient(circle_at_30%_28%,rgba(255,255,255,0.98),rgba(255,255,255,0.92)_55%,rgba(241,245,249,0.92)_100%)] dark:bg-[radial-gradient(circle_at_30%_28%,rgba(255,255,255,0.14),rgba(30,41,59,0.92)_58%,rgba(15,23,42,0.98)_100%)]" />
      <span className="absolute inset-0 rounded-full border border-slate-200/90 dark:border-white/10" />
      <span className="absolute inset-0 rounded-full shadow-[inset_0_1px_0_rgba(255,255,255,0.72)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]" />
      <span className="relative">
        <TenxAssistantOrb />
      </span>
    </button>
  );
}

function TenxAssistantToolCard({
  title,
  body,
  status,
}: {
  title: string;
  body: string;
  status?: TenxAssistantToolStatus;
}) {
  const tone =
    status?.type === "complete"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-100"
      : status?.type === "incomplete"
        ? "border-red-200 bg-red-50 text-red-900 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-100"
        : "border-slate-200 bg-slate-50 text-slate-800 dark:border-white/10 dark:bg-white/5 dark:text-white/85";

  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm shadow-sm ${tone}`}>
      <div className="font-semibold">{title}</div>
      <div className="mt-1 whitespace-pre-wrap leading-6">{body}</div>
    </div>
  );
}

function renderToolError(status?: TenxAssistantToolStatus): string | null {
  if (status?.type !== "incomplete") {
    return null;
  }

  if (typeof status.error === "string" && status.error.trim().length > 0) {
    return status.error;
  }

  if (status.reason === "cancelled") {
    return "工具执行已取消。";
  }

  return "工具执行失败。";
}

function getPersistenceKey(pathname: string, market: TenxMarket): string {
  return `tenx-assistant:v2:${market}:${pathname}`;
}

function loadPersistedMessages(persistenceKey: string): UIMessage[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(persistenceKey);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as UIMessage[]) : [];
  } catch {
    return [];
  }
}

function persistMessages(persistenceKey: string, messages: UIMessage[]) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.setItem(persistenceKey, JSON.stringify(messages));
  } catch {
    // Ignore persistence failures in constrained browsers.
  }
}

function clearPersistedMessages(persistenceKey: string) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage.removeItem(persistenceKey);
  } catch {
    // Ignore persistence failures in constrained browsers.
  }
}

function mapDeerFlowMessageToUIMessage(message: Record<string, unknown>): UIMessage | null {
  const type = typeof message.type === "string" ? message.type : "";
  const role = type === "human" ? "user" : type === "ai" ? "assistant" : null;
  if (!role) {
    return null;
  }

  const parts: UIMessage["parts"] = [];
  if (role === "assistant") {
    const additional = message.additional_kwargs;
    const reasoningText =
      additional && typeof additional === "object"
        ? (additional as Record<string, unknown>).reasoning_content
        : undefined;
    if (
      typeof reasoningText === "string" &&
      reasoningText.trim()
    ) {
      parts.push({
        type: "reasoning",
        text: reasoningText.trim(),
        state: "done",
      });
    }
  }

  if (typeof message.content === "string" && message.content.trim()) {
    parts.push({
      type: "text",
      text: message.content.trim(),
      state: "done",
    });
  }

  if (parts.length === 0) {
    return null;
  }

  const id =
    typeof message.id === "string" && message.id.trim()
      ? message.id
      : `${role}-${Math.random().toString(36).slice(2)}`;

  return {
    id,
    role,
    parts,
  };
}

function mapDeerFlowStateToMessages(state: Record<string, unknown> | null): UIMessage[] {
  if (!state || typeof state !== "object") {
    return [];
  }

  const values = state.values;
  if (!values || typeof values !== "object") {
    return [];
  }

  const messages = (values as Record<string, unknown>).messages;
  if (!Array.isArray(messages)) {
    return [];
  }

  return messages
    .map((message) =>
      message && typeof message === "object"
        ? mapDeerFlowMessageToUIMessage(message as Record<string, unknown>)
        : null,
    )
    .filter((message): message is UIMessage => Boolean(message));
}

function extractLatestDeerFlowThreadId(messages: readonly UIMessage[]): string | null {
  for (const message of [...messages].reverse()) {
    for (const part of message.parts) {
      if (part.type !== "data-deerflow-status") {
        continue;
      }

      const payload = part.data && typeof part.data === "object" ? (part.data as { payload?: unknown }).payload : undefined;

      if (payload && typeof payload === "object" && typeof (payload as { thread_id?: unknown }).thread_id === "string") {
        return (payload as { thread_id: string }).thread_id;
      }

      const label = part.data && typeof part.data === "object" && typeof (part.data as { label?: unknown }).label === "string"
        ? (part.data as { label: string }).label
        : "";

      if (label.startsWith("Thread ")) {
        const threadId = label.slice("Thread ".length).trim();
        if (threadId && !threadId.startsWith("__localid_")) {
          return threadId;
        }
      }
    }
  }

  return null;
}

function mergeUploadedThreadFiles(
  previous: UploadedThreadFileMeta[],
  next: UploadedThreadFileMeta[],
) {
  const merged = new Map<string, UploadedThreadFileMeta>();

  for (const file of previous) {
    merged.set(`${file.virtual_path}:${file.filename}`, file);
  }

  for (const file of next) {
    merged.set(`${file.virtual_path}:${file.filename}`, file);
  }

  return Array.from(merged.values());
}

function createImageTurnThreadId(baseThreadId: string) {
  return `${baseThreadId}:image-turn:${Date.now()}`;
}

function OpenResearchCardToolUI({
  args,
  result,
  status,
}: TenxToolRenderProps<OpenResearchCardArgs, OpenResearchCardResult>) {
  const errorMessage = renderToolError(status);
  const body =
    errorMessage ??
    (status?.type === "complete"
      ? result?.message ?? `已准备打开 ${args?.symbol ?? "目标标的"} 的研究卡。`
      : `正在准备打开 ${args?.symbol ?? "目标标的"} 的研究卡…`);

  return <TenxAssistantToolCard title="打开研究卡" body={body} status={status} />;
}

function WatchlistToolUI({
  title,
  args,
  result,
  status,
  pendingMessage,
}: {
  title: string;
  args?: WatchlistToolArgs;
  result?: WatchlistToolResult;
  status?: TenxAssistantToolStatus;
  pendingMessage: string;
}) {
  const errorMessage = renderToolError(status);
  const body =
    errorMessage ??
    (status?.type === "complete"
      ? result?.message ?? `${args?.symbol ?? "目标标的"} 操作已完成。`
      : pendingMessage.replace("{symbol}", args?.symbol ?? "目标标的"));

  return <TenxAssistantToolCard title={title} body={body} status={status} />;
}

function CreateAlertToolUI({
  args,
  result,
  status,
}: TenxToolRenderProps<CreateAlertArgs, CreateAlertResult>) {
  const errorMessage = renderToolError(status);
  const body =
    errorMessage ??
    (status?.type === "complete"
      ? result?.message ?? `${args?.symbol ?? "目标标的"} 的提醒草稿已创建。`
      : `正在为 ${args?.symbol ?? "目标标的"} 创建提醒：${args?.title ?? "未命名提醒"}。`);

  return <TenxAssistantToolCard title="创建提醒草稿" body={body} status={status} />;
}

function TenxAssistantModelContext({
  instructions,
  pendingResearchTarget,
  clearPendingResearchTarget,
}: {
  instructions: string;
  pendingResearchTarget: string | null;
  clearPendingResearchTarget: () => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const threadIsRunning = useAuiState((state) => state.thread.isRunning);

  useAssistantInstructions(instructions);

  useEffect(() => {
    if (!pendingResearchTarget || threadIsRunning) {
      return;
    }

    if (pendingResearchTarget === pathname) {
      clearPendingResearchTarget();
      return;
    }

    router.push(pendingResearchTarget);
    clearPendingResearchTarget();
  }, [
    clearPendingResearchTarget,
    pathname,
    pendingResearchTarget,
    router,
    threadIsRunning,
  ]);

  return null;
}

function TenxAssistantSidebar({
  market,
  workspace,
  researchCard,
}: {
  market: TenxMarket;
  workspace?: TenxWorkspaceSnapshot | null;
  researchCard?: TenxResearchCard | null;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [activeView, setActiveView] = useState<"chat" | "process">("chat");
  const [pendingResearchTarget, setPendingResearchTarget] = useState<string | null>(null);
  const persistenceKey = useMemo(() => getPersistenceKey(pathname, market), [market, pathname]);
  const [composerThreadId, setComposerThreadId] = useState<string>(persistenceKey);
  const [deerFlowThreadId, setDeerFlowThreadId] = useState<string>(persistenceKey);
  const [initialMessages, setInitialMessages] = useState<UIMessage[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedThreadFileMeta[]>([]);
  const [uploadRevision, setUploadRevision] = useState(0);

  useEffect(() => {
    setInitialMessages(loadPersistedMessages(persistenceKey));
    setComposerThreadId(persistenceKey);
    setDeerFlowThreadId(persistenceKey);
  }, [persistenceKey]);

  useEffect(() => {
    let cancelled = false;

    void loadTenxDeerFlowState(persistenceKey)
      .then((state) => {
        if (cancelled || !state) {
          return;
        }

        const mappedMessages = mapDeerFlowStateToMessages(state);
        if (mappedMessages.length === 0) {
          return;
        }

        setDeerFlowThreadId(persistenceKey);
        setInitialMessages(mappedMessages);
        persistMessages(persistenceKey, mappedMessages);
      })
      .catch(() => {
        // Ignore DeerFlow history hydration failures and keep local fallback.
      });

    return () => {
      cancelled = true;
    };
  }, [persistenceKey]);

  const instructions = useMemo(
    () => buildAssistantInstructions({ market, workspace, researchCard }),
    [market, researchCard, workspace],
  );

  const handleResetConversation = useCallback(() => {
    clearPersistedMessages(persistenceKey);
    setInitialMessages([]);
    setComposerThreadId(persistenceKey);
    setDeerFlowThreadId(persistenceKey);
    setUploadedFiles([]);
  }, [persistenceKey]);

  const modeSwitcher = (
    <div className="inline-flex rounded-full border border-slate-200 bg-white p-1 dark:border-white/10 dark:bg-white/[0.04]">
      {[
        { key: "chat", label: "Chat" },
        { key: "process", label: "Process" },
      ].map((item) => {
        const active = activeView === item.key;
        return (
          <button
            key={item.key}
            type="button"
            onClick={() => setActiveView(item.key as "chat" | "process")}
            className={cn(
              "rounded-full px-3 py-1.5 text-xs font-semibold transition",
              active
                ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900"
                : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );

  const runtime = useChatRuntime({
    id: persistenceKey,
    messages: initialMessages,
    onFinish: ({ messages }) => {
      const threadId = extractLatestDeerFlowThreadId(messages);
      if (threadId) {
        setDeerFlowThreadId(threadId);
      }
      setUploadedFiles([]);
      persistMessages(persistenceKey, messages);
    },
    sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithToolCalls,
    transport: new AssistantChatTransport({
      api: "/api/chat",
      prepareSendMessagesRequest: async (options) => ({
        body: {
          ...(options.body ?? {}),
          id: composerThreadId,
          messages: options.messages,
          trigger: options.trigger,
          messageId: options.messageId,
          metadata: options.requestMetadata,
          deerflowFiles: uploadedFiles,
        },
      }),
    }),
  });

  const toolkit = useMemo<Toolkit>(() => {
    return {
      openResearchCard: {
        description:
          "当需要查看更多个股上下文时，打开相关股票的研究卡页面。适合比较、深挖和跟踪。",
        parameters: openResearchCardSchema,
        execute: async ({ symbol, market: actionMarket }: OpenResearchCardArgs) => {
          const nextMarket = normalizeMarket(market, actionMarket);
          const href = `/tenx-hunter/${toMarketSlug(nextMarket)}/research/${symbol}`;
          setPendingResearchTarget(href);
          return {
            ok: true,
            href,
            message: `已准备打开 ${symbol} 的研究卡。`,
          };
        },
        render: OpenResearchCardToolUI,
      },
      addToWatchlist: {
        description:
          "当用户希望持续跟踪、重点观察或保留关注某个标的时，把它加入观察池。",
        parameters: watchlistToolSchema,
        execute: async ({ symbol, market: actionMarket }: WatchlistToolArgs) => {
          const nextMarket = normalizeMarket(market, actionMarket);
          const result = await createWatchlistEntry(nextMarket, symbol, "watch");
          router.refresh();
          return result;
        },
        render: (props: TenxToolRenderProps<WatchlistToolArgs, WatchlistToolResult>) => (
          <WatchlistToolUI
            title="加入观察池"
            pendingMessage="正在把 {symbol} 加入观察池…"
            {...props}
          />
        ),
      },
      removeFromWatchlist: {
        description:
          "仅当用户明确要求移除、取消关注或清理观察池时，才把标的从观察池移除。",
        parameters: watchlistToolSchema,
        execute: async ({ symbol, market: actionMarket }: WatchlistToolArgs) => {
          if (typeof window !== "undefined") {
            const confirmed = window.confirm(`确认将 ${symbol} 从观察池移除？`);
            if (!confirmed) {
              return {
                ok: false,
                message: `已取消将 ${symbol} 移出观察池。`,
              };
            }
          }

          const nextMarket = normalizeMarket(market, actionMarket);
          const result = await createWatchlistEntry(nextMarket, symbol, "unwatch");
          router.refresh();
          return result;
        },
        render: (props: TenxToolRenderProps<WatchlistToolArgs, WatchlistToolResult>) => (
          <WatchlistToolUI
            title="移出观察池"
            pendingMessage="正在把 {symbol} 从观察池移除…"
            {...props}
          />
        ),
      },
      createAlert: {
        description:
          "当用户希望持续跟踪、后续提醒或不想遗漏关键变量变化时，创建提醒草稿。",
        parameters: createAlertSchema,
        execute: async ({
          symbol,
          market: actionMarket,
          title,
          note,
        }: CreateAlertArgs) => {
          const nextMarket = normalizeMarket(market, actionMarket);
          const result = await createAlertDraft(nextMarket, symbol, title, note);
          router.refresh();
          return result;
        },
        render: CreateAlertToolUI,
      },
    };
  }, [market, router]);

  const aui = useAui({
    tools: Tools({ toolkit }),
    suggestions: Suggestions(getSuggestionEntries(workspace)),
  });

  return (
    <>
      <TenxAssistantLauncher onOpenChange={setIsOpen} />
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="left-auto right-0 top-0 h-screen w-[min(92vw,460px)] max-w-none translate-x-0 translate-y-0 rounded-none border-l border-slate-200 bg-white p-0 shadow-[0_20px_60px_rgba(15,23,42,0.18)] data-[state=closed]:slide-out-to-right data-[state=closed]:slide-out-to-top-0 data-[state=open]:slide-in-from-right data-[state=open]:slide-in-from-top-0 dark:border-white/10 dark:bg-slate-950">
          <DialogHeader className="sr-only">
            <DialogTitle>TenX Assistant</DialogTitle>
            <DialogDescription>
              A streaming research assistant drawer for TenX Hunter.
            </DialogDescription>
          </DialogHeader>
          <AssistantRuntimeProvider runtime={runtime} aui={aui}>
            <TenxAssistantModelContext
              instructions={instructions}
              pendingResearchTarget={pendingResearchTarget}
              clearPendingResearchTarget={() => setPendingResearchTarget(null)}
            />
            <div className="h-full overflow-hidden">
              <TenxAssistantThread
                title="TenX Assistant"
                onNewConversation={handleResetConversation}
                modeSwitcher={modeSwitcher}
                currentView={activeView}
                processPanel={
                  <TenxAssistantProcessPanel
                    currentThreadId={deerFlowThreadId}
                    refreshKey={uploadRevision}
                  />
                }
                currentThreadId={composerThreadId}
                uploadedFileCount={uploadedFiles.length}
                createUploadThreadId={() =>
                  uploadedFiles.length > 0 ? composerThreadId : createImageTurnThreadId(persistenceKey)
                }
                onUploadThreadReady={(threadId) => {
                  setComposerThreadId(threadId);
                  setDeerFlowThreadId(threadId);
                }}
                onUploadedFilesChange={(files) => {
                  setUploadedFiles((previous) => mergeUploadedThreadFiles(previous, files));
                  setUploadRevision((value) => value + 1);
                }}
              />
            </div>
          </AssistantRuntimeProvider>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function TenxCopilotPanel({
  market,
  workspace,
  researchCard,
  children,
}: Props) {
  return (
    <div className="min-w-0">
      {children}
      <TenxAssistantSidebar
        market={market}
        workspace={workspace}
        researchCard={researchCard}
      />
    </div>
  );
}
