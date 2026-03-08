"use client";

import {
  compareStrategyOptimizeTaskAiInsight,
  getStrategyOptimizeTaskAiInsight,
  getStrategyOptimizeTaskDetail,
  type StrategyOptimizeTaskAiCompare,
  type StrategyOptimizeTaskAiInsight,
  type StrategyOptimizeTaskDetail,
} from "@/components/cb-quant/api";
import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import { useRouter, useSearchParams } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useState } from "react";

type Props = {
  params: Promise<{ taskId: string }>;
};

function SectionCard({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950/40">
      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">{title}</div>
      <ul className="space-y-2 text-sm leading-6 text-gray-800 dark:text-gray-100">
        {(items.length ? items : ["暂无"]).map((item) => <li key={item}>• {item}</li>)}
      </ul>
    </div>
  );
}

export default function CbQuantAiInsightPage({ params }: Props) {
  const { taskId } = React.use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const comboId = searchParams.get("comboId") ?? "";
  const compareA = searchParams.get("comboA") ?? "";
  const compareB = searchParams.get("comboB") ?? "";
  const compareMode = Boolean(compareA && compareB);

  const [detail, setDetail] = useState<StrategyOptimizeTaskDetail | null>(null);
  const [singleInsight, setSingleInsight] = useState<StrategyOptimizeTaskAiInsight | null>(null);
  const [compareInsight, setCompareInsight] = useState<StrategyOptimizeTaskAiCompare | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");
  const [copyFeedback, setCopyFeedback] = useState<string>("");

  const targetComboId = useMemo(() => {
    if (compareMode) {
      return "";
    }
    return comboId || detail?.topStrategies[0]?.comboId || "";
  }, [comboId, compareMode, detail?.topStrategies]);

  const copyText = useCallback(async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopyFeedback(`${label}已复制`);
      window.setTimeout(() => setCopyFeedback(""), 2000);
    } catch (err) {
      setCopyFeedback(err instanceof Error ? err.message : `${label}复制失败`);
      window.setTimeout(() => setCopyFeedback(""), 2500);
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const taskDetail = await getStrategyOptimizeTaskDetail(taskId);
      setDetail(taskDetail);
      const initialCapitalWan = taskDetail.task.taskConfig.initialCapitalWan;
      if (compareMode) {
        const payload = await compareStrategyOptimizeTaskAiInsight(taskId, {
          comboIds: [compareA, compareB],
          initialCapitalWan,
        });
        setCompareInsight(payload);
        setSingleInsight(null);
      } else {
        const payload = await getStrategyOptimizeTaskAiInsight(taskId, {
          comboId: comboId || taskDetail.topStrategies[0]?.comboId,
          initialCapitalWan,
        });
        setSingleInsight(payload);
        setCompareInsight(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kimi 白盒页加载失败");
      setSingleInsight(null);
      setCompareInsight(null);
    } finally {
      setLoading(false);
    }
  }, [comboId, compareA, compareB, compareMode, taskId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <CbQuantPageShell
      title={compareMode ? "Kimi 横向优劣分析" : "Kimi 白盒解读"}
      subtitle={compareMode ? "对两个组合做白盒化横向对比。" : "对单个回测组合做白盒化结果解读。"}
    >
      <div className="space-y-6">
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
                {compareMode ? "AI 对比详情" : "AI 解读详情"}
              </h3>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                任务 {taskId}
                {detail ? ` · 模板 ${detail.task.templateName}` : ""}
                {compareMode ? ` · 对比 ${compareA} vs ${compareB}` : targetComboId ? ` · 组合 ${targetComboId}` : ""}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => router.push("/cb-quant/backtest-evaluation")}
                className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200"
              >
                返回回测页
              </button>
              <button
                type="button"
                onClick={() => void load()}
                className="rounded-lg border border-brand-500 px-3 py-2 text-xs font-medium text-brand-600 hover:bg-brand-50 dark:border-brand-400 dark:text-brand-300"
              >
                重新生成
              </button>
            </div>
          </div>
          {copyFeedback ? <p className="mt-3 text-xs text-green-600 dark:text-green-300">{copyFeedback}</p> : null}
          {loading ? <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">Kimi 分析加载中...</p> : null}
          {error ? (
            <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600 dark:border-red-900/50 dark:bg-red-500/10 dark:text-red-300">
              {error}
            </p>
          ) : null}
        </div>

        {!loading && !error && singleInsight ? (
          <div className="space-y-6">
            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{singleInsight.provider} · {singleInsight.model}{singleInsight.cached ? " · cache" : ""}</div>
                  <h3 className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">一句话结论</h3>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void copyText("Prompt", singleInsight.promptMarkdown)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200"
                  >
                    复制Prompt
                  </button>
                  <button
                    type="button"
                    onClick={() => void copyText("上下文", singleInsight.contextMarkdown)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200"
                  >
                    复制上下文
                  </button>
                </div>
              </div>
              {singleInsight.message ? (
                <p className="mt-3 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700 dark:border-blue-900/50 dark:bg-blue-500/10 dark:text-blue-300">
                  {singleInsight.message}
                </p>
              ) : null}
              <p className="mt-4 text-sm leading-7 text-gray-800 dark:text-gray-100">{singleInsight.executiveSummary || "模型尚未返回结构化结论。"}</p>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <SectionCard title="收益驱动" items={singleInsight.returnDrivers} />
              <SectionCard title="风险暴露" items={singleInsight.riskExposures} />
              <SectionCard title="参数解读" items={singleInsight.parameterInterpretation} />
              <SectionCard title="下一步验证建议" items={singleInsight.nextSteps} />
            </div>

            {singleInsight.analysisMarkdown ? (
              <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
                <div className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">模型原始输出</div>
                <div className="whitespace-pre-wrap text-sm leading-6 text-gray-800 dark:text-gray-100">{singleInsight.analysisMarkdown}</div>
              </div>
            ) : null}

            <details className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <summary className="cursor-pointer text-sm font-medium text-gray-800 dark:text-gray-100">查看白盒上下文</summary>
              <pre className="mt-4 whitespace-pre-wrap text-xs leading-6 text-gray-600 dark:text-gray-300">{singleInsight.contextMarkdown}</pre>
            </details>
            <details className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <summary className="cursor-pointer text-sm font-medium text-gray-800 dark:text-gray-100">查看提示词</summary>
              <pre className="mt-4 whitespace-pre-wrap text-xs leading-6 text-gray-600 dark:text-gray-300">{singleInsight.promptMarkdown}</pre>
            </details>
          </div>
        ) : null}

        {!loading && !error && compareInsight ? (
          <div className="space-y-6">
            <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{compareInsight.provider} · {compareInsight.model}{compareInsight.cached ? " · cache" : ""}</div>
                  <h3 className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">对比结论</h3>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void copyText("对比Prompt", compareInsight.promptMarkdown)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200"
                  >
                    复制Prompt
                  </button>
                  <button
                    type="button"
                    onClick={() => void copyText("对比上下文", compareInsight.contextMarkdown)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200"
                  >
                    复制上下文
                  </button>
                </div>
              </div>
              {compareInsight.message ? (
                <p className="mt-3 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700 dark:border-blue-900/50 dark:bg-blue-500/10 dark:text-blue-300">
                  {compareInsight.message}
                </p>
              ) : null}
              <p className="mt-4 text-sm leading-7 text-gray-800 dark:text-gray-100">{compareInsight.executiveSummary || "模型尚未返回结构化结论。"}</p>
              {compareInsight.winnerComboId ? (
                <p className="mt-4 inline-flex rounded-full border border-green-300 bg-green-50 px-3 py-1 text-xs font-medium text-green-700 dark:border-green-900/50 dark:bg-green-500/10 dark:text-green-300">
                  当前更优：{compareInsight.winnerComboId}
                </p>
              ) : null}
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
              <SectionCard title="胜出原因" items={compareInsight.winnerReason} />
              <SectionCard title="下一步验证" items={compareInsight.whatToVerifyNext} />
              <SectionCard title={`组合A(${compareInsight.comboIds[0] ?? "-"})优势`} items={compareInsight.comboAStrengths} />
              <SectionCard title={`组合A(${compareInsight.comboIds[0] ?? "-"})风险`} items={compareInsight.comboARisks} />
              <SectionCard title={`组合B(${compareInsight.comboIds[1] ?? "-"})优势`} items={compareInsight.comboBStrengths} />
              <SectionCard title={`组合B(${compareInsight.comboIds[1] ?? "-"})风险`} items={compareInsight.comboBRisks} />
            </div>

            {compareInsight.analysisMarkdown ? (
              <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
                <div className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">模型原始输出</div>
                <div className="whitespace-pre-wrap text-sm leading-6 text-gray-800 dark:text-gray-100">{compareInsight.analysisMarkdown}</div>
              </div>
            ) : null}

            <details className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <summary className="cursor-pointer text-sm font-medium text-gray-800 dark:text-gray-100">查看对比上下文</summary>
              <pre className="mt-4 whitespace-pre-wrap text-xs leading-6 text-gray-600 dark:text-gray-300">{compareInsight.contextMarkdown}</pre>
            </details>
            <details className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <summary className="cursor-pointer text-sm font-medium text-gray-800 dark:text-gray-100">查看提示词</summary>
              <pre className="mt-4 whitespace-pre-wrap text-xs leading-6 text-gray-600 dark:text-gray-300">{compareInsight.promptMarkdown}</pre>
            </details>
          </div>
        ) : null}
      </div>
    </CbQuantPageShell>
  );
}
