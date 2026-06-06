import { fromMarketSlug, getTenxErrorMessage, loadTenxEarningsLens, marketLabel } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxEarningsLensPanel from "@/components/tenx-hunter/TenxEarningsLensPanel";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";

export default async function TenxHunterEarningsMarketPage({ params }: { params: Promise<{ market: string }> }) {
  const { market: marketSlug } = await params;
  const market = fromMarketSlug(marketSlug);

  try {
    const lens = await loadTenxEarningsLens(market);
    return (
      <TenxPageShell
        market={market}
        title="TenX Hunter · Earnings"
        subtitle="财报日历是从候选发现进入观察池前的事件筛选层，集中处理财报窗口、预期和期权链。"
        marketLabel={`${marketLabel(market)} · Earnings Calendar`}
      >
        <TenxEarningsLensPanel lens={lens} />
      </TenxPageShell>
    );
  } catch (error) {
    return (
      <TenxPageShell
        market={market}
        title="TenX Hunter · Earnings"
        subtitle="财报日历不再混在 Discover 里，单独承接事件窗口和财报期权验证。"
        marketLabel={`${marketLabel(market)} · Earnings Calendar`}
      >
        <TenxDataStateCard
          title="Earnings Calendar 实时数据暂不可用"
          message="请确认 vnpy.web API、PostgreSQL，以及财报日历和期权链采集任务都已经启动。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }
}
