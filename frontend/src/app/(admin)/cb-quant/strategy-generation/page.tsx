"use client";

import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import WorkbenchHeader from "@/components/cb-quant/WorkbenchHeader";
import { strategyCandidates } from "@/components/cb-quant/mockData";
import {
  getPreviewCandidateRows,
  listTemplates,
  saveTemplates,
} from "@/components/cb-quant/strategyCandidateStore";
import { downloadCsv, getPagedRows, getTotalPages } from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import { useRouter, useSearchParams } from "next/navigation";
import React, { Suspense, useEffect, useMemo, useRef, useState } from "react";

type MainTabKey = "templates" | "candidates";
type CandidateRowUi = {
  rank: number;
  templateId: string;
  template: string;
  comboId: string;
  estCombos: number;
  passRate: number;
  window: "full" | "3y" | "1y";
  source: "generated" | "mock";
  runId?: string;
  generatedAt?: string;
};

const mainTabs: { key: MainTabKey; title: string }[] = [
  { key: "templates", title: "模板库" },
  { key: "candidates", title: "候选预览" },
];

const pageSizeOptions = [5, 10, 20];

function getTemplateTone(status: "active" | "draft" | "archived") {
  if (status === "active") return "green" as const;
  if (status === "draft") return "yellow" as const;
  return "slate" as const;
}

function getWindowTone(windowName: "full" | "3y" | "1y") {
  if (windowName === "full") return "blue" as const;
  if (windowName === "3y") return "green" as const;
  return "yellow" as const;
}

function CbQuantStrategyGenerationPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<MainTabKey>("templates");
  const [search, setSearch] = useState<string>("");
  const [showFilter, setShowFilter] = useState<boolean>(false);
  const [candidateWindow, setCandidateWindow] = useState<string>("all");
  const [candidateTemplateId, setCandidateTemplateId] = useState<string>("all");
  const [candidatePageSize, setCandidatePageSize] = useState<number>(5);
  const [templatePage, setTemplatePage] = useState<number>(1);
  const [candidatePage, setCandidatePage] = useState<number>(1);
  const [templates, setTemplates] = useState(() => listTemplates());
  const [generatedCandidates, setGeneratedCandidates] = useState<CandidateRowUi[]>([]);
  const [generatedHint, setGeneratedHint] = useState<string>("");
  const filterRef = useRef<HTMLDivElement>(null);

  const refreshGeneratedCandidates = (): void => {
    const rows = getPreviewCandidateRows();
    if (!rows.length) {
      setGeneratedCandidates([]);
      return;
    }
    const mappedRows: CandidateRowUi[] = rows.map((row, idx) => ({
      rank: idx + 1,
      templateId: row.templateId,
      template: row.template,
      comboId: row.comboId,
      estCombos: row.estCombos,
      passRate: row.passRate,
      window: row.window,
      source: "generated",
      runId: row.runId,
      generatedAt: row.generatedAt,
    }));
    setGeneratedCandidates(mappedRows);
  };

  useEffect(() => {
    setTemplates(listTemplates());
  }, []);

  useEffect(() => {
    refreshGeneratedCandidates();
    const onStorage = (event: StorageEvent) => {
      if (event.key === "cbq_candidate_runs_v1" || event.key === "cbq_template_config_v1") {
        refreshGeneratedCandidates();
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  useEffect(() => {
    const tab = searchParams.get("tab");
    const templateId = searchParams.get("templateId");
    const runId = searchParams.get("runId");

    if (tab === "candidates") {
      setActiveTab("candidates");
    }
    if (templateId) {
      setCandidateTemplateId(templateId);
      setCandidatePage(1);
    }
    if (runId) {
      setGeneratedHint(`已定位到候选集：${runId}`);
    }
    if (tab || templateId || runId) {
      refreshGeneratedCandidates();
    }
  }, [searchParams]);

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
    return templates.filter((row) => {
      return (
        !keyword ||
        row.id.toLowerCase().includes(keyword) ||
        row.name.toLowerCase().includes(keyword) ||
        row.owner.toLowerCase().includes(keyword) ||
        row.version.toLowerCase().includes(keyword)
      );
    });
  }, [keyword, templates]);

  const fallbackCandidates = useMemo<CandidateRowUi[]>(() => {
    return strategyCandidates.map((row) => ({
      rank: row.rank,
      templateId: templates.find((tpl) => tpl.name === row.template)?.id ?? "unknown",
      template: row.template,
      comboId: row.comboId,
      estCombos: row.estCombos,
      passRate: row.passRate,
      window: row.window,
      source: "mock",
    }));
  }, [templates]);

  const candidatesSource = generatedCandidates.length ? "generated" : "mock";
  const sourceCandidates = generatedCandidates.length ? generatedCandidates : fallbackCandidates;

  const filteredCandidates = useMemo(() => {
    return sourceCandidates.filter((row) => {
      const hitKeyword =
        !keyword || row.template.toLowerCase().includes(keyword) || row.comboId.toLowerCase().includes(keyword);
      const hitWindow = candidateWindow === "all" || row.window === candidateWindow;
      const hitTemplate = candidateTemplateId === "all" || row.templateId === candidateTemplateId;
      return hitKeyword && hitWindow && hitTemplate;
    });
  }, [sourceCandidates, keyword, candidateWindow, candidateTemplateId]);

  const templateTotalPages = getTotalPages(filteredTemplates.length, 10);
  const candidateTotalPages = getTotalPages(filteredCandidates.length, candidatePageSize);

  useEffect(() => {
    if (templatePage > templateTotalPages) setTemplatePage(templateTotalPages);
  }, [templatePage, templateTotalPages]);

  useEffect(() => {
    if (candidatePage > candidateTotalPages) setCandidatePage(candidateTotalPages);
  }, [candidatePage, candidateTotalPages]);

  const pagedTemplates = getPagedRows(filteredTemplates, templatePage, 10);
  const pagedCandidates = getPagedRows(filteredCandidates, candidatePage, candidatePageSize);

  const searchPlaceholder =
    activeTab === "templates" ? "Search template/name/owner..." : "Search combo/template...";

  const handleCreateTemplate = (): void => {
    const currentMax = templates.reduce((maxValue, row) => {
      const numericId = Number(row.id.replace("TPL-", ""));
      return Number.isFinite(numericId) ? Math.max(maxValue, numericId) : maxValue;
    }, 0);
    const nextId = `TPL-${String(currentMax + 1).padStart(3, "0")}`;

    const newTemplate = {
      id: nextId,
      name: "新建模板",
      version: "v0.1.0",
      status: "draft" as const,
      factorCount: 0,
      rebalance: "weekly",
      riskPreset: "balanced",
      comboSize: 0,
      owner: "quant_new",
      updatedAt: new Date().toISOString().slice(0, 16).replace("T", " "),
    };

    setTemplates((prev) => {
      const next = [newTemplate, ...prev];
      saveTemplates(next);
      return next;
    });
    setTemplatePage(1);
    router.push(`/cb-quant/strategy-generation/template/${nextId}?mode=edit`);
  };

  const handleCopyTemplate = (templateId: string): void => {
    const source = templates.find((row) => row.id === templateId);
    if (!source) return;

    const currentMax = templates.reduce((maxValue, row) => {
      const numericId = Number(row.id.replace("TPL-", ""));
      return Number.isFinite(numericId) ? Math.max(maxValue, numericId) : maxValue;
    }, 0);
    const nextId = `TPL-${String(currentMax + 1).padStart(3, "0")}`;

    const copied = {
      ...source,
      id: nextId,
      name: `${source.name}-副本`,
      version: "v0.1.0",
      status: "draft" as const,
      updatedAt: new Date().toISOString().slice(0, 16).replace("T", " "),
    };

    setTemplates((prev) => {
      const next = [copied, ...prev];
      saveTemplates(next);
      return next;
    });
    setTemplatePage(1);
  };

  const handleDeleteTemplate = (templateId: string): void => {
    const target = templates.find((row) => row.id === templateId);
    if (!target) return;
    const confirmed = window.confirm(`确认删除模板 ${target.id} - ${target.name} 吗？`);
    if (!confirmed) return;
    setTemplates((prev) => {
      const next = prev.filter((row) => row.id !== templateId);
      saveTemplates(next);
      return next;
    });
  };

  const onExport = (): void => {
    const date = new Date().toISOString().slice(0, 10);
    downloadCsv(
      `cb-quant-strategy-candidates-${date}.csv`,
      ["排名", "模板", "组合ID", "组合规模", "通过率", "评估窗口"],
      filteredCandidates.map((row) => [
        row.rank,
        row.template,
        row.comboId,
        row.estCombos,
        `${row.passRate}%`,
        row.window,
      ]),
    );
  };

  const filterPanel = (
    <div className="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-gray-200 bg-white p-4 shadow-lg dark:border-gray-700 dark:bg-gray-800">
      <div className="space-y-4">
        <div>
          <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">模板</label>
          <select
            value={candidateTemplateId}
            onChange={(event) => {
              setCandidateTemplateId(event.target.value);
              setCandidatePage(1);
            }}
            className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          >
            <option value="all">全部模板</option>
            {templates.map((template) => (
              <option key={template.id} value={template.id}>
                {template.id} · {template.name}
              </option>
            ))}
          </select>
        </div>
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
        <div>
          <label className="mb-2 block text-xs font-medium text-gray-700 dark:text-gray-300">每页条数</label>
          <select
            value={String(candidatePageSize)}
            onChange={(event) => {
              setCandidatePageSize(Number(event.target.value));
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
      subtitle="管理模板并查看候选预览。"
    >
      <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
        <h3 className="text-base font-semibold text-gray-800 dark:text-white/90">用户动线</h3>
        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-4">
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/40">
            <p className="text-xs font-semibold text-brand-500">Step 1</p>
            <p className="mt-1 text-sm font-medium text-gray-900 dark:text-white">模板库</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">新建模板并管理行级操作</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/40">
            <p className="text-xs font-semibold text-brand-500">Step 2</p>
            <p className="mt-1 text-sm font-medium text-gray-900 dark:text-white">模板详情页</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">配置参数空间、因子函数与表达式</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/40">
            <p className="text-xs font-semibold text-brand-500">Step 3</p>
            <p className="mt-1 text-sm font-medium text-gray-900 dark:text-white">候选预览</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">查看模板展开后的组合候选</p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/40">
            <p className="text-xs font-semibold text-brand-500">Step 4</p>
            <p className="mt-1 text-sm font-medium text-gray-900 dark:text-white">回测评估</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">将候选组合送入回测任务中心</p>
          </div>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <WorkbenchHeader
          title="参数与模板工作台"
          description=""
          tabs={mainTabs}
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
          searchPlaceholder={searchPlaceholder}
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value);
            setTemplatePage(1);
            setCandidatePage(1);
          }}
          filterOpen={showFilter}
          onToggleFilter={() => setShowFilter((prev) => !prev)}
          filterPanel={filterPanel}
          filterRef={filterRef}
          onExport={onExport}
          showFilterButton={activeTab === "candidates"}
          showExportButton={activeTab === "candidates"}
          customActions={
            activeTab === "templates" ? (
              <button
                type="button"
                onClick={handleCreateTemplate}
                className="bg-brand-500 hover:bg-brand-600 h-11 rounded-lg px-4 text-sm font-medium text-white"
              >
                新建模板
              </button>
            ) : null
          }
        />

        {activeTab === "templates" && (
          <div className="p-5">
            <ScrollableDataTable
              headers={["模板ID", "模板名", "版本", "状态", "因子数", "调仓", "风控预设", "组合规模", "负责人", "更新时间", "操作"]}
              minTableWidthClass="min-w-[1700px]"
              colSpan={11}
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
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => router.push(`/cb-quant/strategy-generation/template/${row.id}`)}
                        className="rounded-md border border-brand-300 px-2 py-1 text-xs font-medium text-brand-600 hover:bg-brand-50 dark:border-brand-400/40 dark:text-brand-300 dark:hover:bg-brand-500/10"
                      >
                        详情
                      </button>
                      <button
                        type="button"
                        onClick={() => router.push(`/cb-quant/strategy-generation/template/${row.id}?mode=edit`)}
                        className="rounded-md border border-gray-300 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/[0.04]"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        onClick={() => handleCopyTemplate(row.id)}
                        className="rounded-md border border-gray-300 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/[0.04]"
                      >
                        复制
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteTemplate(row.id)}
                        className="rounded-md border border-red-300 px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 dark:border-red-700/50 dark:text-red-300 dark:hover:bg-red-500/10"
                      >
                        删除
                      </button>
                    </div>
                  </TableCell>
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

        {activeTab === "candidates" && (
          <div className="p-5">
            <div
              className={`mb-4 rounded-lg border px-3 py-2 text-sm ${
                candidatesSource === "generated"
                  ? "border-green-200 bg-green-50 text-green-700 dark:border-green-800/50 dark:bg-green-500/10 dark:text-green-300"
                  : "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800/50 dark:bg-amber-500/10 dark:text-amber-300"
              }`}
            >
              {candidatesSource === "generated"
                ? "当前展示来源：已生成候选集。可在模板详情页再次点击“生成候选”刷新。"
                : "当前展示来源：Mock示例数据。请先进入模板详情页点击“生成候选”。"}
              {generatedHint ? ` ${generatedHint}` : ""}
            </div>
            <ScrollableDataTable
              headers={["排名", "模板", "组合ID", "组合规模", "通过率", "评估窗口", "来源", "候选集ID", "生成时间"]}
              minTableWidthClass="min-w-[1460px]"
              colSpan={9}
              isEmpty={pagedCandidates.length === 0}
            >
              {pagedCandidates.map((row) => (
                <TableRow key={`${row.comboId}-${row.window}`} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">#{row.rank}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.template}</TableCell>
                  <TableCell className="px-4 py-3 text-sm font-medium text-gray-900 whitespace-nowrap dark:text-white">{row.comboId}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.estCombos.toLocaleString()}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.passRate.toFixed(1)}%</TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.window} tone={getWindowTone(row.window)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                    <StatusTag label={row.source} tone={row.source === "generated" ? "green" : "yellow"} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">
                    {row.runId ?? "-"}
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap dark:text-gray-400">
                    {row.generatedAt ?? "-"}
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

export default function CbQuantStrategyGenerationPage() {
  return (
    <Suspense
      fallback={
        <CbQuantPageShell title="策略生成行动页" subtitle="管理模板并查看候选预览。">
          <div className="rounded-xl border border-gray-200 bg-white p-6 text-sm text-gray-500 dark:border-gray-800 dark:bg-white/[0.03] dark:text-gray-400">
            正在加载工作台...
          </div>
        </CbQuantPageShell>
      }
    >
      <CbQuantStrategyGenerationPageContent />
    </Suspense>
  );
}
