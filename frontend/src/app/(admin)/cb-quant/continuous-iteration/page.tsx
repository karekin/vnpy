import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "CB Quant Continuous Iteration | TailAdmin",
  description: "持续迭代行动页",
};

const triggerRules = [
  "近3个月持续跑输基准 -> 触发参数重搜。",
  "最大回撤超阈值 -> 降级执行并进入保护模式。",
  "成交偏差持续扩大 -> 回退到更稳健策略池。",
];

const loop = [
  "触发器命中",
  "滚动窗口重训练/重搜索",
  "生成候选策略集",
  "灰度观察",
  "入实盘池",
];

export default function CbQuantContinuousIterationPage() {
  return (
    <CbQuantPageShell
      title="持续迭代行动页"
      subtitle="目标是把策略升级流程制度化：可触发、可回退、可验证，而不是临时人工调参。"
    >
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">触发规则</h3>
          <ul className="mt-4 space-y-3">
            {triggerRules.map((item) => (
              <li key={item} className="rounded-lg border border-gray-200 p-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">迭代闭环</h3>
          <div className="mt-4 grid grid-cols-1 gap-3">
            {loop.map((item, idx) => (
              <div key={item} className="rounded-lg border border-gray-200 p-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">
                {idx + 1}. {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    </CbQuantPageShell>
  );
}
