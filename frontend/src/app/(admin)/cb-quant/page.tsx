"use client";

import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import WorkbenchHeader from "@/components/cb-quant/WorkbenchHeader";
import { actionRows, alertRows, pipelineRows } from "@/components/cb-quant/mockData";
import { downloadCsv, getPagedRows, getTotalPages } from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import React, { useEffect, useMemo, useRef, useState } from "react";

const tabs = [
  { key: "pipeline", title: "流程看板" },
  { key: "alerts", title: "风险告警" },
  { key: "actions", title: "最近动作" },
] as const;

const pageSizeOptions = [5, 10, 20];

function getPipelineTone(status: "ready" | "running" | "blocked") {
  if (status === "ready") return "green" as const;
  if (status === "running") return "blue" as const;
  return "red" as const;
}

function getAlertTone(level: "high" | "medium" | "low") {
  if (level === "high") return "red" as const;
  if (level === "medium") return "yellow" as const;
  return "green" as const;
}

function getActionTone(result: "success" | "running" | "failed") {
  if (result === "success") return "green" as const;
  if (result === "running") return "blue" as const;
  return "red" as const;
}

export default function CbQuantOverviewPage() {
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]["key"]>("pipeline");
  const [search, setSearch] = useState<string>("");
  const [showFilter, setShowFilter] = useState<boolean>(false);
  const [pipelineStatus, setPipelineStatus] = useState<string>("all");
  const [alertLevel, setAlertLevel] = useState<string>("all");
  const [actionResult, setActionResult] = useState<string>("all");
  const [pageSize, setPageSize] = useState<number>(5);
  const [pipelinePage, setPipelinePage] = useState<number>(1);
  const [alertPage, setAlertPage] = useState<number>(1);
  const [actionPage, setActionPage] = useState<number>(1);
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

  const filteredPipeline = useMemo(() => {
    return pipelineRows.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.stage.toLowerCase().includes(keyword) ||
        row.owner.toLowerCase().includes(keyword) ||
        row.note.toLowerCase().includes(keyword);
      const hitStatus = pipelineStatus === "all" || row.status === pipelineStatus;
      return hitKeyword && hitStatus;
    });
  }, [keyword, pipelineStatus]);

  const filteredAlerts = useMemo(() => {
    return alertRows.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.id.toLowerCase().includes(keyword) ||
        row.module.toLowerCase().includes(keyword) ||
        row.message.toLowerCase().includes(keyword) ||
        row.action.toLowerCase().includes(keyword);
      const hitLevel = alertLevel === "all" || row.level === alertLevel;
      return hitKeyword && hitLevel;
    });
  }, [keyword, alertLevel]);

  const filteredActions = useMemo(() => {
    return actionRows.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.operator.toLowerCase().includes(keyword) ||
        row.action.toLowerCase().includes(keyword) ||
        row.target.toLowerCase().includes(keyword);
      const hitResult = actionResult === "all" || row.result === actionResult;
      return hitKeyword && hitResult;
    });
  }, [keyword, actionResult]);

  const pipelineTotalPages = getTotalPages(filteredPipeline.length, pageSize);
  const alertTotalPages = getTotalPages(filteredAlerts.length, pageSize);
  const actionTotalPages = getTotalPages(filteredActions.length, pageSize);

  useEffect(() => {
    if (pipelinePage > pipelineTotalPages) setPipelinePage(pipelineTotalPages);
  }, [pipelinePage, pipelineTotalPages]);

  useEffect(() => {
    if (alertPage > alertTotalPages) setAlertPage(alertTotalPages);
  }, [alertPage, alertTotalPages]);

  useEffect(() => {
    if (actionPage > actionTotalPages) setActionPage(actionTotalPages);
  }, [actionPage, actionTotalPages]);

  const pagedPipeline = getPagedRows(filteredPipeline, pipelinePage, pageSize);
  const pagedAlerts = getPagedRows(filteredAlerts, alertPage, pageSize);
  const pagedActions = getPagedRows(filteredActions, actionPage, pageSize);

  const readyCount = pipelineRows.filter((row) => row.status === "ready").length;
  const runningCount = pipelineRows.filter((row) => row.status === "running").length;
  const blockedCount = pipelineRows.filter((row) => row.status === "blocked").length;
  const highAlertCount = alertRows.filter((row) => row.level === "high").length;

  const searchPlaceholder =
    activeTab === "pipeline"
      ? "Search stage/owner/note..."
      : activeTab === "alerts"
      ? "Search alert/module/message..."
      : "Search operator/action/target...";

  const onExport = () => {
    const date = new Date().toISOString().slice(0, 10);

    if (activeTab === "pipeline") {
      downloadCsv(
        `cb-quant-overview-pipeline-${date}.csv`,
        ["阶段", "状态", "更新时间", "负责人", "说明"],
        filteredPipeline.map((row) => [row.stage, row.status, row.updatedAt, row.owner, row.note])
      );
      return;
    }

    if (activeTab === "alerts") {
      downloadCsv(
        `cb-quant-overview-alerts-${date}.csv`,
        ["告警ID", "等级", "模块", "消息", "影响", "建议动作", "更新时间"],
        filteredAlerts.map((row) => [
          row.id,
          row.level,
          row.module,
          row.message,
          row.impact,
          row.action,
          row.updatedAt,
        ])
      );
      return;
    }

    downloadCsv(
      `cb-quant-overview-actions-${date}.csv`,
      ["时间", "操作人", "动作", "目标", "结果"],
      filteredActions.map((row) => [row.time, row.operator, row.action, row.target, row.result])
    );
  };

  const filterPanel = (
    <div className="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-gray-200 bg-white p-4 shadow-lg dark:border-gray-700 dark:bg-gray-800">
      <div className="space-y-4">
        {activeTab === "pipeline" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">流程状态</label>
            <select
              value={pipelineStatus}
              onChange={(event) => {
                setPipelineStatus(event.target.value);
                setPipelinePage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="ready">ready</option>
              <option value="running">running</option>
              <option value="blocked">blocked</option>
            </select>
          </div>
        )}

        {activeTab === "alerts" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">告警等级</label>
            <select
              value={alertLevel}
              onChange={(event) => {
                setAlertLevel(event.target.value);
                setAlertPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
          </div>
        )}

        {activeTab === "actions" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">执行结果</label>
            <select
              value={actionResult}
              onChange={(event) => {
                setActionResult(event.target.value);
                setActionPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="success">success</option>
              <option value="running">running</option>
              <option value="failed">failed</option>
            </select>
          </div>
        )}

        <div>
          <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">每页条数</label>
          <select
            value={String(pageSize)}
            onChange={(event) => {
              const newPageSize = Number(event.target.value);
              setPageSize(newPageSize);
              setPipelinePage(1);
              setAlertPage(1);
              setActionPage(1);
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
      title="CB Quant 总览"
      subtitle="交易日指挥台：聚焦流程进度、风险告警和关键操作，先定位问题再进入行动页处理。"
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">流程就绪</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{readyCount}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">正在运行</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{runningCount}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">阻塞阶段</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{blockedCount}</p>
        </div>
        <div className="rounded-2xl border border-yellow-200 bg-yellow-50 p-5 dark:border-yellow-700/40 dark:bg-yellow-500/10">
          <p className="text-sm text-yellow-700 dark:text-yellow-300">高优先告警</p>
          <p className="mt-2 text-2xl font-semibold text-yellow-700 dark:text-yellow-300">{highAlertCount}</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <WorkbenchHeader
          title="交易日运行台"
          description="实时查看流程状态、告警和操作留痕"
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
          searchPlaceholder={searchPlaceholder}
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value);
            setPipelinePage(1);
            setAlertPage(1);
            setActionPage(1);
          }}
          filterOpen={showFilter}
          onToggleFilter={() => setShowFilter((prev) => !prev)}
          filterPanel={filterPanel}
          filterRef={filterRef}
          onExport={onExport}
        />

        {activeTab === "pipeline" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["阶段", "状态", "更新时间", "负责人", "说明"]}
              minTableWidthClass="min-w-[1100px]"
              colSpan={5}
              isEmpty={pagedPipeline.length === 0}
            >
              {pagedPipeline.map((row) => (
                <TableRow key={row.stage} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.stage}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.status} tone={getPipelineTone(row.status)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.updatedAt}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.owner}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{row.note}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredPipeline.length}
              currentPage={pipelinePage}
              totalPages={pipelineTotalPages}
              onPageChange={setPipelinePage}
            />
          </div>
        )}

        {activeTab === "alerts" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["告警ID", "等级", "模块", "消息", "影响", "建议动作", "更新时间"]}
              minTableWidthClass="min-w-[1400px]"
              colSpan={7}
              isEmpty={pagedAlerts.length === 0}
            >
              {pagedAlerts.map((row) => (
                <TableRow key={row.id} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.id}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.level} tone={getAlertTone(row.level)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.module}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-200">{row.message}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{row.impact}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{row.action}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-400">{row.updatedAt}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredAlerts.length}
              currentPage={alertPage}
              totalPages={alertTotalPages}
              onPageChange={setAlertPage}
            />
          </div>
        )}

        {activeTab === "actions" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["时间", "操作人", "动作", "目标", "结果"]}
              minTableWidthClass="min-w-[1050px]"
              colSpan={5}
              isEmpty={pagedActions.length === 0}
            >
              {pagedActions.map((row) => (
                <TableRow key={`${row.time}-${row.target}`} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.time}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.operator}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-200">{row.action}</TableCell>
                  <TableCell className="px-4 py-3 text-sm font-medium text-gray-900 whitespace-nowrap dark:text-white">{row.target}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.result} tone={getActionTone(row.result)} />
                  </TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredActions.length}
              currentPage={actionPage}
              totalPages={actionTotalPages}
              onPageChange={setActionPage}
            />
          </div>
        )}
      </div>
    </CbQuantPageShell>
  );
}
