import { fromMarketSlug, getTenxErrorMessage, loadTenxAlerts, marketLabel } from "@/components/tenx-hunter/api";
import {
  AlertList,
  buildAlertFilterCounts,
  filterAlerts,
  getSearchParamValue,
  normalizeAlertFilter,
  sortAlerts,
} from "@/components/tenx-hunter/TenxAlertViews";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { TenxSectionCard } from "@/components/tenx-hunter/TenxCards";
import type { TenxAlertCenter } from "@/components/tenx-hunter/types";
import { redirect } from "next/navigation";

export default async function TenxHunterAlertsMarketPage({
  params,
  searchParams,
}: {
  params: Promise<{ market: string }>;
  searchParams?: Promise<{ alert?: string | string[]; filter?: string | string[] }>;
}) {
  const { market: marketSlug } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : {};
  const legacyAlertId = getSearchParamValue(resolvedSearchParams.alert);
  if (legacyAlertId) {
    redirect(`/tenx-hunter/${marketSlug}/alerts/${encodeURIComponent(legacyAlertId)}`);
  }

  const market = fromMarketSlug(marketSlug);
  const normalizedMarketSlug = market.toLowerCase();
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

  const alertItems = sortAlerts(alerts.items);
  const activeFilter = normalizeAlertFilter(resolvedSearchParams.filter);
  const filteredAlerts = filterAlerts(alertItems, activeFilter);
  const filterCounts = buildAlertFilterCounts(alertItems);

  return (
    <TenxPageShell
      market={market}
      title="TenX Hunter · Alerts"
      subtitle="把值得打断注意力的逻辑变化集中起来。"
      marketLabel={`${marketLabel(market)} · Alert Center`}
    >
      <TenxSectionCard title="Alert Center" description="点击事件进入详情页复核。">
        {alertItems.length ? (
          <AlertList
            items={filteredAlerts}
            marketSlug={normalizedMarketSlug}
            activeFilter={activeFilter}
            counts={filterCounts}
          />
        ) : (
          <div className="rounded-xl bg-gray-50 px-4 py-6 text-sm leading-6 text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
            暂无事件提醒。
          </div>
        )}
      </TenxSectionCard>
    </TenxPageShell>
  );
}
