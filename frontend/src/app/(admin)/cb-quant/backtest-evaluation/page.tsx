"use client";

import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import WorkbenchHeader from "@/components/cb-quant/WorkbenchHeader";
import {
  backtestCompareRows,
  backtestJobs,
  backtestLeaderboard,
} from "@/components/cb-quant/mockData";
import { downloadCsv, getPagedRows, getTotalPages } from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import React, { useEffect, useMemo, useRef, useState } from "react";

const tabs = [
  { key: "jobs", title: "任务队列" },
  { key: "leaderboard", title: "结果榜单" },
  { key: "compare", title: "策略对比" },
] as const;

const pageSizeOptions = [5, 10, 20];

function getJobTone(status: "queued" | "running" | "finished" | "failed") {
  if (status === "queued") return "yellow" as const;
  if (status === "running") return "blue" as const;
  if (status === "finished") return "green" as const;
  return "red" as const;
}

function getWindowTone(windowName: "full" | "3y" | "1y") {
  if (windowName === "full") return "blue" as const;
  if (windowName === "3y") return "green" as const;
  return "yellow" as const;
}

function toPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

export default function CbQuantBacktestEvaluationPage() {
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]["key"]>("jobs");
  const [search, setSearch] = useState<string>("");
  const [showFilter, setShowFilter] = useState<boolean>(false);
  const [jobStatus, setJobStatus] = useState<string>("all");
  const [leaderboardWindow, setLeaderboardWindow] = useState<string>("all");
  const [compareCategory, setCompareCategory] = useState<string>("all");
  const [pageSize, setPageSize] = useState<number>(5);
  const [jobPage, setJobPage] = useState<number>(1);
  const [leaderboardPage, setLeaderboardPage] = useState<number>(1);
  const [comparePage, setComparePage] = useState<number>(1);
  const filterRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClickOutside = (event: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(event.target as Node)) {
        setShowFilter(false);
      }
    };
    document.addEventListener("click", onClickOutside);
    return () => document.removeEventListener("click", onClickOutside);
  }, []);

  useEffect(() => {
    setShowFilter(false);
  }, [activeTab]);

  const keyword = search.trim().toLowerCase();

  const filteredJobs = useMemo(() => {
    return backtestJobs.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.jobId.toLowerCase().includes(keyword) ||
        row.strategyId.toLowerCase().includes(keyword) ||
        row.comboId.toLowerCase().includes(keyword) ||
        row.template.toLowerCase().includes(keyword) ||
        row.worker.toLowerCase().includes(keyword);
      const hitStatus = jobStatus === "all" || row.status === jobStatus;
      return hitKeyword && hitStatus;
    });
  }, [keyword, jobStatus]);

  const filteredLeaderboard = useMemo(() => {
    return backtestLeaderboard.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.strategyId.toLowerCase().includes(keyword) ||
        row.comboId.toLowerCase().includes(keyword) ||
        row.template.toLowerCase().includes(keyword);
      const hitWindow = leaderboardWindow === "all" || row.window === leaderboardWindow;
      return hitKeyword && hitWindow;
    });
  }, [keyword, leaderboardWindow]);

  const filteredCompare = useMemo(() => {
    return backtestCompareRows.filter((row) => {
      const hitKeyword = !keyword || row.metric.toLowerCase().includes(keyword);
      const hitCategory = compareCategory === "all" || row.category === compareCategory;
      return hitKeyword && hitCategory;
    });
  }, [keyword, compareCategory]);

  const jobTotalPages = getTotalPages(filteredJobs.length, pageSize);
  const leaderboardTotalPages = getTotalPages(filteredLeaderboard.length, pageSize);
  const compareTotalPages = getTotalPages(filteredCompare.length, pageSize);

  useEffect(() => {
    if (jobPage > jobTotalPages) setJobPage(jobTotalPages);
  }, [jobPage, jobTotalPages]);

  useEffect(() => {
    if (leaderboardPage > leaderboardTotalPages) setLeaderboardPage(leaderboardTotalPages);
  }, [leaderboardPage, leaderboardTotalPages]);

  useEffect(() => {
    if (comparePage > compareTotalPages) setComparePage(compareTotalPages);
  }, [comparePage, compareTotalPages]);

  const pagedJobs = getPagedRows(filteredJobs, jobPage, pageSize);
  const pagedLeaderboard = getPagedRows(filteredLeaderboard, leaderboardPage, pageSize);
  const pagedCompare = getPagedRows(filteredCompare, comparePage, pageSize);

  const runningJobs = backtestJobs.filter((row) => row.status === "running").length;
  const finishedJobs = backtestJobs.filter((row) => row.status === "finished").length;
  const failedJobs = backtestJobs.filter((row) => row.status === "failed").length;
  const topCagr = Math.max(...backtestLeaderboard.map((row) => row.cagr));

  const searchPlaceholder =
    activeTab === "jobs"
      ? "Search job/strategy/combo/worker..."
      : activeTab === "leaderboard"
      ? "Search strategy/combo/template..."
      : "Search metric name...";

  const onExport = () => {
    const date = new Date().toISOString().slice(0, 10);

    if (activeTab === "jobs") {
      downloadCsv(
        `cb-quant-backtest-jobs-${date}.csv`,
        ["任务ID", "策略ID", "组合ID", "模板", "窗口", "状态", "进度", "开始时间", "ETA", "Worker"],
        filteredJobs.map((row) => [
          row.jobId,
          row.strategyId,
          row.comboId,
          row.template,
          row.window,
          row.status,
          `${row.progress}%`,
          row.startedAt,
          row.eta,
          row.worker,
        ])
      );
      return;
    }

    if (activeTab === "leaderboard") {
      downloadCsv(
        `cb-quant-backtest-leaderboard-${date}.csv`,
        ["排名", "策略ID", "组合ID", "模板", "CAGR", "MDD", "Calmar", "胜率", "换手", "近1年", "稳健分", "窗口"],
        filteredLeaderboard.map((row) => [
          row.rank,
          row.strategyId,
          row.comboId,
          row.template,
          toPercent(row.cagr),
          toPercent(row.mdd),
          row.calmar,
          `${row.winRate.toFixed(1)}%`,
          `${(row.turnover * 100).toFixed(1)}%`,
          toPercent(row.recent1y),
          row.robustScore.toFixed(1),
          row.window,
        ])
      );
      return;
    }

    downloadCsv(
      `cb-quant-backtest-compare-${date}.csv`,
      ["指标", "分类", "Baseline", "Candidate A", "Candidate B", "Candidate C"],
      filteredCompare.map((row) => [
        row.metric,
        row.category,
        row.baseline,
        row.candidateA,
        row.candidateB,
        row.candidateC,
      ])
    );
  };

  const filterPanel = (
    <div className="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-gray-200 bg-white p-4 shadow-lg dark:border-gray-700 dark:bg-gray-800">
      <div className="space-y-4">
        {activeTab === "jobs" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">任务状态</label>
            <select
              value={jobStatus}
              onChange={(event) => {
                setJobStatus(event.target.value);
                setJobPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="queued">queued</option>
              <option value="running">running</option>
              <option value="finished">finished</option>
              <option value="failed">failed</option>
            </select>
          </div>
        )}

        {activeTab === "leaderboard" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">评估窗口</label>
            <select
              value={leaderboardWindow}
              onChange={(event) => {
                setLeaderboardWindow(event.target.value);
                setLeaderboardPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="full">full</option>
              <option value="3y">3y</option>
              <option value="1y">1y</option>
            </select>
          </div>
        )}

        {activeTab === "compare" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">指标分类</label>
            <select
              value={compareCategory}
              onChange={(event) => {
                setCompareCategory(event.target.value);
                setComparePage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="return">return</option>
              <option value="risk">risk</option>
              <option value="trade">trade</option>
            </select>
          </div>
        )}

        <div>
          <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">每页条数</label>
          <select
            value={String(pageSize)}
            onChange={(event) => {
              const nextPageSize = Number(event.target.value);
              setPageSize(nextPageSize);
              setJobPage(1);
              setLeaderboardPage(1);
              setComparePage(1);
            }}
            className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>{`每页 ${size} 条`}</option>
            ))}
          </select>
        </div>
      </div>
      <button
        type="button"
        onClick={() => setShowFilter(false)}
        className="bg-brand-500 hover:bg-brand-600 mt-4 h-10 w-full rounded-lg text-sm font-medium text-white"
      >
        Apply
      </button>
    </div>
  );

  return (
    <CbQuantPageShell
      title="回测评估行动页"
      subtitle="任务队列、结果榜单和策略对比统一管理，先看任务状态，再用多窗口指标筛选 TopN。"
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">运行中任务</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{runningJobs}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">完成任务</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{finishedJobs}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">失败任务</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{failedJobs}</p>
        </div>
        <div className="rounded-2xl border border-green-200 bg-green-50 p-5 dark:border-green-700/40 dark:bg-green-500/10">
          <p className="text-sm text-green-700 dark:text-green-300">当前最高 CAGR</p>
          <p className="mt-2 text-2xl font-semibold text-green-700 dark:text-green-300">{toPercent(topCagr)}</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <WorkbenchHeader
          title="回测任务中心"
          description="支持任务筛选、结果导出与策略横向对比"
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
          searchPlaceholder={searchPlaceholder}
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value);
            setJobPage(1);
            setLeaderboardPage(1);
            setComparePage(1);
          }}
          filterOpen={showFilter}
          onToggleFilter={() => setShowFilter((prev) => !prev)}
          filterPanel={filterPanel}
          filterRef={filterRef}
          onExport={onExport}
        />

        {activeTab === "jobs" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["任务ID", "策略ID", "组合ID", "模板", "窗口", "状态", "进度", "开始时间", "ETA", "Worker"]}
              minTableWidthClass="min-w-[1520px]"
              colSpan={10}
              isEmpty={pagedJobs.length === 0}
            >
              {pagedJobs.map((row) => (
                <TableRow key={row.jobId} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.jobId}</TableCell>
                  <TableCell className="px-4 py-3 text-sm font-medium text-gray-900 whitespace-nowrap dark:text-white">{row.strategyId}</TableCell>
                  <TableCell className="px-4 py-3 text-sm font-medium text-gray-900 whitespace-nowrap dark:text-white">{row.comboId}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.template}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.window}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.status} tone={getJobTone(row.status)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.progress}%</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.startedAt}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.eta}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.worker}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredJobs.length}
              currentPage={jobPage}
              totalPages={jobTotalPages}
              onPageChange={setJobPage}
            />
          </div>
        )}

        {activeTab === "leaderboard" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["排名", "策略ID", "组合ID", "模板", "CAGR", "MDD", "Calmar", "胜率", "换手", "近1年", "稳健分", "窗口"]}
              minTableWidthClass="min-w-[1680px]"
              colSpan={12}
              isEmpty={pagedLeaderboard.length === 0}
            >
              {pagedLeaderboard.map((row) => (
                <TableRow key={row.strategyId} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">#{row.rank}</TableCell>
                  <TableCell className="px-4 py-3 text-sm font-medium text-gray-900 whitespace-nowrap dark:text-white">{row.strategyId}</TableCell>
                  <TableCell className="px-4 py-3 text-sm font-medium text-gray-900 whitespace-nowrap dark:text-white">{row.comboId}</TableCell>
                  <TableCell className="px-4 py-3 text-sm font-medium text-gray-900 whitespace-nowrap dark:text-white">{row.template}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-green-700 whitespace-nowrap dark:text-green-300">{toPercent(row.cagr)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-red-700 whitespace-nowrap dark:text-red-300">{toPercent(row.mdd)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.calmar.toFixed(2)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.winRate.toFixed(1)}%</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{(row.turnover * 100).toFixed(1)}%</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{toPercent(row.recent1y)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.robustScore.toFixed(1)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.window} tone={getWindowTone(row.window)} />
                  </TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredLeaderboard.length}
              currentPage={leaderboardPage}
              totalPages={leaderboardTotalPages}
              onPageChange={setLeaderboardPage}
            />
          </div>
        )}

        {activeTab === "compare" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["指标", "分类", "Baseline", "Candidate A", "Candidate B", "Candidate C"]}
              minTableWidthClass="min-w-[1120px]"
              colSpan={6}
              isEmpty={pagedCompare.length === 0}
            >
              {pagedCompare.map((row) => (
                <TableRow key={row.metric} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.metric}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.category} tone={row.category === "risk" ? "red" : row.category === "return" ? "green" : "slate"} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.baseline.toFixed(3)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.candidateA.toFixed(3)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.candidateB.toFixed(3)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.candidateC.toFixed(3)}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredCompare.length}
              currentPage={comparePage}
              totalPages={compareTotalPages}
              onPageChange={setComparePage}
            />
          </div>
        )}
      </div>
    </CbQuantPageShell>
  );
}
