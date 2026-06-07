import { fromMarketSlug, getTenxErrorMessage, loadTenxEarningsDesk } from "@/components/tenx-hunter/api";
import TenxEarningsDeskClient from "@/components/tenx-hunter/TenxEarningsDeskClient";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";

export default async function TenxHunterEarningsMarketPage({ params }: { params: Promise<{ market: string }> }) {
  const { market: marketSlug } = await params;
  const market = fromMarketSlug(marketSlug);

  const result = await Promise.allSettled([loadTenxEarningsDesk(market)]);

  if (result[0].status === "rejected") {
    return (
      <TenxPageShell
        market={market}
        title="TenX Hunter · Earnings Event Desk"
        subtitle="市场全量财报事件看板。"
        pipelineStage="earnings"
      >
        <TenxDataStateCard
          title="财报事件看板暂不可用"
          message="请确认 vnpy.web API、PostgreSQL，以及对应市场的 TenX data pipeline 都已经启动。"
          detail={getTenxErrorMessage(result[0].reason)}
        />
      </TenxPageShell>
    );
  }

  const deskData = result[0].value;

  return <TenxEarningsDeskClient data={deskData} />;
}
