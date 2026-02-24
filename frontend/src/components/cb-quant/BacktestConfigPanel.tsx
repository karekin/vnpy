"use client";

import type { CandidateRow } from "@/components/cb-quant/api";
import React, { useEffect, useMemo, useState } from "react";

export type EvalWindow = "full" | "3y" | "1y";
export type RuleSourceMode = "inherit" | "candidate" | "custom";

export type BacktestQueuePayload = {
  comboId: string;
  template: string;
  rulePackId: string;
  sourceMode: RuleSourceMode;
  windows: EvalWindow[];
  estStrategies: number;
  startDate: string;
  endDate: string;
  capitalWan: number;
  feePermille: number;
  benchmark: string;
};

type BacktestConfigPanelProps = {
  candidates: CandidateRow[];
  onQueueBacktest: (payload: BacktestQueuePayload) => Promise<string>;
};

type RuleTab = "base" | "intraday" | "postclose" | "bucket";

type RuleSnapshot = {
  base: Array<{ label: string; value: string }>;
  intraday: Array<{ label: string; value: string }>;
  postclose: Array<{ label: string; value: string }>;
  bucket: Array<{ label: string; value: string }>;
};

const ruleTabs: Array<{ key: RuleTab; label: string }> = [
  { key: "base", label: "基础规则" },
  { key: "intraday", label: "盘中过滤" },
  { key: "postclose", label: "盘后过滤" },
  { key: "bucket", label: "分箱" },
];

const sourceModes: Array<{ key: RuleSourceMode; label: string; desc: string }> = [
  { key: "inherit", label: "继承模板默认", desc: "直接使用模板默认规则" },
  { key: "candidate", label: "从候选带入", desc: "带入候选组合的规则快照" },
  { key: "custom", label: "新建规则包", desc: "基于候选复制后生成新规则包" },
];

const windowLabels: Record<EvalWindow, string> = {
  full: "2018-2025",
  "3y": "近3年",
  "1y": "近1年",
};

const inputClassName =
  "h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90";

const snapshotByTemplate: Record<string, RuleSnapshot> = {
  双低稳健A: {
    base: [
      { label: "换仓频率类型", value: "按交易日" },
      { label: "换仓频率", value: "2" },
      { label: "持有权重", value: "等金额" },
      { label: "单标的最大仓位", value: "20%" },
      { label: "持有数量范围", value: "5 ~ 12" },
    ],
    intraday: [
      { label: "最小成交额", value: "5000 万" },
      { label: "最小成交量", value: "3000 手" },
      { label: "盘中动作", value: "开盘后5分钟仅观察" },
      { label: "换仓时间", value: "每日收盘买卖" },
    ],
    postclose: [
      { label: "排除赎回状态", value: "已满足强赎条件 +4 天" },
      { label: "排除新债", value: "上市 20 天内排除" },
      { label: "排除 ST", value: "开启" },
      { label: "排除评级", value: "不排除" },
    ],
    bucket: [
      { label: "分箱因子", value: "双低值" },
      { label: "分箱数量", value: "5" },
      { label: "分箱焦点", value: "全部分箱" },
    ],
  },
  "双低+评级": {
    base: [
      { label: "换仓频率类型", value: "按交易日" },
      { label: "换仓频率", value: "1" },
      { label: "持有权重", value: "评分反比" },
      { label: "单标的最大仓位", value: "18%" },
      { label: "持有数量范围", value: "8 ~ 15" },
    ],
    intraday: [
      { label: "最小成交额", value: "6000 万" },
      { label: "最小成交量", value: "4000 手" },
      { label: "盘中动作", value: "仅盘后调仓" },
      { label: "换仓时间", value: "14:50-15:00 批量执行" },
    ],
    postclose: [
      { label: "排除赎回状态", value: "公告强赎即排除" },
      { label: "排除新债", value: "上市 30 天内排除" },
      { label: "排除 ST", value: "开启" },
      { label: "排除评级", value: "AA-及以下" },
    ],
    bucket: [
      { label: "分箱因子", value: "转股溢价率" },
      { label: "分箱数量", value: "10" },
      { label: "分箱焦点", value: "头部分箱" },
    ],
  },
};

const defaultSnapshot: RuleSnapshot = {
  base: [
    { label: "换仓频率类型", value: "按交易日" },
    { label: "换仓频率", value: "2" },
    { label: "持有权重", value: "等金额" },
    { label: "单标的最大仓位", value: "20%" },
    { label: "持有数量范围", value: "5 ~ 12" },
  ],
  intraday: [
    { label: "最小成交额", value: "5000 万" },
    { label: "最小成交量", value: "3000 手" },
    { label: "盘中动作", value: "开盘后5分钟仅观察" },
    { label: "换仓时间", value: "每日收盘买卖" },
  ],
  postclose: [
    { label: "排除赎回状态", value: "已满足强赎条件 +4 天" },
    { label: "排除新债", value: "上市 20 天内排除" },
    { label: "排除 ST", value: "开启" },
    { label: "排除评级", value: "不排除" },
  ],
  bucket: [
    { label: "分箱因子", value: "双低值" },
    { label: "分箱数量", value: "5" },
    { label: "分箱焦点", value: "全部分箱" },
  ],
};

function getSourceModeShort(mode: RuleSourceMode): string {
  if (mode === "inherit") return "INH";
  if (mode === "candidate") return "CAN";
  return "CUS";
}

function toDateInputValue(value: Date): string {
  return value.toISOString().slice(0, 10);
}

export default function BacktestConfigPanel({ candidates, onQueueBacktest }: BacktestConfigPanelProps) {
  const [activeRuleTab, setActiveRuleTab] = useState<RuleTab>("base");
  const [sourceMode, setSourceMode] = useState<RuleSourceMode>("candidate");
  const [selectedComboId, setSelectedComboId] = useState<string>(candidates[0]?.comboId ?? "");

  const [startDate, setStartDate] = useState<string>(() => {
    const now = new Date();
    const prev = new Date(now.getTime());
    prev.setFullYear(prev.getFullYear() - 1);
    return toDateInputValue(prev);
  });
  const [endDate, setEndDate] = useState<string>(() => toDateInputValue(new Date()));
  const [capitalWan, setCapitalWan] = useState<number>(100);
  const [feePermille, setFeePermille] = useState<number>(1);
  const [slippageBp, setSlippageBp] = useState<number>(8);
  const [benchmark, setBenchmark] = useState<string>("沪深300");
  const [workers, setWorkers] = useState<number>(4);

  const [selectedWindows, setSelectedWindows] = useState<EvalWindow[]>(["full", "3y", "1y"]);
  const [queueHint, setQueueHint] = useState<string>("");
  const [queueing, setQueueing] = useState<boolean>(false);

  const selectedCandidate = useMemo(() => {
    if (!candidates.length) {
      return undefined;
    }
    return candidates.find((item) => item.comboId === selectedComboId) ?? candidates[0];
  }, [candidates, selectedComboId]);

  useEffect(() => {
    if (!selectedCandidate && candidates.length) {
      setSelectedComboId(candidates[0].comboId);
    }
  }, [selectedCandidate, candidates]);

  const selectedSnapshot = useMemo(() => {
    if (!selectedCandidate) return defaultSnapshot;
    return snapshotByTemplate[selectedCandidate.template] ?? defaultSnapshot;
  }, [selectedCandidate]);

  const rulePackId = useMemo(() => {
    if (!selectedCandidate) return "RP-NA-000000";
    const comboDigits = selectedCandidate.comboId.replace(/\D/g, "").slice(0, 6) || "000000";
    return `RP-${getSourceModeShort(sourceMode)}-${comboDigits.padEnd(6, "0")}`;
  }, [selectedCandidate, sourceMode]);

  const estimatedStrategies = useMemo(() => {
    const base = selectedCandidate?.estCombos ?? 0;
    const sourceScale = sourceMode === "inherit" ? 1 : sourceMode === "candidate" ? 0.92 : 1.06;
    const perWindow = Math.max(200, Math.round(base * sourceScale));
    return perWindow * selectedWindows.length;
  }, [selectedCandidate, sourceMode, selectedWindows.length]);

  const strictnessLabel = useMemo(() => {
    if (estimatedStrategies < 50000) return "高约束";
    if (estimatedStrategies < 120000) return "中等约束";
    return "低约束";
  }, [estimatedStrategies]);

  const toggleWindow = (windowName: EvalWindow): void => {
    setSelectedWindows((prev) => {
      if (prev.includes(windowName)) {
        if (prev.length === 1) return prev;
        return prev.filter((item) => item !== windowName);
      }
      return [...prev, windowName];
    });
  };

  const handleQueue = async (): Promise<void> => {
    if (!selectedCandidate || selectedWindows.length === 0 || queueing) {
      return;
    }

    setQueueing(true);
    try {
      const message = await onQueueBacktest({
        comboId: selectedCandidate.comboId,
        template: selectedCandidate.template,
        rulePackId,
        sourceMode,
        windows: selectedWindows,
        estStrategies: estimatedStrategies,
        startDate,
        endDate,
        capitalWan,
        feePermille,
        benchmark,
      });
      setQueueHint(message);
    } catch {
      setQueueHint("回测任务入队失败，请重试。");
    } finally {
      setQueueing(false);
    }
  };

  const currentTabRows = selectedSnapshot[activeRuleTab];

  if (!candidates.length) {
    return (
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">回测配置中心</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">请先在策略生成页产出候选组合，再在此处入队回测。</p>
        </div>
        <div className="p-5">
          <a
            href="/cb-quant/strategy-generation"
            className="inline-flex h-10 items-center justify-center rounded-lg border border-brand-500 px-4 text-sm font-medium text-brand-500 hover:bg-brand-50 dark:border-brand-400 dark:text-brand-300 dark:hover:bg-brand-500/10"
          >
            去策略生成维护规则
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex flex-col gap-3 border-b border-gray-200 px-5 py-4 dark:border-gray-800 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">回测配置中心</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            这里只配置回测实验参数；策略规则来自“策略生成行动页”的参数空间和候选组合。
          </p>
        </div>
        <a
          href="/cb-quant/strategy-generation"
          className="inline-flex h-10 items-center justify-center rounded-lg border border-brand-500 px-4 text-sm font-medium text-brand-500 hover:bg-brand-50 dark:border-brand-400 dark:text-brand-300 dark:hover:bg-brand-500/10"
        >
          去策略生成维护规则
        </a>
      </div>

      <div className="grid gap-5 p-5 xl:grid-cols-12">
        <div className="space-y-5 xl:col-span-8">
          <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
            <h4 className="mb-4 text-base font-semibold text-gray-800 dark:text-white/90">回测对象与规则来源</h4>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">回测对象（Combo）</label>
                <select
                  value={selectedCandidate?.comboId ?? ""}
                  onChange={(event) => setSelectedComboId(event.target.value)}
                  className={inputClassName}
                >
                  {candidates.map((candidate) => (
                    <option key={`${candidate.comboId}-${candidate.window}`} value={candidate.comboId}>
                      {candidate.comboId} · {candidate.template}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">规则来源</label>
                <div className="inline-flex h-11 w-full items-center gap-0.5 rounded-lg bg-gray-100 p-0.5 dark:bg-gray-900">
                  {sourceModes.map((mode) => (
                    <button
                      key={mode.key}
                      type="button"
                      onClick={() => setSourceMode(mode.key)}
                      className={`text-theme-sm h-10 flex-1 whitespace-nowrap rounded-md px-2 py-2 font-medium ${
                        sourceMode === mode.key
                          ? "shadow-theme-xs bg-white text-gray-900 dark:bg-gray-800 dark:text-white"
                          : "text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
                      }`}
                    >
                      {mode.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <p className="mt-3 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700 dark:border-blue-900/50 dark:bg-blue-500/10 dark:text-blue-300">
              {sourceModes.find((mode) => mode.key === sourceMode)?.desc}
              。规则编辑入口在“策略生成行动页”，此处仅做回显，不重复维护。
            </p>
          </div>

          <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
            <div className="border-b border-gray-200 px-4 py-2 dark:border-gray-800">
              <h4 className="mb-2 text-base font-semibold text-gray-800 dark:text-white/90">规则快照（只读）</h4>
              <nav className="flex overflow-x-auto rounded-lg bg-gray-100 p-0.5 dark:bg-gray-900">
                {ruleTabs.map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveRuleTab(tab.key)}
                    className={`text-theme-sm h-10 shrink-0 whitespace-nowrap rounded-md px-4 py-2 font-medium ${
                      activeRuleTab === tab.key
                        ? "shadow-theme-xs bg-white text-gray-900 dark:bg-gray-800 dark:text-white"
                        : "text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </nav>
            </div>
            <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
              {currentTabRows.map((row) => (
                <div key={`${activeRuleTab}-${row.label}`} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-800 dark:bg-gray-900/30">
                  <p className="text-xs text-gray-500 dark:text-gray-400">{row.label}</p>
                  <p className="mt-1 text-sm font-medium text-gray-900 dark:text-white">{row.value}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
            <h4 className="mb-4 text-base font-semibold text-gray-800 dark:text-white/90">实验参数（可编辑）</h4>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">回测开始日期</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(event) => setStartDate(event.target.value)}
                  className={inputClassName}
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">回测结束日期</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(event) => setEndDate(event.target.value)}
                  className={inputClassName}
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">初始资金(万)</label>
                <input
                  type="number"
                  min={1}
                  value={capitalWan}
                  onChange={(event) => setCapitalWan(Number(event.target.value))}
                  className={inputClassName}
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">手续费(单边, ‰)</label>
                <input
                  type="number"
                  min={0}
                  step="0.1"
                  value={feePermille}
                  onChange={(event) => setFeePermille(Number(event.target.value))}
                  className={inputClassName}
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">滑点(bp)</label>
                <input
                  type="number"
                  min={0}
                  value={slippageBp}
                  onChange={(event) => setSlippageBp(Number(event.target.value))}
                  className={inputClassName}
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">基准指标</label>
                <select
                  value={benchmark}
                  onChange={(event) => setBenchmark(event.target.value)}
                  className={inputClassName}
                >
                  <option value="沪深300">沪深300</option>
                  <option value="中证转债">中证转债</option>
                  <option value="可转债等权">可转债等权</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <div className="xl:col-span-4">
          <div className="sticky top-4 rounded-xl border border-gray-200 p-4 dark:border-gray-800">
            <h4 className="text-base font-semibold text-gray-800 dark:text-white/90">运行面板</h4>
            <div className="mt-4 space-y-3">
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/30">
                <p className="text-xs text-gray-500 dark:text-gray-400">回测对象</p>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">{selectedCandidate?.comboId ?? "--"}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{selectedCandidate?.template ?? "--"}</p>
              </div>
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/30">
                <p className="text-xs text-gray-500 dark:text-gray-400">规则包</p>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">{rulePackId}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">来源：{sourceModes.find((mode) => mode.key === sourceMode)?.label}</p>
              </div>
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/30">
                <p className="text-xs text-gray-500 dark:text-gray-400">预计策略规模</p>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">{estimatedStrategies.toLocaleString()}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">约束强度：{strictnessLabel}</p>
              </div>

              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">运行窗口</label>
                <div className="grid grid-cols-3 gap-2">
                  {(Object.keys(windowLabels) as EvalWindow[]).map((windowName) => {
                    const checked = selectedWindows.includes(windowName);
                    return (
                      <button
                        key={windowName}
                        type="button"
                        onClick={() => toggleWindow(windowName)}
                        className={`rounded-lg border px-2 py-2 text-xs font-medium ${
                          checked
                            ? "border-brand-500 bg-brand-50 text-brand-600 dark:border-brand-400 dark:bg-brand-500/10 dark:text-brand-300"
                            : "border-gray-300 text-gray-600 hover:border-gray-400 dark:border-gray-700 dark:text-gray-300"
                        }`}
                      >
                        {windowLabels[windowName]}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">并发 Worker</label>
                <input
                  type="number"
                  min={1}
                  max={32}
                  value={workers}
                  onChange={(event) => setWorkers(Number(event.target.value))}
                  className={inputClassName}
                />
              </div>

              <button
                type="button"
                onClick={() => void handleQueue()}
                disabled={selectedWindows.length === 0 || queueing || !selectedCandidate}
                className="bg-brand-500 hover:bg-brand-600 disabled:bg-brand-300 mt-2 h-11 w-full rounded-lg text-sm font-medium text-white disabled:cursor-not-allowed"
              >
                {queueing ? "入队中..." : "加入任务队列"}
              </button>

              {queueHint && (
                <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-700 dark:border-green-800 dark:bg-green-500/10 dark:text-green-300">
                  {queueHint}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
