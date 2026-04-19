"use client";

import {
  getTenxDeerFlowArtifactUrl,
  loadTenxDeerFlowHistory,
  loadTenxDeerFlowState,
  loadTenxDeerFlowThreads,
  loadTenxDeerFlowUploads,
} from "@/components/tenx-hunter/api";
import { cn } from "@/utils/index";
import { useAuiState } from "@assistant-ui/react";
import {
  FileArchive,
  FileInput,
  FolderTree,
  History,
  LoaderCircle,
  Orbit,
  Route,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type Props = {
  currentThreadId: string;
  refreshKey?: number;
};

type DeerFlowStateResponse = Record<string, unknown>;
type DeerFlowHistoryEntry = Record<string, unknown>;
type DeerFlowThreadRow = Record<string, unknown>;

type StatusEvent = {
  label: string;
  payload?: unknown;
};

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-white">
        {icon}
        <span>{title}</span>
      </div>
      {children}
    </section>
  );
}

function LabelValue({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="grid gap-1">
      <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500">
        {label}
      </div>
      <div className="text-sm text-slate-700 dark:text-slate-200">{value}</div>
    </div>
  );
}

function extractStatusEvents(messages: readonly unknown[]): StatusEvent[] {
  const events: StatusEvent[] = [];

  for (const message of messages) {
    if (!message || typeof message !== "object") {
      continue;
    }

    const content = (message as { content?: unknown }).content;
    if (!Array.isArray(content)) {
      continue;
    }

    for (const part of content) {
      if (!part || typeof part !== "object") {
        continue;
      }

      if ((part as { type?: string }).type !== "data") {
        continue;
      }

      if ((part as { name?: string }).name !== "deerflow-status") {
        continue;
      }

      const data = (part as { data?: { label?: string; payload?: unknown } }).data;
      if (!data?.label) {
        continue;
      }

      events.push({
        label: data.label,
        payload: data.payload,
      });
    }
  }

  return events;
}

function normalizeTitle(thread: DeerFlowThreadRow): string {
  const values = thread.values;
  if (values && typeof values === "object" && typeof (values as { title?: unknown }).title === "string") {
    return (values as { title: string }).title;
  }

  return typeof thread.thread_id === "string" ? thread.thread_id : "Untitled thread";
}

function renderThreadStatus(thread: DeerFlowThreadRow) {
  const status = typeof thread.status === "string" ? thread.status : "unknown";
  const tone =
    status === "busy"
      ? "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-200"
      : status === "error"
        ? "bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-200"
        : "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200";

  return (
    <span className={cn("rounded-full px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.08em]", tone)}>
      {status}
    </span>
  );
}

export default function TenxAssistantProcessPanel({ currentThreadId, refreshKey = 0 }: Props) {
  const isRunning = useAuiState((state) => state.thread.isRunning);
  const threadMessages = useAuiState((state) => state.thread.messages);

  const [selectedThreadId, setSelectedThreadId] = useState(currentThreadId);
  const [state, setState] = useState<DeerFlowStateResponse | null>(null);
  const [history, setHistory] = useState<DeerFlowHistoryEntry[]>([]);
  const [threads, setThreads] = useState<DeerFlowThreadRow[]>([]);
  const [uploads, setUploads] = useState<Array<{ filename: string; size?: number; created_at?: string }>>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setSelectedThreadId(currentThreadId);
  }, [currentThreadId]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      try {
        const [nextState, nextHistory, nextThreads, nextUploads] = await Promise.all([
          loadTenxDeerFlowState(selectedThreadId),
          loadTenxDeerFlowHistory(selectedThreadId, 12).catch(() => []),
          loadTenxDeerFlowThreads(20).catch(() => []),
          loadTenxDeerFlowUploads(selectedThreadId).catch(() => ({ files: [] })),
        ]);

        if (cancelled) {
          return;
        }

        setState(nextState);
        setHistory(nextHistory);
        setThreads(nextThreads);
        setUploads(Array.isArray(nextUploads.files) ? nextUploads.files : []);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    const timer = window.setInterval(() => {
      if (isRunning || selectedThreadId !== currentThreadId) {
        void load();
      }
    }, 2500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [currentThreadId, isRunning, refreshKey, selectedThreadId]);

  const liveStatuses = useMemo(() => extractStatusEvents(threadMessages).slice(-10), [threadMessages]);
  const values = state?.values && typeof state.values === "object" ? (state.values as Record<string, unknown>) : null;
  const metadata = state?.metadata && typeof state.metadata === "object" ? (state.metadata as Record<string, unknown>) : null;
  const threadData =
    values?.thread_data && typeof values.thread_data === "object"
      ? (values.thread_data as Record<string, unknown>)
      : null;
  const artifacts = Array.isArray(values?.artifacts) ? values?.artifacts : [];

  return (
    <div className="space-y-4 p-4">
      <Section title="当前线程" icon={<Orbit className="h-4 w-4 text-brand-500" />}>
        <div className="grid gap-4">
          <LabelValue label="Thread ID" value={<code className="break-all text-xs">{selectedThreadId}</code>} />
          <LabelValue label="Title" value={values?.title && typeof values.title === "string" ? values.title : "未命名"} />
          <LabelValue
            label="状态"
            value={
              <div className="flex items-center gap-2">
                {loading ? <LoaderCircle className="h-4 w-4 animate-spin text-brand-500" /> : null}
                {metadata?.agent_name ? <span>{String(metadata.agent_name)}</span> : <span>default</span>}
                {metadata?.model_name ? <span className="text-slate-400">· {String(metadata.model_name)}</span> : null}
              </div>
            }
          />
        </div>
      </Section>

      <Section title="运行轨迹" icon={<Route className="h-4 w-4 text-brand-500" />}>
        <div className="space-y-2">
          {liveStatuses.length ? (
            liveStatuses.map((item, index) => (
              <div key={`${item.label}-${index}`} className="rounded-xl bg-slate-100 px-3 py-2 text-sm text-slate-700 dark:bg-white/[0.05] dark:text-slate-200">
                {item.label}
              </div>
            ))
          ) : (
            <div className="text-sm text-slate-500 dark:text-slate-400">当前还没有采集到 DeerFlow 运行轨迹。</div>
          )}
        </div>
      </Section>

      <Section title="Artifacts / Outputs" icon={<FileArchive className="h-4 w-4 text-brand-500" />}>
        <div className="space-y-3">
          <LabelValue
            label="Workspace"
            value={<code className="break-all text-xs">{typeof threadData?.workspace_path === "string" ? threadData.workspace_path : "—"}</code>}
          />
          <LabelValue
            label="Outputs"
            value={<code className="break-all text-xs">{typeof threadData?.outputs_path === "string" ? threadData.outputs_path : "—"}</code>}
          />
          {artifacts.length ? (
            <div className="space-y-2">
              {artifacts.map((artifact, index) => {
                const row = artifact as Record<string, unknown>;
                const path = typeof row.path === "string" ? row.path : typeof row.filename === "string" ? row.filename : "";
                return (
                  <a
                    key={`${path}-${index}`}
                    href={path ? getTenxDeerFlowArtifactUrl(selectedThreadId, path) : "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="block rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:border-brand-300 hover:text-brand-700 dark:border-white/10 dark:text-slate-200 dark:hover:border-brand-400/40"
                  >
                    {path || `artifact-${index + 1}`}
                  </a>
                );
              })}
            </div>
          ) : (
            <div className="text-sm text-slate-500 dark:text-slate-400">当前线程还没有可枚举的 artifacts。</div>
          )}
        </div>
      </Section>

      <Section title="Uploads" icon={<FileInput className="h-4 w-4 text-brand-500" />}>
        <div className="space-y-2">
          {uploads.length ? (
            uploads.map((file) => (
              <div key={file.filename} className="rounded-xl bg-slate-100 px-3 py-2 text-sm dark:bg-white/[0.05]">
                <div className="font-medium text-slate-800 dark:text-slate-100">{file.filename}</div>
                <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  {typeof file.size === "number" ? `${file.size} bytes` : "size unknown"}
                </div>
              </div>
            ))
          ) : (
            <div className="text-sm text-slate-500 dark:text-slate-400">当前线程没有已上传文件。</div>
          )}
        </div>
      </Section>

      <Section title="线程列表" icon={<FolderTree className="h-4 w-4 text-brand-500" />}>
        <div className="space-y-2">
          {threads.length ? (
            threads.map((thread) => {
              const threadId = typeof thread.thread_id === "string" ? thread.thread_id : "";
              const active = threadId === selectedThreadId;
              return (
                <button
                  key={threadId}
                  type="button"
                  onClick={() => setSelectedThreadId(threadId)}
                  className={cn(
                    "w-full rounded-2xl border px-3 py-3 text-left transition",
                    active
                      ? "border-brand-300 bg-brand-50/70 dark:border-brand-400/40 dark:bg-brand-500/10"
                      : "border-slate-200 bg-white hover:border-slate-300 dark:border-white/10 dark:bg-white/[0.03]",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium text-slate-800 dark:text-slate-100">{normalizeTitle(thread)}</div>
                      <div className="mt-1 break-all text-xs text-slate-500 dark:text-slate-400">{threadId}</div>
                    </div>
                    {renderThreadStatus(thread)}
                  </div>
                </button>
              );
            })
          ) : (
            <div className="text-sm text-slate-500 dark:text-slate-400">还没有 DeerFlow 线程索引。</div>
          )}
        </div>
      </Section>

      <Section title="Checkpoint 历史" icon={<History className="h-4 w-4 text-brand-500" />}>
        <div className="space-y-2">
          {history.length ? (
            history.map((entry) => {
              const checkpointId = typeof entry.checkpoint_id === "string" ? entry.checkpoint_id : "unknown";
              const entryMetadata =
                entry.metadata && typeof entry.metadata === "object"
                  ? (entry.metadata as Record<string, unknown>)
                  : {};
              const entryValues =
                entry.values && typeof entry.values === "object"
                  ? (entry.values as Record<string, unknown>)
                  : {};
              const messageCount = Array.isArray(entryValues.messages) ? entryValues.messages.length : 0;

              return (
                <details key={checkpointId} className="rounded-2xl border border-slate-200 bg-white px-3 py-3 dark:border-white/10 dark:bg-white/[0.03]">
                  <summary className="cursor-pointer list-none">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium text-slate-800 dark:text-slate-100">
                          step {typeof entryMetadata.step === "number" ? entryMetadata.step : "?"} · {typeof entryMetadata.agent_name === "string" ? entryMetadata.agent_name : "agent"}
                        </div>
                        <div className="mt-1 break-all text-xs text-slate-500 dark:text-slate-400">{checkpointId}</div>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600 dark:bg-white/[0.06] dark:text-slate-300">
                        {messageCount} messages
                      </span>
                    </div>
                  </summary>
                  <div className="mt-3 space-y-3 text-sm text-slate-700 dark:text-slate-200">
                    <div>
                      <div className="text-xs uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500">Model</div>
                      <div className="mt-1">{typeof entryMetadata.model_name === "string" ? entryMetadata.model_name : "—"}</div>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500">Messages</div>
                      <div className="mt-2 space-y-2">
                        {Array.isArray(entryValues.messages) ? (
                          entryValues.messages.slice(-4).map((message, index) => {
                            const row = message as Record<string, unknown>;
                            return (
                              <div key={index} className="rounded-xl bg-slate-100 px-3 py-2 text-xs leading-6 dark:bg-white/[0.05]">
                                <div className="font-semibold uppercase text-slate-500 dark:text-slate-400">
                                  {typeof row.type === "string" ? row.type : "message"}
                                </div>
                                <div className="mt-1 whitespace-pre-wrap text-slate-700 dark:text-slate-200">
                                  {typeof row.content === "string" && row.content.trim() ? row.content : "—"}
                                </div>
                              </div>
                            );
                          })
                        ) : (
                          <div className="text-xs text-slate-500 dark:text-slate-400">没有可展示的消息。</div>
                        )}
                      </div>
                    </div>
                  </div>
                </details>
              );
            })
          ) : (
            <div className="text-sm text-slate-500 dark:text-slate-400">当前线程还没有 checkpoint 历史。</div>
          )}
        </div>
      </Section>
    </div>
  );
}
