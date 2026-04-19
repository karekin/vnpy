"use client";

import "@assistant-ui/react-markdown/styles/dot.css";

import { uploadTenxDeerFlowFiles } from "@/components/tenx-hunter/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/utils/index";
import {
  AuiIf,
  AttachmentPrimitive,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  SuggestionPrimitive,
  ThreadPrimitive,
  useAui,
  useAuiState,
} from "@assistant-ui/react";
import {
  MarkdownTextPrimitive,
  unstable_memoizeMarkdownComponents as memoizeMarkdownComponents,
  useIsMarkdownCodeBlock,
} from "@assistant-ui/react-markdown";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  FileText,
  Paperclip,
  SquareIcon,
  XIcon,
} from "lucide-react";
import remarkGfm from "remark-gfm";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentPropsWithoutRef,
  type ReactNode,
} from "react";

type Props = {
  title: string;
  onNewConversation: () => void;
  modeSwitcher?: ReactNode;
  currentView?: "chat" | "process";
  processPanel?: ReactNode;
  currentThreadId?: string;
  uploadedFileCount?: number;
  createUploadThreadId?: () => string;
  onUploadThreadReady?: (threadId: string) => void;
  onUploadedFilesChange?: (files: UploadedThreadFileMeta[]) => void;
};

export type UploadedThreadFileMeta = {
  filename: string;
  size: string;
  path: string;
  virtual_path: string;
  artifact_url: string;
  markdown_file?: string;
  markdown_path?: string;
  markdown_virtual_path?: string;
  markdown_artifact_url?: string;
};

type DeerFlowStatusPart = {
  type: "data-deerflow-status";
  data: {
    label?: string;
    payload?: unknown;
  };
};

function MarkdownCode({
  className,
  ...props
}: ComponentPropsWithoutRef<"code">) {
  const isCodeBlock = useIsMarkdownCodeBlock();

  return (
    <code
      className={cn(
        !isCodeBlock &&
          "rounded-md border border-slate-200 bg-slate-100 px-1.5 py-0.5 font-mono text-[0.85em] dark:border-white/10 dark:bg-white/5",
        className,
      )}
      {...props}
    />
  );
}

const markdownComponents = memoizeMarkdownComponents({
  p: ({ className, ...props }) => (
    <p
      className={cn("my-2 text-sm leading-7 first:mt-0 last:mb-0", className)}
      {...props}
    />
  ),
  ul: ({ className, ...props }) => (
    <ul
      className={cn("my-2 ml-5 list-disc text-sm leading-7", className)}
      {...props}
    />
  ),
  ol: ({ className, ...props }) => (
    <ol
      className={cn("my-2 ml-5 list-decimal text-sm leading-7", className)}
      {...props}
    />
  ),
  li: ({ className, ...props }) => (
    <li className={cn("my-1", className)} {...props} />
  ),
  table: ({ className, ...props }) => (
    <div className="my-3 overflow-x-auto rounded-2xl border border-slate-200 dark:border-white/10">
      <table
        className={cn("min-w-full border-collapse text-left text-sm", className)}
        {...props}
      />
    </div>
  ),
  thead: ({ className, ...props }) => (
    <thead
      className={cn("bg-slate-100/90 dark:bg-white/5", className)}
      {...props}
    />
  ),
  th: ({ className, ...props }) => (
    <th
      className={cn(
        "border-b border-slate-200 px-3 py-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500 dark:border-white/10 dark:text-slate-300",
        className,
      )}
      {...props}
    />
  ),
  td: ({ className, ...props }) => (
    <td
      className={cn(
        "border-b border-slate-200 px-3 py-2 align-top text-sm text-slate-700 dark:border-white/10 dark:text-slate-100",
        className,
      )}
      {...props}
    />
  ),
  code: MarkdownCode,
  pre: ({ className, ...props }) => (
    <pre
      className={cn(
        "overflow-x-auto rounded-2xl border border-slate-200 bg-slate-100 p-4 text-xs leading-6 dark:border-white/10 dark:bg-white/5",
        className,
      )}
      {...props}
    />
  ),
  a: ({ className, ...props }) => (
    <a
      className={cn(
        "font-medium text-brand-600 underline underline-offset-2 hover:text-brand-500 dark:text-brand-300 dark:hover:text-brand-200",
        className,
      )}
      {...props}
    />
  ),
});

function TenxAssistantMarkdown() {
  return (
    <MarkdownTextPrimitive
      remarkPlugins={[remarkGfm]}
      className="aui-md"
      components={markdownComponents}
    />
  );
}

function TenxAssistantMessageError() {
  return (
    <MessagePrimitive.Error>
      <ErrorPrimitive.Root className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-100">
        <ErrorPrimitive.Message />
      </ErrorPrimitive.Root>
    </MessagePrimitive.Error>
  );
}

function TenxAssistantUserMessage() {
  return (
    <MessagePrimitive.Root className="ml-auto flex max-w-[88%] justify-end py-2">
      <div className="flex flex-col items-end">
        <TenxUserMessageAttachments />
        <div className="rounded-[22px] bg-slate-900 px-4 py-3 text-sm leading-7 text-white shadow-sm dark:bg-slate-800">
          <MessagePrimitive.Parts>
            {({ part }) => (part.type === "text" ? <TenxAssistantMarkdown /> : null)}
          </MessagePrimitive.Parts>
          <TenxAssistantMessageError />
        </div>
      </div>
    </MessagePrimitive.Root>
  );
}

function TenxAssistantFallbackTool({
  toolName,
  status,
  argsText,
}: {
  toolName?: string;
  status?: { type: string };
  argsText?: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-white/5 dark:text-white/80">
      <div className="font-semibold">{toolName ?? "工具调用"}</div>
      <div className="mt-1">
        {status?.type === "running" ? "工具正在执行…" : "工具调用已完成。"}
      </div>
      {argsText ? <pre className="mt-2 whitespace-pre-wrap text-xs opacity-80">{argsText}</pre> : null}
    </div>
  );
}

function TenxAssistantStreamingPlaceholder() {
  return (
    <div className="rounded-2xl bg-slate-100/80 px-4 py-4 dark:bg-white/[0.04]">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-brand-600 dark:text-brand-300">
        <span className="inline-flex gap-1">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.2s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.1s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current" />
        </span>
        <span>正在分析</span>
      </div>
      <div className="mt-3 space-y-2">
        <div className="h-2.5 w-[78%] animate-pulse rounded-full bg-slate-300/80 dark:bg-white/12" />
        <div className="h-2.5 w-[92%] animate-pulse rounded-full bg-slate-300/70 dark:bg-white/10" />
        <div className="h-2.5 w-[66%] animate-pulse rounded-full bg-slate-300/60 dark:bg-white/8" />
      </div>
    </div>
  );
}

function isDeerFlowStatusPart(part: unknown): part is DeerFlowStatusPart {
  return Boolean(
    part &&
      typeof part === "object" &&
      "type" in part &&
      (part as { type?: string }).type === "data-deerflow-status",
  );
}

function useAttachmentSrc() {
  const attachmentType = useAuiState((state) => state.attachment.type);
  const attachmentFile = useAuiState((state) => state.attachment.file);
  const attachmentContent = useAuiState((state) => state.attachment.content);
  const [src, setSrc] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (attachmentType !== "image") {
      setSrc(undefined);
      return;
    }

    if (attachmentFile instanceof File) {
      const objectUrl = URL.createObjectURL(attachmentFile);
      setSrc(objectUrl);
      return () => {
        URL.revokeObjectURL(objectUrl);
      };
    }

    const imagePart = attachmentContent?.find((item) => item.type === "image");
    if (imagePart?.type === "image") {
      setSrc(imagePart.image);
      return;
    }

    setSrc(undefined);
  }, [attachmentContent, attachmentFile, attachmentType]);

  return src;
}

function TenxAttachmentPreviewDialog({ children }: { children: ReactNode }) {
  const src = useAttachmentSrc();
  if (!src) {
    return <>{children}</>;
  }

  return (
    <Dialog>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="max-w-3xl border-none bg-black/90 p-3 shadow-2xl">
        <DialogTitle className="sr-only">Attachment preview</DialogTitle>
        <img src={src} alt="Attachment preview" className="mx-auto max-h-[80vh] max-w-full rounded-2xl object-contain" />
      </DialogContent>
    </Dialog>
  );
}

function TenxAttachmentItem({ composer }: { composer: boolean }) {
  const attachmentType = useAuiState((state) => state.attachment.type);
  const attachmentFile = useAuiState((state) => state.attachment.file);
  const attachmentContent = useAuiState((state) => state.attachment.content);
  const src = useAttachmentSrc();

  const label = useMemo(() => {
    if (attachmentFile instanceof File && attachmentFile.name) {
      return attachmentFile.name;
    }
    if (attachmentContent?.[0]?.type === "file" && attachmentContent[0].filename) {
      return attachmentContent[0].filename;
    }
    return attachmentType === "image" ? "图片附件" : "文件附件";
  }, [attachmentContent, attachmentFile, attachmentType]);

  const tile = (
    <div
      className={cn(
        "group relative overflow-hidden rounded-2xl border border-slate-200 bg-slate-100/80 shadow-sm dark:border-white/10 dark:bg-white/[0.05]",
        composer ? "h-16 w-16" : "h-12 w-12",
      )}
    >
      {src ? (
        <img src={src} alt={label} className="h-full w-full object-cover" />
      ) : (
        <div className="flex h-full w-full items-center justify-center">
          <FileText className="h-5 w-5 text-slate-500 dark:text-slate-300" />
        </div>
      )}
    </div>
  );

  return (
    <AttachmentPrimitive.Root className="relative flex items-center gap-3">
      <TenxAttachmentPreviewDialog>{tile}</TenxAttachmentPreviewDialog>
      <div className={cn("min-w-0", composer ? "max-w-[180px]" : "max-w-[160px]")}>
        <div className="truncate text-sm font-medium text-slate-700 dark:text-slate-100">{label}</div>
        <div className="truncate text-xs text-slate-400 dark:text-slate-500">{attachmentType}</div>
      </div>
      {composer ? (
        <AttachmentPrimitive.Remove asChild>
          <button
            type="button"
            className="absolute -right-1 -top-1 inline-flex h-6 w-6 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:text-red-600 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300"
            aria-label="Remove attachment"
          >
            <XIcon className="h-3.5 w-3.5" />
          </button>
        </AttachmentPrimitive.Remove>
      ) : null}
    </AttachmentPrimitive.Root>
  );
}

function TenxComposerAttachments() {
  return (
    <div className="flex w-full flex-wrap gap-3 empty:hidden">
      <ComposerPrimitive.Attachments>
        {() => <TenxAttachmentItem composer={true} />}
      </ComposerPrimitive.Attachments>
    </div>
  );
}

function TenxUserMessageAttachments() {
  return (
    <div className="mb-2 flex w-full flex-wrap justify-end gap-3">
      <MessagePrimitive.Attachments>
        {() => <TenxAttachmentItem composer={false} />}
      </MessagePrimitive.Attachments>
    </div>
  );
}

function TenxAssistantStatusChip({ label }: { label: string }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 dark:bg-white/[0.06] dark:text-slate-300">
      <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
      <span>{label}</span>
    </div>
  );
}

function TenxAssistantAssistantMessage() {
  const isRunning = useAuiState((state) => state.thread.isRunning);
  const isLast = useAuiState((state) => state.message.isLast);
  const hasVisibleContent = useAuiState((state) => state.message.content.length > 0);

  return (
    <MessagePrimitive.Root className="py-2">
      <div className="space-y-3 px-1 text-slate-800 dark:text-slate-100">
        {isRunning && isLast && !hasVisibleContent ? <TenxAssistantStreamingPlaceholder /> : null}
        <MessagePrimitive.Parts>
          {({ part }) => {
            if (part.type === "text") {
              return (
                <div className="px-3 py-1">
                  <TenxAssistantMarkdown />
                </div>
              );
            }

            if (part.type === "tool-call") {
              return (
                part.toolUI ?? (
                  <TenxAssistantFallbackTool
                    toolName={part.toolName}
                    status={part.status}
                    argsText={part.argsText}
                  />
                )
              );
            }

            if (isDeerFlowStatusPart(part)) {
              const statusPart = part as DeerFlowStatusPart;
              return <TenxAssistantStatusChip label={statusPart.data.label ?? "DeerFlow status"} />;
            }

            return null;
          }}
        </MessagePrimitive.Parts>
        <TenxAssistantMessageError />
      </div>
    </MessagePrimitive.Root>
  );
}

function TenxAssistantThreadMessage() {
  const role = useAuiState((state) => state.message.role);
  return role === "user" ? (
    <TenxAssistantUserMessage />
  ) : (
    <TenxAssistantAssistantMessage />
  );
}

function TenxAssistantSuggestion() {
  return (
    <SuggestionPrimitive.Trigger send asChild>
      <button
        type="button"
        className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-brand-200 hover:bg-brand-50/60 dark:border-white/10 dark:bg-white/5 dark:hover:border-brand-400/30 dark:hover:bg-brand-500/10"
      >
        <div className="text-sm font-semibold text-slate-900 dark:text-white">
          <SuggestionPrimitive.Title />
        </div>
        <div className="mt-1 text-xs leading-6 text-slate-500 dark:text-slate-300">
          <SuggestionPrimitive.Description />
        </div>
      </button>
    </SuggestionPrimitive.Trigger>
  );
}

function TenxAssistantWelcome() {
  return (
    <div className="mx-auto flex h-full w-full max-w-2xl flex-col justify-center px-5 py-8">
      <div className="rounded-[28px] border border-slate-200 bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.12),transparent_32%),linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] px-6 py-6 shadow-sm dark:border-white/10 dark:bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.18),transparent_30%),linear-gradient(180deg,#0f172a_0%,#020617_100%)]">
        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-brand-600 dark:text-brand-300">
          TenX Assistant
        </div>
        <h2 className="mt-3 text-2xl font-semibold text-slate-900 dark:text-white">
          直接问研究问题，或让我帮你执行 TenX 动作
        </h2>
        <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-300">
          当前面板基于 Vercel AI SDK 的稳定消息流和 assistant-ui 线程界面。先做可靠的聊天与工具调用，不做过重的 agent-driven UI。
        </p>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <ThreadPrimitive.Suggestions>
          {() => <TenxAssistantSuggestion />}
        </ThreadPrimitive.Suggestions>
      </div>
    </div>
  );
}

function TenxAssistantComposer({
  currentThreadId,
  uploadedFileCount = 0,
  createUploadThreadId,
  onUploadThreadReady,
  onUploadedFilesChange,
}: {
  currentThreadId: string;
  uploadedFileCount?: number;
  createUploadThreadId?: () => string;
  onUploadThreadReady?: (threadId: string) => void;
  onUploadedFilesChange?: (files: UploadedThreadFileMeta[]) => void;
}) {
  const aui = useAui();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const composerAttachmentCount = useAuiState((state) => state.composer.attachments.length);
  const hasPendingUploads = composerAttachmentCount > uploadedFileCount;

  const addAndUploadFiles = async (files: File[] | FileList) => {
    const normalized = Array.from(files);
    if (normalized.length === 0) {
      return;
    }

    const targetThreadId = createUploadThreadId?.() ?? currentThreadId;

    if (!targetThreadId) {
      setUploadError("当前线程还没准备好，请稍后再上传。");
      return;
    }

    setUploadError(null);
    setIsUploading(true);
    onUploadThreadReady?.(targetThreadId);

    for (const file of normalized) {
      await aui.composer().addAttachment(file);
    }

    try {
      const result = await uploadTenxDeerFlowFiles(targetThreadId, normalized);
      onUploadedFilesChange?.(result.files);
    } catch (error) {
      console.error("Failed to upload files to DeerFlow thread", error);
      setUploadError("附件还在上传或上传失败，请稍后重试。");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <ComposerPrimitive.Root className="flex w-full flex-col">
      <ComposerPrimitive.AttachmentDropzone
        onDropCapture={(event) => {
          const files = event.dataTransfer?.files;
          if (files && files.length > 0) {
            void addAndUploadFiles(files);
          }
        }}
      >
      <div className="rounded-[28px] border border-slate-200 bg-white p-3 shadow-sm transition focus-within:border-brand-200 focus-within:shadow-[0_0_0_4px_rgba(59,130,246,0.08)] data-[dragging=true]:border-brand-300 data-[dragging=true]:bg-brand-50/60 dark:border-white/10 dark:bg-slate-950 dark:focus-within:border-brand-400/40 dark:focus-within:shadow-[0_0_0_4px_rgba(59,130,246,0.12)] dark:data-[dragging=true]:bg-brand-500/10">
        <TenxComposerAttachments />
        <ComposerPrimitive.Input
          placeholder="问研究问题，或直接要求我执行 TenX 动作…"
          className="min-h-24 w-full resize-none bg-transparent px-1 py-1 text-sm leading-7 text-slate-900 outline-none placeholder:text-slate-400 dark:text-white dark:placeholder:text-slate-500"
          rows={4}
          aria-label="TenX assistant message input"
          onPaste={(event) => {
            const clipboardFiles = Array.from(event.clipboardData?.files ?? []);
            if (clipboardFiles.length === 0) {
              return;
            }

            event.preventDefault();
            void addAndUploadFiles(clipboardFiles);
          }}
          onKeyDown={(event) => {
            if ((isUploading || hasPendingUploads) && event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
            }
          }}
        />
        <input
          ref={fileInputRef}
          type="file"
          multiple
          hidden
          accept="image/*,.pdf,.txt,.md,.csv,.xlsx,.doc,.docx,.ppt,.pptx"
          onChange={(event) => {
            if (event.target.files?.length) {
              void addAndUploadFiles(event.target.files);
            }
            event.target.value = "";
          }}
        />
        <div className="mt-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 transition hover:border-brand-300 hover:text-brand-700 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300 dark:hover:border-brand-400/40 dark:hover:text-white"
                  aria-label="Add attachment"
                >
                  <Paperclip className="h-4 w-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent>上传图片、文档或表格</TooltipContent>
            </Tooltip>
            <span>
              {isUploading || hasPendingUploads
                ? "正在上传附件，上传完成后才能发送…"
                : "支持多模态文件、拖拽上传与流式回答"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <AuiIf condition={(state) => !state.thread.isRunning}>
              <ComposerPrimitive.Send asChild>
                <Button
                  type="button"
                  size="icon"
                  className="h-9 w-9 rounded-full bg-brand-600 text-white hover:bg-brand-500"
                  aria-label="Send message"
                  disabled={isUploading || hasPendingUploads}
                >
                  <ArrowUpIcon className="h-4 w-4" />
                </Button>
              </ComposerPrimitive.Send>
            </AuiIf>
            <AuiIf condition={(state) => state.thread.isRunning}>
              <ComposerPrimitive.Cancel asChild>
                <Button
                  type="button"
                  size="icon"
                  variant="outline"
                  className="h-9 w-9 rounded-full"
                  aria-label="Stop generating"
                >
                  <SquareIcon className="h-3.5 w-3.5 fill-current" />
                </Button>
              </ComposerPrimitive.Cancel>
            </AuiIf>
          </div>
        </div>
        {uploadError || hasPendingUploads ? (
          <div className="mt-2 text-xs text-red-600 dark:text-red-300">
            {uploadError ?? "附件还没有全部上传完成，请稍等后再发送。"}
          </div>
        ) : null}
      </div>
      </ComposerPrimitive.AttachmentDropzone>
    </ComposerPrimitive.Root>
  );
}

function TenxAssistantScrollToBottom() {
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="absolute bottom-28 left-1/2 z-10 h-9 w-9 -translate-x-1/2 rounded-full shadow-sm"
        aria-label="Scroll to bottom"
      >
        <ArrowDownIcon className="h-4 w-4" />
      </Button>
    </ThreadPrimitive.ScrollToBottom>
  );
}

function TenxAssistantHeader({
  title,
  onNewConversation,
  modeSwitcher,
}: Props) {
  const aui = useAui();

  const handleNewConversation = () => {
    onNewConversation();
    aui.thread().reset();
  };

  return (
    <div className="border-b border-slate-200 bg-[linear-gradient(180deg,#f8fafc_0%,#ffffff_100%)] px-5 py-4 dark:border-white/10 dark:bg-[linear-gradient(180deg,#0f172a_0%,#020617_100%)]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900 dark:text-white">
            {title}
          </div>
          <div className="mt-1 text-xs leading-6 text-slate-500 dark:text-slate-300">
            稳定聊天、流式输出、工具调用
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="rounded-full"
          onClick={handleNewConversation}
        >
          新对话
        </Button>
      </div>
      {modeSwitcher ? <div className="mt-3">{modeSwitcher}</div> : null}
    </div>
  );
}

export default function TenxAssistantThread({
  title,
  onNewConversation,
  modeSwitcher,
  currentView = "chat",
  processPanel,
  currentThreadId = "",
  uploadedFileCount = 0,
  createUploadThreadId,
  onUploadThreadReady,
  onUploadedFilesChange,
}: Props) {
  return (
    <TooltipProvider>
      <ThreadPrimitive.Root className="flex h-full flex-col bg-transparent">
        <TenxAssistantHeader
          title={title}
          onNewConversation={onNewConversation}
          modeSwitcher={modeSwitcher}
        />

        {currentView === "process" ? (
          <div className="flex-1 overflow-y-auto bg-slate-50/70 dark:bg-slate-950">
            {processPanel}
          </div>
        ) : (
          <ThreadPrimitive.Viewport className="relative flex-1 overflow-y-auto px-4 py-4">
            <AuiIf condition={(state) => state.thread.isEmpty}>
              <TenxAssistantWelcome />
            </AuiIf>

            <div className="mx-auto w-full max-w-2xl">
              <ThreadPrimitive.Messages>
                {() => <TenxAssistantThreadMessage />}
              </ThreadPrimitive.Messages>
            </div>

          <div className="sticky bottom-0 mx-auto mt-6 w-full max-w-2xl bg-gradient-to-t from-white via-white to-white/75 pt-4 dark:from-slate-950 dark:via-slate-950 dark:to-slate-950/70">
            <TenxAssistantScrollToBottom />
            <TenxAssistantComposer
              currentThreadId={currentThreadId}
              uploadedFileCount={uploadedFileCount}
              createUploadThreadId={createUploadThreadId}
              onUploadThreadReady={onUploadThreadReady}
              onUploadedFilesChange={onUploadedFilesChange}
            />
          </div>
          </ThreadPrimitive.Viewport>
        )}
      </ThreadPrimitive.Root>
    </TooltipProvider>
  );
}
