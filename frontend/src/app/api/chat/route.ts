import { createAnthropic } from "@ai-sdk/anthropic";
import { frontendTools } from "@assistant-ui/react-ai-sdk";
import {
  JSONSchema7,
  createUIMessageStream,
  createUIMessageStreamResponse,
  convertToModelMessages,
  streamText,
  type UIMessage,
} from "ai";
import { readFileSync } from "fs";
import { resolve } from "path";
import { extractNormalizedMessageParts } from "./message-parts";

function loadLocalEnv() {
  const result: Record<string, string> = {};
  const candidates = [
    resolve(process.cwd(), "../.env.tushare.local"),
    resolve(process.cwd(), ".env.local"),
  ];

  for (const path of candidates) {
    try {
      const content = readFileSync(path, "utf-8");
      for (const raw of content.split("\n")) {
        const line = raw.trim();
        if (!line || line.startsWith("#") || !line.includes("=")) {
          continue;
        }

        const cleaned = line.startsWith("export ") ? line.slice(7) : line;
        const [key, ...rest] = cleaned.split("=");
        result[key.trim()] = rest.join("=").trim().replace(/^['"]|['"]$/g, "");
      }
    } catch {
      continue;
    }
  }

  return result;
}

const env = loadLocalEnv();
const apiKey = process.env.MINIMAX_API_KEY || env.MINIMAX_API_KEY || "";
const baseURL = (
  process.env.MINIMAX_BASE_URL ||
  env.MINIMAX_BASE_URL ||
  "https://api.minimaxi.com/anthropic/v1"
).replace(/\/$/, "");
const model = process.env.MINIMAX_MODEL || env.MINIMAX_MODEL || "MiniMax-M2.7";
const deerFlowEnabled =
  !["0", "false", "no", "off"].includes(
    (process.env.TENX_DEERFLOW_ENABLED || env.TENX_DEERFLOW_ENABLED || "").trim().toLowerCase(),
  );
const deerFlowApiBase = (
  process.env.TENX_DEERFLOW_API_URL ||
  process.env.NEXT_PUBLIC_TENX_HUNTER_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  env.NEXT_PUBLIC_TENX_HUNTER_API_URL ||
  env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8002"
).replace(/\/$/, "");

const anthropic = createAnthropic({
  apiKey,
  baseURL,
  headers: {
    "anthropic-version": "2023-06-01",
  },
});

function buildCurrentTurnPrompt({
  system,
  messages,
}: {
  system?: string;
  messages: UIMessage[];
}) {
  const latestUserMessage = [...messages]
    .reverse()
    .find((message) => message.role === "user");
  const latestUserParts = extractNormalizedMessageParts(latestUserMessage);

  const latestUserText = latestUserParts
    .filter((part): part is Extract<(typeof latestUserParts)[number], { type: "text" }> => part.type === "text")
    .map((part) => part.text)
    .join("\n")
    .trim();

  const latestFiles = latestUserParts
    .filter((part): part is Extract<(typeof latestUserParts)[number], { type: "file" }> => part.type === "file")
    .map((part) => `${part.filename || "unnamed-file"} (${part.mediaType || "unknown"})`);

  return [
    system ? `SYSTEM:\n${system}` : null,
    latestUserText ? `USER:\n${latestUserText}` : null,
    latestFiles?.length ? `UPLOADED FILES IN CURRENT THREAD:\n- ${latestFiles.join("\n- ")}` : null,
  ]
    .filter(Boolean)
    .join("\n\n");
}

type DeerFlowSseEvent = {
  event: string;
  data: string;
};

function parseDeerFlowEvents(chunkBuffer: string) {
  const segments = chunkBuffer.split("\n\n");
  const completeSegments = segments.slice(0, -1);
  const remainder = segments.at(-1) ?? "";

  const events: DeerFlowSseEvent[] = [];
  for (const segment of completeSegments) {
    const lines = segment.split("\n").filter(Boolean);
    if (lines.length === 0) {
      continue;
    }

    let event = "message";
    const dataLines: string[] = [];
    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
        continue;
      }
      if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }

    events.push({
      event,
      data: dataLines.join("\n"),
    });
  }

  return { events, remainder };
}

function maybeEmitAssistantFallback({
  candidate,
  writer,
  startedTextIds,
  startedReasoningIds,
  currentMessageId,
}: {
  candidate: Record<string, unknown> | null | undefined;
  writer: Parameters<Parameters<typeof createUIMessageStream>[0]["execute"]>[0]["writer"];
  startedTextIds: Set<string>;
  startedReasoningIds: Set<string>;
  currentMessageId: string;
}) {
  if (!candidate || candidate.type !== "ai" || typeof candidate.content !== "string") {
    return;
  }

  const fallbackMessageId =
    typeof candidate.id === "string" && candidate.id.trim()
      ? candidate.id
      : currentMessageId;

  const additional = candidate.additional_kwargs;
  const reasoningText =
    additional &&
    typeof additional === "object" &&
    typeof (additional as Record<string, unknown>).reasoning_content === "string"
      ? ((additional as Record<string, unknown>).reasoning_content as string).trim()
      : "";

  if (!startedReasoningIds.has(`${fallbackMessageId}-reasoning`) && reasoningText) {
    const reasoningId = `${fallbackMessageId}-reasoning`;
    writer.write({ type: "reasoning-start", id: reasoningId });
    startedReasoningIds.add(reasoningId);
    writer.write({
      type: "reasoning-delta",
      id: reasoningId,
      delta: reasoningText,
    });
  }

  if (!startedTextIds.has(fallbackMessageId)) {
    writer.write({ type: "text-start", id: fallbackMessageId });
    startedTextIds.add(fallbackMessageId);
    writer.write({
      type: "text-delta",
      id: fallbackMessageId,
      delta: candidate.content,
    });
  }
}

export async function POST(req: Request) {
  const {
    id,
    messages,
    system,
    tools,
    deerflowFiles,
  }: {
    id?: string;
    messages: UIMessage[];
    system?: string;
    tools?: Record<string, { description?: string; parameters: JSONSchema7 }>;
    deerflowFiles?: Array<{
      filename: string;
      size: string;
      path: string;
      virtual_path: string;
      artifact_url: string;
      markdown_file?: string;
      markdown_path?: string;
      markdown_virtual_path?: string;
      markdown_artifact_url?: string;
    }>;
  } = await req.json();

  const latestUserParts = extractNormalizedMessageParts(
    [...messages].reverse().find((message) => message.role === "user"),
  );
  const latestUserHasFileParts = latestUserParts.some((part) => part.type === "file");
  const latestUploadedFiles = deerflowFiles ?? [];

  if (latestUserHasFileParts && latestUploadedFiles.length === 0) {
    const stream = createUIMessageStream({
      originalMessages: messages,
      execute({ writer }) {
        const messageId = "attachment-upload-missing";
        writer.write({ type: "text-start", id: messageId });
        writer.write({
          type: "text-delta",
          id: messageId,
          delta: "附件还没有成功上传到 DeerFlow 线程，请等待上传完成后再发送，或重新上传一次。",
        });
        writer.write({ type: "text-end", id: messageId });
      },
    });

    return createUIMessageStreamResponse({ stream });
  }

  if (deerFlowEnabled) {
    const prompt = buildCurrentTurnPrompt({ system, messages });
    const upstream = await fetch(`${deerFlowApiBase}/api/v1/tenx-hunter/deerflow/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prompt,
        thread_id: id,
        files: deerflowFiles ?? [],
      }),
      signal: req.signal,
      cache: "no-store",
    });

    if (upstream.ok && upstream.body) {
      const stream = createUIMessageStream({
        originalMessages: messages,
        async execute({ writer }) {
          const decoder = new TextDecoder();
          const reader = upstream.body!.getReader();
          let buffer = "";
          let currentMessageId = "deerflow-response";
          let lastStatusKey = "";
          const startedTextIds = new Set<string>();
          const startedReasoningIds = new Set<string>();

          const emitStatus = (label: string, payload?: unknown) => {
            writer.write({
              type: "data-deerflow-status",
              data: {
                label,
                payload: payload ?? null,
              },
            });
          };

          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) {
                break;
              }

              buffer += decoder.decode(value, { stream: true });
              const parsed = parseDeerFlowEvents(buffer);
              buffer = parsed.remainder;

              for (const event of parsed.events) {
                if (event.event === "metadata") {
                  try {
                    const payload = JSON.parse(event.data) as { thread_id?: string };
                    if (payload.thread_id) {
                      emitStatus(`Thread ${payload.thread_id}`);
                    }
                  } catch {
                    continue;
                  }
                }

                if (event.event === "updates") {
                  try {
                    const payload = JSON.parse(event.data) as Record<string, unknown>;
                    const key = Object.keys(payload)[0] ?? "";
                    if (key && key !== lastStatusKey) {
                      lastStatusKey = key;
                      emitStatus(key, payload[key]);
                    }

                    if (key === "model" && payload[key] && typeof payload[key] === "object") {
                      const modelPayload = payload[key] as Record<string, unknown>;
                      const modelMessages = Array.isArray(modelPayload.messages)
                        ? (modelPayload.messages as Array<Record<string, unknown>>)
                        : [];
                      const lastAiMessage = [...modelMessages]
                        .reverse()
                        .find((message) => message?.type === "ai" && typeof message.content === "string");
                      maybeEmitAssistantFallback({
                        candidate: lastAiMessage,
                        writer,
                        startedTextIds,
                        startedReasoningIds,
                        currentMessageId,
                      });
                    }
                  } catch {
                    continue;
                  }
                }

                if (event.event === "messages") {
                  try {
                    const payload = JSON.parse(event.data) as [Record<string, unknown>, Record<string, unknown>?];
                    const chunk = payload[0] ?? {};
                    const meta = payload[1] ?? {};

                    if (typeof meta.agent_name === "string" && typeof meta.langgraph_node === "string") {
                      emitStatus(
                        `${meta.agent_name} · ${meta.langgraph_node}${typeof meta.langgraph_step === "number" ? ` · step ${meta.langgraph_step}` : ""}`,
                        meta,
                      );
                    }

                    const eventMessageId =
                      typeof chunk.id === "string" && chunk.id.trim()
                        ? chunk.id
                        : currentMessageId;
                    currentMessageId = eventMessageId;

                    if (chunk.type !== "ai") {
                      continue;
                    }

                    if (!startedTextIds.has(eventMessageId)) {
                      writer.write({ type: "text-start", id: eventMessageId });
                      startedTextIds.add(eventMessageId);
                    }

                    const additional = chunk.additional_kwargs;
                    if (
                      additional &&
                      typeof additional === "object" &&
                      typeof (additional as Record<string, unknown>).reasoning_content === "string"
                    ) {
                      const delta = ((additional as Record<string, unknown>).reasoning_content as string).trim();
                      if (delta) {
                        const reasoningId = `${eventMessageId}-reasoning`;
                        if (!startedReasoningIds.has(reasoningId)) {
                          writer.write({ type: "reasoning-start", id: reasoningId });
                          startedReasoningIds.add(reasoningId);
                        }
                        writer.write({
                          type: "reasoning-delta",
                          id: reasoningId,
                          delta,
                        });
                      }
                    }

                    if (typeof chunk.content === "string" && chunk.content.length > 0) {
                      writer.write({
                        type: "text-delta",
                        id: eventMessageId,
                        delta: chunk.content,
                      });
                    }
                  } catch {
                    continue;
                  }
                }

                if (event.event === "values") {
                  try {
                    const payload = JSON.parse(event.data) as Record<string, unknown>;
                    if (payload.thread_data) {
                      emitStatus("thread_data", payload.thread_data);
                    }
                    if (Array.isArray(payload.artifacts) && payload.artifacts.length > 0) {
                      emitStatus("artifacts", payload.artifacts);
                    }
                    const modelPayload =
                      payload.model && typeof payload.model === "object"
                        ? (payload.model as Record<string, unknown>)
                        : null;
                    const modelMessages = Array.isArray(modelPayload?.messages)
                      ? (modelPayload?.messages as Array<Record<string, unknown>>)
                      : [];
                    const lastAiMessage = [...modelMessages]
                      .reverse()
                      .find((message) => message?.type === "ai" && typeof message.content === "string");
                    maybeEmitAssistantFallback({
                      candidate: lastAiMessage,
                      writer,
                      startedTextIds,
                      startedReasoningIds,
                      currentMessageId,
                    });
                  } catch {
                    continue;
                  }
                }
              }
            }
          } finally {
            for (const reasoningId of startedReasoningIds) {
              writer.write({ type: "reasoning-end", id: reasoningId });
            }
            for (const textId of startedTextIds) {
              writer.write({ type: "text-end", id: textId });
            }
            reader.releaseLock();
          }
        },
      });

      return createUIMessageStreamResponse({ stream });
    }

    console.warn("DeerFlow stream request failed with status", upstream.status);
  }

  const result = streamText({
    abortSignal: req.signal,
    model: anthropic(model),
    messages: await convertToModelMessages(messages),
    system,
    tools: {
      ...frontendTools(tools ?? {}),
    },
  });

  return result.toUIMessageStreamResponse();
}
