"use client";

import {
  createStrategyOptimizeTask,
  getHistoryDataSummary,
  getHistorySyncStatus,
  getStrategyOptimizeSummary,
  getStrategyOptimizeTaskDetail,
  listStrategyOptimizeTasks,
  listStrategyTemplates,
  triggerHistorySync,
  type HistoryDataSummary,
  type HistorySyncStatus,
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
import React, { useCallback, useEffect, useMemo, useState } from "react";

export const dynamic = "force-dynamic";

function statusTone(status: StrategyOptimizeTask["status"]) {
  if (status === "queued") return "yellow" as const;
  if (status === "running") return "blue" as const;
  if (status === "finished") return "green" as const;
  return "red" as const;
}

function toPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function dateToInput(value: Date): string {
  return value.toISOString().slice(0, 10);
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
  const [selectedTaskId, setSelectedTaskId] = useState<string>("");
  const [resultMode, setResultMode] = useState<"global" | "task">("global");
  const [detail, setDetail] = useState<StrategyOptimizeTaskDetail | null>(null);
  const [summary, setSummary] = useState<StrategyOptimizeSummary | null>(null);

  const [loadingTasks, setLoadingTasks] = useState<boolean>(false);
  const [syncingHistory, setSyncingHistory] = useState<boolean>(false);
  const [historySummary, setHistorySummary] = useState<HistoryDataSummary | null>(null);
  const [historySyncStatus, setHistorySyncStatus] = useState<HistorySyncStatus | null>(null);
  const [creating, setCreating] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [hint, setHint] = useState<string>("");

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

  const loadBootstrap = useCallback(async () => {
    try {
      const [strategyResp, summary] = await Promise.all([
        listStrategyTemplates({ page: 1, pageSize: 500 }),
        getHistoryDataSummary(),
      ]);
      setStrategies(strategyResp.items);
      setHistorySummary(summary);

      const syncStatus = await getHistorySyncStatus();
      setHistorySyncStatus(syncStatus);

      if (summary.dateStart && summary.dateEnd) {
        setStartDate(summary.dateStart);
        setEndDate(summary.dateEnd);
      } else {
        const now = new Date();
        const prev = new Date(now.getTime());
        prev.setFullYear(prev.getFullYear() - 3);
        setStartDate(dateToInput(prev));
        setEndDate(dateToInput(now));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "初始化失败");
    }
  }, []);

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

  useEffect(() => {
    void loadBootstrap();
  }, [loadBootstrap]);

  useEffect(() => {
    void loadTasks();
  }, [tasksPage, loadTasks]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadTasks();
      void loadDetail();
      void loadSummary();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loadTasks, loadDetail, loadSummary]);

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
      await loadDetail();
      await loadSummary();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建优化任务失败");
    } finally {
      setCreating(false);
    }
  };

  const handleSyncHistory = async () => {
    setSyncingHistory(true);
    setError("");
    try {
      const result = await triggerHistorySync();
      setHint(result.message);
      const [summary, syncStatus] = await Promise.all([getHistoryDataSummary(), getHistorySyncStatus()]);
      setHistorySummary(summary);
      setHistorySyncStatus(syncStatus);
    } catch (err) {
      setError(err instanceof Error ? err.message : "历史快照同步失败");
    } finally {
      setSyncingHistory(false);
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
            <p className="text-sm text-gray-500 dark:text-gray-400">用户动线：同步历史快照 → 启动回测搜索 → 轮询进度 → 查看最优策略与当前Top20。</p>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-600 dark:text-gray-300">
              <span>
                历史快照：
                {historySummary
                  ? `${historySummary.snapshotCount} 天，${historySummary.dateStart ?? "--"} ~ ${historySummary.dateEnd ?? "--"}`
                  : "--"}
              </span>
              <span>
                最新同步：
                {historySyncStatus?.hasLog
                  ? `${historySyncStatus.syncAt ?? "--"}（${historySyncStatus.mode ?? "--"}，${historySyncStatus.upserted}条）`
                  : "暂无"}
              </span>
              <button
                type="button"
                onClick={handleSyncHistory}
                disabled={syncingHistory}
                className="rounded-lg border border-brand-500 px-3 py-1 text-xs font-medium text-brand-600 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-brand-400 dark:text-brand-300"
              >
                {syncingHistory ? "同步中..." : "立即同步历史快照"}
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

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
            <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
              <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">
                {showingGlobal ? "全局最优策略榜单（跨任务汇总）" : "最优策略榜单（单任务）"}
              </h3>
            </div>
            <div className="p-5">
              <ScrollableDataTable
                headers={["排名", "任务ID", "模板", "组合ID", "稳健分", "CAGR", "MDD", "Calmar", "收益%", "参数"]}
                minTableWidthClass="min-w-[1400px]"
                colSpan={10}
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
      </div>
    </CbQuantPageShell>
  );
}
