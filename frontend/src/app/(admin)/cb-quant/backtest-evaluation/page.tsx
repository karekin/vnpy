"use client";

import {
  cancelBacktestJob,
  createStrategyOptimizeTask,
  getHistoryDataSummary,
  listBacktestJobs,
  getTushareHistorySummary,
  getTushareHistorySyncStatus,
  getStrategyOptimizeTaskAnalysis,
  getStrategyOptimizeSummary,
  getStrategyOptimizeTaskDetail,
  listStrategyOptimizeTasks,
  listStrategyTemplates,
  triggerTushareHistorySync,
  type BacktestJob,
  type StrategyBacktestDistributionRow,
  type StrategyBacktestMetricRow,
  type StrategyBacktestRotationRow,
  type StrategyOptimizeTaskAnalysis,
  type HistoryDataSummary,
  type TushareDataSummary,
  type TushareSyncStatus,
  type StrategyOptimizeSummary,
  type StrategyOptimizeTask,
  type StrategyOptimizeTaskDetail,
  type StrategyTemplate,
  type WindowName,
} from "@/components/cb-quant/api";
import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import { getTotalPages } from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import type { ApexOptions } from "apexcharts";
import dynamicImport from "next/dynamic";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

export const dynamic = "force-dynamic";
const ReactApexChart = dynamicImport(() => import("react-apexcharts"), { ssr: false });

function statusTone(status: StrategyOptimizeTask["status"]) {
  if (status === "queued") return "yellow" as const;
  if (status === "running") return "blue" as const;
  if (status === "finished") return "green" as const;
  return "red" as const;
}

function backtestJobTone(status: BacktestJob["status"]) {
  if (status === "queued") return "yellow" as const;
  if (status === "running") return "blue" as const;
  if (status === "finished") return "green" as const;
  if (status === "cancelled") return "slate" as const;
  return "red" as const;
}

function toPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function dateToInput(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function defaultDateRange(): { start: string; end: string } {
  const now = new Date();
  const prev = new Date(now.getTime());
  prev.setFullYear(prev.getFullYear() - 3);
  return {
    start: dateToInput(prev),
    end: dateToInput(now),
  };
}

function estimateTradeDays(startDate?: string, endDate?: string): number {
  if (!startDate || !endDate) {
    return 1500;
  }
  const start = new Date(startDate);
  const end = new Date(endDate);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return 1500;
  }
  const diff = Math.abs(end.getTime() - start.getTime());
  const days = Math.floor(diff / (24 * 60 * 60 * 1000)) + 1;
  const estimated = Math.ceil(days * 0.75) + 20;
  return Math.max(30, Math.min(5000, estimated));
}

function formatPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "/";
  }
  return `${value.toFixed(digits)}%`;
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "/";
  }
  return value.toFixed(digits);
}

function distributionLabel(period: "yearly" | "monthly" | "weekly"): string {
  if (period === "yearly") return "年度回报";
  if (period === "monthly") return "月度回报";
  return "周度回报";
}

export default function CbQuantBacktestEvaluationPage() {
  const [strategies, setStrategies] = useState<StrategyTemplate[]>([]);

  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");
  const [topN, setTopN] = useState<number>(20);
  const [currentTopN, setCurrentTopN] = useState<number>(20);
  const [windows, setWindows] = useState<Record<WindowName, boolean>>({ full: true, "3y": true, "1y": true });

  const [tasks, setTasks] = useState<StrategyOptimizeTask[]>([]);
  const [tasksPage, setTasksPage] = useState<number>(1);
  const [tasksTotal, setTasksTotal] = useState<number>(0);
  const [tasksTotalPages, setTasksTotalPages] = useState<number>(1);
  const [backtestJobs, setBacktestJobs] = useState<BacktestJob[]>([]);
  const [backtestJobsPage, setBacktestJobsPage] = useState<number>(1);
  const [backtestJobsTotal, setBacktestJobsTotal] = useState<number>(0);
  const [backtestJobsTotalPages, setBacktestJobsTotalPages] = useState<number>(1);
  const [backtestJobStatusFilter, setBacktestJobStatusFilter] = useState<string>("all");
  const [backtestBusinessDate, setBacktestBusinessDate] = useState<string>("");
  const [backtestBusinessDateFrom, setBacktestBusinessDateFrom] = useState<string>("");
  const [backtestBusinessDateTo, setBacktestBusinessDateTo] = useState<string>("");
  const [cancellingBacktestJobId, setCancellingBacktestJobId] = useState<string>("");
  const [selectedTaskId, setSelectedTaskId] = useState<string>("");
  const [resultMode, setResultMode] = useState<"global" | "task">("global");
  const [detail, setDetail] = useState<StrategyOptimizeTaskDetail | null>(null);
  const [summary, setSummary] = useState<StrategyOptimizeSummary | null>(null);
  const [analysis, setAnalysis] = useState<StrategyOptimizeTaskAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState<boolean>(false);
  const [analysisError, setAnalysisError] = useState<string>("");
  const [distributionPeriod, setDistributionPeriod] = useState<"yearly" | "monthly" | "weekly">("yearly");

  const [loadingTasks, setLoadingTasks] = useState<boolean>(false);
  const [loadingBacktestJobs, setLoadingBacktestJobs] = useState<boolean>(false);
  const [syncingTushareHistory, setSyncingTushareHistory] = useState<boolean>(false);
  const [historySummary, setHistorySummary] = useState<HistoryDataSummary | null>(null);
  const [tushareSummary, setTushareSummary] = useState<TushareDataSummary | null>(null);
  const [tushareSyncStatus, setTushareSyncStatus] = useState<TushareSyncStatus | null>(null);
  const [creating, setCreating] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [hint, setHint] = useState<string>("");
  const pollingRef = useRef<boolean>(false);

  const enabledStrategies = useMemo(() => strategies.filter((row) => row.status === "active"), [strategies]);
  const strategyById = useMemo(() => new Map(strategies.map((row) => [row.id, row])), [strategies]);
  const totalCombinations = useMemo(
    () => enabledStrategies.reduce((sum, row) => sum + row.comboSize, 0),
    [enabledStrategies],
  );

  const activeWindows = useMemo(
    () => (Object.entries(windows).filter(([, checked]) => checked).map(([key]) => key) as WindowName[]),
    [windows],
  );
  const showingGlobal = resultMode === "global";
  const displayTopStrategies = showingGlobal ? (summary?.topStrategies ?? []) : (detail?.topStrategies ?? []);
  const displayTopBonds = showingGlobal ? (summary?.topBonds ?? []) : (detail?.topBonds ?? []);
  const distributionRows = useMemo<StrategyBacktestDistributionRow[]>(() => {
    if (!analysis) {
      return [];
    }
    if (distributionPeriod === "yearly") {
      return analysis.yearlyDistribution;
    }
    if (distributionPeriod === "monthly") {
      return analysis.monthlyDistribution;
    }
    return analysis.weeklyDistribution;
  }, [analysis, distributionPeriod]);
  const rotationRows = useMemo<StrategyBacktestRotationRow[]>(() => {
    if (!analysis) {
      return [];
    }
    return [...analysis.rotations].slice(-80).reverse();
  }, [analysis]);

  const trendSeries = useMemo(() => {
    if (!analysis) {
      return [];
    }
    return [
      { name: "策略累计收益", data: analysis.curve.map((row) => row.strategyCumReturnPct) },
      { name: "基准累计收益", data: analysis.curve.map((row) => row.benchmarkCumReturnPct) },
      { name: "相对超额", data: analysis.curve.map((row) => row.relativeExcessPct) },
      { name: "绝对超额", data: analysis.curve.map((row) => row.absoluteExcessPct) },
      { name: "回撤", data: analysis.curve.map((row) => row.drawdownPct) },
    ];
  }, [analysis]);

  const trendOptions = useMemo<ApexOptions>(() => {
    return {
      chart: {
        toolbar: { show: true },
        animations: { enabled: false },
      },
      stroke: {
        curve: "straight",
        width: [2, 2, 2, 2, 1],
      },
      dataLabels: { enabled: false },
      xaxis: {
        categories: analysis?.curve.map((row) => row.date) ?? [],
        labels: { rotate: -45, hideOverlappingLabels: true },
      },
      yaxis: {
        title: { text: "收益率/回撤(%)" },
        labels: {
          formatter: (value) => `${value.toFixed(1)}%`,
        },
      },
      tooltip: {
        y: {
          formatter: (value) => `${value.toFixed(2)}%`,
        },
      },
      legend: { position: "top" },
      colors: ["#2563eb", "#16a34a", "#f59e0b", "#64748b", "#93c5fd"],
    };
  }, [analysis]);

  const distributionSeries = useMemo(() => {
    return [
      {
        name: "策略收益",
        data: distributionRows.map((row) => row.strategyReturnPct),
      },
      {
        name: "基准收益",
        data: distributionRows.map((row) => row.benchmarkReturnPct),
      },
      {
        name: "超额收益",
        data: distributionRows.map((row) => row.excessReturnPct),
      },
    ];
  }, [distributionRows]);

  const distributionOptions = useMemo<ApexOptions>(() => {
    return {
      chart: {
        type: "bar",
        toolbar: { show: false },
        animations: { enabled: false },
      },
      plotOptions: {
        bar: {
          horizontal: false,
          columnWidth: "50%",
        },
      },
      dataLabels: { enabled: false },
      xaxis: {
        categories: distributionRows.map((row) => row.period),
      },
      yaxis: {
        labels: {
          formatter: (value) => `${value.toFixed(1)}%`,
        },
      },
      tooltip: {
        y: {
          formatter: (value) => `${value.toFixed(2)}%`,
        },
      },
      colors: ["#2563eb", "#22c55e", "#6366f1"],
      legend: { position: "top" },
    };
  }, [distributionRows]);

  const rotationSeries = useMemo(() => {
    return [
      {
        name: "换手率",
        data: rotationRows.map((row) => row.turnoverPct),
      },
      {
        name: "持仓涨跌幅",
        data: rotationRows.map((row) => row.periodReturnPct),
      },
    ];
  }, [rotationRows]);

  const rotationOptions = useMemo<ApexOptions>(() => {
    return {
      chart: {
        toolbar: { show: false },
        animations: { enabled: false },
      },
      stroke: { width: 2 },
      xaxis: {
        categories: rotationRows.map((row) => row.rebalanceDate),
        labels: { rotate: -45, hideOverlappingLabels: true },
      },
      yaxis: {
        title: { text: "百分比(%)" },
        labels: {
          formatter: (value) => `${value.toFixed(1)}%`,
        },
      },
      legend: { position: "top" },
      tooltip: {
        y: {
          formatter: (value) => `${value.toFixed(2)}%`,
        },
      },
      colors: ["#3b82f6", "#ef4444"],
    };
  }, [rotationRows]);

  const loadStrategies = useCallback(async () => {
    const merged: StrategyTemplate[] = [];
    const pageSize = 200;
    let page = 1;
    let total = 0;
    while (page <= 100) {
      const response = await listStrategyTemplates({
        status: "all",
        page,
        pageSize,
      });
      merged.push(...response.items);
      total = response.total;
      if (merged.length >= total || response.items.length === 0) {
        break;
      }
      page += 1;
    }
    setStrategies(merged);
  }, []);

  const loadBootstrap = useCallback(async () => {
    const fallbackRange = defaultDateRange();
    setStartDate((prev) => prev || fallbackRange.start);
    setEndDate((prev) => prev || fallbackRange.end);

    const [strategyRes, summaryRes, tsSummaryRes, tsSyncRes] = await Promise.allSettled([
      loadStrategies(),
      getHistoryDataSummary(),
      getTushareHistorySummary(),
      getTushareHistorySyncStatus(),
    ]);

    if (summaryRes.status === "fulfilled") {
      const summaryPayload = summaryRes.value;
      setHistorySummary(summaryPayload);
      if (summaryPayload.dateStart && summaryPayload.dateEnd) {
        setStartDate(summaryPayload.dateStart);
        setEndDate(summaryPayload.dateEnd);
      }
    } else {
      setHistorySummary(null);
    }

    if (tsSummaryRes.status === "fulfilled") {
      setTushareSummary(tsSummaryRes.value);
    } else {
      setTushareSummary(null);
    }

    if (tsSyncRes.status === "fulfilled") {
      setTushareSyncStatus(tsSyncRes.value);
    } else {
      setTushareSyncStatus(null);
    }

    if (strategyRes.status !== "fulfilled") {
      setStrategies([]);
      const reason = strategyRes.reason instanceof Error ? strategyRes.reason.message : "策略加载失败";
      setError(reason);
    }
  }, [loadStrategies]);

  const loadTasks = useCallback(async () => {
    setLoadingTasks(true);
    try {
      const response = await listStrategyOptimizeTasks({
        templateId: "all",
        page: tasksPage,
        pageSize: 10,
      });
      setTasks(response.items);
      setTasksTotal(response.total);
      setTasksTotalPages(getTotalPages(response.total, 10));
      if (!selectedTaskId && response.items.length) {
        setSelectedTaskId(response.items[0].taskId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "任务列表加载失败");
      setTasks([]);
      setTasksTotal(0);
      setTasksTotalPages(1);
    } finally {
      setLoadingTasks(false);
    }
  }, [tasksPage, selectedTaskId]);

  const loadBacktestJobs = useCallback(async () => {
    setLoadingBacktestJobs(true);
    try {
      const response = await listBacktestJobs({
        status: backtestJobStatusFilter,
        businessDate: backtestBusinessDate || undefined,
        businessDateFrom: backtestBusinessDateFrom || undefined,
        businessDateTo: backtestBusinessDateTo || undefined,
        page: backtestJobsPage,
        pageSize: 10,
      });
      setBacktestJobs(response.items);
      setBacktestJobsTotal(response.total);
      setBacktestJobsTotalPages(getTotalPages(response.total, 10));
    } catch (err) {
      setBacktestJobs([]);
      setBacktestJobsTotal(0);
      setBacktestJobsTotalPages(1);
      setError(err instanceof Error ? err.message : "回测任务列表加载失败");
    } finally {
      setLoadingBacktestJobs(false);
    }
  }, [
    backtestBusinessDate,
    backtestBusinessDateFrom,
    backtestBusinessDateTo,
    backtestJobStatusFilter,
    backtestJobsPage,
  ]);

  const loadDetail = useCallback(async () => {
    if (!selectedTaskId) {
      setDetail(null);
      return;
    }
    try {
      const response = await getStrategyOptimizeTaskDetail(selectedTaskId);
      setDetail(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "任务详情加载失败");
      setDetail(null);
    }
  }, [selectedTaskId]);

  const loadSummary = useCallback(async () => {
    try {
      const response = await getStrategyOptimizeSummary({
        topN,
        currentTopN,
      });
      setSummary(response);
    } catch (err) {
      setSummary(null);
      setError(err instanceof Error ? err.message : "全局汇总加载失败");
    }
  }, [topN, currentTopN]);

  const loadAnalysis = useCallback(async (taskId: string, comboId?: string) => {
    if (!taskId) {
      setAnalysis(null);
      return;
    }
    setAnalysisLoading(true);
    setAnalysisError("");
    try {
      const response = await getStrategyOptimizeTaskAnalysis(taskId, {
        comboId,
        initialCapitalWan: 100,
      });
      setAnalysis(response);
    } catch (err) {
      setAnalysis(null);
      setAnalysisError(err instanceof Error ? err.message : "分析数据加载失败");
    } finally {
      setAnalysisLoading(false);
    }
  }, []);

  const loadTaskDetailById = useCallback(async (taskId: string) => {
    if (!taskId) {
      return;
    }
    try {
      const response = await getStrategyOptimizeTaskDetail(taskId);
      setDetail(response);
      const defaultCombo = response.topStrategies[0]?.comboId;
      await loadAnalysis(taskId, defaultCombo);
    } catch (err) {
      setDetail(null);
      setError(err instanceof Error ? err.message : "任务详情加载失败");
    }
  }, [loadAnalysis]);

  useEffect(() => {
    void loadBootstrap();
  }, [loadBootstrap]);

  useEffect(() => {
    void loadTasks();
  }, [tasksPage, loadTasks]);

  useEffect(() => {
    void loadBacktestJobs();
  }, [loadBacktestJobs]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    if (showingGlobal) {
      const first = summary?.topStrategies[0];
      if (!first?.taskId || !first.comboId) {
        return;
      }
      if (analysis?.taskId === first.taskId && analysis?.comboId === first.comboId) {
        return;
      }
      void loadAnalysis(first.taskId, first.comboId);
      return;
    }

    const taskId = detail?.task.taskId ?? selectedTaskId;
    const comboId = detail?.topStrategies[0]?.comboId;
    if (!taskId) {
      return;
    }
    const taskFinished = detail?.task.status === "finished";
    if (
      taskFinished
      && analysis?.taskId === taskId
      && (comboId ? analysis?.comboId === comboId : true)
      && analysis.metricRows.length > 0
    ) {
      return;
    }
    void loadAnalysis(taskId, comboId);
  }, [
    analysis?.comboId,
    analysis?.taskId,
    analysis?.metricRows.length,
    detail,
    loadAnalysis,
    selectedTaskId,
    showingGlobal,
    summary,
  ]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (pollingRef.current) {
        return;
      }
      pollingRef.current = true;
      void Promise.allSettled([
        loadTasks(),
        loadBacktestJobs(),
        loadSummary(),
        showingGlobal ? Promise.resolve() : loadDetail(),
      ]).finally(() => {
        pollingRef.current = false;
      });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loadBacktestJobs, loadTasks, loadDetail, loadSummary, showingGlobal]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadStrategies();
    }, 30000);
    return () => window.clearInterval(timer);
  }, [loadStrategies]);

  const handleCreateTask = async () => {
    if (!enabledStrategies.length) {
      setError("没有启用策略，请先到策略生成页启用策略。");
      return;
    }
    if (!activeWindows.length) {
      setError("至少选择一个回测窗口");
      return;
    }

    setCreating(true);
    setError("");
    setHint("");
    try {
      const createdTaskIds: string[] = [];
      const failedStrategyNames: string[] = [];

      for (const strategy of enabledStrategies) {
        try {
          const strategyData = strategyById.get(strategy.id);
          const result = await createStrategyOptimizeTask({
            templateId: strategy.id,
            windows: activeWindows,
            startDate,
            endDate,
            topN,
            maxCombinations: strategyData?.comboSize ?? undefined,
            currentTopN,
          });
          createdTaskIds.push(result.task.taskId);
        } catch {
          failedStrategyNames.push(strategy.name);
        }
      }

      const createdCount = createdTaskIds.length;
      const totalTasks = createdCount * activeWindows.length;
      if (!createdCount) {
        setError("任务创建失败，请检查策略配置与历史数据。");
        return;
      }

      setHint(
        `已为 ${createdCount} 个启用策略创建回测任务，共 ${totalTasks} 个窗口任务。${
          failedStrategyNames.length ? `失败 ${failedStrategyNames.length} 个策略：${failedStrategyNames.join("、")}` : ""
        }`,
      );
      setSelectedTaskId(createdTaskIds[0]);
      setResultMode("task");
      setTasksPage(1);
      await loadTasks();
      await loadTaskDetailById(createdTaskIds[0]);
      await loadSummary();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建优化任务失败");
    } finally {
      setCreating(false);
    }
  };

  const handleSyncTushareHistory = async () => {
    setSyncingTushareHistory(true);
    setError("");
    try {
      const maxTradeDays = estimateTradeDays(startDate, endDate);
      const payload = await triggerTushareHistorySync({
        startDate: startDate || undefined,
        endDate: endDate || undefined,
        maxTradeDays,
      });
      setHint(payload.message);
      const [tsSummary, tsSyncStatus, history] = await Promise.all([
        getTushareHistorySummary(),
        getTushareHistorySyncStatus(),
        getHistoryDataSummary(),
      ]);
      setTushareSummary(tsSummary);
      setTushareSyncStatus(tsSyncStatus);
      setHistorySummary(history);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tushare 同步失败");
    } finally {
      setSyncingTushareHistory(false);
    }
  };

  const handleCancelBacktestJob = async (jobId: string) => {
    setCancellingBacktestJobId(jobId);
    setError("");
    try {
      const payload = await cancelBacktestJob(jobId);
      setHint(payload.message);
      await loadBacktestJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "取消回测任务失败");
    } finally {
      setCancellingBacktestJobId("");
    }
  };

  return (
    <CbQuantPageShell
      title="回测评估行动页"
      subtitle="按启用策略批量回测，轮询进度并输出最优策略与当前Top20。"
    >
      <div className="space-y-6">
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
            <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">回测任务创建</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">用户动线：同步Tushare历史 → 启动回测搜索 → 轮询进度 → 查看最优策略与当前Top20。</p>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-600 dark:text-gray-300">
              <span>
                历史快照：
                {historySummary
                  ? `${historySummary.snapshotCount} 天，${historySummary.dateStart ?? "--"} ~ ${historySummary.dateEnd ?? "--"}`
                  : "--"}
              </span>
              <span>
                Tushare：
                {tushareSummary
                  ? `${tushareSummary.cbTradeDays} 天（因子 ${tushareSummary.factorTradeDays} 天，事件 ${tushareSummary.eventRows} 条）`
                  : "暂无"}
              </span>
              <span>
                Tushare 最近：
                {tushareSyncStatus?.hasLog
                  ? `${tushareSyncStatus.syncAt ?? "--"}（cb ${tushareSyncStatus.cbDailyRows} / factor ${tushareSyncStatus.factorRows} / event ${tushareSyncStatus.eventRows}）`
                  : "暂无"}
              </span>
              <button
                type="button"
                onClick={handleSyncTushareHistory}
                disabled={syncingTushareHistory}
                className="rounded-lg border border-green-500 px-3 py-1 text-xs font-medium text-green-600 hover:bg-green-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-green-400 dark:text-green-300"
              >
                {syncingTushareHistory ? "Tushare同步中..." : "立即同步Tushare"}
              </button>
            </div>
          </div>
          <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-4">
            <div>
              <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">启用策略数</label>
              <div className="h-11 rounded-lg border border-gray-300 bg-gray-50 px-3 text-sm leading-11 text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200">
                {enabledStrategies.length} / {strategies.length}
              </div>
            </div>
            <div>
              <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">回测开始日期</label>
              <input
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
                className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">回测结束日期</label>
              <input
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
                className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">窗口</label>
              <div className="flex h-11 items-center gap-2 rounded-lg border border-gray-300 px-3 text-sm dark:border-gray-700">
                <label className="flex items-center gap-1">
                  <input type="checkbox" checked={windows.full} onChange={() => setWindows((prev) => ({ ...prev, full: !prev.full }))} />
                  全周期
                </label>
                <label className="flex items-center gap-1">
                  <input type="checkbox" checked={windows["3y"]} onChange={() => setWindows((prev) => ({ ...prev, "3y": !prev["3y"] }))} />
                  近3年
                </label>
                <label className="flex items-center gap-1">
                  <input type="checkbox" checked={windows["1y"]} onChange={() => setWindows((prev) => ({ ...prev, "1y": !prev["1y"] }))} />
                  近1年
                </label>
              </div>
            </div>
            <div>
              <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">TopN策略</label>
              <input
                type="number"
                min={1}
                max={200}
                value={topN}
                onChange={(event) => setTopN(Number(event.target.value))}
                className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">待评估组合数</label>
              <input
                type="text"
                readOnly
                value={totalCombinations > 0 ? totalCombinations.toLocaleString() : "--"}
                className="h-11 w-full rounded-lg border border-gray-300 bg-gray-50 px-3 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              />
            </div>
            <div>
              <label className="mb-2 block text-xs font-medium text-gray-600 dark:text-gray-400">当前推荐数量</label>
              <input
                type="number"
                min={1}
                max={200}
                value={currentTopN}
                onChange={(event) => setCurrentTopN(Number(event.target.value))}
                className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              />
            </div>
            <div className="flex items-end">
              <button
                type="button"
                disabled={creating}
                onClick={handleCreateTask}
                className="inline-flex h-11 w-full items-center justify-center rounded-lg bg-brand-500 px-4 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-60"
              >
                {creating ? "任务创建中..." : "开始回测搜索"}
              </button>
            </div>
          </div>
          {error ? (
            <p className="mx-5 mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600 dark:border-red-900/50 dark:bg-red-500/10 dark:text-red-300">
              {error}
            </p>
          ) : null}
          {hint ? (
            <p className="mx-5 mb-4 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700 dark:border-green-900/50 dark:bg-green-500/10 dark:text-green-300">
              {hint}
            </p>
          ) : null}
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
            <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">回测任务队列（轮询刷新）</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">当前显示全量任务队列。</p>
          </div>
          <div className="p-5">
            <ScrollableDataTable
              headers={["任务ID", "策略", "状态", "进度", "已评估/总组合", "窗口", "ETA", "更新时间", "操作"]}
              minTableWidthClass="min-w-[1280px]"
              colSpan={9}
              isEmpty={!loadingTasks && tasks.length === 0}
              emptyText="暂无任务，请先创建回测搜索任务"
            >
              {tasks.map((row) => (
                <TableRow key={row.taskId} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 dark:text-white">{row.taskId}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-900 dark:text-white">{row.templateName}</TableCell>
                  <TableCell className="px-4 py-3">
                    <StatusTag label={row.status} tone={statusTone(row.status)} />
                  </TableCell>
                  <TableCell className="px-4 py-3">
                    <div className="w-40">
                      <div className="h-2 rounded bg-gray-200 dark:bg-gray-700">
                        <div className="h-2 rounded bg-brand-500" style={{ width: `${row.progress}%` }} />
                      </div>
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{row.progress}%</p>
                    </div>
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                    {row.evaluatedCombinations.toLocaleString()} / {row.totalCombinations.toLocaleString()}
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.windows.join("/")}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.eta}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">{row.finishedAt ?? row.startedAt ?? row.createdAt}</TableCell>
                  <TableCell className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedTaskId(row.taskId);
                        setResultMode("task");
                        void loadTaskDetailById(row.taskId);
                      }}
                      className="rounded-lg border border-brand-500 px-3 py-1.5 text-xs font-medium text-brand-600 hover:bg-brand-50 dark:border-brand-400 dark:text-brand-300"
                    >
                      查看结果
                    </button>
                  </TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={tasksTotal}
              currentPage={tasksPage}
              totalPages={tasksTotalPages}
              onPageChange={setTasksPage}
            />
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
            <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">回测执行任务（可取消 + 业务日期筛选）</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">对应 `/api/v1/cb-quant/backtest/jobs`。</p>
          </div>
          <div className="space-y-4 p-5">
            <div className="grid gap-3 md:grid-cols-5">
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">状态</label>
                <select
                  value={backtestJobStatusFilter}
                  onChange={(event) => {
                    setBacktestJobStatusFilter(event.target.value);
                    setBacktestJobsPage(1);
                  }}
                  className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                >
                  <option value="all">all</option>
                  <option value="queued">queued</option>
                  <option value="running">running</option>
                  <option value="finished">finished</option>
                  <option value="failed">failed</option>
                  <option value="cancelled">cancelled</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">业务日期</label>
                <input
                  type="date"
                  value={backtestBusinessDate}
                  onChange={(event) => {
                    setBacktestBusinessDate(event.target.value);
                    setBacktestJobsPage(1);
                  }}
                  className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">业务日期从</label>
                <input
                  type="date"
                  value={backtestBusinessDateFrom}
                  onChange={(event) => {
                    setBacktestBusinessDateFrom(event.target.value);
                    setBacktestJobsPage(1);
                  }}
                  className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">业务日期至</label>
                <input
                  type="date"
                  value={backtestBusinessDateTo}
                  onChange={(event) => {
                    setBacktestBusinessDateTo(event.target.value);
                    setBacktestJobsPage(1);
                  }}
                  className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                />
              </div>
              <div className="flex items-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setBacktestBusinessDate("");
                    setBacktestBusinessDateFrom("");
                    setBacktestBusinessDateTo("");
                    setBacktestJobStatusFilter("all");
                    setBacktestJobsPage(1);
                  }}
                  className="h-10 rounded-lg border border-gray-300 px-3 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300"
                >
                  重置筛选
                </button>
                <button
                  type="button"
                  onClick={() => void loadBacktestJobs()}
                  className="h-10 rounded-lg border border-brand-500 px-3 text-xs font-medium text-brand-600 hover:bg-brand-50 dark:border-brand-400 dark:text-brand-300"
                >
                  手动刷新
                </button>
              </div>
            </div>

            <ScrollableDataTable
              headers={["任务ID", "组合", "规则包", "窗口", "状态", "进度", "业务日期", "ETA", "Worker", "创建时间", "操作"]}
              minTableWidthClass="min-w-[1380px]"
              colSpan={11}
              isEmpty={!loadingBacktestJobs && backtestJobs.length === 0}
              emptyText="暂无回测执行任务"
            >
              {backtestJobs.map((row) => {
                const cancellable = row.status === "queued" || row.status === "running";
                return (
                  <TableRow key={row.jobId} className="border-b border-gray-100 dark:border-gray-800">
                    <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 dark:text-white">{row.jobId}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.comboId}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.rulePackId}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.window}</TableCell>
                    <TableCell className="px-4 py-3">
                      <StatusTag label={row.status} tone={backtestJobTone(row.status)} />
                    </TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.progress}%</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.businessDate ?? "--"}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.eta}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.worker}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">{row.createdAt ?? "--"}</TableCell>
                    <TableCell className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => void handleCancelBacktestJob(row.jobId)}
                        disabled={!cancellable || cancellingBacktestJobId === row.jobId}
                        className="rounded-lg border border-red-500 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-red-400 dark:text-red-300"
                      >
                        {cancellingBacktestJobId === row.jobId ? "取消中..." : "取消"}
                      </button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={backtestJobsTotal}
              currentPage={backtestJobsPage}
              totalPages={backtestJobsTotalPages}
              onPageChange={setBacktestJobsPage}
            />
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setResultMode("global")}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${
                showingGlobal
                  ? "border-brand-500 bg-brand-50 text-brand-600 dark:border-brand-400 dark:bg-brand-500/10 dark:text-brand-300"
                  : "border-gray-300 text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300"
              }`}
            >
              全局汇总（全部双/三因子）
            </button>
            <button
              type="button"
              onClick={() => setResultMode("task")}
              disabled={!selectedTaskId}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${
                !showingGlobal
                  ? "border-brand-500 bg-brand-50 text-brand-600 dark:border-brand-400 dark:bg-brand-500/10 dark:text-brand-300"
                  : "border-gray-300 text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300"
              } disabled:cursor-not-allowed disabled:opacity-60`}
            >
              单任务视图（当前选择）
            </button>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {showingGlobal
                ? `已完成任务 ${summary?.finishedTaskCount ?? 0} 个，汇总策略 ${summary?.totalResultCount ?? 0} 条。`
                : `当前任务：${detail?.task.taskId ?? selectedTaskId ?? "--"}。`}
            </span>
          </div>
          {showingGlobal && summary?.message ? (
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{summary.message}</p>
          ) : null}
          {!showingGlobal && detail?.task.message ? (
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">{detail.task.message}</p>
          ) : null}
        </div>

        <div className="grid grid-cols-1 gap-6">
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
            <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
              <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
                {showingGlobal ? "全局最优策略榜单（跨任务汇总）" : "最优策略榜单（单任务）"}
              </h3>
            </div>
            <div className="p-5">
              <ScrollableDataTable
                headers={["排名", "任务ID", "模板", "组合ID", "稳健分", "CAGR", "MDD", "Calmar", "收益%", "参数", "操作"]}
                minTableWidthClass="min-w-[1400px]"
                colSpan={11}
                isEmpty={displayTopStrategies.length === 0}
                emptyText="任务完成后展示TopN策略"
              >
                {displayTopStrategies.map((row) => (
                  <TableRow key={`${row.taskId ?? "task"}-${row.comboId}-${row.rank}`} className="border-b border-gray-100 dark:border-gray-800">
                    <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 dark:text-white">#{row.rank}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.taskId ?? "--"}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.templateName ?? "--"}</TableCell>
                    <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 dark:text-white">{row.comboId}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.robustScore.toFixed(2)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm font-medium text-green-600">{toPercent(row.cagr)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm font-medium text-red-600">{toPercent(row.mdd)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.calmar.toFixed(2)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.totalReturnPct.toFixed(2)}%</TableCell>
                    <TableCell className="px-4 py-3 text-xs text-gray-500 dark:text-gray-400">
                      <code>{JSON.stringify(row.params)}</code>
                    </TableCell>
                    <TableCell className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => {
                          const taskId = row.taskId ?? selectedTaskId;
                          if (!taskId) {
                            return;
                          }
                          setSelectedTaskId(taskId);
                          setResultMode("task");
                          void loadAnalysis(taskId, row.comboId);
                        }}
                        className="rounded-lg border border-brand-500 px-3 py-1.5 text-xs font-medium text-brand-600 hover:bg-brand-50 dark:border-brand-400 dark:text-brand-300"
                      >
                        回测分析
                      </button>
                    </TableCell>
                  </TableRow>
                ))}
              </ScrollableDataTable>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
            <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
              <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
                {showingGlobal ? "当前市场 Top20 可转债（按全局最优策略）" : "当前市场 Top20 可转债（按任务最优策略）"}
              </h3>
            </div>
            <div className="p-5">
              <ScrollableDataTable
                headers={["排名", "转债代码", "转债名称", "现价", "转股溢价率", "双低", "成交额(万)", "评分"]}
                minTableWidthClass="min-w-[980px]"
                colSpan={8}
                isEmpty={displayTopBonds.length === 0}
                emptyText="仅展示实时行情可得的Top20（非实时源时不展示）"
              >
                {displayTopBonds.map((row) => (
                  <TableRow key={`${row.bondId}-${row.rank}`} className="border-b border-gray-100 dark:border-gray-800">
                    <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 dark:text-white">#{row.rank}</TableCell>
                    <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 dark:text-white">{row.bondId}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-900 dark:text-white">{row.bondName}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.price.toFixed(3)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.premiumRt.toFixed(2)}%</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.dblow.toFixed(3)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{(row.amountWan ?? 0).toLocaleString()}</TableCell>
                    <TableCell className="px-4 py-3 text-sm font-medium text-brand-600">{row.score.toFixed(4)}</TableCell>
                  </TableRow>
                ))}
              </ScrollableDataTable>
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
            <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">回测结果</h3>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {analysis
                ? `任务 ${analysis.taskId} · 策略 ${analysis.comboId} · 基准 ${analysis.benchmarkName} · 窗口 ${analysis.window}`
                : "选择一个策略后展示专业回测结果。"}
            </p>
            {analysis?.message ? <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{analysis.message}</p> : null}
          </div>
          <div className="p-5">
            {analysisLoading ? <p className="text-sm text-gray-500 dark:text-gray-400">回测结果加载中...</p> : null}
            {analysisError ? (
              <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600 dark:border-red-900/50 dark:bg-red-500/10 dark:text-red-300">
                {analysisError}
              </p>
            ) : null}
            {!analysisLoading && !analysisError && analysis ? (
              <ScrollableDataTable
                headers={[
                  "策略组合",
                  "总收益率",
                  "累计资产(万)",
                  "年化收益率",
                  "最大回撤",
                  "夏普比",
                  "索提诺比",
                  "卡玛比",
                  "日均换手",
                  "交易周期",
                  "盈利周期",
                  "亏损周期",
                  "胜率",
                  "盈亏比",
                  "平均每周期收益",
                  "最大单周期盈利",
                  "最大单周期亏损",
                  "最大回撤持续天数",
                ]}
                minTableWidthClass="min-w-[1900px]"
                colSpan={18}
                isEmpty={analysis.metricRows.length === 0}
                emptyText="暂无可展示的回测指标。"
              >
                {analysis.metricRows.map((row: StrategyBacktestMetricRow) => (
                  <TableRow key={row.strategyCombo} className="border-b border-gray-100 dark:border-gray-800">
                    <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 dark:text-white">{row.strategyCombo}</TableCell>
                    <TableCell className={`px-4 py-3 text-sm ${((row.totalReturnPct ?? 0) >= 0) ? "text-green-600" : "text-red-600"}`}>{formatPercent(row.totalReturnPct)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatNumber(row.cumulativeAssetWan, 2)}</TableCell>
                    <TableCell className={`px-4 py-3 text-sm ${((row.annualReturnPct ?? 0) >= 0) ? "text-green-600" : "text-red-600"}`}>{formatPercent(row.annualReturnPct)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-red-600">{formatPercent(row.maxDrawdownPct)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatNumber(row.sharpe, 3)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatNumber(row.sortino, 3)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatNumber(row.calmar, 3)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatPercent(row.avgTurnoverPct)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatNumber(row.tradeCycles, 0)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatNumber(row.profitCycles, 0)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatNumber(row.lossCycles, 0)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatPercent(row.winRatePct)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatNumber(row.profitLossRatio, 3)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatPercent(row.avgCycleReturnPct)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-green-600">{formatPercent(row.maxCycleProfitPct)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-red-600">{formatPercent(row.maxCycleLossPct)}</TableCell>
                    <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatNumber(row.maxDrawdownDurationDays, 0)}</TableCell>
                  </TableRow>
                ))}
              </ScrollableDataTable>
            ) : null}
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
            <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
              <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">回测走势</h3>
            </div>
            <div className="p-5">
              {analysis && trendSeries.length > 0 ? (
                <ReactApexChart options={trendOptions} series={trendSeries} type="line" height={360} />
              ) : (
                <p className="text-sm text-gray-500 dark:text-gray-400">暂无回测走势数据。</p>
              )}
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
            <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">回报分布</h3>
                <div className="flex items-center gap-2">
                  {(["yearly", "monthly", "weekly"] as const).map((period) => (
                    <button
                      key={period}
                      type="button"
                      onClick={() => setDistributionPeriod(period)}
                      className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${
                        distributionPeriod === period
                          ? "border-brand-500 bg-brand-50 text-brand-600 dark:border-brand-400 dark:bg-brand-500/10 dark:text-brand-300"
                          : "border-gray-300 text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300"
                      }`}
                    >
                      {distributionLabel(period)}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="p-5">
              {analysis && distributionRows.length > 0 ? (
                <ReactApexChart options={distributionOptions} series={distributionSeries} type="bar" height={360} />
              ) : (
                <p className="text-sm text-gray-500 dark:text-gray-400">暂无分布数据。</p>
              )}
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
            <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">持仓轮换</h3>
          </div>
          <div className="space-y-4 p-5">
            {analysis && rotationRows.length > 0 ? (
              <ReactApexChart options={rotationOptions} series={rotationSeries} type="line" height={300} />
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">暂无持仓轮换数据。</p>
            )}
            <ScrollableDataTable
              headers={["调仓日", "星期", "持有标的", "持仓数", "换手率", "持仓涨跌幅", "累计收益率", "累计净值(万)"]}
              minTableWidthClass="min-w-[1400px]"
              colSpan={8}
              isEmpty={!analysis || rotationRows.length === 0}
              emptyText="暂无持仓轮换明细。"
            >
              {rotationRows.map((row) => (
                <TableRow key={`${row.rebalanceDate}-${row.holdings}`} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-brand-600">{row.rebalanceDate}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.weekday}</TableCell>
                  <TableCell className="max-w-[520px] truncate px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.holdings}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.holdingCount}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatPercent(row.turnoverPct)}</TableCell>
                  <TableCell className={`px-4 py-3 text-sm ${row.periodReturnPct >= 0 ? "text-green-600" : "text-red-600"}`}>{formatPercent(row.periodReturnPct)}</TableCell>
                  <TableCell className={`px-4 py-3 text-sm ${row.cumulativeReturnPct >= 0 ? "text-green-600" : "text-red-600"}`}>{formatPercent(row.cumulativeReturnPct)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{formatNumber(row.navWan, 2)}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
          </div>
        </div>
      </div>
    </CbQuantPageShell>
  );
}
