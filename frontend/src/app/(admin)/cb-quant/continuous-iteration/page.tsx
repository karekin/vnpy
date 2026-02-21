"use client";

import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import WorkbenchHeader from "@/components/cb-quant/WorkbenchHeader";
import {
  rolloutRows,
  strategyPoolRows,
  triggerRows,
} from "@/components/cb-quant/mockData";
import { downloadCsv, getPagedRows, getTotalPages } from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import React, { useEffect, useMemo, useRef, useState } from "react";

const tabs = [
  { key: "triggers", title: "触发器" },
  { key: "pool", title: "策略池" },
  { key: "rollout", title: "发布记录" },
] as const;

const pageSizeOptions = [5, 10, 20];

function getTriggerTone(status: "armed" | "fired" | "muted") {
  if (status === "armed") return "blue" as const;
  if (status === "fired") return "red" as const;
  return "slate" as const;
}

function getPoolStageTone(stage: "prod" | "watch" | "out") {
  if (stage === "prod") return "green" as const;
  if (stage === "watch") return "yellow" as const;
  return "slate" as const;
}

function getRolloutTone(result: "running" | "success" | "rollback") {
  if (result === "running") return "blue" as const;
  if (result === "success") return "green" as const;
  return "red" as const;
}

export default function CbQuantContinuousIterationPage() {
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]["key"]>("triggers");
  const [search, setSearch] = useState<string>("");
  const [showFilter, setShowFilter] = useState<boolean>(false);
  const [triggerStatusFilter, setTriggerStatusFilter] = useState<string>("all");
  const [poolStageFilter, setPoolStageFilter] = useState<string>("all");
  const [rolloutResultFilter, setRolloutResultFilter] = useState<string>("all");
  const [pageSize, setPageSize] = useState<number>(5);
  const [triggerPage, setTriggerPage] = useState<number>(1);
  const [poolPage, setPoolPage] = useState<number>(1);
  const [rolloutPage, setRolloutPage] = useState<number>(1);
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

  const filteredTriggers = useMemo(() => {
    return triggerRows.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.rule.toLowerCase().includes(keyword) ||
        row.action.toLowerCase().includes(keyword);
      const hitStatus = triggerStatusFilter === "all" || row.status === triggerStatusFilter;
      return hitKeyword && hitStatus;
    });
  }, [keyword, triggerStatusFilter]);

  const filteredPool = useMemo(() => {
    return strategyPoolRows.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.strategy.toLowerCase().includes(keyword) ||
        row.owner.toLowerCase().includes(keyword) ||
        row.nextAction.toLowerCase().includes(keyword);
      const hitStage = poolStageFilter === "all" || row.stage === poolStageFilter;
      return hitKeyword && hitStage;
    });
  }, [keyword, poolStageFilter]);

  const filteredRollout = useMemo(() => {
    return rolloutRows.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.version.toLowerCase().includes(keyword) ||
        row.operator.toLowerCase().includes(keyword);
      const hitResult = rolloutResultFilter === "all" || row.result === rolloutResultFilter;
      return hitKeyword && hitResult;
    });
  }, [keyword, rolloutResultFilter]);

  const triggerTotalPages = getTotalPages(filteredTriggers.length, pageSize);
  const poolTotalPages = getTotalPages(filteredPool.length, pageSize);
  const rolloutTotalPages = getTotalPages(filteredRollout.length, pageSize);

  useEffect(() => {
    if (triggerPage > triggerTotalPages) setTriggerPage(triggerTotalPages);
  }, [triggerPage, triggerTotalPages]);

  useEffect(() => {
    if (poolPage > poolTotalPages) setPoolPage(poolTotalPages);
  }, [poolPage, poolTotalPages]);

  useEffect(() => {
    if (rolloutPage > rolloutTotalPages) setRolloutPage(rolloutTotalPages);
  }, [rolloutPage, rolloutTotalPages]);

  const pagedTriggers = getPagedRows(filteredTriggers, triggerPage, pageSize);
  const pagedPool = getPagedRows(filteredPool, poolPage, pageSize);
  const pagedRollout = getPagedRows(filteredRollout, rolloutPage, pageSize);

  const prodCount = strategyPoolRows.filter((row) => row.stage === "prod").length;
  const watchCount = strategyPoolRows.filter((row) => row.stage === "watch").length;
  const firedCount = triggerRows.filter((row) => row.status === "fired").length;
  const runningRollout = rolloutRows.filter((row) => row.result === "running").length;

  const searchPlaceholder =
    activeTab === "triggers"
      ? "Search trigger rule/action..."
      : activeTab === "pool"
      ? "Search strategy/owner/next action..."
      : "Search rollout version/operator...";

  const onExport = () => {
    const date = new Date().toISOString().slice(0, 10);

    if (activeTab === "triggers") {
      downloadCsv(
        `cb-quant-iteration-triggers-${date}.csv`,
        ["规则", "状态", "阈值", "当前值", "命中次数", "最近触发", "动作"],
        filteredTriggers.map((row) => [
          row.rule,
          row.status,
          row.threshold,
          row.currentValue,
          row.hitCount,
          row.lastTriggered,
          row.action,
        ])
      );
      return;
    }

    if (activeTab === "pool") {
      downloadCsv(
        `cb-quant-iteration-pool-${date}.csv`,
        ["策略", "阶段", "稳健分", "CAGR", "MDD", "近3月", "下一步", "Owner"],
        filteredPool.map((row) => [
          row.strategy,
          row.stage,
          row.robustScore,
          row.cagr,
          row.mdd,
          row.recent3m,
          row.nextAction,
          row.owner,
        ])
      );
      return;
    }

    downloadCsv(
      `cb-quant-iteration-rollout-${date}.csv`,
      ["版本", "from", "to", "结果", "开始", "结束", "操作人"],
      filteredRollout.map((row) => [
        row.version,
        row.from,
        row.to,
        row.result,
        row.startAt,
        row.endAt,
        row.operator,
      ])
    );
  };

  const filterPanel = (
    <div className="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-gray-200 bg-white p-4 shadow-lg dark:border-gray-700 dark:bg-gray-800">
      <div className="space-y-4">
        {activeTab === "triggers" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">触发器状态</label>
            <select
              value={triggerStatusFilter}
              onChange={(event) => {
                setTriggerStatusFilter(event.target.value);
                setTriggerPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="armed">armed</option>
              <option value="fired">fired</option>
              <option value="muted">muted</option>
            </select>
          </div>
        )}

        {activeTab === "pool" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">策略池阶段</label>
            <select
              value={poolStageFilter}
              onChange={(event) => {
                setPoolStageFilter(event.target.value);
                setPoolPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="prod">prod</option>
              <option value="watch">watch</option>
              <option value="out">out</option>
            </select>
          </div>
        )}

        {activeTab === "rollout" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">发布结果</label>
            <select
              value={rolloutResultFilter}
              onChange={(event) => {
                setRolloutResultFilter(event.target.value);
                setRolloutPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="running">running</option>
              <option value="success">success</option>
              <option value="rollback">rollback</option>
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
              setTriggerPage(1);
              setPoolPage(1);
              setRolloutPage(1);
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
      title="持续迭代行动页"
      subtitle="触发器、策略池与发布记录联动管理，让策略升级可触发、可回退、可审计。"
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">生产池策略</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{prodCount}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">观察池策略</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{watchCount}</p>
        </div>
        <div className="rounded-2xl border border-red-200 bg-red-50 p-5 dark:border-red-700/40 dark:bg-red-500/10">
          <p className="text-sm text-red-700 dark:text-red-300">触发器命中</p>
          <p className="mt-2 text-2xl font-semibold text-red-700 dark:text-red-300">{firedCount}</p>
        </div>
        <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5 dark:border-blue-700/40 dark:bg-blue-500/10">
          <p className="text-sm text-blue-700 dark:text-blue-300">进行中发布</p>
          <p className="mt-2 text-2xl font-semibold text-blue-700 dark:text-blue-300">{runningRollout}</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <WorkbenchHeader
          title="迭代控制台"
          description="通过触发器自动发现问题，并推动策略池与发布链路更新"
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
          searchPlaceholder={searchPlaceholder}
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value);
            setTriggerPage(1);
            setPoolPage(1);
            setRolloutPage(1);
          }}
          filterOpen={showFilter}
          onToggleFilter={() => setShowFilter((prev) => !prev)}
          filterPanel={filterPanel}
          filterRef={filterRef}
          onExport={onExport}
        />

        {activeTab === "triggers" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["规则", "状态", "阈值", "当前值", "命中次数", "最近触发", "动作"]}
              minTableWidthClass="min-w-[1240px]"
              colSpan={7}
              isEmpty={pagedTriggers.length === 0}
            >
              {pagedTriggers.map((row) => (
                <TableRow key={row.rule} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-white">{row.rule}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.status} tone={getTriggerTone(row.status)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.threshold}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.currentValue}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.hitCount}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.lastTriggered}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{row.action}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredTriggers.length}
              currentPage={triggerPage}
              totalPages={triggerTotalPages}
              onPageChange={setTriggerPage}
            />
          </div>
        )}

        {activeTab === "pool" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["策略", "阶段", "稳健分", "CAGR", "MDD", "近3月", "下一步", "Owner"]}
              minTableWidthClass="min-w-[1280px]"
              colSpan={8}
              isEmpty={pagedPool.length === 0}
            >
              {pagedPool.map((row) => (
                <TableRow key={row.strategy} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.strategy}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.stage} tone={getPoolStageTone(row.stage)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.robustScore.toFixed(1)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-green-700 whitespace-nowrap dark:text-green-300">{(row.cagr * 100).toFixed(2)}%</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-red-700 whitespace-nowrap dark:text-red-300">{(row.mdd * 100).toFixed(2)}%</TableCell>
                  <TableCell className={`px-4 py-3 text-sm whitespace-nowrap ${row.recent3m >= 0 ? "text-green-700 dark:text-green-300" : "text-red-700 dark:text-red-300"}`}>
                    {row.recent3m >= 0 ? "+" : ""}
                    {(row.recent3m * 100).toFixed(2)}%
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{row.nextAction}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.owner}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredPool.length}
              currentPage={poolPage}
              totalPages={poolTotalPages}
              onPageChange={setPoolPage}
            />
          </div>
        )}

        {activeTab === "rollout" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["版本", "from", "to", "结果", "开始", "结束", "操作人"]}
              minTableWidthClass="min-w-[1080px]"
              colSpan={7}
              isEmpty={pagedRollout.length === 0}
            >
              {pagedRollout.map((row) => (
                <TableRow key={row.version} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.version}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.from}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.to}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.result} tone={getRolloutTone(row.result)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.startAt}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.endAt}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap dark:text-gray-300">{row.operator}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredRollout.length}
              currentPage={rolloutPage}
              totalPages={rolloutTotalPages}
              onPageChange={setRolloutPage}
            />
          </div>
        )}
      </div>
    </CbQuantPageShell>
  );
}
