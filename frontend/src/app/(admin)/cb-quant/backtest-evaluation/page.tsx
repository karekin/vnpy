"use client";

import BacktestConfigPanel, {
  BacktestQueuePayload,
  EvalWindow,
} from "@/components/cb-quant/BacktestConfigPanel";
import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import WorkbenchHeader from "@/components/cb-quant/WorkbenchHeader";
import {
  backtestCompareRows,
  backtestJobs,
  backtestLeaderboard,
  strategyCandidates,
  type BacktestJobRow,
} from "@/components/cb-quant/mockData";
import {
  downloadCsv,
  getPagedRows,
  getTotalPages,
} from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import React, { useEffect, useMemo, useRef, useState } from "react";

const sectionTabs = [
  {
    key: "config",
    title: "回测配置",
    subtitle: "先定义非打分规则并生成规则包",
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 20 20"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M4.83203 2.5835C3.58939 2.5835 2.58203 3.59085 2.58203 4.83349V7.25015C2.58203 8.49279 3.58939 9.50015 4.83203 9.50015H7.2487C8.49134 9.50015 9.4987 8.49279 9.4987 7.25015V4.8335C9.4987 3.59086 8.49134 2.5835 7.2487 2.5835H4.83203ZM4.08203 4.83349C4.08203 4.41928 4.41782 4.0835 4.83203 4.0835H7.2487C7.66291 4.0835 7.9987 4.41928 7.9987 4.8335V7.25015C7.9987 7.66436 7.66291 8.00015 7.2487 8.00015H4.83203C4.41782 8.00015 4.08203 7.66436 4.08203 7.25015V4.83349ZM10.4987 4.83349C10.4987 3.59085 11.5061 2.5835 12.7487 2.5835H15.1654C16.408 2.5835 17.4154 3.59086 17.4154 4.8335V7.25015C17.4154 8.49279 16.408 9.50015 15.1654 9.50015H12.7487C11.5061 9.50015 10.4987 8.49279 10.4987 7.25015V4.83349ZM12.7487 4.0835C12.3345 4.0835 11.9987 4.41928 11.9987 4.83349V7.25015C11.9987 7.66436 12.3345 8.00015 12.7487 8.00015H15.1654C15.5796 8.00015 15.9154 7.66436 15.9154 7.25015V4.8335C15.9154 4.41928 15.5796 4.0835 15.1654 4.0835H12.7487ZM4.83203 10.5002C3.58939 10.5002 2.58203 11.5075 2.58203 12.7502V15.1668C2.58203 16.4095 3.58939 17.4168 4.83203 17.4168H7.2487C8.49134 17.4168 9.4987 16.4095 9.4987 15.1668V12.7502C9.4987 11.5075 8.49134 10.5002 7.2487 10.5002H4.83203ZM4.08203 12.7502C4.08203 12.336 4.41782 12.0002 4.83203 12.0002H7.2487C7.66291 12.0002 7.9987 12.336 7.9987 12.7502V15.1668C7.9987 15.5811 7.66291 15.9168 7.2487 15.9168H4.83203C4.41782 15.9168 4.08203 15.5811 4.08203 15.1668V12.7502ZM12.7487 10.5002C11.5061 10.5002 10.4987 11.5075 10.4987 12.7502V15.1668C10.4987 16.4095 11.5061 17.4168 12.7487 17.4168H15.1654C16.408 17.4168 17.4154 16.4095 17.4154 15.1668V12.7502C17.4154 11.5075 16.408 10.5002 15.1654 10.5002H12.7487ZM11.9987 12.7502C11.9987 12.336 12.3345 12.0002 12.7487 12.0002H15.1654C15.5796 12.0002 15.9154 12.336 15.9154 12.7502V15.1668C15.9154 15.5811 15.5796 15.9168 15.1654 15.9168H12.7487C12.3345 15.9168 11.9987 15.5811 11.9987 15.1668V12.7502Z"
          fill="currentColor"
        />
      </svg>
    ),
  },
  {
    key: "tasks",
    title: "回测任务",
    subtitle: "查看队列进度、榜单和策略对比",
    icon: (
      <svg
        width="20"
        height="20"
        viewBox="0 0 20 20"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M10.7487 2.29248C10.7487 1.87827 10.4129 1.54248 9.9987 1.54248C9.58448 1.54248 9.2487 1.87827 9.2487 2.29248V2.83613C6.08132 3.20733 3.6237 5.9004 3.6237 9.16748V14.4591H3.33203C2.91782 14.4591 2.58203 14.7949 2.58203 15.2091C2.58203 15.6234 2.91782 15.9591 3.33203 15.9591H4.3737H15.6237H16.6654C17.0796 15.9591 17.4154 15.6234 17.4154 15.2091C17.4154 14.7949 17.0796 14.4591 16.6654 14.4591H16.3737V9.16748C16.3737 5.9004 13.9161 3.20733 10.7487 2.83613V2.29248ZM14.8737 14.4591V9.16748C14.8737 6.47509 12.6911 4.29248 9.9987 4.29248C7.30631 4.29248 5.1237 6.47509 5.1237 9.16748V14.4591H14.8737ZM7.9987 17.7085C7.9987 18.1228 8.33448 18.4585 8.7487 18.4585H11.2487C11.6629 18.4585 11.9987 18.1228 11.9987 17.7085C11.9987 17.2943 11.6629 16.9585 11.2487 16.9585H8.7487C8.33448 16.9585 7.9987 17.2943 7.9987 17.7085Z"
          fill="currentColor"
        />
      </svg>
    ),
  },
] as const;

const taskTabs = [
  { key: "jobs", title: "任务队列" },
  { key: "leaderboard", title: "结果榜单" },
  { key: "compare", title: "策略对比" },
] as const;

const pageSizeOptions = [5, 10, 20];
const workers = ["wk-01", "wk-02", "wk-03", "wk-04", "wk-05"];

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

function mapEvalWindow(windowName: EvalWindow): string {
  if (windowName === "full") return "2018-2025";
  if (windowName === "3y") return "近3年";
  return "近1年";
}

function getNowTimeLabel(date: Date): string {
  return date.toTimeString().slice(0, 8);
}

function getDateStamp(date: Date): string {
  return date.toISOString().slice(0, 10).replace(/-/g, "");
}

export default function CbQuantBacktestEvaluationPage() {
  const [jobs, setJobs] = useState<BacktestJobRow[]>(backtestJobs);
  const [activeSection, setActiveSection] = useState<
    (typeof sectionTabs)[number]["key"]
  >("config");
  const [activeTaskTab, setActiveTaskTab] = useState<
    (typeof taskTabs)[number]["key"]
  >("jobs");

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
  }, [activeTaskTab, activeSection]);

  const keyword = search.trim().toLowerCase();

  const filteredJobs = useMemo(() => {
    return jobs.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.jobId.toLowerCase().includes(keyword) ||
        row.strategyId.toLowerCase().includes(keyword) ||
        row.comboId.toLowerCase().includes(keyword) ||
        row.rulePackId.toLowerCase().includes(keyword) ||
        row.template.toLowerCase().includes(keyword) ||
        row.worker.toLowerCase().includes(keyword);
      const hitStatus = jobStatus === "all" || row.status === jobStatus;
      return hitKeyword && hitStatus;
    });
  }, [jobs, keyword, jobStatus]);

  const filteredLeaderboard = useMemo(() => {
    return backtestLeaderboard.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.strategyId.toLowerCase().includes(keyword) ||
        row.comboId.toLowerCase().includes(keyword) ||
        row.rulePackId.toLowerCase().includes(keyword) ||
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

  const runningJobs = jobs.filter((row) => row.status === "running").length;
  const queuedJobs = jobs.filter((row) => row.status === "queued").length;
  const finishedJobs = jobs.filter((row) => row.status === "finished").length;
  const rulePackCount = new Set(jobs.map((row) => row.rulePackId)).size;
  const topCagr = Math.max(...backtestLeaderboard.map((row) => row.cagr));

  const searchPlaceholder =
    activeTaskTab === "jobs"
      ? "Search job/strategy/combo/rulePack..."
      : activeTaskTab === "leaderboard"
      ? "Search strategy/combo/rulePack..."
      : "Search metric name...";

  const onExport = () => {
    const date = new Date().toISOString().slice(0, 10);

    if (activeTaskTab === "jobs") {
      downloadCsv(
        `cb-quant-backtest-jobs-${date}.csv`,
        [
          "任务ID",
          "策略ID",
          "组合ID",
          "规则包",
          "模板",
          "窗口",
          "状态",
          "进度",
          "开始时间",
          "ETA",
          "Worker",
        ],
        filteredJobs.map((row) => [
          row.jobId,
          row.strategyId,
          row.comboId,
          row.rulePackId,
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

    if (activeTaskTab === "leaderboard") {
      downloadCsv(
        `cb-quant-backtest-leaderboard-${date}.csv`,
        [
          "排名",
          "策略ID",
          "组合ID",
          "规则包",
          "模板",
          "CAGR",
          "MDD",
          "Calmar",
          "胜率",
          "换手",
          "近1年",
          "稳健分",
          "窗口",
        ],
        filteredLeaderboard.map((row) => [
          row.rank,
          row.strategyId,
          row.comboId,
          row.rulePackId,
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

  const handleQueueBacktest = (payload: BacktestQueuePayload): void => {
    const now = new Date();
    const timestamp = getNowTimeLabel(now);
    const dateStamp = getDateStamp(now);

    setJobs((previousRows) => {
      const startSeq = previousRows.length + 1;
      const nextRows: BacktestJobRow[] = payload.windows.map((windowName, index) => {
        const seq = startSeq + index;
        return {
          jobId: `BT-${dateStamp}-${String(seq).padStart(3, "0")}`,
          strategyId: `STR-${String(seq).padStart(3, "0")}`,
          comboId: payload.comboId,
          rulePackId: payload.rulePackId,
          template: payload.template,
          window: mapEvalWindow(windowName),
          status: "queued",
          progress: 0,
          startedAt: timestamp,
          eta: "--",
          worker: workers[seq % workers.length],
        };
      });

      return [...nextRows, ...previousRows];
    });

    setActiveSection("tasks");
    setActiveTaskTab("jobs");
    setSearch(payload.rulePackId);
    setJobStatus("all");
    setJobPage(1);
  };

  const filterPanel = (
    <div className="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-gray-200 bg-white p-4 shadow-lg dark:border-gray-700 dark:bg-gray-800">
      <div className="space-y-4">
        {activeTaskTab === "jobs" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">
              任务状态
            </label>
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

        {activeTaskTab === "leaderboard" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">
              评估窗口
            </label>
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

        {activeTaskTab === "compare" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">
              指标分类
            </label>
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
          <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">
            每页条数
          </label>
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
      subtitle="业务动线：先在回测配置定义 rulePack，再进入回测任务查看队列、榜单和对比结果。"
    >
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="border-b border-gray-200 px-5 pt-4 dark:border-gray-800">
          <nav className="flex space-x-2 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {sectionTabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveSection(tab.key)}
                className={`inline-flex items-center gap-2 border-b-2 px-2.5 py-2 text-sm font-medium transition-colors duration-200 ${
                  activeSection === tab.key
                    ? "text-brand-500 border-brand-500 dark:text-brand-400 dark:border-brand-400"
                    : "text-gray-500 border-transparent hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                }`}
              >
                {tab.icon}
                {tab.title}
              </button>
            ))}
          </nav>
        </div>
        <div className="px-5 py-3">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {sectionTabs.find((tab) => tab.key === activeSection)?.subtitle}
          </p>
        </div>
      </div>

      {activeSection === "config" && (
        <BacktestConfigPanel
          candidates={strategyCandidates}
          onQueueBacktest={handleQueueBacktest}
        />
      )}

      {activeSection === "tasks" && (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <p className="text-sm text-gray-500 dark:text-gray-400">运行中任务</p>
              <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{runningJobs}</p>
            </div>
            <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <p className="text-sm text-gray-500 dark:text-gray-400">排队任务</p>
              <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{queuedJobs}</p>
            </div>
            <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
              <p className="text-sm text-gray-500 dark:text-gray-400">规则包数量</p>
              <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{rulePackCount}</p>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">完成任务：{finishedJobs}</p>
            </div>
            <div className="rounded-2xl border border-green-200 bg-green-50 p-5 dark:border-green-700/40 dark:bg-green-500/10">
              <p className="text-sm text-green-700 dark:text-green-300">当前最高 CAGR</p>
              <p className="mt-2 text-2xl font-semibold text-green-700 dark:text-green-300">{toPercent(topCagr)}</p>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
            <WorkbenchHeader
              title="回测任务中心"
              description="任务筛选、结果导出与策略横向对比"
              tabs={taskTabs}
              activeTab={activeTaskTab}
              onTabChange={(tab) => setActiveTaskTab(tab)}
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

            {activeTaskTab === "jobs" && (
              <div className="p-5">
                <ScrollableDataTable
                  headers={[
                    "任务ID",
                    "策略ID",
                    "组合ID",
                    "规则包",
                    "模板",
                    "窗口",
                    "状态",
                    "进度",
                    "开始时间",
                    "ETA",
                    "Worker",
                  ]}
                  minTableWidthClass="min-w-[1720px]"
                  colSpan={11}
                  isEmpty={pagedJobs.length === 0}
                >
                  {pagedJobs.map((row) => (
                    <TableRow
                      key={row.jobId}
                      className="border-b border-gray-100 dark:border-gray-800"
                    >
                      <TableCell className="px-4 py-3 text-sm font-semibold whitespace-nowrap text-gray-900 dark:text-white">
                        {row.jobId}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm font-medium whitespace-nowrap text-gray-900 dark:text-white">
                        {row.strategyId}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm font-medium whitespace-nowrap text-gray-900 dark:text-white">
                        {row.comboId}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.rulePackId}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.template}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.window}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                        <StatusTag label={row.status} tone={getJobTone(row.status)} />
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.progress}%
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.startedAt}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-600 dark:text-gray-300">
                        {row.eta}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-600 dark:text-gray-300">
                        {row.worker}
                      </TableCell>
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

            {activeTaskTab === "leaderboard" && (
              <div className="p-5">
                <ScrollableDataTable
                  headers={[
                    "排名",
                    "策略ID",
                    "组合ID",
                    "规则包",
                    "模板",
                    "CAGR",
                    "MDD",
                    "Calmar",
                    "胜率",
                    "换手",
                    "近1年",
                    "稳健分",
                    "窗口",
                  ]}
                  minTableWidthClass="min-w-[1860px]"
                  colSpan={13}
                  isEmpty={pagedLeaderboard.length === 0}
                >
                  {pagedLeaderboard.map((row) => (
                    <TableRow
                      key={`${row.strategyId}-${row.rulePackId}`}
                      className="border-b border-gray-100 dark:border-gray-800"
                    >
                      <TableCell className="px-4 py-3 text-sm font-semibold whitespace-nowrap text-gray-900 dark:text-white">
                        #{row.rank}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm font-medium whitespace-nowrap text-gray-900 dark:text-white">
                        {row.strategyId}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm font-medium whitespace-nowrap text-gray-900 dark:text-white">
                        {row.comboId}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.rulePackId}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm font-medium whitespace-nowrap text-gray-900 dark:text-white">
                        {row.template}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-green-700 dark:text-green-300">
                        {toPercent(row.cagr)}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-red-700 dark:text-red-300">
                        {toPercent(row.mdd)}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.calmar.toFixed(2)}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.winRate.toFixed(1)}%
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {(row.turnover * 100).toFixed(1)}%
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {toPercent(row.recent1y)}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.robustScore.toFixed(1)}
                      </TableCell>
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

            {activeTaskTab === "compare" && (
              <div className="p-5">
                <ScrollableDataTable
                  headers={[
                    "指标",
                    "分类",
                    "Baseline",
                    "Candidate A",
                    "Candidate B",
                    "Candidate C",
                  ]}
                  minTableWidthClass="min-w-[1120px]"
                  colSpan={6}
                  isEmpty={pagedCompare.length === 0}
                >
                  {pagedCompare.map((row) => (
                    <TableRow
                      key={row.metric}
                      className="border-b border-gray-100 dark:border-gray-800"
                    >
                      <TableCell className="px-4 py-3 text-sm font-semibold whitespace-nowrap text-gray-900 dark:text-white">
                        {row.metric}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                        <StatusTag
                          label={row.category}
                          tone={
                            row.category === "risk"
                              ? "red"
                              : row.category === "return"
                                ? "green"
                                : "slate"
                          }
                        />
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-600 dark:text-gray-300">
                        {row.baseline.toFixed(3)}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.candidateA.toFixed(3)}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.candidateB.toFixed(3)}
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap text-gray-700 dark:text-gray-200">
                        {row.candidateC.toFixed(3)}
                      </TableCell>
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
        </>
      )}
    </CbQuantPageShell>
  );
}
