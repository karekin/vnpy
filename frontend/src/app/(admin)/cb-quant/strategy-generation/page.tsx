"use client";

import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import WorkbenchHeader from "@/components/cb-quant/WorkbenchHeader";
import {
  strategyCandidates,
  strategyParameters,
  strategyTemplates,
} from "@/components/cb-quant/mockData";
import { downloadCsv, getPagedRows, getTotalPages } from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import React, { useEffect, useMemo, useRef, useState } from "react";

const tabs = [
  { key: "templates", title: "模板库" },
  { key: "params", title: "参数空间" },
  { key: "candidates", title: "候选预览" },
] as const;

const pageSizeOptions = [5, 10, 20];

function getTemplateTone(status: "active" | "draft" | "archived") {
  if (status === "active") return "green" as const;
  if (status === "draft") return "yellow" as const;
  return "slate" as const;
}

function getGroupTone(group: "filters" | "ranking" | "portfolio" | "rebalance" | "risk") {
  if (group === "filters") return "blue" as const;
  if (group === "ranking") return "green" as const;
  if (group === "portfolio") return "yellow" as const;
  if (group === "rebalance") return "slate" as const;
  return "red" as const;
}

function getWindowTone(windowName: "full" | "3y" | "1y") {
  if (windowName === "full") return "blue" as const;
  if (windowName === "3y") return "green" as const;
  return "yellow" as const;
}

export default function CbQuantStrategyGenerationPage() {
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]["key"]>("templates");
  const [search, setSearch] = useState<string>("");
  const [showFilter, setShowFilter] = useState<boolean>(false);
  const [templateStatus, setTemplateStatus] = useState<string>("all");
  const [paramGroup, setParamGroup] = useState<string>("all");
  const [candidateWindow, setCandidateWindow] = useState<string>("all");
  const [pageSize, setPageSize] = useState<number>(5);
  const [templatePage, setTemplatePage] = useState<number>(1);
  const [paramPage, setParamPage] = useState<number>(1);
  const [candidatePage, setCandidatePage] = useState<number>(1);
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

  const filteredTemplates = useMemo(() => {
    return strategyTemplates.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.id.toLowerCase().includes(keyword) ||
        row.name.toLowerCase().includes(keyword) ||
        row.owner.toLowerCase().includes(keyword) ||
        row.version.toLowerCase().includes(keyword);
      const hitStatus = templateStatus === "all" || row.status === templateStatus;
      return hitKeyword && hitStatus;
    });
  }, [keyword, templateStatus]);

  const filteredParams = useMemo(() => {
    return strategyParameters.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.key.toLowerCase().includes(keyword) ||
        row.group.toLowerCase().includes(keyword) ||
        row.type.toLowerCase().includes(keyword);
      const hitGroup = paramGroup === "all" || row.group === paramGroup;
      return hitKeyword && hitGroup;
    });
  }, [keyword, paramGroup]);

  const filteredCandidates = useMemo(() => {
    return strategyCandidates.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.template.toLowerCase().includes(keyword) ||
        row.comboId.toLowerCase().includes(keyword);
      const hitWindow = candidateWindow === "all" || row.window === candidateWindow;
      return hitKeyword && hitWindow;
    });
  }, [keyword, candidateWindow]);

  const templateTotalPages = getTotalPages(filteredTemplates.length, pageSize);
  const paramTotalPages = getTotalPages(filteredParams.length, pageSize);
  const candidateTotalPages = getTotalPages(filteredCandidates.length, pageSize);

  useEffect(() => {
    if (templatePage > templateTotalPages) setTemplatePage(templateTotalPages);
  }, [templatePage, templateTotalPages]);

  useEffect(() => {
    if (paramPage > paramTotalPages) setParamPage(paramTotalPages);
  }, [paramPage, paramTotalPages]);

  useEffect(() => {
    if (candidatePage > candidateTotalPages) setCandidatePage(candidateTotalPages);
  }, [candidatePage, candidateTotalPages]);

  const pagedTemplates = getPagedRows(filteredTemplates, templatePage, pageSize);
  const pagedParams = getPagedRows(filteredParams, paramPage, pageSize);
  const pagedCandidates = getPagedRows(filteredCandidates, candidatePage, pageSize);

  const activeTemplateCount = strategyTemplates.filter((row) => row.status === "active").length;
  const enabledParamCount = strategyParameters.filter((row) => row.enabled).length;
  const totalCombos = strategyTemplates.reduce((sum, row) => sum + row.comboSize, 0);
  const bestRobustScore = Math.max(...strategyCandidates.map((row) => row.robustScore));

  const searchPlaceholder =
    activeTab === "templates"
      ? "Search template/name/owner..."
      : activeTab === "params"
      ? "Search key/group/type..."
      : "Search combo/template...";

  const onExport = () => {
    const date = new Date().toISOString().slice(0, 10);

    if (activeTab === "templates") {
      downloadCsv(
        `cb-quant-strategy-templates-${date}.csv`,
        ["模板ID", "模板名", "版本", "状态", "因子数", "调仓", "风控", "组合规模", "负责人", "更新时间"],
        filteredTemplates.map((row) => [
          row.id,
          row.name,
          row.version,
          row.status,
          row.factorCount,
          row.rebalance,
          row.riskPreset,
          row.comboSize,
          row.owner,
          row.updatedAt,
        ])
      );
      return;
    }

    if (activeTab === "params") {
      downloadCsv(
        `cb-quant-strategy-params-${date}.csv`,
        ["参数", "分组", "类型", "范围", "步长", "默认值", "启用"],
        filteredParams.map((row) => [
          row.key,
          row.group,
          row.type,
          row.range,
          row.step,
          row.defaultValue,
          row.enabled ? "true" : "false",
        ])
      );
      return;
    }

    downloadCsv(
      `cb-quant-strategy-candidates-${date}.csv`,
      ["排名", "模板", "组合ID", "组合规模", "通过率", "稳健分", "窗口"],
      filteredCandidates.map((row) => [
        row.rank,
        row.template,
        row.comboId,
        row.estCombos,
        `${row.passRate}%`,
        row.robustScore,
        row.window,
      ])
    );
  };

  const filterPanel = (
    <div className="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-gray-200 bg-white p-4 shadow-lg dark:border-gray-700 dark:bg-gray-800">
      <div className="space-y-4">
        {activeTab === "templates" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">模板状态</label>
            <select
              value={templateStatus}
              onChange={(event) => {
                setTemplateStatus(event.target.value);
                setTemplatePage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="active">active</option>
              <option value="draft">draft</option>
              <option value="archived">archived</option>
            </select>
          </div>
        )}

        {activeTab === "params" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">参数分组</label>
            <select
              value={paramGroup}
              onChange={(event) => {
                setParamGroup(event.target.value);
                setParamPage(1);
              }}
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            >
              <option value="all">全部</option>
              <option value="filters">filters</option>
              <option value="ranking">ranking</option>
              <option value="portfolio">portfolio</option>
              <option value="rebalance">rebalance</option>
              <option value="risk">risk</option>
            </select>
          </div>
        )}

        {activeTab === "candidates" && (
          <div>
            <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">评估窗口</label>
            <select
              value={candidateWindow}
              onChange={(event) => {
                setCandidateWindow(event.target.value);
                setCandidatePage(1);
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

        <div>
          <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">每页条数</label>
          <select
            value={String(pageSize)}
            onChange={(event) => {
              const nextPageSize = Number(event.target.value);
              setPageSize(nextPageSize);
              setTemplatePage(1);
              setParamPage(1);
              setCandidatePage(1);
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
      title="策略生成行动页"
      subtitle="把可转债规则参数化：模板管理、参数空间维护、候选组合预览全部在一个工作台完成。"
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">活跃模板</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{activeTemplateCount}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">启用参数</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{enabledParamCount}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">组合空间</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{totalCombos.toLocaleString()}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-500 dark:text-gray-400">最高稳健分</p>
          <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{bestRobustScore.toFixed(1)}</p>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <WorkbenchHeader
          title="参数与模板工作台"
          description="沿用 Invoices 交互：页签、搜索、过滤、导出"
          tabs={tabs}
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
          searchPlaceholder={searchPlaceholder}
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value);
            setTemplatePage(1);
            setParamPage(1);
            setCandidatePage(1);
          }}
          filterOpen={showFilter}
          onToggleFilter={() => setShowFilter((prev) => !prev)}
          filterPanel={filterPanel}
          filterRef={filterRef}
          onExport={onExport}
        />

        {activeTab === "templates" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["模板ID", "模板名", "版本", "状态", "因子数", "调仓", "风控预设", "组合规模", "负责人", "更新时间"]}
              minTableWidthClass="min-w-[1450px]"
              colSpan={10}
              isEmpty={pagedTemplates.length === 0}
            >
              {pagedTemplates.map((row) => (
                <TableRow key={row.id} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.id}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.name}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.version}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.status} tone={getTemplateTone(row.status)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.factorCount}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.rebalance}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.riskPreset}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.comboSize.toLocaleString()}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.owner}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap dark:text-gray-400">{row.updatedAt}</TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredTemplates.length}
              currentPage={templatePage}
              totalPages={templateTotalPages}
              onPageChange={setTemplatePage}
            />
          </div>
        )}

        {activeTab === "params" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["参数键", "分组", "类型", "范围", "步长", "默认值", "启用"]}
              minTableWidthClass="min-w-[1180px]"
              colSpan={7}
              isEmpty={pagedParams.length === 0}
            >
              {pagedParams.map((row) => (
                <TableRow key={row.key} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.key}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.group} tone={getGroupTone(row.group)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.type}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.range}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.step}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.defaultValue}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.enabled ? "enabled" : "disabled"} tone={row.enabled ? "green" : "slate"} />
                  </TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredParams.length}
              currentPage={paramPage}
              totalPages={paramTotalPages}
              onPageChange={setParamPage}
            />
          </div>
        )}

        {activeTab === "candidates" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["排名", "模板", "组合ID", "组合规模", "通过率", "稳健分", "评估窗口"]}
              minTableWidthClass="min-w-[1100px]"
              colSpan={7}
              isEmpty={pagedCandidates.length === 0}
            >
              {pagedCandidates.map((row) => (
                <TableRow key={row.comboId} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">#{row.rank}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.template}</TableCell>
                  <TableCell className="px-4 py-3 text-sm font-medium text-gray-900 whitespace-nowrap dark:text-white">{row.comboId}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.estCombos.toLocaleString()}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.passRate.toFixed(1)}%</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.robustScore.toFixed(1)}</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.window} tone={getWindowTone(row.window)} />
                  </TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredCandidates.length}
              currentPage={candidatePage}
              totalPages={candidateTotalPages}
              onPageChange={setCandidatePage}
            />
          </div>
        )}
      </div>
    </CbQuantPageShell>
  );
}
