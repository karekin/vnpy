import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "CB Quant Overview | TailAdmin",
  description: "可转债量化策略闭环总览页面",
};

const targets = [
  { label: "长期收益目标", value: "年化约 30%", desc: "在控制回撤与交易成本前提下达成。" },
  { label: "近期鲁棒目标", value: "近3年/近1年持续有效", desc: "不依赖单一历史行情窗口。" },
  { label: "自动化目标", value: "少人工决策", desc: "日常自动筛选，人工仅确认执行。" },
];

const loopStages = [
  { id: 1, title: "信息挖掘", desc: "从公开调仓记录、社区经验与历史回测提取可参数化规则。" },
  { id: 2, title: "策略生成", desc: "用 Filters + Ranking + Portfolio + Rebalance + Risk 统一表达策略。" },
  { id: 3, title: "回测评估", desc: "批量搜索策略并在全周期与近窗口同时打分和筛选。" },
  { id: 4, title: "自动执行", desc: "先半自动推荐，后接交易接口逐步升级到全自动。" },
  { id: 5, title: "反馈复盘", desc: "归因收益与回撤来源，检测策略失效并触发再优化。" },
  { id: 6, title: "持续迭代", desc: "保留参数稳健区间，滚动更新，避免单点过拟合。" },
];

const architecture = [
  { stage: "A 信息挖掘", output: "策略要素字典 + 初始策略族" },
  { stage: "B 数据接入", output: "可复现版本化快照" },
  { stage: "C 策略生成", output: "<=30 参数配置化策略" },
  { stage: "D 回测搜索", output: "多窗口评分与稳健区间" },
  { stage: "E 决策层", output: "可解释推荐清单" },
  { stage: "F 执行层", output: "成交回写与偏差记录" },
  { stage: "G 反馈层", output: "失效触发 + 再训练" },
];

const milestones = [
  { id: "M1", title: "数据管道 + 基准回测", span: "1-2周" },
  { id: "M2", title: "参数化 + 10万策略搜索", span: "2-4周" },
  { id: "M3", title: "反推公开组合规则", span: "2-6周" },
  { id: "M4", title: "自动推荐 + 线上监控", span: "持续迭代" },
];

const robustness = [
  "多窗口硬约束：全周期、近3年、近1年同时达标。",
  "稳健区间优先：选择参数平台而非单点最优。",
  "状态切换：按溢价率中枢和波动率动态调整权重。",
];

const stack = [
  "数据：AKShare / TuShare / 自建落库",
  "回测：Backtrader / Qlib",
  "执行：半自动清单优先，逐步升级自动交易",
];

export default function CbQuantOverviewPage() {
  return (
    <CbQuantPageShell
      title="CB Quant 总览"
      subtitle="总览页聚合所有核心信息：目标、闭环阶段、架构、里程碑、稳健性与工具栈。6个行动页只保留可执行任务。"
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {targets.map((target) => (
          <div
            key={target.label}
            className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
          >
            <p className="text-sm text-gray-500 dark:text-gray-400">{target.label}</p>
            <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{target.value}</p>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{target.desc}</p>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">策略闭环阶段</h3>
        <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-3">
          {loopStages.map((stage) => (
            <div key={stage.title} className="rounded-2xl border border-gray-200 p-6 dark:border-gray-700">
              <div className="flex items-center gap-4">
                <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-brand-100 text-2xl font-semibold text-brand-600 dark:bg-brand-500/20 dark:text-brand-300">
                  {stage.id}
                </span>
                <h4 className="text-2xl font-semibold text-gray-900 dark:text-white">{stage.title}</h4>
              </div>
              <p className="mt-4 text-sm leading-8 text-gray-600 dark:text-gray-300">{stage.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">全流程架构输出</h3>
          <ul className="mt-4 space-y-3 text-sm text-gray-700 dark:text-gray-200">
            {architecture.map((item) => (
              <li key={item.stage} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                <p className="font-semibold text-gray-900 dark:text-white">{item.stage}</p>
                <p className="mt-1 text-gray-600 dark:text-gray-300">{item.output}</p>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-5">
          <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">里程碑计划</h3>
            <div className="mt-4 space-y-3 text-sm text-gray-700 dark:text-gray-200">
              {milestones.map((item) => (
                <div key={item.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                  <p className="font-semibold text-gray-900 dark:text-white">{item.id} · {item.title}</p>
                  <p className="mt-1 text-gray-600 dark:text-gray-300">周期：{item.span}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">稳健性机制</h3>
            <ul className="mt-4 space-y-3 text-sm text-gray-700 dark:text-gray-200">
              {robustness.map((item) => (
                <li key={item} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">工具栈建议</h3>
            <ul className="mt-4 space-y-3 text-sm text-gray-700 dark:text-gray-200">
              {stack.map((item) => (
                <li key={item} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </CbQuantPageShell>
  );
}
