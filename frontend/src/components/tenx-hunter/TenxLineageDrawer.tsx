"use client";

import { lineageByStage } from "@/components/tenx-hunter/lineageData";
import clsx from "clsx";
import { ArrowRight, Database, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type Props = {
  stageId: string;
};

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
      {children}
    </h3>
  );
}

export default function TenxLineageDrawer({ stageId }: Props) {
  const [open, setOpen] = useState(false);
  const openDrawer = useCallback(() => setOpen(true), []);
  const closeDrawer = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeDrawer();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, closeDrawer]);

  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const lineage = lineageByStage[stageId];
  if (!lineage) return null;

  return (
    <>
      <button
        type="button"
        onClick={openDrawer}
        className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 text-sm font-medium text-gray-600 shadow-xs transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
        aria-label={`查看 ${lineage.title} 数据血缘`}
        title="数据血缘"
      >
        <Database className="h-4 w-4" />
        <span className="hidden sm:inline">数据血缘</span>
      </button>

      <div
        className={clsx(
          "fixed inset-0 z-50 transition-colors duration-300",
          open ? "visible bg-black/40" : "invisible bg-black/0",
        )}
        onClick={closeDrawer}
        aria-hidden="true"
      >
        <aside
          className={clsx(
            "absolute right-0 top-0 flex h-full w-full max-w-md flex-col overflow-y-auto bg-white shadow-2xl transition-transform duration-300 dark:bg-gray-950",
            open ? "translate-x-0" : "translate-x-full",
          )}
          onClick={(e) => e.stopPropagation()}
          role="dialog"
          aria-label={`${lineage.title} 数据血缘`}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-800">
            <div>
              <h2 className="text-base font-semibold text-gray-900 dark:text-white">
                数据血缘 · {lineage.title}
              </h2>
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{lineage.summary}</p>
            </div>
            <button
              type="button"
              onClick={closeDrawer}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300"
              aria-label="关闭"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex-1 space-y-6 px-5 py-4">
            {/* Upstream */}
            <section>
              <SectionTitle>数据来源 (Upstream)</SectionTitle>
              <div className="space-y-2">
                {lineage.upstream.map((src) => (
                  <div
                    key={src.label}
                    className="rounded-lg border border-gray-200 p-3 dark:border-gray-800"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-gray-900 dark:text-white">{src.label}</span>
                      {src.store ? (
                        <span className="inline-flex rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono text-gray-500 dark:bg-gray-800 dark:text-gray-400">{src.store}</span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">{src.desc}</p>
                  </div>
                ))}
              </div>
            </section>

            {/* Processing */}
            <section>
              <SectionTitle>处理逻辑 (Processing)</SectionTitle>
              <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-900/60">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{lineage.processing.summary}</p>
                <ul className="mt-3 space-y-2">
                  {lineage.processing.steps.map((step, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs leading-5 text-gray-600 dark:text-gray-400">
                      <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-white text-[10px] font-bold text-gray-500 ring-1 ring-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:ring-gray-700">
                        {i + 1}
                      </span>
                      {step}
                    </li>
                  ))}
                </ul>
              </div>
            </section>

            {/* Outputs */}
            <section>
              <SectionTitle>输出与下游 (Outputs)</SectionTitle>
              <div className="space-y-2">
                {lineage.outputs.map((out) => (
                  <div
                    key={out.label}
                    className="flex items-start gap-3 rounded-lg border border-gray-200 p-3 dark:border-gray-800"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-gray-900 dark:text-white">{out.label}</span>
                        {out.store ? (
                          <span className="inline-flex rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono text-gray-500 dark:bg-gray-800 dark:text-gray-400">{out.store}</span>
                        ) : null}
                      </div>
                      <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">{out.desc}</p>
                    </div>
                    {out.to ? (
                      <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-brand-50 px-2 py-1 text-[11px] font-semibold text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">
                        <ArrowRight className="h-3 w-3" />
                        {out.to}
                      </span>
                    ) : null}
                  </div>
                ))}
              </div>
            </section>

            {/* Data Models */}
            <section>
              <SectionTitle>数据模型 (Models)</SectionTitle>
              <div className="space-y-2">
                {lineage.models.map((model) => (
                  <div
                    key={model.name}
                    className="rounded-lg border border-gray-200 p-3 dark:border-gray-800"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono font-semibold text-gray-900 dark:text-white">{model.name}</span>
                      <span className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-bold ${
                        model.schema === "oltp"
                          ? "bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300"
                          : model.schema === "dim"
                            ? "bg-purple-50 text-purple-700 dark:bg-purple-500/10 dark:text-purple-300"
                            : "bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-300"
                      }`}>{model.schema}</span>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {model.fields.map((f) => (
                        <span
                          key={f}
                          className="inline-flex rounded bg-gray-100 px-1.5 py-0.5 text-[11px] font-mono text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                        >
                          {f}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* API Endpoints */}
            <section>
              <SectionTitle>API 端点</SectionTitle>
              <div className="space-y-2">
                {lineage.apis.map((api) => (
                  <div
                    key={`${api.method}-${api.path}`}
                    className="flex items-start gap-3 rounded-lg border border-gray-200 p-3 dark:border-gray-800"
                  >
                    <span
                      className={clsx(
                        "shrink-0 rounded px-1.5 py-0.5 text-[11px] font-bold",
                        api.method === "GET"
                          ? "bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300"
                          : "bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-300",
                      )}
                    >
                      {api.method}
                    </span>
                    <div className="min-w-0">
                      <div className="text-xs font-mono text-gray-900 dark:text-white">{api.path}</div>
                      <p className="mt-0.5 text-[11px] text-gray-500 dark:text-gray-400">{api.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </aside>
      </div>
    </>
  );
}
