"use client";

import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import WorkbenchHeader from "@/components/cb-quant/WorkbenchHeader";
import {
  executionLogs,
  orderBlotterRows,
  rebalancePlanRows,
} from "@/components/cb-quant/mockData";
import { downloadCsv, getPagedRows, getTotalPages } from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import React, { useEffect, useMemo, useRef, useState } from "react";

const tabs = [
  { key: "plan", title: "调仓计划" },
  { key: "orders", title: "订单流水" },
  { key: "logs", title: "执行日志" },
] as const;

const pageSizeOptions = [5, 10, 20];

function getActionTone(action: "buy" | "sell" | "hold") {
  if (action === "buy") return "green" as const;
  if (action === "sell") return "red" as const;
  return "slate" as const;
}

function getPriorityTone(priority: "high" | "medium" | "low") {
  if (priority === "high") return "red" as const;
  if (priority === "medium") return "yellow" as const;
  return "green" as const;
}

function getOrderTone(status: "new" | "part_filled" | "filled" | "canceled" | "rejected") {
  if (status === "filled") return "green" as const;
  if (status === "part_filled") return "blue" as const;
  if (status === "new") return "yellow" as const;
  if (status === "canceled") return "slate" as const;
  return "red" as const;
}

function getLogTone(level: "info" | "warn" | "error") {
  if (level === "info") return "blue" as const;
  if (level === "warn") return "yellow" as const;
  return "red" as const;
}

export default function CbQuantAutoExecutionPage() {
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]["key"]>("plan");
  const [search, setSearch] = useState<string>("");
  const [showFilter, setShowFilter] = useState<boolean>(false);
  const [tradeMode, setTradeMode] = useState<string>("paper");
  const [planActionFilter, setPlanActionFilter] = useState<string>("all");
  const [orderStatusFilter, setOrderStatusFilter] = useState<string>("all");
  const [logLevelFilter, setLogLevelFilter] = useState<string>("all");
  const [pageSize, setPageSize] = useState<number>(5);
  const [planPage, setPlanPage] = useState<number>(1);
  const [orderPage, setOrderPage] = useState<number>(1);
  const [logPage, setLogPage] = useState<number>(1);
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

  const filteredPlanRows = useMemo(() => {
    return rebalancePlanRows.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.symbol.toLowerCase().includes(keyword) ||
        row.name.toLowerCase().includes(keyword);
      const hitAction = planActionFilter === "all" || row.action === planActionFilter;
      return hitKeyword && hitAction;
    });
  }, [keyword, planActionFilter]);

  const filteredOrderRows = useMemo(() => {
    return orderBlotterRows.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.orderId.toLowerCase().includes(keyword) ||
        row.symbol.toLowerCase().includes(keyword);
      const hitStatus = orderStatusFilter === "all" || row.status === orderStatusFilter;
      return hitKeyword && hitStatus;
    });
  }, [keyword, orderStatusFilter]);

  const filteredLogs = useMemo(() => {
    return executionLogs.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.source.toLowerCase().includes(keyword) ||
        row.message.toLowerCase().includes(keyword);
      const hitLevel = logLevelFilter === "all" || row.level === logLevelFilter;
      return hitKeyword && hitLevel;
    });
  }, [keyword, logLevelFilter]);

  const planTotalPages = getTotalPages(filteredPlanRows.length, pageSize);
  const orderTotalPages = getTotalPages(filteredOrderRows.length, pageSize);
  const logTotalPages = getTotalPages(filteredLogs.length, pageSize);

  useEffect(() => {
    if (planPage > planTotalPages) setPlanPage(planTotalPages);
  }, [planPage, planTotalPages]);

  useEffect(() => {
    if (orderPage > orderTotalPages) setOrderPage(orderTotalPages);
  }, [orderPage, orderTotalPages]);

  useEffect(() => {
    if (logPage > logTotalPages) setLogPage(logTotalPages);
  }, [logPage, logTotalPages]);

  const pagedPlanRows = getPagedRows(filteredPlanRows, planPage, pageSize);
  const pagedOrderRows = getPagedRows(filteredOrderRows, orderPage, pageSize);
  const pagedLogs = getPagedRows(filteredLogs, logPage, pageSize);

  const pendingOrders = orderBlotterRows.filter((row) => row.status === "new" || row.status === "part_filled").length;
  const filledOrders = orderBlotterRows.filter((row) => row.status === "filled").length;
  const fillRate = orderBlotterRows.length ? (filledOrders / orderBlotterRows.length) * 100 : 0;
  const avgSlippage = orderBlotterRows.length
    ? orderBlotterRows.reduce((sum, row) => sum + row.slippageBp, 0) / orderBlotterRows.length
    : 0;

  const searchPlaceholder =
    activeTab === "plan"
      ? "Search bond code/name..."
      : activeTab === "orders"
      ? "Search order id/symbol..."
      : "Search source/message...";

  const onExport = () => {
    const date = new Date().toISOString().slice(0, 10);

    if (activeTab === "plan") {
      downloadCsv(
        `cb-quant-execution-plan-${date}.csv`,
        ["代码", "名称", "动作", "当前权重", "目标权重", "权重差", "预计金额(万)", "优先级"],
        filteredPlanRows.map((row) => [
          row.symbol,
          row.name,
          row.action,
          `${(row.currentWeight * 100).toFixed(2)}%`,
          `${(row.targetWeight * 100).toFixed(2)}%`,
          `${(row.diffWeight * 100).toFixed(2)}%`,
          row.estAmountWan,
          row.priority,
        ])
      );
      return;
    }

    if (activeTab === "orders") {
      downloadCsv(
        `cb-quant-execution-orders-${date}.csv`,
        ["订单ID", "代码", "方向", "委托价", "委托量", "成交量", "状态", "滑点(bp)", "提交时间"],
        filteredOrderRows.map((row) => [
          row.orderId,
          row.symbol,
          row.side,
          row.price,
          row.volume,
          row.filled,
          row.status,
          row.slippageBp,
          row.submitTime,
        ])
      );
      return;
    }

    downloadCsv(
      `cb-quant-execution-logs-${date}.csv`,
      ["时间", "级别", "来源", "消息"],
      filteredLogs.map((row) => [row.time, row.level, row.source, row.message])
    );
  };

  const filterPanel = (
    <div className="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-gray-200 bg-white p-4 shadow-lg dark:border-gray-700 dark:bg-gray-800">
      <div className="space-y-4">
        <div>
          <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">交易模式</label>
          <select
            value={tradeMode}
            onChange={(event) => setTradeMode(event.target.value)}
            className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          >
            <option value="paper">paper</option>
            <option value="semi_auto">semi_auto</option>
            <option value="live">live</option>
          </select>
        </div>

        {activeTab === "plan" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">调仓动作</label>
            <select
              value={planActionFilter}
              onChange={(event) => {
                setPlanActionFilter(event.target.value);
                setPlanPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="buy">buy</option>
              <option value="sell">sell</option>
              <option value="hold">hold</option>
            </select>
          </div>
        )}

        {activeTab === "orders" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">订单状态</label>
            <select
              value={orderStatusFilter}
              onChange={(event) => {
                setOrderStatusFilter(event.target.value);
                setOrderPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="new">new</option>
              <option value="part_filled">part_filled</option>
              <option value="filled">filled</option>
              <option value="canceled">canceled</option>
              <option value="rejected">rejected</option>
            </select>
          </div>
        )}

        {activeTab === "logs" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">日志等级</label>
            <select
              value={logLevelFilter}
              onChange={(event) => {
                setLogLevelFilter(event.target.value);
                setLogPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="info">info</option>
              <option value="warn">warn</option>
              <option value="error">error</option>
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
              setPlanPage(1);
              setOrderPage(1);
              setLogPage(1);
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
      title="自动执行行动页"
      subtitle="调仓计划、订单流水和执行日志联动展示，优先跑通半自动交易，再平滑升级实盘自动化。"
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">交易模式</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 uppercase dark:text-white">{tradeMode}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">待完成订单</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{pendingOrders}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">成交完成率</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{fillRate.toFixed(1)}%</p>
        </div>
        <div className="rounded-2xl border border-yellow-200 bg-yellow-50 p-5 dark:border-yellow-700/40 dark:bg-yellow-500/10">
          <p className="text-sm text-yellow-700 dark:text-yellow-300">平均滑点</p>
          <p className="mt-2 text-2xl font-semibold text-yellow-700 dark:text-yellow-300">{avgSlippage.toFixed(1)}bp</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <WorkbenchHeader
          title="执行工作台"
          description="目标持仓差异、订单回报与执行日志统一视图"
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
          searchPlaceholder={searchPlaceholder}
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value);
            setPlanPage(1);
            setOrderPage(1);
            setLogPage(1);
          }}
          filterOpen={showFilter}
          onToggleFilter={() => setShowFilter((prev) => !prev)}
          filterPanel={filterPanel}
          filterRef={filterRef}
          onExport={onExport}
        />

        {activeTab === "plan" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["代码", "名称", "动作", "当前权重", "目标权重", "权重差", "预计金额(万)", "优先级"]}
              minTableWidthClass="min-w-[1250px]"
              colSpan={8}
              isEmpty={pagedPlanRows.length === 0}
            >
              {pagedPlanRows.map((row) => (
                <TableRow key={row.symbol} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.symbol}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.name}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.action} tone={getActionTone(row.action)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{(row.currentWeight * 100).toFixed(2)}%</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{(row.targetWeight * 100).toFixed(2)}%</TableCell>
                  <TableCell className={`px-4 py-3 text-sm whitespace-nowrap ${row.diffWeight >= 0 ? "text-green-700 dark:text-green-300" : "text-red-700 dark:text-red-300"}`}>
                    {row.diffWeight >= 0 ? "+" : ""}
                    {(row.diffWeight * 100).toFixed(2)}%
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.estAmountWan.toFixed(1)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.priority} tone={getPriorityTone(row.priority)} />
                  </TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredPlanRows.length}
              currentPage={planPage}
              totalPages={planTotalPages}
              onPageChange={setPlanPage}
            />
          </div>
        )}

        {activeTab === "orders" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["订单ID", "代码", "方向", "委托价", "委托量", "成交量", "状态", "滑点(bp)", "提交时间"]}
              minTableWidthClass="min-w-[1300px]"
              colSpan={9}
              isEmpty={pagedOrderRows.length === 0}
            >
              {pagedOrderRows.map((row) => (
                <TableRow key={row.orderId} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.orderId}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.symbol}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.side} tone={row.side === "buy" ? "green" : "red"} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.price.toFixed(2)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.volume}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.filled}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.status} tone={getOrderTone(row.status)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.slippageBp.toFixed(1)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.submitTime}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredOrderRows.length}
              currentPage={orderPage}
              totalPages={orderTotalPages}
              onPageChange={setOrderPage}
            />
          </div>
        )}

        {activeTab === "logs" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["时间", "级别", "来源", "消息"]}
              minTableWidthClass="min-w-[1080px]"
              colSpan={4}
              isEmpty={pagedLogs.length === 0}
            >
              {pagedLogs.map((row) => (
                <TableRow key={`${row.time}-${row.source}`} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.time}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.level} tone={getLogTone(row.level)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.source}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-200">{row.message}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredLogs.length}
              currentPage={logPage}
              totalPages={logTotalPages}
              onPageChange={setLogPage}
            />
          </div>
        )}
      </div>
    </CbQuantPageShell>
  );
}
