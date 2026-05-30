"use client";

import { useState } from "react";

export default function WatchlistRulesDrawer() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-9 items-center rounded-lg border border-gray-200 px-3 text-sm font-semibold text-gray-700 hover:border-brand-300 hover:text-brand-600 dark:border-gray-800 dark:text-gray-300 dark:hover:border-brand-700 dark:hover:text-brand-300"
      >
        观察池规则
      </button>
      {open ? (
        <div className="fixed inset-0 z-[999999]">
          <button
            type="button"
            aria-label="关闭观察池规则"
            className="absolute inset-0 bg-gray-900/35"
            onClick={() => setOpen(false)}
          />
          <aside className="absolute right-0 top-0 flex h-full w-full max-w-md flex-col border-l border-gray-200 bg-white shadow-2xl dark:border-gray-800 dark:bg-gray-950">
            <div className="flex items-start justify-between gap-4 border-b border-gray-200 px-6 py-5 dark:border-gray-800">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">观察池规则</h2>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">首期只保留研究动作，不开放交易动作。</p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-semibold text-gray-500 hover:text-gray-900 dark:border-gray-800 dark:text-gray-400 dark:hover:text-white"
              >
                关闭
              </button>
            </div>
            <div className="space-y-3 overflow-y-auto p-6 text-sm text-gray-600 dark:text-gray-300">
              <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
                <div className="font-semibold text-gray-800 dark:text-white/90">逻辑增强</div>
                <p className="mt-2">优先刷新研究卡片和提醒，不把 UI 做成交易终端。</p>
              </div>
              <div className="rounded-xl bg-gray-50 p-4 dark:bg-gray-900/60">
                <div className="font-semibold text-gray-800 dark:text-white/90">需要复核</div>
                <p className="mt-2">证据不足、分歧增大或风险上升时，显式降级为人工复核。</p>
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}
