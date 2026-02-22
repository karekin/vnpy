"use client";

import type { StrategyCandidateRow } from "@/components/cb-quant/mockData";
import React, { useMemo, useState } from "react";

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
  candidates: StrategyCandidateRow[];
  onQueueBacktest: (payload: BacktestQueuePayload) => void;
};

type ConfigTab = "strategy" | "intraday" | "postclose" | "bucket";

const configTabs: Array<{ key: ConfigTab; label: string }> = [
  { key: "strategy", label: "策略回测" },
  { key: "intraday", label: "盘中选债" },
  { key: "postclose", label: "盘后选债" },
  { key: "bucket", label: "分箱" },
];

const sourceModes: Array<{ key: RuleSourceMode; label: string }> = [
  { key: "inherit", label: "继承模板默认" },
  { key: "candidate", label: "从候选带入" },
  { key: "custom", label: "新建规则包" },
];

const windowLabels: Record<EvalWindow, string> = {
  full: "2018-2025",
  "3y": "近3年",
  "1y": "近1年",
};

const inputClassName =
  "h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90";

function getSourceModeShort(mode: RuleSourceMode): string {
  if (mode === "inherit") return "INH";
  if (mode === "candidate") return "CAN";
  return "CUS";
}

export default function BacktestConfigPanel({
  candidates,
  onQueueBacktest,
}: BacktestConfigPanelProps) {
  const [activeTab, setActiveTab] = useState<ConfigTab>("strategy");
  const [sourceMode, setSourceMode] = useState<RuleSourceMode>("candidate");
  const [selectedComboId, setSelectedComboId] = useState<string>(
    candidates[0]?.comboId ?? ""
  );

  const [startDate, setStartDate] = useState<string>("2025-02-13");
  const [endDate, setEndDate] = useState<string>("2026-02-13");
  const [capitalWan, setCapitalWan] = useState<number>(100);
  const [feePermille, setFeePermille] = useState<number>(1);
  const [slippageBp, setSlippageBp] = useState<number>(8);
  const [benchmark, setBenchmark] = useState<string>("沪深300");

  const [rebalanceType, setRebalanceType] = useState<string>("按交易日");
  const [rebalanceFreq, setRebalanceFreq] = useState<number>(2);
  const [weightMode, setWeightMode] = useState<string>("等金额");
  const [maxSingleWeight, setMaxSingleWeight] = useState<number>(20);
  const [holdMin, setHoldMin] = useState<number>(5);
  const [holdMax, setHoldMax] = useState<number>(12);

  const [minTurnoverWan, setMinTurnoverWan] = useState<number>(5000);
  const [minVolumeLot, setMinVolumeLot] = useState<number>(3000);
  const [intradayAction, setIntradayAction] = useState<string>("开盘后5分钟仅观察");
  const [dealTiming, setDealTiming] = useState<string>("收盘买卖");

  const [excludeSt, setExcludeSt] = useState<boolean>(true);
  const [excludeNewBondDays, setExcludeNewBondDays] = useState<number>(20);
  const [forceRedeemGuard, setForceRedeemGuard] = useState<string>("已满足强赎条件+4天");
  const [excludeMarket, setExcludeMarket] = useState<string>("不排除");
  const [excludeIndustry, setExcludeIndustry] = useState<string>("不排除");
  const [excludeRating, setExcludeRating] = useState<string>("不排除");

  const [bucketFactor, setBucketFactor] = useState<string>("双低值");
  const [bucketCount, setBucketCount] = useState<number>(5);
  const [bucketFocus, setBucketFocus] = useState<string>("全部分箱");

  const [workers, setWorkers] = useState<number>(4);
  const [selectedWindows, setSelectedWindows] = useState<EvalWindow[]>([
    "full",
    "3y",
    "1y",
  ]);
  const [queueHint, setQueueHint] = useState<string>("");

  const selectedCandidate = useMemo(() => {
    return candidates.find((item) => item.comboId === selectedComboId) ?? candidates[0];
  }, [candidates, selectedComboId]);

  const rulePackId = useMemo(() => {
    const digest = [
      rebalanceFreq,
      holdMin,
      holdMax,
      maxSingleWeight,
      excludeSt ? 1 : 0,
      excludeNewBondDays,
      Math.round(minTurnoverWan / 1000),
      bucketCount,
      workers,
    ]
      .join("")
      .slice(0, 6)
      .padEnd(6, "0");

    return `RP-${getSourceModeShort(sourceMode)}-${digest}`;
  }, [
    rebalanceFreq,
    holdMin,
    holdMax,
    maxSingleWeight,
    excludeSt,
    excludeNewBondDays,
    minTurnoverWan,
    bucketCount,
    workers,
    sourceMode,
  ]);

  const estimatedStrategies = useMemo(() => {
    const base = selectedCandidate?.estCombos ?? 0;

    let scale = 1;
    if (excludeSt) scale *= 0.95;
    if (excludeNewBondDays >= 20) scale *= 0.9;
    if (minTurnoverWan >= 10000) scale *= 0.82;
    else if (minTurnoverWan >= 5000) scale *= 0.9;
    if (holdMax <= 10) scale *= 0.86;
    if (sourceMode === "custom") scale *= 1.15;
    if (bucketFocus === "头部分箱") scale *= 0.72;

    const perWindow = Math.max(200, Math.round(base * scale));
    return perWindow * selectedWindows.length;
  }, [
    selectedCandidate,
    excludeSt,
    excludeNewBondDays,
    minTurnoverWan,
    holdMax,
    sourceMode,
    bucketFocus,
    selectedWindows.length,
  ]);

  const strictnessLabel = useMemo(() => {
    if (estimatedStrategies < 50000) return "高约束";
    if (estimatedStrategies < 120000) return "中等约束";
    return "低约束";
  }, [estimatedStrategies]);

  const toggleWindow = (windowName: EvalWindow): void => {
    setSelectedWindows((prev) => {
      if (prev.includes(windowName)) {
        if (prev.length === 1) {
          return prev;
        }
        return prev.filter((item) => item !== windowName);
      }
      return [...prev, windowName];
    });
  };

  const handleQueue = (): void => {
    if (!selectedCandidate || selectedWindows.length === 0) {
      return;
    }

    onQueueBacktest({
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

    setQueueHint(
      `已入队 ${selectedWindows.length} 个窗口任务（每个窗口 1 条）：${selectedCandidate.comboId} × ${rulePackId}`
    );
  };

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex flex-col gap-3 border-b border-gray-200 px-5 py-4 dark:border-gray-800 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">回测配置中心</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            打分因子来自策略模板；非打分规则在此配置为规则包（rulePack）并与 combo 组合后入队回测。
          </p>
        </div>
        <div className="inline-flex h-11 items-center gap-0.5 rounded-lg bg-gray-100 p-0.5 dark:bg-gray-900">
          {sourceModes.map((mode) => (
            <button
              key={mode.key}
              type="button"
              onClick={() => setSourceMode(mode.key)}
              className={`text-theme-sm h-10 whitespace-nowrap rounded-md px-3 py-2 font-medium ${
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

      <div className="grid gap-5 p-5 xl:grid-cols-12">
        <div className="space-y-5 xl:col-span-8">
          <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
            <h4 className="mb-4 text-base font-semibold text-gray-800 dark:text-white/90">基础设置</h4>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">回测对象（Combo）</label>
                <select
                  value={selectedComboId}
                  onChange={(event) => setSelectedComboId(event.target.value)}
                  className={inputClassName}
                >
                  {candidates.map((candidate) => (
                    <option key={candidate.comboId} value={candidate.comboId}>
                      {candidate.comboId} · {candidate.template}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">换仓频率类型</label>
                <select
                  value={rebalanceType}
                  onChange={(event) => setRebalanceType(event.target.value)}
                  className={inputClassName}
                >
                  <option value="按交易日">按交易日</option>
                  <option value="按自然周">按自然周</option>
                </select>
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">换仓频率</label>
                <input
                  type="number"
                  min={1}
                  value={rebalanceFreq}
                  onChange={(event) => setRebalanceFreq(Number(event.target.value))}
                  className={inputClassName}
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">持有权重</label>
                <select
                  value={weightMode}
                  onChange={(event) => setWeightMode(event.target.value)}
                  className={inputClassName}
                >
                  <option value="等金额">等金额</option>
                  <option value="等权重">等权重</option>
                  <option value="评分反比">评分反比</option>
                </select>
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">单标的最大仓位(%)</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={maxSingleWeight}
                  onChange={(event) => setMaxSingleWeight(Number(event.target.value))}
                  className={inputClassName}
                />
              </div>
              <div>
                <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">持有数量范围</label>
                <div className="grid grid-cols-2 gap-3">
                  <input
                    type="number"
                    min={1}
                    value={holdMin}
                    onChange={(event) => setHoldMin(Number(event.target.value))}
                    className={inputClassName}
                  />
                  <input
                    type="number"
                    min={1}
                    value={holdMax}
                    onChange={(event) => setHoldMax(Number(event.target.value))}
                    className={inputClassName}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
            <div className="border-b border-gray-200 px-4 py-2 dark:border-gray-800">
              <nav className="flex overflow-x-auto rounded-lg bg-gray-100 p-0.5 dark:bg-gray-900">
                {configTabs.map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveTab(tab.key)}
                    className={`text-theme-sm h-10 shrink-0 whitespace-nowrap rounded-md px-4 py-2 font-medium ${
                      activeTab === tab.key
                        ? "shadow-theme-xs bg-white text-gray-900 dark:bg-gray-800 dark:text-white"
                        : "text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </nav>
            </div>

            <div className="p-4">
              {activeTab === "strategy" && (
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
              )}

              {activeTab === "intraday" && (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">最小成交额(万)</label>
                    <input
                      type="number"
                      min={0}
                      value={minTurnoverWan}
                      onChange={(event) => setMinTurnoverWan(Number(event.target.value))}
                      className={inputClassName}
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">最小成交量(手)</label>
                    <input
                      type="number"
                      min={0}
                      value={minVolumeLot}
                      onChange={(event) => setMinVolumeLot(Number(event.target.value))}
                      className={inputClassName}
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">盘中动作</label>
                    <select
                      value={intradayAction}
                      onChange={(event) => setIntradayAction(event.target.value)}
                      className={inputClassName}
                    >
                      <option value="开盘后5分钟仅观察">开盘后5分钟仅观察</option>
                      <option value="盘中实时可调仓">盘中实时可调仓</option>
                      <option value="仅盘后调仓">仅盘后调仓</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">换仓时间</label>
                    <select
                      value={dealTiming}
                      onChange={(event) => setDealTiming(event.target.value)}
                      className={inputClassName}
                    >
                      <option value="收盘买卖">每日收盘买卖</option>
                      <option value="次日开盘买卖">次日开盘买卖</option>
                      <option value="14:50-15:00">14:50-15:00 批量执行</option>
                    </select>
                  </div>
                  <div className="md:col-span-2 xl:col-span-2">
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">执行说明</label>
                    <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-3 text-sm text-gray-600 dark:border-gray-800 dark:bg-gray-900/30 dark:text-gray-300">
                      当前设定会先按流动性过滤候选，再按模板打分排序执行调仓；盘中仅用于交易可达性判断，不改变因子权重。
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "postclose" && (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">排除赎回状态</label>
                    <select
                      value={forceRedeemGuard}
                      onChange={(event) => setForceRedeemGuard(event.target.value)}
                      className={inputClassName}
                    >
                      <option value="已满足强赎条件+4天">已满足强赎条件 +4 天</option>
                      <option value="公告强赎即排除">公告强赎即排除</option>
                      <option value="不排除">不排除</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">排除新债(上市天数)</label>
                    <input
                      type="number"
                      min={0}
                      value={excludeNewBondDays}
                      onChange={(event) => setExcludeNewBondDays(Number(event.target.value))}
                      className={inputClassName}
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">排除 ST</label>
                    <select
                      value={excludeSt ? "true" : "false"}
                      onChange={(event) => setExcludeSt(event.target.value === "true")}
                      className={inputClassName}
                    >
                      <option value="true">开启</option>
                      <option value="false">关闭</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">排除市场</label>
                    <select
                      value={excludeMarket}
                      onChange={(event) => setExcludeMarket(event.target.value)}
                      className={inputClassName}
                    >
                      <option value="不排除">不排除</option>
                      <option value="排除北交所">排除北交所</option>
                      <option value="排除科创板正股">排除科创板正股</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">排除行业</label>
                    <select
                      value={excludeIndustry}
                      onChange={(event) => setExcludeIndustry(event.target.value)}
                      className={inputClassName}
                    >
                      <option value="不排除">不排除</option>
                      <option value="高波动行业">高波动行业</option>
                      <option value="地产链">地产链</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">排除评级</label>
                    <select
                      value={excludeRating}
                      onChange={(event) => setExcludeRating(event.target.value)}
                      className={inputClassName}
                    >
                      <option value="不排除">不排除</option>
                      <option value="AA-及以下">AA-及以下</option>
                      <option value="A+及以下">A+及以下</option>
                    </select>
                  </div>
                </div>
              )}

              {activeTab === "bucket" && (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">分箱因子</label>
                    <select
                      value={bucketFactor}
                      onChange={(event) => setBucketFactor(event.target.value)}
                      className={inputClassName}
                    >
                      <option value="双低值">双低值</option>
                      <option value="转股溢价率">转股溢价率</option>
                      <option value="纯债溢价率">纯债溢价率</option>
                      <option value="成交额">成交额</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">分箱数量</label>
                    <input
                      type="number"
                      min={2}
                      max={20}
                      value={bucketCount}
                      onChange={(event) => setBucketCount(Number(event.target.value))}
                      className={inputClassName}
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">分箱焦点</label>
                    <select
                      value={bucketFocus}
                      onChange={(event) => setBucketFocus(event.target.value)}
                      className={inputClassName}
                    >
                      <option value="全部分箱">全部分箱</option>
                      <option value="头部分箱">头部分箱</option>
                      <option value="尾部分箱">尾部分箱</option>
                    </select>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="xl:col-span-4">
          <div className="sticky top-4 rounded-xl border border-gray-200 p-4 dark:border-gray-800">
            <h4 className="text-base font-semibold text-gray-800 dark:text-white/90">运行面板</h4>
            <div className="mt-4 space-y-3">
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/30">
                <p className="text-xs text-gray-500 dark:text-gray-400">回测对象</p>
                <p className="text-sm font-semibold text-gray-900 dark:text-white">
                  {selectedCandidate?.comboId ?? "--"}
                </p>
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
                onClick={handleQueue}
                disabled={selectedWindows.length === 0}
                className="bg-brand-500 hover:bg-brand-600 disabled:bg-brand-300 mt-2 h-11 w-full rounded-lg text-sm font-medium text-white disabled:cursor-not-allowed"
              >
                加入任务队列
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
