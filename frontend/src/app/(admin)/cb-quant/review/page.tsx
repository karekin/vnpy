import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "CB Quant Review | TailAdmin",
  description: "反馈复盘行动页",
};

const weekly = [
  "本周收益归因：策略贡献、券种贡献、市场贡献。",
  "执行偏差归因：滑点、未成交、延迟、异常数据。",
  "风险归因：回撤来源、拥挤风险、强赎暴露。",
];

const monthly = [
  "更新策略分层池（核心池/观察池/淘汰池）。",
  "评估参数漂移并确认是否触发重搜。",
  "形成月度复盘报告并沉淀规则库。",
];

export default function CbQuantReviewPage() {
  return (
    <CbQuantPageShell
      title="反馈复盘行动页"
      subtitle="目标是持续识别收益来源和失效来源，为再优化提供高质量反馈信号。"
    >
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">周度复盘</h3>
          <ul className="mt-4 space-y-3">
            {weekly.map((item) => (
              <li key={item} className="rounded-lg border border-gray-200 p-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">月度复盘</h3>
          <ul className="mt-4 space-y-3">
            {monthly.map((item) => (
              <li key={item} className="rounded-lg border border-gray-200 p-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </CbQuantPageShell>
  );
}
