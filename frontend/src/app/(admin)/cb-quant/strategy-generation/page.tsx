import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "CB Quant Strategy Generation | TailAdmin",
  description: "策略生成行动页",
};

const modules = [
  "Filters：可交易、流动性、评级、强赎和到期过滤。",
  "Ranking：双低分、加权分、分位数分等排序器。",
  "Portfolio：TopK、权重模式、单券上限。",
  "Rebalance：日频/周频/阈值触发调仓。",
  "Risk：回撤阈值、换手约束、黑名单机制。",
];

const checklist = [
  "参数字段总数控制在 30 以内并分层分组。",
  "每个参数定义类型、范围、默认值、采样方式。",
  "生成配置模板后可自动产出 10 万候选策略。",
];

export default function CbQuantStrategyGenerationPage() {
  return (
    <CbQuantPageShell
      title="策略生成行动页"
      subtitle="目标是把策略从“文字规则”转成可组合、可搜索、可回测的参数化对象。"
    >
      <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">策略模块拆解</h3>
        <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-2">
          {modules.map((module) => (
            <div key={module} className="rounded-lg border border-gray-200 p-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">
              {module}
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">完成标准</h3>
        <ul className="mt-4 space-y-3">
          {checklist.map((item, idx) => (
            <li key={item} className="rounded-lg border border-gray-200 p-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">
              {idx + 1}. {item}
            </li>
          ))}
        </ul>
      </div>
    </CbQuantPageShell>
  );
}
