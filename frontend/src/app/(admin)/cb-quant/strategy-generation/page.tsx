"use client";

import {
  batchDeleteStrategyTemplates,
  batchEnableStrategyTemplates,
  createStrategyTemplate,
  deleteStrategyTemplate,
  expandStrategyFactorCombos,
  getStrategyTemplateDetail,
  listStrategyTemplates,
  updateStrategyTemplate,
  updateStrategyTemplateConfig,
  type StrategyParamSpaceRow,
  type StrategyTemplate,
} from "@/components/cb-quant/api";
import CbQuantPageShell from "@/components/cb-quant/CbQuantPageShell";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import { getTotalPages } from "@/components/cb-quant/tableUtils";
import { TableCell, TableRow } from "@/components/ui/table";
import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useState } from "react";

function getStrategyTone(status: "active" | "draft" | "archived") {
  if (status === "active") return "green" as const;
  if (status === "draft") return "yellow" as const;
  return "slate" as const;
}

function choose(n: number, k: number): number {
  if (k < 0 || n < k) return 0;
  if (k === 0 || n === k) return 1;
  let result = 1;
  for (let i = 1; i <= k; i += 1) {
    result = (result * (n - i + 1)) / i;
  }
  return Math.round(result);
}

const baselineFactorKeys = [
  "dblow",
  "conv_prem",
  "turnover",
  "remain_size",
  "rating",
  "price_bemchmark",
  "premium_bemchmark",
  "stock_ratio",
  "premium_ratio",
  "stock_stdevry_bemchmark",
  "max_price",
  "head_count",
  "remain_ratio",
  "max_hold_num",
];

function baselineParamRow(factorKey: string): StrategyParamSpaceRow {
  if (factorKey === "rating") {
    return {
      factorKey,
      valueType: "enum",
      enabled: true,
      minValue: null,
      maxValue: null,
      step: null,
      enumValues: ["AA", "AA+", "AAA"],
    };
  }

  const defaults: Record<string, [number, number, number]> = {
    dblow: [100, 180, 5],
    conv_prem: [0, 40, 2],
    turnover: [0.2, 8, 0.2],
    remain_size: [1, 80, 1],
    price_bemchmark: [106, 124, 2],
    premium_bemchmark: [16, 34, 2],
    stock_ratio: [0.2, 0.35, 0.05],
    premium_ratio: [0.15, 0.35, 0.05],
    stock_stdevry_bemchmark: [20, 35, 5],
    max_price: [130, 200, 10],
    head_count: [5, 15, 5],
    remain_ratio: [0.1, 0.2, 0.05],
    max_hold_num: [5, 10, 5],
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

export default function CbQuantStrategyGenerationPage() {
  const router = useRouter();

  const [search, setSearch] = useState<string>("");
  const [strategies, setStrategies] = useState<StrategyTemplate[]>([]);
  const [page, setPage] = useState<number>(1);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);
  const [runningActionId, setRunningActionId] = useState<string>("");
  const [selectedStrategyIds, setSelectedStrategyIds] = useState<string[]>([]);
  const [selectingAll, setSelectingAll] = useState<boolean>(false);

  const [hint, setHint] = useState<string>("");
  const [error, setError] = useState<string>("");

  const keyword = search.trim();
  const selectedSet = useMemo(() => new Set(selectedStrategyIds), [selectedStrategyIds]);

  const loadStrategies = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await listStrategyTemplates({
        keyword,
        page,
        pageSize: 10,
      });
      setStrategies(response.items);
      setTotal(response.total);
      setTotalPages(getTotalPages(response.total, 10));
    } catch (err) {
      setStrategies([]);
      setTotal(0);
      setTotalPages(1);
      setError(err instanceof Error ? err.message : "策略列表加载失败");
    } finally {
      setLoading(false);
    }
  }, [keyword, page]);

  const loadAllStrategies = useCallback(async (): Promise<StrategyTemplate[]> => {
    const pageSize = 500;
    let nextPage = 1;
    const all: StrategyTemplate[] = [];

    while (true) {
      const response = await listStrategyTemplates({
        keyword,
        page: nextPage,
        pageSize,
      });
      all.push(...response.items);
      if (all.length >= response.total || response.items.length === 0) {
        break;
      }
      nextPage += 1;
      if (nextPage > 100) {
        break;
      }
    }

    return all;
  }, [keyword]);

  useEffect(() => {
    void loadStrategies();
  }, [loadStrategies]);

  const handleCreateStrategy = async () => {
    setError("");
    setHint("");
    try {
      const created = await createStrategyTemplate({ name: "新策略", owner: "quant_new" });
      await loadStrategies();
      router.push(`/cb-quant/strategy-generation/template/${created.id}?mode=edit`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "新建策略失败");
    }
  };

  const handleCopyStrategy = async (strategy: StrategyTemplate) => {
    setRunningActionId(strategy.id);
    setError("");
    setHint("");
    try {
      const copied = await createStrategyTemplate({
        name: `${strategy.name}-副本`,
        owner: strategy.owner,
      });
      await updateStrategyTemplate(copied.id, {
        status: "draft",
        rebalance: strategy.rebalance,
        riskPreset: strategy.riskPreset,
      });
      const detail = await getStrategyTemplateDetail(strategy.id);
      await updateStrategyTemplateConfig(copied.id, {
        factorKeys: detail.config.factorKeys,
        expressionDraft: detail.config.expressionDraft,
        parameterSpace: detail.config.parameterSpace,
      });
      await loadStrategies();
      setHint(`已复制策略：${copied.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "复制策略失败");
    } finally {
      setRunningActionId("");
    }
  };

  const handleExpandAllStrategies = async () => {
    setError("");
    setHint("");

    setRunningActionId("GLOBAL_EXPAND");
    try {
      const allStrategies = await loadAllStrategies();
      let targets = selectedStrategyIds.length
        ? allStrategies.filter((row) => selectedSet.has(row.id))
        : allStrategies;
      let autoCreatedTemplate: StrategyTemplate | null = null;

      if (!targets.length) {
        if (keyword) {
          setError("当前筛选结果为空，请清空搜索或调整筛选条件后重试。");
          return;
        }
        autoCreatedTemplate = await createStrategyTemplate({ name: "双三因子基准策略", owner: "quant_new" });
        await updateStrategyTemplateConfig(autoCreatedTemplate.id, {
          factorKeys: baselineFactorKeys,
          expressionDraft: "",
          parameterSpace: baselineFactorKeys.map((factorKey) => baselineParamRow(factorKey)),
        });
        const detail = await getStrategyTemplateDetail(autoCreatedTemplate.id);
        targets = [detail.template];
      }

      const eligibleTargets = targets.filter((row) => row.factorCount >= 2);

      if (!eligibleTargets.length) {
        setError("所选策略因子数不足 2，无法生成双因子/三因子组合。");
        return;
      }

      const subsetEstimate = eligibleTargets.reduce(
        (sum, row) => sum + choose(row.factorCount, 2) + choose(row.factorCount, 3),
        0,
      );
      const ok = window.confirm(
        `将为 ${eligibleTargets.length} 个策略生成全部“双因子+三因子”组合（理论子集约 ${subsetEstimate.toLocaleString()} 个），继续执行吗？`,
      );
      if (!ok) {
        return;
      }

      let createdTotal = 0;
      let subsetTotal = 0;
      for (const target of eligibleTargets) {
        const result = await expandStrategyFactorCombos(target.id, {
          minFactorCount: 2,
          maxFactorCount: 3,
        });
        createdTotal += result.createdCount;
        subsetTotal += result.totalSubsets;
      }

      await loadStrategies();
      const skippedCount = targets.length - eligibleTargets.length;
      const skippedHint = skippedCount > 0 ? `，跳过 ${skippedCount} 个因子数不足 2 的策略` : "";
      const autoCreateHint = autoCreatedTemplate ? `已自动创建基准策略 ${autoCreatedTemplate.id}。` : "";
      setHint(
        `${autoCreateHint}已完成 ${eligibleTargets.length} 个策略的双/三因子组合生成，新增策略 ${createdTotal} 个（理论子集 ${subsetTotal.toLocaleString()} 个）${skippedHint}。`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "全局生成组合失败");
    } finally {
      setRunningActionId("");
    }
  };

  const handleSelectAllFiltered = async () => {
    setError("");
    setHint("");
    setSelectingAll(true);
    try {
      const allStrategies = await loadAllStrategies();
      setSelectedStrategyIds(allStrategies.map((row) => row.id));
      setHint(`已全选当前筛选结果：${allStrategies.length} 个策略。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "全选策略失败");
    } finally {
      setSelectingAll(false);
    }
  };

  const handleBatchEnableStrategies = async () => {
    setError("");
    setHint("");
    if (!selectedStrategyIds.length) {
      setError("请先勾选要启用的策略。");
      return;
    }

    const ok = window.confirm(`确认启用已选 ${selectedStrategyIds.length} 个策略？`);
    if (!ok) return;

    setRunningActionId("GLOBAL_ENABLE");
    try {
      const result = await batchEnableStrategyTemplates(selectedStrategyIds, "active");
      await loadStrategies();
      setHint(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量启用策略失败");
    } finally {
      setRunningActionId("");
    }
  };

  const handleBatchDeleteStrategies = async () => {
    setError("");
    setHint("");
    if (!selectedStrategyIds.length) {
      setError("请先勾选要删除的策略。");
      return;
    }

    const ok = window.confirm(`确认删除已选 ${selectedStrategyIds.length} 个策略？此操作不可恢复。`);
    if (!ok) return;

    setRunningActionId("GLOBAL_DELETE");
    try {
      const result = await batchDeleteStrategyTemplates(selectedStrategyIds);
      setSelectedStrategyIds([]);
      await loadStrategies();
      setHint(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "批量删除策略失败");
    } finally {
      setRunningActionId("");
    }
  };

  const handleDeleteStrategy = async (strategy: StrategyTemplate) => {
    const ok = window.confirm(`确认删除策略 ${strategy.id} - ${strategy.name}？`);
    if (!ok) return;

    setRunningActionId(strategy.id);
    setError("");
    setHint("");
    try {
      await deleteStrategyTemplate(strategy.id);
      setSelectedStrategyIds((prev) => prev.filter((id) => id !== strategy.id));
      await loadStrategies();
      setHint(`已删除策略：${strategy.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除策略失败");
    } finally {
      setRunningActionId("");
    }
  };

  const allSelectedOnPage = strategies.length > 0 && strategies.every((row) => selectedSet.has(row.id));

  const toggleSelectAllOnPage = () => {
    if (allSelectedOnPage) {
      setSelectedStrategyIds((prev) => prev.filter((id) => !strategies.some((row) => row.id === id)));
      return;
    }

    const next = new Set(selectedStrategyIds);
    strategies.forEach((row) => next.add(row.id));
    setSelectedStrategyIds(Array.from(next));
  };

  const toggleSelectOne = (strategyId: string) => {
    setSelectedStrategyIds((prev) => {
      if (prev.includes(strategyId)) {
        return prev.filter((id) => id !== strategyId);
      }
      return [...prev, strategyId];
    });
  };

  return (
    <CbQuantPageShell
      title="策略生成行动页"
      subtitle="维护策略参数并批量生成双因子/三因子组合。"
    >
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
        <div className="flex flex-col gap-3 border-b border-gray-200 px-5 py-4 dark:border-gray-800 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">策略库</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">先配置参数空间，再批量生成双因子/三因子组合。</p>
          </div>
          <div className="flex flex-nowrap items-center gap-2 overflow-x-auto pb-1">
            <div className="relative">
              <span className="absolute top-1/2 left-4 -translate-y-1/2 text-gray-500 dark:text-gray-400">
                <svg className="fill-current" width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    fillRule="evenodd"
                    clipRule="evenodd"
                    d="M3.04199 9.37363C3.04199 5.87693 5.87735 3.04199 9.37533 3.04199C12.8733 3.04199 15.7087 5.87693 15.7087 9.37363C15.7087 12.8703 12.8733 15.7053 9.37533 15.7053C5.87735 15.7053 3.04199 12.8703 3.04199 9.37363ZM9.37533 1.54199C5.04926 1.54199 1.54199 5.04817 1.54199 9.37363C1.54199 13.6991 5.04926 17.2053 9.37533 17.2053C11.2676 17.2053 13.0032 16.5344 14.3572 15.4176L17.1773 18.238C17.4702 18.5309 17.945 18.5309 18.2379 18.238C18.5308 17.9451 18.5309 17.4703 18.238 17.1773L15.4182 14.3573C16.5367 13.0033 17.2087 11.2669 17.2087 9.37363C17.2087 5.04817 13.7014 1.54199 9.37533 1.54199Z"
                    fill=""
                  />
                </svg>
              </span>
              <input
                type="text"
                placeholder="Search strategy/name/owner..."
                className="dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-[320px] min-w-[260px] rounded-lg border border-gray-300 bg-transparent py-2.5 pr-4 pl-11 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
              />
            </div>
            <button
              type="button"
              onClick={handleExpandAllStrategies}
              disabled={Boolean(runningActionId) || loading}
              className="inline-flex h-11 items-center justify-center whitespace-nowrap rounded-lg border border-brand-500 px-4 text-sm font-medium text-brand-600 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-brand-400 dark:text-brand-300"
            >
              {runningActionId === "GLOBAL_EXPAND" ? "生成中..." : "生成双/三因子"}
            </button>
            <button
              type="button"
              onClick={handleBatchEnableStrategies}
              disabled={Boolean(runningActionId) || !selectedStrategyIds.length}
              className="inline-flex h-11 items-center justify-center whitespace-nowrap rounded-lg border border-brand-500 px-4 text-sm font-medium text-brand-600 hover:bg-brand-50 dark:border-brand-400 dark:text-brand-300"
            >
              {runningActionId === "GLOBAL_ENABLE" ? "启用中..." : "启用策略"}
            </button>
            <button
              type="button"
              onClick={handleBatchDeleteStrategies}
              disabled={Boolean(runningActionId) || !selectedStrategyIds.length}
              className="inline-flex h-11 items-center justify-center whitespace-nowrap rounded-lg border border-red-300 px-4 text-sm font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-700 dark:text-red-300"
            >
              {runningActionId === "GLOBAL_DELETE" ? "删除中..." : "删除策略"}
            </button>
            <button
              type="button"
              onClick={handleCreateStrategy}
              disabled={Boolean(runningActionId)}
              className="inline-flex h-11 items-center justify-center whitespace-nowrap rounded-lg bg-brand-500 px-4 text-sm font-medium text-white hover:bg-brand-600"
            >
              新建策略
            </button>
          </div>
        </div>

        <div className="p-5">
          <p className="mb-3 text-sm text-gray-500 dark:text-gray-400">
            已勾选 {selectedStrategyIds.length} 个策略（支持表头全选）。
          </p>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void handleSelectAllFiltered()}
              disabled={selectingAll || loading}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-300"
            >
              {selectingAll ? "全选中..." : "全选筛选结果"}
            </button>
            <button
              type="button"
              onClick={() => setSelectedStrategyIds([])}
              disabled={!selectedStrategyIds.length}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-300"
            >
              清空选择
            </button>
          </div>

          {error ? (
            <p className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600 dark:border-red-900/50 dark:bg-red-500/10 dark:text-red-300">
              {error}
            </p>
          ) : null}
          {hint ? (
            <p className="mb-4 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700 dark:border-green-900/50 dark:bg-green-500/10 dark:text-green-300">
              {hint}
            </p>
          ) : null}

          <ScrollableDataTable
            headers={[
              <input
                key="select-all-on-page"
                type="checkbox"
                aria-label="全选当前页策略"
                checked={allSelectedOnPage}
                onChange={toggleSelectAllOnPage}
              />,
              "策略ID",
              "策略名",
              "状态",
              "因子数",
              "组合规模",
              "更新",
              "操作",
            ]}
            minTableWidthClass="min-w-[1380px]"
            colSpan={8}
            isEmpty={!loading && strategies.length === 0}
            emptyText="暂无策略，请先新建策略"
          >
            {strategies.map((row) => {
              const disabled = Boolean(runningActionId);
              return (
                <TableRow key={row.id} className="border-b border-gray-100 dark:border-gray-800">
                  <TableCell className="px-4 py-3">
                    <input
                      type="checkbox"
                      aria-label={`选择策略 ${row.id}`}
                      checked={selectedSet.has(row.id)}
                      onChange={() => toggleSelectOne(row.id)}
                    />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-base font-semibold text-gray-900 dark:text-white">{row.id}</TableCell>
                  <TableCell className="px-4 py-3 text-base text-gray-900 dark:text-white">{row.name}</TableCell>
                  <TableCell className="px-4 py-3">
                    <StatusTag label={row.status} tone={getStrategyTone(row.status)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-base text-gray-700 dark:text-gray-300">{row.factorCount}</TableCell>
                  <TableCell className="px-4 py-3 text-base font-medium text-gray-900 dark:text-white">{row.comboSize.toLocaleString()}</TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">{row.updatedAt}</TableCell>
                  <TableCell className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => router.push(`/cb-quant/strategy-generation/template/${row.id}`)}
                        className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300"
                      >
                        参数设置
                      </button>
                      <button
                        type="button"
                        disabled={disabled}
                        onClick={() => void handleCopyStrategy(row)}
                        className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-300"
                      >
                        复制
                      </button>
                      <button
                        type="button"
                        disabled={disabled}
                        onClick={() => void handleDeleteStrategy(row)}
                        className="rounded-lg border border-red-300 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-700 dark:text-red-300"
                      >
                        删除
                      </button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </ScrollableDataTable>
          <TablePaginationBar
            totalItems={total}
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
          />
        </div>
      </div>
    </CbQuantPageShell>
  );
}
