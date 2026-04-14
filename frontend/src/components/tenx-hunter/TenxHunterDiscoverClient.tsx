"use client";

import Link from "next/link";
import React, { useMemo, useState } from "react";
import ScrollableDataTable from "@/components/cb-quant/ScrollableDataTable";
import StatusTag from "@/components/cb-quant/StatusTag";
import TablePaginationBar from "@/components/cb-quant/TablePaginationBar";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { getRiskTone, getStageTone, TenxSectionCard } from "@/components/tenx-hunter/TenxCards";
import type { TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";
import { TableCell, TableRow } from "@/components/ui/table";

const stageOptions = ["all", "early", "validation", "acceleration", "crowded"] as const;
const pageSizeOptions = [5, 10];

type TenxHunterDiscoverClientProps = {
  snapshot: TenxWorkspaceSnapshot;
};

export default function TenxHunterDiscoverClient({ snapshot }: TenxHunterDiscoverClientProps) {
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState<string>("all");
  const [theme, setTheme] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [showTimeline, setShowTimeline] = useState(false);

  const keyword = search.trim().toLowerCase();

  const filteredCandidates = useMemo(() => {
    return snapshot.candidates.filter((item) => {
      const hitKeyword =
        !keyword ||
        [item.symbol, item.name, item.theme, item.sector, item.keySignal].some((field) =>
          field.toLowerCase().includes(keyword),
        );
      const hitStage = stage === "all" || item.stage === stage;
      const hitTheme = theme === "all" || item.theme === theme;
      return hitKeyword && hitStage && hitTheme;
    });
  }, [keyword, stage, theme, snapshot.candidates]);

  const themeOptions = useMemo(() => {
    const dynamicThemes = Array.from(new Set(snapshot.candidates.map((item) => item.theme))).sort((a, b) =>
      a.localeCompare(b),
    );
    return ["all", ...dynamicThemes];
  }, [snapshot.candidates]);

  const totalPages = Math.max(1, Math.ceil(filteredCandidates.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pagedCandidates = filteredCandidates.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  return (
    <TenxPageShell
      title="TenX Hunter · Discover"
      subtitle="围绕美股成长科技做候选发现，先看谁值得研究，再进入研究卡片。这里的排序代表研究优先级，而非直接交易建议。"
    >
      <TenxSectionCard
        title="Universe Builder"
        description={`${snapshot.universeDescription} 当前策略：${snapshot.universeStrategy}`}
      >
        <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
          {snapshot.universeBuckets.map((bucket) => (
            <div key={bucket.slug} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-base font-semibold text-gray-900 dark:text-white">{bucket.label}</div>
                  <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{bucket.symbolCount} 个研究标的</div>
                </div>
                <StatusTag label={bucket.slug} tone="slate" />
              </div>
              <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{bucket.rationale}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {bucket.sampleSymbols.map((symbol) => (
                  <StatusTag key={`${bucket.slug}-${symbol}`} label={symbol} tone="blue" />
                ))}
              </div>
            </div>
          ))}
        </div>
      </TenxSectionCard>

      <TenxSectionCard
        title="Candidate Pool"
        description="工作台优先。先完成搜索、筛选和事件扫描，再进入单票研究卡片或观察池动作。"
        action={
          <div className="inline-flex rounded-lg bg-gray-100 p-1 dark:bg-gray-900">
            <button
              type="button"
              onClick={() => setShowTimeline(false)}
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                !showTimeline
                  ? "bg-white text-gray-900 shadow dark:bg-gray-800 dark:text-white"
                  : "text-gray-500 dark:text-gray-400"
              }`}
            >
              候选池
            </button>
            <button
              type="button"
              onClick={() => setShowTimeline(true)}
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                showTimeline
                  ? "bg-white text-gray-900 shadow dark:bg-gray-800 dark:text-white"
                  : "text-gray-500 dark:text-gray-400"
              }`}
            >
              事件流
            </button>
          </div>
        }
      >
        <div className="mb-5 grid grid-cols-1 gap-3 lg:grid-cols-[1.6fr_repeat(3,minmax(0,1fr))]">
          <input
            type="text"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Search symbol / company / theme / signal..."
            className="h-11 rounded-lg border border-gray-300 bg-transparent px-4 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          />
          <select
            value={stage}
            onChange={(event) => {
              setStage(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          >
            {stageOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <select
            value={theme}
            onChange={(event) => {
              setTheme(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          >
            {themeOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <select
            value={String(pageSize)}
            onChange={(event) => {
              setPageSize(Number(event.target.value));
              setPage(1);
            }}
            className="h-11 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-800 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>{`每页 ${size} 条`}</option>
            ))}
          </select>
        </div>

        {!showTimeline ? (
          <>
            <ScrollableDataTable
              headers={["Symbol", "Theme", "Stage", "Score", "Price", "Risk", "Next event", "Why selected"]}
              minTableWidthClass="min-w-[1100px]"
              colSpan={8}
              isEmpty={!pagedCandidates.length}
            >
              {pagedCandidates.map((row) => (
                <TableRow key={row.symbol} className="border-b border-gray-100 last:border-b-0 dark:border-gray-800">
                  <TableCell className="px-4 py-3 align-top">
                    <Link
                      href={`/tenx-hunter/research/${row.symbol}`}
                      className="font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300"
                    >
                      {row.symbol}
                    </Link>
                    <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{row.name}</div>
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{row.theme}</TableCell>
                  <TableCell className="px-4 py-3">
                    <StatusTag label={row.stage} tone={getStageTone(row.stage)} />
                    <div className="mt-2 max-w-[220px] text-xs leading-5 text-gray-500 dark:text-gray-400">
                      {row.stageReason ?? row.theme}
                    </div>
                  </TableCell>
                  <TableCell className="px-4 py-3 align-top">
                    <div className="font-semibold text-gray-900 dark:text-white">{row.score}</div>
                    <div
                      className={`text-xs ${
                        row.scoreChange >= 0 ? "text-green-600 dark:text-green-300" : "text-red-600 dark:text-red-300"
                      }`}
                    >
                      {row.scoreChange >= 0 ? "+" : ""}
                      {row.scoreChange.toFixed(1)}
                    </div>
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">
                    ${row.price.toFixed(2)} · {row.priceChangePct >= 0 ? "+" : ""}
                    {row.priceChangePct.toFixed(1)}%
                  </TableCell>
                  <TableCell className="px-4 py-3">
                    <StatusTag label={row.riskLevel} tone={getRiskTone(row.riskLevel)} />
                  </TableCell>
                  <TableCell className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{row.nextEvent}</TableCell>
                  <TableCell className="px-4 py-3 text-sm leading-6 text-gray-600 dark:text-gray-300">
                    <div>{row.selectionReason ?? row.keySignal}</div>
                    <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">{row.crowdingNote ?? row.keySignal}</div>
                  </TableCell>
                </TableRow>
              ))}
            </ScrollableDataTable>
            <TablePaginationBar
              totalItems={filteredCandidates.length}
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </>
        ) : (
          <div className="space-y-4">
            {snapshot.timeline.map((event) => (
              <div key={event.id} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">{event.date}</div>
                    <div className="mt-1 text-base font-semibold text-gray-900 dark:text-white">{event.title}</div>
                    <div className="mt-1 text-sm text-gray-600 dark:text-gray-300">{event.summary}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusTag label={event.type} tone="blue" />
                    <Link
                      href={`/tenx-hunter/research/${event.symbol}`}
                      className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-300 dark:hover:text-brand-200"
                    >
                      {event.symbol}
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </TenxSectionCard>
    </TenxPageShell>
  );
}
