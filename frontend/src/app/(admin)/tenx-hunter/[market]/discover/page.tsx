import { fromMarketSlug, getTenxErrorMessage, loadTenxWorkspaceSnapshot } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxHunterDiscoverClient from "@/components/tenx-hunter/TenxHunterDiscoverClient";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";

export default async function TenxHunterDiscoverMarketPage({ params }: { params: Promise<{ market: string }> }) {
  const { market: marketSlug } = await params;
  const market = fromMarketSlug(marketSlug);
  try {
    const snapshot = await loadTenxWorkspaceSnapshot(market);
    return <TenxHunterDiscoverClient snapshot={snapshot} />;
  } catch (error) {
    return (
      <TenxPageShell
        market={market}
        title="TenX Hunter · Discover"
        subtitle="围绕真实数据做候选发现，不再回退任何 mock 结果。"
        marketLabel={market === "CN" ? "A股发现" : "US Discover"}
      >
        <TenxDataStateCard
          title="TenX 实时候选池暂不可用"
          message="请确认 vnpy.web API、PostgreSQL，以及对应市场的 TenX data pipeline 都已经启动。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }
}
