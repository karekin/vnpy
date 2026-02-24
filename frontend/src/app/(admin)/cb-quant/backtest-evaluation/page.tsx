"use client";

import {
  createStrategyOptimizeTask,
  getHistoryDataSummary,
  getHistorySyncStatus,
  getStrategyOptimizeTaskDetail,
  listStrategyOptimizeTasks,
  listStrategyTemplates,
  triggerHistorySync,
  type HistoryDataSummary,
  type HistorySyncStatus,
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
import { useSearchParams } from "next/navigation";
import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";

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

function CbQuantBacktestEvaluationContent() {
  const searchParams = useSearchParams();
  const strategyIdFromQuery = searchParams.get("strategyId") ?? "";
  const strategyIdsFromQueryRaw = searchParams.get("strategyIds") ?? "";
  const strategyIdsFromQuery = useMemo(
    () =>
      strategyIdsFromQueryRaw
        .split(",")
        .map((id) => id.trim())
        .filter((id) => id.length > 0),
    [strategyIdsFromQueryRaw],
  );

  const [strategies, setStrategies] = useState<StrategyTemplate[]>([]);
  const [selectedStrategyIds, setSelectedStrategyIds] = useState<string[]>([]);

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
  const [detail, setDetail] = useState<StrategyOptimizeTaskDetail | null>(null);

  const [loadingTasks, setLoadingTasks] = useState<boolean>(false);
  const [syncingHistory, setSyncingHistory] = useState<boolean>(false);
  const [historySummary, setHistorySummary] = useState<HistoryDataSummary | null>(null);
  const [historySyncStatus, setHistorySyncStatus] = useState<HistorySyncStatus | null>(null);
  const [creating, setCreating] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [hint, setHint] = useState<string>("");

  const selectedStrategySet = useMemo(() => new Set(selectedStrategyIds), [selectedStrategyIds]);
  const selectedStrategies = useMemo(
    () => strategies.filter((row) => selectedStrategySet.has(row.id)),
    [selectedStrategySet, strategies],
  );
  const strategyById = useMemo(() => new Map(strategies.map((row) => [row.id, row])), [strategies]);
  const totalCombinations = useMemo(
    () => selectedStrategies.reduce((sum, row) => sum + row.comboSize, 0),
    [selectedStrategies],
  );

  const activeWindows = useMemo(
    () => (Object.entries(windows).filter(([, checked]) => checked).map(([key]) => key) as WindowName[]),
    [windows],
  );

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

      if (strategyResp.items.length) {
        const validIdSet = new Set(strategyResp.items.map((item) => item.id));
        const queryIds = strategyIdsFromQuery.filter((id) => validIdSet.has(id));
        const querySingle = validIdSet.has(strategyIdFromQuery) ? strategyIdFromQuery : "";
        setSelectedStrategyIds((prev) => {
          if (prev.length) return prev;
          if (queryIds.length) return Array.from(new Set(queryIds));
          if (querySingle) return [querySingle];
          return [strategyResp.items[0].id];
        });
      }

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
  }, [strategyIdFromQuery, strategyIdsFromQuery]);

  const loadTasks = useCallback(async () => {
    setLoadingTasks(true);
    try {
      const response = await listStrategyOptimizeTasks({
        templateId: selectedStrategyIds.length === 1 ? selectedStrategyIds[0] : "all",
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
  }, [selectedStrategyIds, tasksPage, selectedTaskId]);

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

  useEffect(() => {
    void loadBootstrap();
  }, [loadBootstrap]);

  useEffect(() => {
    if (!selectedStrategyIds.length) return;
    void loadTasks();
  }, [selectedStrategyIds, tasksPage, loadTasks]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadTasks();
      void loadDetail();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loadTasks, loadDetail]);

  const handleCreateTask = async () => {
    if (!selectedStrategyIds.length) {
      setError("请先勾选至少一个策略");
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
      const failedStrategyIds: string[] = [];

      for (const strategyId of selectedStrategyIds) {
        try {
          const strategy = strategyById.get(strategyId);
          const result = await createStrategyOptimizeTask({
            templateId: strategyId,
            windows: activeWindows,
            startDate,
            endDate,
            topN,
            maxCombinations: strategy?.comboSize ?? undefined,
            currentTopN,
          });
          createdTaskIds.push(result.task.taskId);
        } catch {
          failedStrategyIds.push(strategyId);
        }
      }

      const createdCount = createdTaskIds.length;
      const totalTasks = createdCount * activeWindows.length;
      if (!createdCount) {
        setError("任务创建失败，请检查策略配置与历史数据。");
        return;
      }

      setHint(
        `已创建 ${createdCount} 个策略的回测任务，共 ${totalTasks} 个窗口任务。${
          failedStrategyIds.length ? `失败 ${failedStrategyIds.length} 个策略：${failedStrategyIds.join("、")}` : ""
        }`,
      );
      setSelectedTaskId(createdTaskIds[0]);
      setTasksPage(1);
      await loadTasks();
      await loadDetail();
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
      subtitle="多选策略后批量创建回测任务，系统轮询进度并输出最优策略与当前Top20。"
    >
      <div className="space-y-6">
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
            <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">回测任务创建</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">用户动线：选策略与窗口 → 启动回测搜索 → 轮询进度 → 查看最优策略与当前Top20。</p>
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
              <div className="mb-2 flex items-center justify-between">
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400">策略（可多选）</label>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedStrategyIds(strategies.map((row) => row.id));
                      setTasksPage(1);
                    }}
                    disabled={!strategies.length}
                    className="rounded border border-gray-300 px-2 py-0.5 text-[11px] text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-300"
                  >
                    全选
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedStrategyIds([]);
                      setTasksPage(1);
                    }}
                    disabled={!selectedStrategyIds.length}
                    className="rounded border border-gray-300 px-2 py-0.5 text-[11px] text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-300"
                  >
                    清空
                  </button>
                </div>
              </div>
              <div className="h-[128px] space-y-1 overflow-y-auto rounded-lg border border-gray-300 bg-transparent px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white">
                {strategies.map((row) => (
                  <label key={row.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedStrategySet.has(row.id)}
                      onChange={() => {
                        setSelectedStrategyIds((prev) => {
                          if (prev.includes(row.id)) {
                            return prev.filter((id) => id !== row.id);
                          }
                          return [...prev, row.id];
                        });
                        setTasksPage(1);
                      }}
                    />
                    <span className="truncate text-xs">
                      {row.id} · {row.name}
                    </span>
                  </label>
                ))}
              </div>
              <p className="mt-1 text-[11px] text-gray-500 dark:text-gray-400">已选 {selectedStrategyIds.length} 个策略</p>
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
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {selectedStrategyIds.length === 1 ? "当前按单策略过滤任务队列。" : "当前显示全量任务队列（多策略模式）。"}
            </p>
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
                      onClick={() => setSelectedTaskId(row.taskId)}
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

        <div className="grid gap-6 xl:grid-cols-2">
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
            <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
              <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">最优策略榜单</h3>
            </div>
            <div className="p-5">
              <ScrollableDataTable
                headers={["排名", "组合ID", "稳健分", "CAGR", "MDD", "Calmar", "收益%", "参数"]}
                minTableWidthClass="min-w-[1100px]"
                colSpan={8}
                isEmpty={!detail || detail.topStrategies.length === 0}
                emptyText="任务完成后展示TopN策略"
              >
                {(detail?.topStrategies ?? []).map((row) => (
                  <TableRow key={row.comboId} className="border-b border-gray-100 dark:border-gray-800">
                    <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 dark:text-white">#{row.rank}</TableCell>
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
              <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">当前市场 Top20 可转债</h3>
            </div>
            <div className="p-5">
              <ScrollableDataTable
                headers={["排名", "转债代码", "转债名称", "现价", "转股溢价率", "双低", "成交额(万)", "评分"]}
                minTableWidthClass="min-w-[980px]"
                colSpan={8}
                isEmpty={!detail || detail.topBonds.length === 0}
                emptyText="任务完成后按最优策略实时计算Top20"
              >
                {(detail?.topBonds ?? []).map((row) => (
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

export default function CbQuantBacktestEvaluationPage() {
  return (
    <Suspense
      fallback={
        <CbQuantPageShell
          title="回测评估行动页"
          subtitle="多选策略后批量创建回测任务，系统轮询进度并输出最优策略与当前Top20。"
        >
          <div className="rounded-xl border border-gray-200 bg-white px-5 py-10 text-sm text-gray-500 dark:border-gray-800 dark:bg-white/[0.03] dark:text-gray-400">
            加载中...
          </div>
        </CbQuantPageShell>
      }
    >
      <CbQuantBacktestEvaluationContent />
    </Suspense>
  );
}
