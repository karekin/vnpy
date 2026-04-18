"use client";

import { createAlertDraft, createWatchlistEntry } from "@/components/tenx-hunter/api";
import type { TenxMarket } from "@/components/tenx-hunter/types";
import { useState } from "react";

type Props = {
  market: TenxMarket;
  symbol: string;
};

export default function TenxActionDrawer({ market, symbol }: Props) {
  const [message, setMessage] = useState<string>("");
  const [pending, setPending] = useState<"watch" | "alert" | null>(null);

  async function handleWatch() {
    try {
      setPending("watch");
      const result = await createWatchlistEntry(market, symbol, "watch");
      setMessage(result.message);
    } finally {
      setPending(null);
    }
  }

  async function handleAlert() {
    try {
      setPending("alert");
      const result = await createAlertDraft(market, symbol, `${symbol} 逻辑变更提醒`, "请在财务兑现、主题变化或风险升级时提醒我复核。");
      setMessage(result.message);
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="text-sm font-semibold text-gray-800 dark:text-white/90">Action Drawer</div>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleWatch}
          disabled={pending !== null}
          className="rounded-lg border border-brand-500 px-3 py-2 text-sm font-medium text-brand-700 transition hover:bg-brand-50 disabled:opacity-60 dark:border-brand-400 dark:text-brand-300 dark:hover:bg-brand-500/10"
        >
          {pending === "watch" ? "提交中..." : "加入观察池"}
        </button>
        <button
          type="button"
          onClick={handleAlert}
          disabled={pending !== null}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 disabled:opacity-60 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
        >
          {pending === "alert" ? "创建中..." : "创建提醒"}
        </button>
      </div>
      {message ? <div className="mt-3 text-sm text-gray-600 dark:text-gray-300">{message}</div> : null}
    </div>
  );
}
