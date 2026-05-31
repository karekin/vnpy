"use client";

import "streamdown/styles.css";

import { cjk } from "@streamdown/cjk";
import { code } from "@streamdown/code";
import { math } from "@streamdown/math";
import { mermaid } from "@streamdown/mermaid";
import { getTenxErrorMessage, uploadTenxResearchReport } from "@/components/tenx-hunter/api";
import type { TenxMarket, TenxResearchReport } from "@/components/tenx-hunter/types";
import { BookOpen, FileText, Upload } from "lucide-react";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import { Streamdown } from "streamdown";

type TenxResearchReportPanelProps = {
  market: TenxMarket;
  symbol: string;
  initialReport: TenxResearchReport | null;
  showContent?: boolean;
};

const streamdownPlugins = { cjk, code, math, mermaid };

function excerpt(markdown: string) {
  const compact = markdown
    .replace(/^#+\s+/gm, "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return compact.length > 220 ? `${compact.slice(0, 220)}...` : compact;
}

export default function TenxResearchReportPanel({
  market,
  symbol,
  initialReport,
  showContent = false,
}: TenxResearchReportPanelProps) {
  const [report, setReport] = useState<TenxResearchReport | null>(initialReport);
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const marketPath = market.toLowerCase();
  const preview = useMemo(() => (report ? excerpt(report.contentMarkdown) : ""), [report]);

  async function handleFile(file: File | null) {
    if (!file) return;
    setIsUploading(true);
    setMessage(null);
    try {
      const result = await uploadTenxResearchReport(market, symbol, file);
      setReport(result.report);
      setMessage(result.message);
    } catch (error) {
      setMessage(getTenxErrorMessage(error));
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  return (
    <section className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex flex-col gap-3 border-b border-gray-200 px-5 py-4 dark:border-gray-800 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
              <BookOpen className="h-4 w-4" aria-hidden="true" />
            </span>
            <div>
              <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">投研知识库</h3>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{report ? report.title : `${symbol.toUpperCase()} 暂无手动报告`}</p>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {report && !showContent ? (
            <Link
              href={`/tenx-hunter/${marketPath}/research/${symbol.toUpperCase()}/report`}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
            >
              <FileText className="h-4 w-4" aria-hidden="true" />
              打开报告
            </Link>
          ) : null}
          <label
            aria-disabled={isUploading}
            className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-brand-500 px-3 py-2 text-sm font-medium text-white transition hover:bg-brand-600 aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
          >
            <Upload className="h-4 w-4" aria-hidden="true" />
            {isUploading ? "上传中" : "上传 Markdown"}
            <input
              ref={fileInputRef}
              type="file"
              accept=".md,.markdown,.txt,text/markdown,text/plain"
              className="sr-only"
              disabled={isUploading}
              onChange={(event) => {
                void handleFile(event.target.files?.[0] ?? null);
              }}
            />
          </label>
        </div>
      </div>
      <div className="p-5">
        {message ? (
          <div className="mb-4 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">{message}</div>
        ) : null}
        {report ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
              <span className="rounded-full bg-gray-100 px-2 py-1 dark:bg-gray-900">{report.sourceFilename}</span>
              <span className="rounded-full bg-gray-100 px-2 py-1 dark:bg-gray-900">{report.wordCount} 字符</span>
              <span className="rounded-full bg-gray-100 px-2 py-1 dark:bg-gray-900">{report.updatedAt}</span>
            </div>
            {showContent ? (
              <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm leading-7 text-gray-700 dark:border-gray-800 dark:bg-gray-900/40 dark:text-gray-200">
                <Streamdown className="tenx-research-markdown" mode="static" plugins={streamdownPlugins}>
                  {report.contentMarkdown}
                </Streamdown>
              </div>
            ) : (
              <p className="text-sm leading-7 text-gray-600 dark:text-gray-300">{preview}</p>
            )}
          </div>
        ) : (
          <div className="rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
            上传后会绑定到 {symbol.toUpperCase()}，研究卡片和报告页会读取同一份内容。
          </div>
        )}
      </div>
    </section>
  );
}
