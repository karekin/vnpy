import StatusTag from "@/components/cb-quant/StatusTag";
import { fromMarketSlug, getTenxErrorMessage, loadTenxAlerts, marketLabel } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { TenxSectionCard } from "@/components/tenx-hunter/TenxCards";
import type { TenxAlertCenter } from "@/components/tenx-hunter/types";

function severityTone(severity: "P1" | "P2" | "P3") {
  if (severity === "P1") return "red" as const;
  if (severity === "P2") return "yellow" as const;
  return "slate" as const;
}

export default async function TenxHunterAlertsMarketPage({ params }: { params: Promise<{ market: string }> }) {
  const { market: marketSlug } = await params;
  const market = fromMarketSlug(marketSlug);
  let alerts: TenxAlertCenter;
  try {
    alerts = await loadTenxAlerts(market);
  } catch (error) {
    return (
      <TenxPageShell
        market={market}
        title="TenX Hunter · Alerts"
        subtitle="提醒中心只展示逻辑变化，而不是噪音通知。"
        marketLabel={marketLabel(market)}
      >
        <TenxDataStateCard
          title="Alert Center 暂不可用"
          message="请检查提醒中心 API、数据库以及 TenX 写接口骨架是否正常。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }

  return (
    <TenxPageShell
      market={market}
      title="TenX Hunter · Alerts"
      subtitle="把值得打断注意力的逻辑变化集中起来。"
      marketLabel={`${marketLabel(market)} · Alert Center`}
    >
      <TenxSectionCard title="Alert Center" description={`最新刷新：${alerts.freshness.updatedAt}`}>
        <div className="space-y-4">
          {alerts.items.map((item) => (
            <div key={item.id} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <StatusTag label={item.severity} tone={severityTone(item.severity)} />
                    <StatusTag label={item.alertType} tone="blue" />
                    <div className="text-sm text-gray-500 dark:text-gray-400">{item.symbol}</div>
                  </div>
                  <div className="mt-2 text-base font-semibold text-gray-900 dark:text-white">{item.title}</div>
                  <div className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{item.summary}</div>
                </div>
                <div className="text-right text-sm text-gray-500 dark:text-gray-400">
                  <div>{item.createdAt}</div>
                  <div className="mt-2">{item.source}</div>
                </div>
              </div>
              <div className="mt-3 rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
                下一步：{item.nextAction}
              </div>
            </div>
          ))}
        </div>
      </TenxSectionCard>
    </TenxPageShell>
  );
}
