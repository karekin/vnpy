import { fromMarketSlug, getTenxErrorMessage, loadTenxAlerts, marketLabel } from "@/components/tenx-hunter/api";
import {
  AlertDetail,
  EventFrameworkStrip,
  findAlertById,
  sortAlerts,
} from "@/components/tenx-hunter/TenxAlertViews";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { TenxSectionCard } from "@/components/tenx-hunter/TenxCards";
import type { TenxAlertCenter } from "@/components/tenx-hunter/types";
import Link from "next/link";

export default async function TenxHunterAlertDetailPage({
  params,
}: {
  params: Promise<{ market: string; alertId: string }>;
}) {
  const { market: marketSlug, alertId } = await params;
  const market = fromMarketSlug(marketSlug);
  const normalizedMarketSlug = market.toLowerCase();
  let alerts: TenxAlertCenter;
  try {
    alerts = await loadTenxAlerts(market);
  } catch (error) {
    return (
      <TenxPageShell
        market={market}
        title="TenX Hunter · Alert Detail"
        subtitle="提醒详情只保留可复核的事件、结构、执行和反证。"
        marketLabel={marketLabel(market)}
      >
        <TenxDataStateCard
          title="Alert Detail 暂不可用"
          message="请检查提醒中心 API、数据库以及 TenX 写接口骨架是否正常。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }

  const alertItems = sortAlerts(alerts.items);
  const alert = findAlertById(alertItems, alertId);

  return (
    <TenxPageShell
      market={market}
      title="TenX Hunter · Alert Detail"
      subtitle="把单个事件拆成可验证、可证伪、可执行的复核清单。"
      marketLabel={`${marketLabel(market)} · Alert Detail`}
    >
      <EventFrameworkStrip updatedAt={alerts.freshness.updatedAt} />

      <TenxSectionCard
        title="Alert Detail"
        description="详情页只展示当前事件的完整复核材料。"
        action={
          <Link
            href={`/tenx-hunter/${normalizedMarketSlug}/alerts`}
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-800 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
          >
            返回列表
          </Link>
        }
      >
        {alert ? (
          <AlertDetail item={alert} />
        ) : (
          <div className="rounded-xl bg-gray-50 px-4 py-6 text-sm leading-6 text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
            <div className="font-semibold text-gray-800 dark:text-white/90">提醒不存在</div>
            <div className="mt-1">这个提醒可能已被删除或不属于当前市场。</div>
            <div className="mt-3 break-words text-xs text-gray-500 dark:text-gray-400">alertId: {alertId}</div>
          </div>
        )}
      </TenxSectionCard>
    </TenxPageShell>
  );
}
