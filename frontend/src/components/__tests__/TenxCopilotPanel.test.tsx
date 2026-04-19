import { act, fireEvent, render, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

const mockUseChatRuntime: jest.Mock = jest.fn(() => ({ runtime: "chat-runtime" }));
const mockUseAui: jest.Mock = jest.fn(() => ({ aui: "assistant-aui" }));
const mockAssistantChatTransport: jest.Mock = jest.fn((options) => ({ kind: "transport", options }));
const mockUseAssistantInstructions: jest.Mock = jest.fn();
const mockUsePathname = jest.fn(() => "/tenx-hunter/cn");
const threadReset = jest.fn();
const mockTenxAssistantThread = jest.fn(
  (props: { title: string; onNewConversation: () => void; currentThreadId?: string }) => (
    <div data-testid="assistant-thread">
      <button type="button" onClick={props.onNewConversation}>
        new conversation
      </button>
      {props.title}
    </div>
  ),
);

let mockAuiState = {
  thread: {
    isRunning: false,
  },
};

const routerPush = jest.fn();

jest.mock("@assistant-ui/react", () => ({
  AssistantRuntimeProvider: ({
    children,
  }: {
    children: ReactNode;
  }) => <div data-testid="assistant-runtime-provider">{children}</div>,
  Suggestions: jest.fn((config) => ({ kind: "suggestions", config })),
  Tools: jest.fn((config) => ({ kind: "tools", ...config })),
  useAssistantInstructions: (instruction: unknown) => mockUseAssistantInstructions(instruction),
  useAui: (config: unknown) =>
    mockUseAui(config) || {
      thread: () => ({
        reset: threadReset,
      }),
    },
  useAuiState: (selector: (state: typeof mockAuiState) => unknown) => selector(mockAuiState),
}));

jest.mock("@assistant-ui/react-ai-sdk", () => ({
  AssistantChatTransport: function AssistantChatTransport(options: unknown) {
    return mockAssistantChatTransport(options);
  },
  useChatRuntime: (config: unknown) => mockUseChatRuntime(config),
}));

jest.mock("ai", () => ({
  lastAssistantMessageIsCompleteWithToolCalls: "AUTO_SEND_AFTER_TOOL_CALLS",
}));

jest.mock("next/navigation", () => ({
  useRouter() {
    return {
      push: (...args: unknown[]) => routerPush(...args),
      replace: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
      forward: jest.fn(),
      refresh: jest.fn(),
    };
  },
  usePathname() {
    return mockUsePathname();
  },
}));

jest.mock("@/components/tenx-hunter/TenxAssistantThread", () => ({
  __esModule: true,
  default: (props: { title: string; onNewConversation: () => void; currentThreadId?: string }) =>
    mockTenxAssistantThread(props),
}));

jest.mock("@/components/ui/dialog", () => ({
  Dialog: ({
    children,
    open,
  }: {
    children: ReactNode;
    open: boolean;
  }) => <div data-testid="dialog-root" data-open={open}>{children}</div>,
  DialogContent: ({
    children,
  }: {
    children: ReactNode;
  }) => <div data-testid="dialog-content">{children}</div>,
  DialogHeader: ({
    children,
  }: {
    children: ReactNode;
  }) => <div>{children}</div>,
  DialogTitle: ({
    children,
  }: {
    children: ReactNode;
  }) => <div>{children}</div>,
  DialogDescription: ({
    children,
  }: {
    children: ReactNode;
  }) => <div>{children}</div>,
}));

const createWatchlistEntry = jest.fn();
const createAlertDraft = jest.fn();
const loadTenxDeerFlowState = jest.fn();

jest.mock("@/components/tenx-hunter/api", () => ({
  createAlertDraft: (...args: unknown[]) => createAlertDraft(...(args as [unknown, unknown, unknown, unknown])),
  createWatchlistEntry: (...args: unknown[]) => createWatchlistEntry(...(args as [unknown, unknown, unknown])),
  loadTenxDeerFlowState: (...args: unknown[]) => loadTenxDeerFlowState(...(args as [unknown])),
  toMarketSlug: (market: string) => market.toLowerCase(),
}));

import TenxCopilotPanel from "@/components/tenx-hunter/TenxCopilotPanel";

describe("TenxCopilotPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    threadReset.mockReset();
    mockTenxAssistantThread.mockClear();
    mockAuiState = {
      thread: {
        isRunning: false,
      },
    };
    mockUsePathname.mockReturnValue("/tenx-hunter/cn");
    mockUseAui.mockImplementation((config) => {
      if (config !== undefined) {
        return { aui: "assistant-aui" };
      }

      return {
        thread: () => ({
          reset: threadReset,
        }),
      };
    });
    loadTenxDeerFlowState.mockResolvedValue(null);
    window.localStorage.clear();
  });

  test("wires assistant-ui runtime to /api/chat with automatic follow-up after tool calls", () => {
    const { getByRole } = render(
      <TenxCopilotPanel market="CN">
        <div>workspace</div>
      </TenxCopilotPanel>,
    );

    fireEvent.click(getByRole("button", { name: "Open TenX assistant" }));

    expect(mockAssistantChatTransport).toHaveBeenCalledWith({
      api: "/api/chat",
      prepareSendMessagesRequest: expect.any(Function),
    });
    expect(mockUseChatRuntime).toHaveBeenCalledWith({
      id: "tenx-assistant:v2:CN:/tenx-hunter/cn",
      messages: [],
      onFinish: expect.any(Function),
      sendAutomaticallyWhen: "AUTO_SEND_AFTER_TOOL_CALLS",
      transport: {
        kind: "transport",
        options: {
          api: "/api/chat",
          prepareSendMessagesRequest: expect.any(Function),
        },
      },
    });

    const threadProps = mockTenxAssistantThread.mock.calls[0][0];
    expect(threadProps.currentThreadId).toBe("tenx-assistant:v2:CN:/tenx-hunter/cn");

    const prepareSendMessagesRequest = mockAssistantChatTransport.mock.calls[0][0]
      .prepareSendMessagesRequest as (options: {
      body?: Record<string, unknown>;
      id: string;
      messages: unknown[];
      trigger?: string;
      messageId?: string;
      requestMetadata?: unknown;
    }) => Promise<{ body: Record<string, unknown> }>;

    return expect(
      prepareSendMessagesRequest({
        body: {},
        id: "__localid_abc123",
        messages: [{ role: "user", content: "hello" }],
      }),
    ).resolves.toEqual({
      body: {
        id: "tenx-assistant:v2:CN:/tenx-hunter/cn",
        messages: [{ role: "user", content: "hello" }],
        trigger: undefined,
        messageId: undefined,
        metadata: undefined,
        deerflowFiles: [],
      },
    });
  });

  test("registers workspace prompts as assistant-ui suggestions", () => {
    const { getByRole } = render(
      <TenxCopilotPanel
        market="CN"
        workspace={{
          market: "CN",
          universe: "核心资产",
          universeStrategy: "preset",
          universeDescription: "desc",
          universeBuckets: [],
          snapshotAt: "2026-04-18T10:00:00Z",
          freshness: {
            updatedAt: "2026-04-18T10:00:00Z",
            dataComplete: true,
            sourceSummary: "summary",
            coverage: "full",
          },
          availableActions: [],
          candidates: [],
          themes: [],
          watchlist: [],
          timeline: [],
          copilotPrompts: ["比较今天最值得研究的两只股票", "总结主线主题"],
        }}
      >
        <div>workspace</div>
      </TenxCopilotPanel>,
    );

    fireEvent.click(getByRole("button", { name: "Open TenX assistant" }));

    const auiConfig = (mockUseAui.mock.calls[0] as [unknown] | undefined)?.[0] as {
      suggestions: unknown;
    };
    expect(auiConfig.suggestions).toEqual({
      kind: "suggestions",
      config: [
        {
          title: "比较今天最值得研究的两只股票",
          label: "快速开始",
          prompt: "比较今天最值得研究的两只股票",
        },
        {
          title: "总结主线主题",
          label: "快速开始",
          prompt: "总结主线主题",
        },
      ],
    });
  });

  test("injects market, workspace, and research-card summaries as assistant instructions", () => {
    const { getByRole } = render(
      <TenxCopilotPanel
        market="CN"
        workspace={{
          market: "CN",
          universe: "AI 核心资产",
          universeStrategy: "preset",
          universeDescription: "desc",
          universeBuckets: [],
          snapshotAt: "2026-04-18T10:00:00Z",
          freshness: {
            updatedAt: "2026-04-18T10:00:00Z",
            dataComplete: true,
            sourceSummary: "summary",
            coverage: "full",
          },
          availableActions: [],
          candidates: [
            {
              market: "CN",
              symbol: "300750.SZ",
              name: "宁德时代",
              sector: "新能源",
              theme: "储能",
              stage: "validation",
              lifecycleStage: { key: "validation", label: "验证期", summary: "验证逻辑" },
              score: 87,
              scoreChange: 4,
              price: 200,
              priceChangePct: 1.2,
              marketCapLabel: "large",
              evidenceCount: 5,
              riskLevel: "medium",
              momentum: "strengthening",
              nextEvent: "财报",
              thesis: "thesis",
              keySignal: "signal",
              selectionReason: "reason",
              stageReason: "stage reason",
              crowdingNote: "crowding",
              scoreDrivers: [],
              whySelected: { summary: "进入候选池", bullets: [] },
              scoreBreakdown: [],
              freshness: {
                updatedAt: "2026-04-18T10:00:00Z",
                dataComplete: true,
                sourceSummary: "summary",
                coverage: "full",
              },
              availableActions: [],
            },
          ],
          themes: [],
          watchlist: [],
          timeline: [],
          copilotPrompts: [],
        }}
        researchCard={{
          market: "CN",
          symbol: "300750.SZ",
          name: "宁德时代",
          sector: "新能源",
          theme: "储能",
          stage: "validation",
          lifecycleStage: { key: "validation", label: "验证期", summary: "验证逻辑" },
          score: 87,
          thesisSummary: "研究卡摘要",
          selectionReason: "reason",
          stageReason: "stage reason",
          crowdingNote: "crowding",
          scoreDrivers: [],
          whySelected: { summary: "进入候选池", bullets: [] },
          scoreBreakdown: [],
          facts: [],
          thesisPoints: [],
          evidenceItems: [],
          riskItems: [{ title: "需求波动", severity: "medium", trigger: "订单下滑", note: "note" }],
          nextWatchPoints: ["关注下季度出货"],
          freshness: {
            updatedAt: "2026-04-18T10:00:00Z",
            dataComplete: true,
            sourceSummary: "summary",
            coverage: "full",
          },
          availableActions: [],
        }}
      >
        <div>workspace</div>
      </TenxCopilotPanel>,
    );

    fireEvent.click(getByRole("button", { name: "Open TenX assistant" }));

    const instructions = mockUseAssistantInstructions.mock.calls[0][0] as string;
    expect(instructions).toContain("你是 TenX Hunter 的应用内研究助手。");
    expect(instructions).toContain("当前页面市场：CN");
    expect(instructions).toContain("工作台范围：AI 核心资产");
    expect(instructions).toContain("300750.SZ | 宁德时代");
    expect(instructions).toContain("当前研究卡：300750.SZ | 宁德时代");
    expect(instructions).toContain("研究卡摘要");
  });

  test("defers research-card navigation until the thread is no longer running", async () => {
    mockAuiState.thread.isRunning = true;

    const { getByRole, rerender } = render(
      <TenxCopilotPanel market="CN">
        <div>workspace</div>
      </TenxCopilotPanel>,
    );

    fireEvent.click(getByRole("button", { name: "Open TenX assistant" }));

    const auiConfig = (mockUseAui.mock.calls[0] as [unknown] | undefined)?.[0] as {
      tools: {
        toolkit: {
          openResearchCard: {
            execute: (args: { symbol: string; market?: string }) => Promise<unknown>;
          };
        };
      };
    };
    const openResearchCard = auiConfig.tools.toolkit.openResearchCard;

    let result: unknown;
    await act(async () => {
      result = await openResearchCard.execute({
        symbol: "300750.SZ",
        market: "CN",
      });
    });

    expect(result).toEqual({
      ok: true,
      href: "/tenx-hunter/cn/research/300750.SZ",
      message: "已准备打开 300750.SZ 的研究卡。",
    });
    expect(routerPush).not.toHaveBeenCalled();

    mockAuiState.thread.isRunning = false;

    rerender(
      <TenxCopilotPanel market="CN">
        <div>workspace</div>
      </TenxCopilotPanel>,
    );

    await waitFor(() => {
      expect(routerPush).toHaveBeenCalledWith("/tenx-hunter/cn/research/300750.SZ");
    });
  });

  test("hydrates initial messages from localStorage and clears them on new conversation", async () => {
    window.localStorage.setItem(
      "tenx-assistant:v2:CN:/tenx-hunter/cn",
      JSON.stringify([{ id: "m1", role: "assistant", parts: [{ type: "text", text: "hello" }] }]),
    );

    const { getByRole, rerender } = render(
      <TenxCopilotPanel market="CN">
        <div>workspace</div>
      </TenxCopilotPanel>,
    );

    fireEvent.click(getByRole("button", { name: "Open TenX assistant" }));

    rerender(
      <TenxCopilotPanel market="CN">
        <div>workspace</div>
      </TenxCopilotPanel>,
    );

    await waitFor(() => {
      expect(mockUseChatRuntime).toHaveBeenLastCalledWith(
        expect.objectContaining({
          messages: [{ id: "m1", role: "assistant", parts: [{ type: "text", text: "hello" }] }],
        }),
      );
    });

    fireEvent.click(getByRole("button", { name: "new conversation" }));

    await waitFor(() => {
      expect(window.localStorage.getItem("tenx-assistant:v2:CN:/tenx-hunter/cn")).toBeNull();
    });
  });

  test("requires a real confirmation before removing from watchlist", async () => {
    const confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(false);

    const { getByRole } = render(
      <TenxCopilotPanel market="CN">
        <div>workspace</div>
      </TenxCopilotPanel>,
    );

    fireEvent.click(getByRole("button", { name: "Open TenX assistant" }));

    const auiConfig = (mockUseAui.mock.calls[0] as [unknown] | undefined)?.[0] as {
      tools: {
        toolkit: {
          removeFromWatchlist: {
            execute: (args: { symbol: string; market?: string }) => Promise<unknown>;
          };
        };
      };
    };

    let result: unknown;
    await act(async () => {
      result = await auiConfig.tools.toolkit.removeFromWatchlist.execute({
        symbol: "300750.SZ",
        market: "CN",
      });
    });

    expect(confirmSpy).toHaveBeenCalledWith("确认将 300750.SZ 从观察池移除？");
    expect(createWatchlistEntry).not.toHaveBeenCalled();
    expect(result).toEqual({
      ok: false,
      message: "已取消将 300750.SZ 移出观察池。",
    });

    confirmSpy.mockRestore();
  });
});
