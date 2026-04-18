import StatusTag from "@/components/cb-quant/StatusTag";
import type { TenxRiskLevel, TenxStage } from "@/components/tenx-hunter/types";
import React from "react";

export function getRiskTone(level: TenxRiskLevel) {
  if (level === "high") return "red" as const;
  if (level === "medium") return "yellow" as const;
  return "green" as const;
}

export function getStageTone(stage: TenxStage) {
  if (stage === "acceleration") return "green" as const;
  if (stage === "validation") return "blue" as const;
  if (stage === "falsified") return "red" as const;
  if (stage === "crowded") return "yellow" as const;
  return "slate" as const;
}

type MetricCardProps = {
  label: string;
  value: string;
  delta: string;
};

export function TenxMetricCard({ label, value, delta }: MetricCardProps) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
      <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
      <div className="mt-2 text-3xl font-semibold text-gray-900 dark:text-white">{value}</div>
      <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{delta}</p>
    </div>
  );
}

type SectionCardProps = {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
};

export function TenxSectionCard({ title, description, action, children }: SectionCardProps) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex flex-col gap-3 border-b border-gray-200 px-5 py-4 dark:border-gray-800 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">{title}</h3>
          {description ? <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{description}</p> : null}
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

type CopilotPanelProps = {
  context: string[];
  prompts: string[];
};

export function CopilotPanel({ context, prompts }: CopilotPanelProps) {
  return (
    <TenxSectionCard
      title="Research Copilot"
      description="工作台先行，对话补充。围绕当前候选、主题和观察池追问，不做开放域泛聊。"
      action={<div className="whitespace-nowrap"><StatusTag label="Copilot" tone="blue" /></div>}
    >
      <div className="space-y-4">
        <div>
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200">当前上下文</h4>
          <ul className="mt-2 space-y-2 text-sm text-gray-600 dark:text-gray-300">
            {context.map((item) => (
              <li key={item} className="rounded-xl bg-gray-50 px-3 py-2 dark:bg-gray-900/60">
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200">建议追问</h4>
          <div className="mt-2 flex flex-wrap gap-2">
            {prompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="rounded-full border border-gray-200 px-3 py-2 text-left text-sm text-gray-600 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </div>
    </TenxSectionCard>
  );
}
