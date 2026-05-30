import type { Metadata } from "next";
import InvestmentCopilotDashboard from "@/components/investment-copilot/InvestmentCopilotDashboard";
import { InvestmentCopilotApiError, loadInvestmentCopilotDailyBrief } from "@/components/investment-copilot/api";

export const metadata: Metadata = {
  title: "AI 投资驾驶舱 | vn.py",
  description: "汇总账户风控、研究候选和策略状态，生成每日行动建议。",
};

export default async function InvestmentCopilotPage() {
  try {
    const brief = await loadInvestmentCopilotDailyBrief("US");
    return <InvestmentCopilotDashboard brief={brief} />;
  } catch (error) {
    const detail = error instanceof InvestmentCopilotApiError ? `${error.message} ${error.url}` : error instanceof Error ? error.message : "Unknown error";
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100">
        <h1 className="text-xl font-semibold">AI 投资驾驶舱暂不可用</h1>
        <p className="mt-2 text-sm leading-6">请先启动 vnpy.web API，再刷新页面。</p>
        <p className="mt-3 rounded-xl bg-white/60 p-3 text-sm dark:bg-black/20">{detail}</p>
      </div>
    );
  }
}
