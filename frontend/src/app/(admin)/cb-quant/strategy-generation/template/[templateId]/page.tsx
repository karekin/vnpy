"use client";

import {
  getStrategyTemplateDetail,
  listFactorCatalog,
  updateStrategyTemplate,
  updateStrategyTemplateConfig,
  type FactorCatalogCategory,
  type StrategyParamSpaceRow,
  type StrategyTemplate,
  type StrategyTemplateStatus,
} from "@/components/cb-quant/api";
import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import { getPagedRows, getTotalPages } from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import { useParams, useRouter } from "next/navigation";
import React, { useEffect, useMemo, useState } from "react";

type EditableParamRow = StrategyParamSpaceRow & {
  factorName: string;
  categoryKey: string;
  categoryName: string;
};

type FactorOption = {
  factorKey: string;
  factorName: string;
  expressionType: number;
  categoryKey: string;
  categoryName: string;
};

const pageSizeOptions = [10, 20, 50];
const defaultFactorKeys = ["dblow", "conv_prem", "turnover", "remain_size", "rating"];

function statusTone(status: StrategyTemplateStatus) {
  if (status === "active") return "green" as const;
  if (status === "draft") return "yellow" as const;
  return "slate" as const;
}

function defaultParamRow(factorKey: string, expressionType?: number): StrategyParamSpaceRow {
  if (factorKey === "rating" || expressionType === 2) {
    return {
      factorKey,
      valueType: "enum",
      enabled: true,
      minValue: null,
      maxValue: null,
      step: null,
      enumValues: factorKey === "rating" ? ["AA", "AA+", "AAA"] : [],
    };
  }

  const defaults: Record<string, [number, number, number]> = {
    dblow: [100, 180, 5],
    conv_prem: [0, 30, 1],
    turnover: [0.2, 8, 0.2],
    remain_size: [1, 80, 1],
    price_max: [105, 150, 1],
    premium_max: [5, 35, 0.5],
  };
  const [minValue, maxValue, step] = defaults[factorKey] ?? [0, 10, 1];
  return {
    factorKey,
    valueType: "number",
    enabled: true,
    minValue,
    maxValue,
    step,
    enumValues: [],
  };
}

function parseNumberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function comboCount(rows: StrategyParamSpaceRow[]): number {
  if (!rows.length) return 0;
  let total = 1;
  for (const row of rows) {
    if (!row.enabled) continue;
    if (row.valueType === "enum") {
      const size = row.enumValues.filter((item) => item.trim()).length || 1;
      total *= size;
      continue;
    }
    if (row.minValue === null || row.maxValue === null || row.step === null || row.step <= 0 || row.maxValue < row.minValue) {
      continue;
    }
    const size = Math.floor((row.maxValue - row.minValue + 1e-9) / row.step) + 1;
    total *= Math.max(1, size);
  }
  return Math.max(1, total);
}

export default function StrategyDetailPage() {
  const router = useRouter();
  const params = useParams<{ templateId: string }>();
  const strategyId = params?.templateId ?? "";

  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [hint, setHint] = useState<string>("");

  const [strategy, setStrategy] = useState<StrategyTemplate | null>(null);
  const [factorCatalog, setFactorCatalog] = useState<FactorCatalogCategory[]>([]);

  const [draft, setDraft] = useState({
    name: "",
    status: "draft" as StrategyTemplateStatus,
    rebalance: "weekly",
    riskPreset: "balanced",
    owner: "quant_new",
  });

  const [factorKeyword, setFactorKeyword] = useState<string>("");
  const [selectedFactorKeys, setSelectedFactorKeys] = useState<string[]>([]);
  const [parameterSpaceMap, setParameterSpaceMap] = useState<Record<string, StrategyParamSpaceRow>>({});
  const [expressionDraft, setExpressionDraft] = useState<string>("");

  const [paramPage, setParamPage] = useState<number>(1);
  const [paramPageSize, setParamPageSize] = useState<number>(10);

  useEffect(() => {
    const load = async (): Promise<void> => {
      if (!strategyId) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError("");
      try {
        const [detail, factorResp] = await Promise.all([
          getStrategyTemplateDetail(strategyId),
          listFactorCatalog({ category: "all" }),
        ]);

        setStrategy(detail.template);
        setDraft({
          name: detail.template.name,
          status: detail.template.status,
          rebalance: detail.template.rebalance,
          riskPreset: detail.template.riskPreset,
          owner: detail.template.owner,
        });

        setFactorCatalog(factorResp.items);

        const factorKeys = detail.config.factorKeys.length ? detail.config.factorKeys : defaultFactorKeys;
        setSelectedFactorKeys(factorKeys);
        setExpressionDraft(detail.config.expressionDraft ?? "");

        const map = Object.fromEntries(
          detail.config.parameterSpace.map((row) => [
            row.factorKey,
            {
              ...row,
              enumValues: row.enumValues ?? [],
            },
          ]),
        );
        setParameterSpaceMap(map);
      } catch (err) {
        setError(err instanceof Error ? err.message : "策略详情加载失败");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [strategyId]);

  const factorOptions = useMemo<FactorOption[]>(() => {
    return factorCatalog.flatMap((category) =>
      category.factors.map((factor) => ({
        factorKey: factor.factorKey,
        factorName: factor.factorName,
        expressionType: factor.expressionType,
        categoryKey: category.categoryKey,
        categoryName: category.categoryName,
      })),
    );
  }, [factorCatalog]);

  const factorMap = useMemo<Record<string, FactorOption>>(
    () => Object.fromEntries(factorOptions.map((row) => [row.factorKey, row])),
    [factorOptions],
  );

  useEffect(() => {
    if (!selectedFactorKeys.length) return;
    setParameterSpaceMap((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const factorKey of selectedFactorKeys) {
        if (next[factorKey]) continue;
        next[factorKey] = defaultParamRow(factorKey, factorMap[factorKey]?.expressionType);
        changed = true;
      }
      return changed ? next : prev;
    });
  }, [selectedFactorKeys, factorMap]);

  const filteredFactors = useMemo(() => {
    const keyword = factorKeyword.trim().toLowerCase();
    return factorOptions.filter((row) => {
      if (!keyword) return true;
      return row.factorKey.toLowerCase().includes(keyword) || row.factorName.toLowerCase().includes(keyword);
    });
  }, [factorOptions, factorKeyword]);

  const parameterRows = useMemo<EditableParamRow[]>(() => {
    return selectedFactorKeys.map((factorKey) => {
      const meta = factorMap[factorKey];
      const row = parameterSpaceMap[factorKey] ?? defaultParamRow(factorKey, meta?.expressionType);
      return {
        ...row,
        factorName: meta?.factorName ?? factorKey,
        categoryKey: meta?.categoryKey ?? "custom",
        categoryName: meta?.categoryName ?? "未分类",
      };
    });
  }, [selectedFactorKeys, factorMap, parameterSpaceMap]);

  const pagedRows = useMemo(() => getPagedRows(parameterRows, paramPage, paramPageSize), [parameterRows, paramPage, paramPageSize]);
  const totalPages = useMemo(() => getTotalPages(parameterRows.length, paramPageSize), [parameterRows.length, paramPageSize]);

  useEffect(() => {
    if (paramPage > totalPages) setParamPage(totalPages);
  }, [paramPage, totalPages]);

  const normalizedParameterSpace = useMemo<StrategyParamSpaceRow[]>(
    () =>
      selectedFactorKeys.map((factorKey) => {
        const row = parameterSpaceMap[factorKey] ?? defaultParamRow(factorKey, factorMap[factorKey]?.expressionType);
        return {
          factorKey,
          valueType: row.valueType,
          enabled: row.enabled,
          minValue: row.minValue,
          maxValue: row.maxValue,
          step: row.step,
          enumValues: row.enumValues,
        };
      }),
    [selectedFactorKeys, parameterSpaceMap, factorMap],
  );

  const estimatedCombos = useMemo(() => comboCount(normalizedParameterSpace), [normalizedParameterSpace]);

  const toggleFactor = (factorKey: string): void => {
    setSelectedFactorKeys((prev) => {
      if (prev.includes(factorKey)) {
        return prev.filter((item) => item !== factorKey);
      }
      return [...prev, factorKey];
    });
  };

  const updateParamRow = (factorKey: string, patch: Partial<StrategyParamSpaceRow>): void => {
    setParameterSpaceMap((prev) => {
      const current = prev[factorKey] ?? defaultParamRow(factorKey, factorMap[factorKey]?.expressionType);
      return {
        ...prev,
        [factorKey]: {
          ...current,
          ...patch,
        },
      };
    });
  };

  const saveStrategy = async (): Promise<void> => {
    if (!strategy) return;
    setSaving(true);
    setError("");
    setHint("");
    try {
      await updateStrategyTemplate(strategy.id, {
        name: draft.name,
        status: draft.status,
        rebalance: draft.rebalance,
        riskPreset: draft.riskPreset,
        owner: draft.owner,
      });
      const config = await updateStrategyTemplateConfig(strategy.id, {
        factorKeys: selectedFactorKeys,
        expressionDraft,
        parameterSpace: normalizedParameterSpace,
      });
      const refreshed = await getStrategyTemplateDetail(strategy.id);
      setStrategy(refreshed.template);
      setHint(`策略已保存，参数空间组合数：${config.comboSize.toLocaleString()}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "策略保存失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <CbQuantPageShell title="策略详情" subtitle="加载中...">
        <div className="rounded-xl border border-gray-200 bg-white p-6 text-sm text-gray-600 dark:border-gray-800 dark:bg-white/[0.03] dark:text-gray-300">正在加载策略详情...</div>
      </CbQuantPageShell>
    );
  }

  if (!strategy) {
    return (
      <CbQuantPageShell title="策略详情" subtitle="策略不存在或已删除">
        <div className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03]">
          {error ? <p className="text-sm text-red-600 dark:text-red-300">{error}</p> : null}
          <button
            type="button"
            onClick={() => router.push("/cb-quant/strategy-generation")}
            className="mt-4 rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600"
          >
            返回策略库
          </button>
        </div>
      </CbQuantPageShell>
    );
  }

  return (
    <CbQuantPageShell
      title={`策略详情 · ${strategy.id}`}
      subtitle="配置因子与参数空间，回测评估页将按真实组合规模执行全量搜索。"
    >
      <div className="space-y-6">
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex flex-col gap-3 border-b border-gray-200 p-4 lg:flex-row lg:items-center lg:justify-between dark:border-gray-800">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{strategy.name}</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">策略ID: {strategy.id}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => router.push("/cb-quant/strategy-generation")}
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/[0.04]"
              >
                返回策略库
              </button>
              <button
                type="button"
                onClick={() => router.push(`/cb-quant/backtest-evaluation?strategyId=${strategy.id}`)}
                className="rounded-lg border border-brand-300 px-3 py-2 text-sm font-medium text-brand-600 hover:bg-brand-50 dark:border-brand-400/40 dark:text-brand-300 dark:hover:bg-brand-500/10"
              >
                去回测评估
              </button>
              <button
                type="button"
                onClick={() => void saveStrategy()}
                disabled={saving}
                className="rounded-lg bg-brand-500 px-3 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? "保存中..." : "保存策略"}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2 xl:grid-cols-5">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">策略名</label>
              <input
                value={draft.name}
                onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
                className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">状态</label>
              <select
                value={draft.status}
                onChange={(event) => setDraft((prev) => ({ ...prev, status: event.target.value as StrategyTemplateStatus }))}
                className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              >
                <option value="active">active</option>
                <option value="draft">draft</option>
                <option value="archived">archived</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">调仓</label>
              <input
                value={draft.rebalance}
                onChange={(event) => setDraft((prev) => ({ ...prev, rebalance: event.target.value }))}
                className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500 dark:text-gray-400">风控预设</label>
              <input
                value={draft.riskPreset}
                onChange={(event) => setDraft((prev) => ({ ...prev, riskPreset: event.target.value }))}
                className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              />
            </div>
            <div className="flex items-end">
              <div className="w-full rounded-lg border border-gray-200 px-3 py-2 dark:border-gray-700">
                <p className="text-xs text-gray-500 dark:text-gray-400">当前状态</p>
                <div className="mt-1"><StatusTag label={draft.status} tone={statusTone(draft.status)} /></div>
              </div>
            </div>
          </div>

          {error ? (
            <p className="mx-4 mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-500/10 dark:text-red-300">
              {error}
            </p>
          ) : null}
          {hint ? (
            <p className="mx-4 mb-4 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700 dark:border-green-900/50 dark:bg-green-500/10 dark:text-green-300">
              {hint}
            </p>
          ) : null}
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">步骤1：选择因子</h3>
          <div className="mt-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <input
              value={factorKeyword}
              onChange={(event) => setFactorKeyword(event.target.value)}
              placeholder="搜索因子 key/name..."
              className="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-900 lg:max-w-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
            />
            <p className="text-sm text-gray-500 dark:text-gray-400">已选择 {selectedFactorKeys.length} 个因子</p>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
            {filteredFactors.map((factor) => {
              const checked = selectedFactorKeys.includes(factor.factorKey);
              return (
                <label
                  key={`${factor.categoryKey}-${factor.factorKey}`}
                  className={`flex cursor-pointer items-center justify-between rounded-lg border px-3 py-2 ${
                    checked
                      ? "border-brand-300 bg-brand-50 dark:border-brand-500/50 dark:bg-brand-500/10"
                      : "border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900"
                  }`}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-gray-900 dark:text-white">{factor.factorName}</span>
                    <span className="block truncate text-xs text-gray-500 dark:text-gray-400">{factor.factorKey} · {factor.categoryName}</span>
                  </span>
                  <input type="checkbox" checked={checked} onChange={() => toggleFactor(factor.factorKey)} />
                </label>
              );
            })}
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
          <div className="flex flex-col gap-3 border-b border-gray-200 px-4 py-3 lg:flex-row lg:items-center lg:justify-between dark:border-gray-800">
            <h3 className="text-base font-semibold text-gray-900 dark:text-white">步骤2：配置参数空间（上下限/步长）</h3>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 dark:text-gray-400">每页</span>
              <select
                value={paramPageSize}
                onChange={(event) => {
                  setParamPageSize(Number(event.target.value));
                  setParamPage(1);
                }}
                className="h-9 rounded-lg border border-gray-300 bg-transparent px-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
              >
                {pageSizeOptions.map((size) => (
                  <option key={size} value={size}>{size}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="p-4">
            <ScrollableDataTable
              headers={["参数键", "参数名", "分类", "值类型", "启用", "最小值", "最大值", "步长", "枚举值"]}
              minTableWidthClass="min-w-[1300px]"
              colSpan={9}
              isEmpty={pagedRows.length === 0}
              emptyText="请先在上方选择因子"
            >
              {pagedRows.map((row) => (
                <TableRow key={row.factorKey} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3 text-sm font-semibold text-gray-900 dark:text-white">{row.factorKey}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-900 dark:text-white">{row.factorName}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.categoryName}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-700 dark:text-gray-300">{row.valueType}</TableCell>
                  <TableCell className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={row.enabled}
                      onChange={(event) => updateParamRow(row.factorKey, { enabled: event.target.checked })}
                    />
                  </TableCell>
                  <TableCell className="px-4 py-3">
                    <input
                      disabled={row.valueType === "enum"}
                      value={row.minValue ?? ""}
                      onChange={(event) => updateParamRow(row.factorKey, { minValue: parseNumberOrNull(event.target.value) })}
                      className="h-9 w-24 rounded border border-gray-300 bg-transparent px-2 text-sm text-gray-900 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                    />
                  </TableCell>
                  <TableCell className="px-4 py-3">
                    <input
                      disabled={row.valueType === "enum"}
                      value={row.maxValue ?? ""}
                      onChange={(event) => updateParamRow(row.factorKey, { maxValue: parseNumberOrNull(event.target.value) })}
                      className="h-9 w-24 rounded border border-gray-300 bg-transparent px-2 text-sm text-gray-900 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                    />
                  </TableCell>
                  <TableCell className="px-4 py-3">
                    <input
                      disabled={row.valueType === "enum"}
                      value={row.step ?? ""}
                      onChange={(event) => updateParamRow(row.factorKey, { step: parseNumberOrNull(event.target.value) })}
                      className="h-9 w-20 rounded border border-gray-300 bg-transparent px-2 text-sm text-gray-900 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                    />
                  </TableCell>
                  <TableCell className="px-4 py-3">
                    <input
                      disabled={row.valueType !== "enum"}
                      value={row.enumValues.join(",")}
                      onChange={(event) =>
                        updateParamRow(row.factorKey, {
                          enumValues: event.target.value
                            .split(",")
                            .map((item) => item.trim())
                            .filter((item) => item.length > 0),
                        })
                      }
                      className="h-9 w-52 rounded border border-gray-300 bg-transparent px-2 text-sm text-gray-900 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={parameterRows.length}
              currentPage={paramPage}
              totalPages={totalPages}
              onPageChange={setParamPage}
            />
          </div>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">步骤3：保存并回测</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">回测页将使用该策略的真实参数空间组合规模执行评估，不再使用候选预览。</p>
          <div className="mt-3 rounded-lg border border-gray-200 px-3 py-2 dark:border-gray-700">
            <p className="text-xs text-gray-500 dark:text-gray-400">参数空间组合规模</p>
            <p className="text-xl font-semibold text-gray-900 dark:text-white">{estimatedCombos.toLocaleString()}</p>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void saveStrategy()}
              disabled={saving}
              className="rounded-lg bg-brand-500 px-3 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "保存中..." : "保存策略"}
            </button>
            <button
              type="button"
              onClick={() => router.push(`/cb-quant/backtest-evaluation?strategyId=${strategy.id}`)}
              className="rounded-lg border border-brand-300 px-3 py-2 text-sm font-medium text-brand-600 hover:bg-brand-50 dark:border-brand-400/40 dark:text-brand-300 dark:hover:bg-brand-500/10"
            >
              去回测评估
            </button>
          </div>
        </div>
      </div>
    </CbQuantPageShell>
  );
}
