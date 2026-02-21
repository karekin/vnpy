import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "CB Quant Auto Execution | TailAdmin",
  description: "自动执行行动页",
};

const steps = [
  "每天开盘前生成推荐清单与目标仓位。",
  "半自动模式下人工确认后下单并记录成交差异。",
  "逐步接入交易接口，增加幂等、断线重试、风控熔断。",
  "记录订单生命周期并回写到复盘系统。",
];

const safeguards = [
  "单券最大仓位限制",
  "单日换手上限",
  "组合最大回撤熔断",
  "数据缺失自动暂停执行",
];

export default function CbQuantAutoExecutionPage() {
  return (
    <CbQuantPageShell
      title="自动执行行动页"
      subtitle="目标是把策略输出稳定转成执行结果，降低滑点、漏单和异常行情冲击。"
    >
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">执行步骤</h3>
          <ul className="mt-4 space-y-3">
            {steps.map((item, idx) => (
              <li key={item} className="rounded-lg border border-gray-200 p-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">
                {idx + 1}. {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">执行风控</h3>
          <ul className="mt-4 space-y-3">
            {safeguards.map((item) => (
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
