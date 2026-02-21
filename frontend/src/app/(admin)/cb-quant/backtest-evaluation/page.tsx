import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "CB Quant Backtest Evaluation | TailAdmin",
  description: "回测评估行动页",
};

const windows = ["全周期(2018-2025)", "近3年", "近1年", "牛熊震荡分阶段"];
const metrics = ["CAGR", "MDD", "Calmar", "换手率", "成本敏感性", "胜率"];
const process = [
  "批量生成候选策略并并行回测。",
  "对每个窗口计算指标并做硬约束筛选。",
  "淘汰近期失效策略，保留稳健参数区间。",
  "输出可解释排行榜和入池名单。",
];

export default function CbQuantBacktestEvaluationPage() {
  return (
    <CbQuantPageShell
      title="回测评估行动页"
      subtitle="目标是从大规模候选策略中筛出“长期有效且近期不掉队”的稳健策略集。"
    >
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">回测窗口</h3>
          <ul className="mt-4 space-y-2 text-sm text-gray-700 dark:text-gray-200">
            {windows.map((item) => (
              <li key={item} className="rounded-lg border border-gray-200 p-2 dark:border-gray-700">{item}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">核心指标</h3>
          <ul className="mt-4 space-y-2 text-sm text-gray-700 dark:text-gray-200">
            {metrics.map((item) => (
              <li key={item} className="rounded-lg border border-gray-200 p-2 dark:border-gray-700">{item}</li>
            ))}
          </ul>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">执行流程</h3>
          <ul className="mt-4 space-y-2 text-sm text-gray-700 dark:text-gray-200">
            {process.map((item, idx) => (
              <li key={item} className="rounded-lg border border-gray-200 p-2 dark:border-gray-700">{idx + 1}. {item}</li>
            ))}
          </ul>
        </div>
      </div>
    </CbQuantPageShell>
  );
}
