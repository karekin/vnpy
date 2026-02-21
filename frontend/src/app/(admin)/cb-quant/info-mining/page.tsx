import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "CB Quant Info Mining | TailAdmin",
  description: "信息挖掘行动页",
};

const tasks = [
  "收集公开调仓记录并结构化为日期、买卖列表、仓位变化。",
  "同步社区策略样本，提取可参数化规则关键词。",
  "建立策略要素字典（过滤器、排序、风控、调仓频率）。",
  "输出候选规则库用于策略生成阶段。",
];

const io = [
  { k: "输入", v: "公开组合调仓记录、文章/论坛策略样本、历史回测快照" },
  { k: "输出", v: "rules_dictionary.json、teacher_actions.csv、initial_strategy_family.yaml" },
  { k: "验收", v: "至少覆盖双低、低溢价、强赎过滤、流动性过滤四类规则" },
];

export default function CbQuantInfoMiningPage() {
  return (
    <CbQuantPageShell
      title="信息挖掘行动页"
      subtitle="目标是把“经验和案例”转成机器可读规则，作为后续参数搜索的输入。"
    >
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">执行清单</h3>
          <ul className="mt-4 space-y-3">
            {tasks.map((task, idx) => (
              <li key={task} className="rounded-lg border border-gray-200 p-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">
                {idx + 1}. {task}
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">输入输出定义</h3>
          <div className="mt-4 space-y-3">
            {io.map((item) => (
              <div key={item.k} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                <p className="text-sm font-semibold text-gray-900 dark:text-white">{item.k}</p>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{item.v}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </CbQuantPageShell>
  );
}
