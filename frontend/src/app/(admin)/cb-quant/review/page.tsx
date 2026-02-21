"use client";

import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import WorkbenchHeader from "@/components/cb-quant/WorkbenchHeader";
import {
  attributionRows,
  deviationRows,
  ticketRows,
} from "@/components/cb-quant/mockData";
import { downloadCsv, getPagedRows, getTotalPages } from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import React, { useEffect, useMemo, useRef, useState } from "react";

const tabs = [
  { key: "attribution", title: "收益归因" },
  { key: "deviation", title: "执行偏差" },
  { key: "tickets", title: "问题台账" },
] as const;

const pageSizeOptions = [5, 10, 20];

function getSeverityTone(severity: "high" | "medium" | "low") {
  if (severity === "high") return "red" as const;
  if (severity === "medium") return "yellow" as const;
  return "green" as const;
}

function getTicketTone(status: "open" | "in_progress" | "closed") {
  if (status === "open") return "red" as const;
  if (status === "in_progress") return "yellow" as const;
  return "green" as const;
}

function getReasonTone(reason: "liquidity" | "delay" | "rejected" | "manual") {
  if (reason === "liquidity") return "yellow" as const;
  if (reason === "delay") return "blue" as const;
  if (reason === "rejected") return "red" as const;
  return "slate" as const;
}

export default function CbQuantReviewPage() {
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]["key"]>("attribution");
  const [search, setSearch] = useState<string>("");
  const [showFilter, setShowFilter] = useState<boolean>(false);
  const [periodFilter, setPeriodFilter] = useState<string>("all");
  const [reasonFilter, setReasonFilter] = useState<string>("all");
  const [ticketStatusFilter, setTicketStatusFilter] = useState<string>("all");
  const [pageSize, setPageSize] = useState<number>(5);
  const [attributionPage, setAttributionPage] = useState<number>(1);
  const [deviationPage, setDeviationPage] = useState<number>(1);
  const [ticketPage, setTicketPage] = useState<number>(1);
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

  const filteredAttribution = useMemo(() => {
    return attributionRows.filter((row) => {
      const hitKeyword = !keyword || row.strategy.toLowerCase().includes(keyword);
      const hitPeriod = periodFilter === "all" || row.period === periodFilter;
      return hitKeyword && hitPeriod;
    });
  }, [keyword, periodFilter]);

  const filteredDeviation = useMemo(() => {
    return deviationRows.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.orderId.toLowerCase().includes(keyword) ||
        row.symbol.toLowerCase().includes(keyword);
      const hitReason = reasonFilter === "all" || row.reason === reasonFilter;
      return hitKeyword && hitReason;
    });
  }, [keyword, reasonFilter]);

  const filteredTickets = useMemo(() => {
    return ticketRows.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.ticketId.toLowerCase().includes(keyword) ||
        row.owner.toLowerCase().includes(keyword) ||
        row.summary.toLowerCase().includes(keyword);
      const hitStatus = ticketStatusFilter === "all" || row.status === ticketStatusFilter;
      return hitKeyword && hitStatus;
    });
  }, [keyword, ticketStatusFilter]);

  const attributionTotalPages = getTotalPages(filteredAttribution.length, pageSize);
  const deviationTotalPages = getTotalPages(filteredDeviation.length, pageSize);
  const ticketTotalPages = getTotalPages(filteredTickets.length, pageSize);

  useEffect(() => {
    if (attributionPage > attributionTotalPages) setAttributionPage(attributionTotalPages);
  }, [attributionPage, attributionTotalPages]);

  useEffect(() => {
    if (deviationPage > deviationTotalPages) setDeviationPage(deviationTotalPages);
  }, [deviationPage, deviationTotalPages]);

  useEffect(() => {
    if (ticketPage > ticketTotalPages) setTicketPage(ticketTotalPages);
  }, [ticketPage, ticketTotalPages]);

  const pagedAttribution = getPagedRows(filteredAttribution, attributionPage, pageSize);
  const pagedDeviation = getPagedRows(filteredDeviation, deviationPage, pageSize);
  const pagedTickets = getPagedRows(filteredTickets, ticketPage, pageSize);

  const weeklyPnl = attributionRows
    .filter((row) => row.period === "weekly")
    .reduce((sum, row) => sum + row.pnlWan, 0);
  const avgSlippage = deviationRows.length
    ? deviationRows.reduce((sum, row) => sum + row.slippageBp, 0) / deviationRows.length
    : 0;
  const openTickets = ticketRows.filter((row) => row.status !== "closed").length;
  const unresolvedDeviation = deviationRows.filter((row) => !row.resolved).length;

  const searchPlaceholder =
    activeTab === "attribution"
      ? "Search strategy..."
      : activeTab === "deviation"
      ? "Search order/symbol..."
      : "Search ticket/owner/summary...";

  const onExport = () => {
    const date = new Date().toISOString().slice(0, 10);

    if (activeTab === "attribution") {
      downloadCsv(
        `cb-quant-review-attribution-${date}.csv`,
        ["策略", "周期", "收益(万)", "正股贡献", "转债贡献", "择时贡献", "成本贡献"],
        filteredAttribution.map((row) => [
          row.strategy,
          row.period,
          row.pnlWan,
          `${(row.stockContribution * 100).toFixed(1)}%`,
          `${(row.bondContribution * 100).toFixed(1)}%`,
          `${(row.timingContribution * 100).toFixed(1)}%`,
          `${(row.costContribution * 100).toFixed(1)}%`,
        ])
      );
      return;
    }

    if (activeTab === "deviation") {
      downloadCsv(
        `cb-quant-review-deviation-${date}.csv`,
        ["订单ID", "代码", "预期价", "成交价", "滑点(bp)", "原因", "已处理", "时间"],
        filteredDeviation.map((row) => [
          row.orderId,
          row.symbol,
          row.expectedPrice,
          row.filledPrice,
          row.slippageBp,
          row.reason,
          row.resolved ? "yes" : "no",
          row.time,
        ])
      );
      return;
    }

    downloadCsv(
      `cb-quant-review-tickets-${date}.csv`,
      ["工单ID", "类型", "严重级别", "状态", "负责人", "摘要", "更新时间"],
      filteredTickets.map((row) => [
        row.ticketId,
        row.type,
        row.severity,
        row.status,
        row.owner,
        row.summary,
        row.updatedAt,
      ])
    );
  };

  const filterPanel = (
    <div className="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-gray-200 bg-white p-4 shadow-lg dark:border-gray-700 dark:bg-gray-800">
      <div className="space-y-4">
        {activeTab === "attribution" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">归因周期</label>
            <select
              value={periodFilter}
              onChange={(event) => {
                setPeriodFilter(event.target.value);
                setAttributionPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="weekly">weekly</option>
              <option value="monthly">monthly</option>
            </select>
          </div>
        )}

        {activeTab === "deviation" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">偏差原因</label>
            <select
              value={reasonFilter}
              onChange={(event) => {
                setReasonFilter(event.target.value);
                setDeviationPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="liquidity">liquidity</option>
              <option value="delay">delay</option>
              <option value="rejected">rejected</option>
              <option value="manual">manual</option>
            </select>
          </div>
        )}

        {activeTab === "tickets" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">工单状态</label>
            <select
              value={ticketStatusFilter}
              onChange={(event) => {
                setTicketStatusFilter(event.target.value);
                setTicketPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="open">open</option>
              <option value="in_progress">in_progress</option>
              <option value="closed">closed</option>
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
              setAttributionPage(1);
              setDeviationPage(1);
              setTicketPage(1);
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
      title="反馈复盘行动页"
      subtitle="收益归因、执行偏差、问题台账统一复盘，沉淀可操作问题并推动下一轮优化。"
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">周度累计收益</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{weeklyPnl.toFixed(1)} 万</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">平均滑点</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{avgSlippage.toFixed(1)}bp</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">未关闭工单</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{openTickets}</p>
        </div>
        <div className="rounded-2xl border border-red-200 bg-red-50 p-5 dark:border-red-700/40 dark:bg-red-500/10">
          <p className="text-sm text-red-700 dark:text-red-300">未解决偏差</p>
          <p className="mt-2 text-2xl font-semibold text-red-700 dark:text-red-300">{unresolvedDeviation}</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <WorkbenchHeader
          title="复盘工作台"
          description="筛选异常、导出台账、推动问题闭环"
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
          searchPlaceholder={searchPlaceholder}
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value);
            setAttributionPage(1);
            setDeviationPage(1);
            setTicketPage(1);
          }}
          filterOpen={showFilter}
          onToggleFilter={() => setShowFilter((prev) => !prev)}
          filterPanel={filterPanel}
          filterRef={filterRef}
          onExport={onExport}
        />

        {activeTab === "attribution" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["策略", "周期", "收益(万)", "正股贡献", "转债贡献", "择时贡献", "成本贡献"]}
              minTableWidthClass="min-w-[1220px]"
              colSpan={7}
              isEmpty={pagedAttribution.length === 0}
            >
              {pagedAttribution.map((row, index) => (
                <TableRow key={`${row.strategy}-${index}`} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-medium text-gray-900 whitespace-nowrap dark:text-white">{row.strategy}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.period} tone={row.period === "weekly" ? "blue" : "green"} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-green-700 whitespace-nowrap dark:text-green-300">{row.pnlWan.toFixed(1)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{(row.stockContribution * 100).toFixed(1)}%</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{(row.bondContribution * 100).toFixed(1)}%</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{(row.timingContribution * 100).toFixed(1)}%</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-red-700 whitespace-nowrap dark:text-red-300">{(row.costContribution * 100).toFixed(1)}%</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredAttribution.length}
              currentPage={attributionPage}
              totalPages={attributionTotalPages}
              onPageChange={setAttributionPage}
            />
          </div>
        )}

        {activeTab === "deviation" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["订单ID", "代码", "预期价", "成交价", "滑点(bp)", "原因", "处理状态", "时间"]}
              minTableWidthClass="min-w-[1250px]"
              colSpan={8}
              isEmpty={pagedDeviation.length === 0}
            >
              {pagedDeviation.map((row) => (
                <TableRow key={row.orderId} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.orderId}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.symbol}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.expectedPrice.toFixed(2)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.filledPrice ? row.filledPrice.toFixed(2) : "--"}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-red-700 whitespace-nowrap dark:text-red-300">{row.slippageBp.toFixed(1)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.reason} tone={getReasonTone(row.reason)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.resolved ? "resolved" : "pending"} tone={row.resolved ? "green" : "yellow"} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.time}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredDeviation.length}
              currentPage={deviationPage}
              totalPages={deviationTotalPages}
              onPageChange={setDeviationPage}
            />
          </div>
        )}

        {activeTab === "tickets" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["工单ID", "类型", "严重级别", "状态", "负责人", "摘要", "更新时间"]}
              minTableWidthClass="min-w-[1220px]"
              colSpan={7}
              isEmpty={pagedTickets.length === 0}
            >
              {pagedTickets.map((row) => (
                <TableRow key={row.ticketId} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.ticketId}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.type}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.severity} tone={getSeverityTone(row.severity)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.status} tone={getTicketTone(row.status)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.owner}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{row.summary}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.updatedAt}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredTickets.length}
              currentPage={ticketPage}
              totalPages={ticketTotalPages}
              onPageChange={setTicketPage}
            />
          </div>
        )}
      </div>
    </CbQuantPageShell>
  );
}
