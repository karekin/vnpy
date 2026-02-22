"use client";

import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import type { StrategyTemplateRow } from "@/components/cb-quant/mockData";
import {
  createMockCandidateRun,
  getTemplateById,
  getLatestCandidateRun,
  getTemplateConfig,
  saveCandidateRun,
  upsertTemplate,
  upsertTemplateConfig,
} from "@/components/cb-quant/strategyCandidateStore";
import { getPagedRows, getTotalPages } from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";

type TemplateDetailTabKey = "overview" | "params" | "catalog";
type GenerateState = "idle" | "running" | "finished" | "failed";

const pageSizeOptions = [5, 10, 20];
const defaultSeedFactorKeys = ["dblow", "conv_prem", "turnover", "remain_size", "rating"];

type FactorCatalogRow = {
  id: string;
  factor_name: string;
  factor_key: string;
  factor_type: number;
  expression: string;
  expression_type: number;
  enabled: boolean;
  remark: string;
  view_style: number;
  view_precision: number;
  view_color: boolean;
  view_ratio: number;
  view_unit: string;
};

type FactorCatalogCategory = {
  category_name: string;
  category_key: string;
  factors: FactorCatalogRow[];
};

type FactorCatalogResponse = {
  items: FactorCatalogCategory[];
  total_categories: number;
  total_factors: number;
};

type FunctionParameter = {
  name: string;
  description: string;
  type_name: string;
  type: string;
};

type FunctionCatalogRow = {
  name: string;
  formular: string;
  description: string;
  parameter_size: number;
  parameters: FunctionParameter[];
};

type FunctionCatalogCategory = {
  category_name: string;
  category_key: string;
  functions: FunctionCatalogRow[];
};

type FunctionCatalogResponse = {
  items: FunctionCatalogCategory[];
  total_categories: number;
  total_functions: number;
};

type FactorItem = FactorCatalogRow & {
  category_name: string;
  category_key: string;
};

type FunctionItem = FunctionCatalogRow & {
  category_name: string;
  category_key: string;
};

type ParamSpaceRow = {
  factorKey: string;
  factorName: string;
  categoryKey: string;
  categoryName: string;
  valueType: string;
  expression: string;
  precision: string;
  enabled: boolean;
};

const detailTabs: {
  key: TemplateDetailTabKey;
  label: string;
  icon: React.ReactNode;
}[] = [
  {
    key: "overview",
    label: "模板详情",
    icon: (
      <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          fillRule="evenodd"
          clipRule="evenodd"
          d="M4.83203 2.5835C3.58939 2.5835 2.58203 3.59085 2.58203 4.83349V7.25015C2.58203 8.49279 3.58939 9.50015 4.83203 9.50015H7.2487C8.49134 9.50015 9.4987 8.49279 9.4987 7.25015V4.8335C9.4987 3.59086 8.49134 2.5835 7.2487 2.5835H4.83203ZM10.4987 4.83349C10.4987 3.59085 11.5061 2.5835 12.7487 2.5835H15.1654C16.408 2.5835 17.4154 3.59086 17.4154 4.8335V7.25015C17.4154 8.49279 16.408 9.50015 15.1654 9.50015H12.7487C11.5061 9.50015 10.4987 8.49279 10.4987 7.25015V4.83349Z"
          fill="currentColor"
        />
      </svg>
    ),
  },
  {
    key: "params",
    label: "参数空间",
    icon: (
      <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M5.00016 4.16675H15.0002M5.00016 10.0001H15.0002M5.00016 15.8334H15.0002M7.0835 4.16675V15.8334M12.9168 4.16675V15.8334"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
  {
    key: "catalog",
    label: "因子函数",
    icon: (
      <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path
          d="M2.9165 5.83325C2.9165 4.68266 3.84924 3.74992 4.99984 3.74992H8.33317C9.48376 3.74992 10.4165 4.68266 10.4165 5.83325V14.1666C10.4165 15.3172 9.48376 16.2499 8.33317 16.2499H4.99984C3.84924 16.2499 2.9165 15.3172 2.9165 14.1666V5.83325ZM11.6665 7.08325C11.6665 5.93266 12.5992 4.99992 13.7498 4.99992H14.9998C16.1504 4.99992 17.0832 5.93266 17.0832 7.08325V12.9166C17.0832 14.0672 16.1504 14.9999 14.9998 14.9999H13.7498C12.5992 14.9999 11.6665 14.0672 11.6665 12.9166V7.08325Z"
          stroke="currentColor"
          strokeWidth="1.5"
        />
      </svg>
    ),
  },
];

const factorFallback: FactorCatalogCategory[] = [
  {
    category_name: "基础因子",
    category_key: "base",
    factors: [
      {
        id: "fallback-dblow",
        factor_name: "双低",
        factor_key: "dblow",
        factor_type: 0,
        expression: "[dblow]",
        expression_type: 1,
        enabled: true,
        remark: "",
        view_style: 0,
        view_precision: 3,
        view_color: false,
        view_ratio: 1,
        view_unit: "",
      },
      {
        id: "fallback-conv-prem",
        factor_name: "转股溢价率",
        factor_key: "conv_prem",
        factor_type: 0,
        expression: "[conv_prem]",
        expression_type: 1,
        enabled: true,
        remark: "",
        view_style: 1,
        view_precision: 2,
        view_color: false,
        view_ratio: 1,
        view_unit: "",
      },
      {
        id: "fallback-turnover",
        factor_name: "换手率",
        factor_key: "turnover",
        factor_type: 0,
        expression: "[turnover]",
        expression_type: 1,
        enabled: true,
        remark: "",
        view_style: 1,
        view_precision: 2,
        view_color: false,
        view_ratio: 1,
        view_unit: "",
      },
    ],
  },
  {
    category_name: "历史类因子",
    category_key: "history",
    factors: [
      {
        id: "fallback-bias5",
        factor_name: "5日乖离率",
        factor_key: "bias_5",
        factor_type: 2,
        expression: "[bias_5]",
        expression_type: 1,
        enabled: true,
        remark: "",
        view_style: 0,
        view_precision: 2,
        view_color: false,
        view_ratio: 1,
        view_unit: "",
      },
    ],
  },
  {
    category_name: "正股相关因子",
    category_key: "stk",
    factors: [
      {
        id: "fallback-pb",
        factor_name: "市净率",
        factor_key: "pb",
        factor_type: 0,
        expression: "[pb]",
        expression_type: 1,
        enabled: true,
        remark: "",
        view_style: 0,
        view_precision: 2,
        view_color: false,
        view_ratio: 1,
        view_unit: "",
      },
    ],
  },
];

const functionFallback: FunctionCatalogCategory[] = [
  {
    category_name: "截面函数",
    category_key: "cross_section",
    functions: [
      {
        name: "cs_rank",
        formular: "cs_rank(指标: 数值向量, 排序标记: 布尔值)",
        description: "计算交易日截面指标排名。",
        parameter_size: 2,
        parameters: [
          { name: "指标", description: "指标参数", type_name: "数值向量", type: "number_vector" },
          { name: "排序标记", description: "排序标记参数", type_name: "布尔值", type: "boolean" },
        ],
      },
    ],
  },
  {
    category_name: "时序函数",
    category_key: "time_series",
    functions: [
      {
        name: "ts_mean",
        formular: "ts_mean(指标: 数值向量, 交易日: 数值)",
        description: "计算时间窗口均值。",
        parameter_size: 2,
        parameters: [
          { name: "指标", description: "指标参数", type_name: "数值向量", type: "number_vector" },
          { name: "交易日", description: "交易日参数", type_name: "数值", type: "number" },
        ],
      },
    ],
  },
];

function getCategoryTone(categoryKey: string) {
  if (categoryKey === "base") return "blue" as const;
  if (categoryKey === "history") return "green" as const;
  if (categoryKey === "stk") return "yellow" as const;
  return "slate" as const;
}

function getValueTypeLabel(expressionType: number): string {
  return expressionType === 2 ? "text" : "number";
}

export default function StrategyTemplateDetailPage() {
  const router = useRouter();
  const params = useParams<{ templateId: string }>();
  const searchParams = useSearchParams();
  const mode = searchParams.get("mode");

  const templateId = params?.templateId ?? "";
  const [template, setTemplate] = useState<StrategyTemplateRow | null>(null);

  const [detailTab, setDetailTab] = useState<TemplateDetailTabKey>("overview");
  const [isEditing, setIsEditing] = useState<boolean>(mode === "edit");
  const [factorCatalog, setFactorCatalog] = useState<FactorCatalogCategory[]>(factorFallback);
  const [functionCatalog, setFunctionCatalog] = useState<FunctionCatalogCategory[]>(functionFallback);
  const [catalogSource, setCatalogSource] = useState<string>("mock");
  const [searchKeyword, setSearchKeyword] = useState<string>("");
  const [factorCategory, setFactorCategory] = useState<string>("all");
  const [functionCategory, setFunctionCategory] = useState<string>("all");
  const [enabledOnly, setEnabledOnly] = useState<boolean>(false);
  const [pageSize, setPageSize] = useState<number>(5);
  const [paramPage, setParamPage] = useState<number>(1);

  const [draft, setDraft] = useState({
    name: template?.name ?? "",
    status: template?.status ?? ("draft" as const),
    rebalance: template?.rebalance ?? "weekly",
    riskPreset: template?.riskPreset ?? "balanced",
    owner: template?.owner ?? "quant_new",
  });

  const [selectedFactorKeys, setSelectedFactorKeys] = useState<string[]>([]);
  const [expressionDraft, setExpressionDraft] = useState<string>("");
  const [generateState, setGenerateState] = useState<GenerateState>("idle");
  const [generateMessage, setGenerateMessage] = useState<string>("");
  const [latestRunId, setLatestRunId] = useState<string>("");

  useEffect(() => {
    if (!templateId) {
      setTemplate(null);
      return;
    }
    setTemplate(getTemplateById(templateId));
  }, [templateId]);

  useEffect(() => {
    setDraft({
      name: template?.name ?? "",
      status: template?.status ?? ("draft" as const),
      rebalance: template?.rebalance ?? "weekly",
      riskPreset: template?.riskPreset ?? "balanced",
      owner: template?.owner ?? "quant_new",
    });
    setIsEditing(mode === "edit");
  }, [mode, template]);

  useEffect(() => {
    if (!templateId) {
      return;
    }
    const latestRun = getLatestCandidateRun(templateId);
    if (latestRun) {
      setLatestRunId(latestRun.runId);
      setGenerateState("finished");
      setGenerateMessage(`最新候选集：${latestRun.runId}（${latestRun.rows.length} 条）`);
    } else {
      setLatestRunId("");
      setGenerateState("idle");
      setGenerateMessage("");
    }
  }, [templateId]);

  useEffect(() => {
    const controller = new AbortController();
    const apiBase = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";

    const loadCatalog = async () => {
      try {
        const [factorRes, functionRes] = await Promise.all([
          fetch(`${apiBase}/api/v1/cb-quant/catalog/factors?category=all`, {
            method: "GET",
            cache: "no-store",
            signal: controller.signal,
          }),
          fetch(`${apiBase}/api/v1/cb-quant/catalog/functions?category=all`, {
            method: "GET",
            cache: "no-store",
            signal: controller.signal,
          }),
        ]);
        if (!factorRes.ok || !functionRes.ok) {
          throw new Error(`HTTP ${factorRes.status}/${functionRes.status}`);
        }
        const factorPayload = (await factorRes.json()) as FactorCatalogResponse;
        const functionPayload = (await functionRes.json()) as FunctionCatalogResponse;
        if (!controller.signal.aborted) {
          setFactorCatalog(factorPayload.items?.length ? factorPayload.items : factorFallback);
          setFunctionCatalog(functionPayload.items?.length ? functionPayload.items : functionFallback);
          setCatalogSource("api");
        }
      } catch {
        if (!controller.signal.aborted) {
          setFactorCatalog(factorFallback);
          setFunctionCatalog(functionFallback);
          setCatalogSource("mock");
        }
      }
    };

    loadCatalog();
    return () => controller.abort();
  }, []);

  const flatFactors = useMemo(() => {
    return factorCatalog.flatMap((category) =>
      category.factors.map((factor) => ({
        ...factor,
        category_key: category.category_key,
        category_name: category.category_name,
      })),
    );
  }, [factorCatalog]);

  const flatFunctions = useMemo(() => {
    return functionCatalog.flatMap((category) =>
      category.functions.map((fn) => ({
        ...fn,
        category_key: category.category_key,
        category_name: category.category_name,
      })),
    );
  }, [functionCatalog]);

  useEffect(() => {
    if (!flatFactors.length || !templateId) return;

    const savedConfig = getTemplateConfig(templateId);
    const validKeys = (savedConfig?.factorKeys ?? []).filter((key) =>
      flatFactors.some((factor) => factor.factor_key === key),
    );

    if (validKeys.length) {
      setSelectedFactorKeys(validKeys);
      setExpressionDraft(savedConfig?.expressionDraft ?? "");
      return;
    }

    const seeded = defaultSeedFactorKeys.filter((key) =>
      flatFactors.some((factor) => factor.factor_key === key),
    );
    setSelectedFactorKeys(seeded.length ? seeded : [flatFactors[0].factor_key]);
    setExpressionDraft(savedConfig?.expressionDraft ?? "");
  }, [flatFactors, templateId]);

  const keyword = searchKeyword.trim().toLowerCase();

  const factorCategoryOptions = useMemo(() => {
    return [{ key: "all", name: "全部因子分类" }, ...factorCatalog.map((item) => ({ key: item.category_key, name: item.category_name }))];
  }, [factorCatalog]);

  const functionCategoryOptions = useMemo(() => {
    return [
      { key: "all", name: "全部函数分类" },
      ...functionCatalog.map((item) => ({ key: item.category_key, name: item.category_name })),
    ];
  }, [functionCatalog]);

  const selectedFactorRows = useMemo<FactorItem[]>(() => {
    const keySet = new Set(selectedFactorKeys);
    return flatFactors.filter((item) => keySet.has(item.factor_key));
  }, [flatFactors, selectedFactorKeys]);

  const paramRows = useMemo<ParamSpaceRow[]>(() => {
    return selectedFactorRows.map((row) => ({
      factorKey: row.factor_key,
      factorName: row.factor_name,
      categoryKey: row.category_key,
      categoryName: row.category_name,
      valueType: getValueTypeLabel(row.expression_type),
      expression: row.expression,
      precision: String(row.view_precision),
      enabled: row.enabled,
    }));
  }, [selectedFactorRows]);

  const filteredParamRows = useMemo(() => {
    return paramRows.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.factorKey.toLowerCase().includes(keyword) ||
        row.factorName.toLowerCase().includes(keyword) ||
        row.expression.toLowerCase().includes(keyword);
      const hitCategory = factorCategory === "all" || row.categoryKey === factorCategory;
      const hitEnabled = !enabledOnly || row.enabled;
      return hitKeyword && hitCategory && hitEnabled;
    });
  }, [paramRows, keyword, factorCategory, enabledOnly]);

  const filteredFactorLibrary = useMemo(() => {
    return flatFactors.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.factor_key.toLowerCase().includes(keyword) ||
        row.factor_name.toLowerCase().includes(keyword);
      const hitCategory = factorCategory === "all" || row.category_key === factorCategory;
      const hitEnabled = !enabledOnly || row.enabled;
      return hitKeyword && hitCategory && hitEnabled;
    });
  }, [flatFactors, keyword, factorCategory, enabledOnly]);

  const filteredFunctionLibrary = useMemo(() => {
    return flatFunctions.filter((row) => {
      const hitKeyword =
        !keyword ||
        row.name.toLowerCase().includes(keyword) ||
        row.formular.toLowerCase().includes(keyword) ||
        row.description.toLowerCase().includes(keyword);
      const hitCategory = functionCategory === "all" || row.category_key === functionCategory;
      return hitKeyword && hitCategory;
    });
  }, [flatFunctions, keyword, functionCategory]);

  const paramTotalPages = getTotalPages(filteredParamRows.length, pageSize);

  useEffect(() => {
    if (paramPage > paramTotalPages) setParamPage(paramTotalPages);
  }, [paramPage, paramTotalPages]);

  const pagedParams = getPagedRows(filteredParamRows, paramPage, pageSize);

  const addFactorToParamSpace = (factorKey: string): void => {
    setSelectedFactorKeys((prev) => {
      if (prev.includes(factorKey)) return prev;
      return [...prev, factorKey];
    });
  };

  const removeFactorFromParamSpace = (factorKey: string): void => {
    setSelectedFactorKeys((prev) => prev.filter((key) => key !== factorKey));
  };

  const appendFactorToken = (factorKey: string): void => {
    setExpressionDraft((prev) => (prev ? `${prev} [${factorKey}]` : `[${factorKey}]`));
  };

  const appendFunctionTemplate = (fn: FunctionItem): void => {
    const args = fn.parameters.map((param) => `<${param.name}>`).join(", ");
    const snippet = `${fn.name}(${args})`;
    setExpressionDraft((prev) => (prev ? `${prev}\n${snippet}` : snippet));
  };

  const persistTemplateConfig = (): void => {
    if (!templateId || !template) {
      return;
    }
    upsertTemplateConfig({
      templateId,
      templateName: draft.name || template.name,
      factorKeys: selectedFactorKeys,
      expressionDraft,
      updatedAt: new Date().toISOString(),
    });
  };

  const handleSave = (): void => {
    if (!template) {
      return;
    }
    const now = new Date().toISOString().slice(0, 16).replace("T", " ");
    const updatedTemplate: StrategyTemplateRow = {
      ...template,
      name: draft.name || template.name,
      status: draft.status,
      rebalance: draft.rebalance,
      riskPreset: draft.riskPreset,
      owner: draft.owner || template.owner,
      factorCount: selectedFactorKeys.length,
      updatedAt: now,
    };
    upsertTemplate(updatedTemplate);
    setTemplate(updatedTemplate);
    persistTemplateConfig();
    setGenerateMessage(`模板已保存：${updatedTemplate.id}（${updatedTemplate.updatedAt}）`);
    setIsEditing(false);
  };

  const handleGenerateCandidates = async (): Promise<void> => {
    if (!templateId || !template) {
      return;
    }
    setGenerateState("running");
    setGenerateMessage("候选生成中，请稍候...");

    try {
      persistTemplateConfig();
      await new Promise((resolve) => {
        window.setTimeout(resolve, 900);
      });
      const run = createMockCandidateRun({
        templateId,
        templateName: draft.name || template.name,
        factorCount: selectedFactorKeys.length,
        expressionDraft,
      });
      saveCandidateRun(run);
      setLatestRunId(run.runId);
      setGenerateState("finished");
      setGenerateMessage(`已生成候选集：${run.runId}（${run.rows.length} 条）`);
    } catch {
      setGenerateState("failed");
      setGenerateMessage("候选生成失败，请重试。");
    }
  };

  if (!template) {
    return (
      <CbQuantPageShell title="模板详情" subtitle="模板不存在或已删除。">
        <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          <p className="text-sm text-gray-600 dark:text-gray-300">未找到模板 {templateId}。</p>
          <button
            type="button"
            onClick={() => router.push("/cb-quant/strategy-generation")}
            className="bg-brand-500 hover:bg-brand-600 mt-4 rounded-lg px-4 py-2 text-sm font-medium text-white"
          >
            返回模板库
          </button>
        </div>
      </CbQuantPageShell>
    );
  }

  return (
    <CbQuantPageShell
      title={`模板详情 · ${template.id}`}
      subtitle="此页面承载该模板的参数空间与因子函数维护，不与模板列表混排。"
    >
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="flex flex-col gap-3 border-b border-gray-200 p-4 lg:flex-row lg:items-center lg:justify-between dark:border-gray-800">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{template.name}</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              模板ID: {template.id} · Catalog源: {catalogSource === "api" ? "后端注册表" : "本地Fallback"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleGenerateCandidates}
              disabled={generateState === "running"}
              className="bg-brand-500 hover:bg-brand-600 disabled:bg-brand-300 rounded-lg px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed"
            >
              {generateState === "running" ? "生成中..." : "生成候选"}
            </button>
            <button
              type="button"
              onClick={() =>
                router.push(
                  `/cb-quant/strategy-generation?tab=candidates&templateId=${template.id}${latestRunId ? `&runId=${latestRunId}` : ""}`,
                )
              }
              className="rounded-lg border border-brand-300 px-3 py-2 text-sm font-medium text-brand-600 hover:bg-brand-50 dark:border-brand-400/40 dark:text-brand-300 dark:hover:bg-brand-500/10"
            >
              查看候选预览
            </button>
            <button
              type="button"
              onClick={() => router.push("/cb-quant/strategy-generation")}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/[0.04]"
            >
              返回模板库
            </button>
            {isEditing ? (
              <>
                <button
                  type="button"
                  onClick={handleSave}
                  className="bg-brand-500 hover:bg-brand-600 rounded-lg px-3 py-2 text-sm font-medium text-white"
                >
                  保存（Mock）
                </button>
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/[0.04]"
                >
                  取消
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setIsEditing(true)}
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/[0.04]"
              >
                编辑
              </button>
            )}
          </div>
        </div>

        <div className="p-4">
          {generateMessage && (
            <div
              className={`mb-4 rounded-lg border px-3 py-2 text-sm ${
                generateState === "finished"
                  ? "border-green-200 bg-green-50 text-green-700 dark:border-green-800/50 dark:bg-green-500/10 dark:text-green-300"
                  : generateState === "failed"
                    ? "border-red-200 bg-red-50 text-red-700 dark:border-red-800/50 dark:bg-red-500/10 dark:text-red-300"
                    : "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800/50 dark:bg-blue-500/10 dark:text-blue-300"
              }`}
            >
              {generateMessage}
            </div>
          )}
          <div className="border-b border-gray-200 dark:border-gray-800">
            <nav className="flex space-x-3 overflow-x-auto">
              {detailTabs.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => {
                    setDetailTab(tab.key);
                    setParamPage(1);
                  }}
                  className={`inline-flex items-center gap-2 border-b-2 px-2.5 py-3 text-sm font-medium transition-colors ${
                    detailTab === tab.key
                      ? "border-brand-500 text-brand-500 dark:border-brand-400 dark:text-brand-400"
                      : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          <div className="pt-4">
            {detailTab === "overview" && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">模板ID</label>
                  <input
                    value={template.id}
                    disabled
                    className="h-10 w-full rounded-lg border border-gray-300 bg-gray-100 px-3 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-900/50 dark:text-gray-300"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">模板名</label>
                  <input
                    value={draft.name}
                    onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
                    disabled={!isEditing}
                    className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 disabled:bg-gray-100 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:disabled:bg-gray-900/50"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">状态</label>
                  <select
                    value={draft.status}
                    onChange={(event) =>
                      setDraft((prev) => ({ ...prev, status: event.target.value as "active" | "draft" | "archived" }))
                    }
                    disabled={!isEditing}
                    className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 disabled:bg-gray-100 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:disabled:bg-gray-900/50"
                  >
                    <option value="active">active</option>
                    <option value="draft">draft</option>
                    <option value="archived">archived</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">调仓频率</label>
                  <select
                    value={draft.rebalance}
                    onChange={(event) => setDraft((prev) => ({ ...prev, rebalance: event.target.value }))}
                    disabled={!isEditing}
                    className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 disabled:bg-gray-100 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:disabled:bg-gray-900/50"
                  >
                    <option value="daily">daily</option>
                    <option value="weekly">weekly</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">风控预设</label>
                  <select
                    value={draft.riskPreset}
                    onChange={(event) => setDraft((prev) => ({ ...prev, riskPreset: event.target.value }))}
                    disabled={!isEditing}
                    className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 disabled:bg-gray-100 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:disabled:bg-gray-900/50"
                  >
                    <option value="balanced">balanced</option>
                    <option value="aggressive">aggressive</option>
                    <option value="conservative">conservative</option>
                  </select>
                </div>
                <div className="md:col-span-2 xl:col-span-5">
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/40">
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      语义说明：模板定义策略骨架；参数空间定义可搜索维度；候选组合是该模板在参数空间内的展开结果。
                    </p>
                  </div>
                </div>
              </div>
            )}

            {detailTab === "params" && (
              <div className="space-y-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex-1">
                    <input
                      value={searchKeyword}
                      onChange={(event) => {
                        setSearchKeyword(event.target.value);
                        setParamPage(1);
                      }}
                      placeholder="Search factor/expression..."
                      className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      value={factorCategory}
                      onChange={(event) => {
                        setFactorCategory(event.target.value);
                        setParamPage(1);
                      }}
                      className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                    >
                      {factorCategoryOptions.map((option) => (
                        <option key={option.key} value={option.key}>
                          {option.name}
                        </option>
                      ))}
                    </select>
                    <select
                      value={enabledOnly ? "enabled" : "all"}
                      onChange={(event) => {
                        setEnabledOnly(event.target.value === "enabled");
                        setParamPage(1);
                      }}
                      className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                    >
                      <option value="all">全部</option>
                      <option value="enabled">仅启用</option>
                    </select>
                    <select
                      value={String(pageSize)}
                      onChange={(event) => {
                        setPageSize(Number(event.target.value));
                        setParamPage(1);
                      }}
                      className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                    >
                      {pageSizeOptions.map((size) => (
                        <option key={size} value={size}>{`每页 ${size} 条`}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
                  <h5 className="text-sm font-semibold text-gray-900 dark:text-white">表达式草稿</h5>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">点击 token 或函数模板即可插入草稿。</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedFactorRows.map((factor) => (
                      <button
                        key={`chip-${factor.factor_key}`}
                        type="button"
                        onClick={() => appendFactorToken(factor.factor_key)}
                        className="rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-900/40"
                      >
                        [{factor.factor_key}]
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={expressionDraft}
                    onChange={(event) => setExpressionDraft(event.target.value)}
                    placeholder="例如：cs_rank([dblow], false) + ts_mean([conv_prem], 5)"
                    className="mt-3 h-24 w-full rounded-lg border border-gray-300 bg-transparent px-3 py-2 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                  />
                </div>

                <ScrollableDataTable
                  headers={["参数键", "参数名", "分类", "值类型", "表达式", "精度", "启用", "操作"]}
                  minTableWidthClass="min-w-[1480px]"
                  colSpan={8}
                  isEmpty={pagedParams.length === 0}
                >
                  {pagedParams.map((row) => (
                    <TableRow key={row.factorKey} className="border-b border-gray-100 dark:border-gray-800">
                      <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 whitespace-nowrap dark:text-white">{row.factorKey}</TableCell>
                      <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.factorName}</TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                        <StatusTag label={row.categoryKey} tone={getCategoryTone(row.categoryKey)} />
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.valueType}</TableCell>
                      <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.expression}</TableCell>
                      <TableCell className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap dark:text-gray-200">{row.precision}</TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                        <StatusTag label={row.enabled ? "enabled" : "disabled"} tone={row.enabled ? "green" : "slate"} />
                      </TableCell>
                      <TableCell className="px-4 py-3 text-sm whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => removeFactorFromParamSpace(row.factorKey)}
                          className="rounded-md border border-red-300 px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:border-red-700/50 dark:text-red-300 dark:hover:bg-red-500/10"
                        >
                          移除
                        </button>
                      </TableCell>
                    </TableRow>
                  ))}
                </ScrollableDataTable>
                <TablePaginationBar
                  totalItems={filteredParamRows.length}
                  currentPage={paramPage}
                  totalPages={paramTotalPages}
                  onPageChange={setParamPage}
                />
              </div>
            )}

            {detailTab === "catalog" && (
              <div className="space-y-4">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex-1">
                    <input
                      value={searchKeyword}
                      onChange={(event) => setSearchKeyword(event.target.value)}
                      placeholder="Search factor/function..."
                      className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <select
                      value={factorCategory}
                      onChange={(event) => setFactorCategory(event.target.value)}
                      className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                    >
                      {factorCategoryOptions.map((option) => (
                        <option key={option.key} value={option.key}>
                          {option.name}
                        </option>
                      ))}
                    </select>
                    <select
                      value={functionCategory}
                      onChange={(event) => setFunctionCategory(event.target.value)}
                      className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
                    >
                      {functionCategoryOptions.map((option) => (
                        <option key={option.key} value={option.key}>
                          {option.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                  <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
                    <div className="mb-3 flex items-center justify-between">
                      <h4 className="text-base font-semibold text-gray-800 dark:text-white/90">因子库</h4>
                      <p className="text-xs text-gray-500 dark:text-gray-400">{filteredFactorLibrary.length} 个因子</p>
                    </div>
                    <div className="max-h-[340px] overflow-y-auto rounded-lg border border-gray-200 dark:border-gray-800">
                      <table className="w-full">
                        <tbody>
                          {filteredFactorLibrary.map((factor) => {
                            const selected = selectedFactorKeys.includes(factor.factor_key);
                            return (
                              <tr key={`${factor.category_key}-${factor.factor_key}`} className="border-b border-gray-100 last:border-b-0 dark:border-gray-800">
                                <td className="px-3 py-2 align-top">
                                  <p className="text-sm font-medium text-gray-900 dark:text-white">{factor.factor_name}</p>
                                  <p className="text-xs text-gray-500 dark:text-gray-400">{factor.factor_key}</p>
                                </td>
                                <td className="px-3 py-2 text-right align-top">
                                  <div className="mb-1 inline-flex">
                                    <StatusTag label={factor.category_key} tone={getCategoryTone(factor.category_key)} />
                                  </div>
                                  <button
                                    type="button"
                                    disabled={selected}
                                    onClick={() => addFactorToParamSpace(factor.factor_key)}
                                    className={`block rounded-md px-2 py-1 text-xs font-medium ${
                                      selected
                                        ? "cursor-not-allowed bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500"
                                        : "bg-brand-50 text-brand-600 hover:bg-brand-100 dark:bg-brand-500/10 dark:text-brand-300"
                                    }`}
                                  >
                                    {selected ? "已加入" : "加入参数空间"}
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
                    <div className="mb-3 flex items-center justify-between">
                      <h4 className="text-base font-semibold text-gray-800 dark:text-white/90">函数库</h4>
                      <p className="text-xs text-gray-500 dark:text-gray-400">{filteredFunctionLibrary.length} 个函数</p>
                    </div>
                    <div className="max-h-[340px] overflow-y-auto rounded-lg border border-gray-200 dark:border-gray-800">
                      <table className="w-full">
                        <tbody>
                          {filteredFunctionLibrary.map((fn) => (
                            <tr key={`${fn.category_key}-${fn.name}`} className="border-b border-gray-100 last:border-b-0 dark:border-gray-800">
                              <td className="px-3 py-2 align-top">
                                <p className="text-sm font-medium text-gray-900 dark:text-white">{fn.name}</p>
                                <p className="text-xs text-gray-500 dark:text-gray-400">{fn.formular}</p>
                                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{fn.description}</p>
                              </td>
                              <td className="px-3 py-2 text-right align-top">
                                <button
                                  type="button"
                                  onClick={() => appendFunctionTemplate(fn)}
                                  className="block rounded-md bg-brand-50 px-2 py-1 text-xs font-medium text-brand-600 hover:bg-brand-100 dark:bg-brand-500/10 dark:text-brand-300"
                                >
                                  插入草稿
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </CbQuantPageShell>
  );
}
