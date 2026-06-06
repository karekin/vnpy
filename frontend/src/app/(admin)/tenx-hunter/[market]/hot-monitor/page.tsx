import { redirect } from "next/navigation";
import { fromMarketSlug, marketLabel } from "@/components/tenx-hunter/api";
import { getSocialHotErrorMessage, loadSocialHotStocks, type SocialHotStocksResponse } from "@/components/tenx-hunter/socialHotApi";
import TenxHotUsMonitorClient from "@/components/tenx-hunter/TenxHotUsMonitorClient";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";

export default async function TenxHotMonitorMarketPage({ params }: { params: Promise<{ market: string }> }) {
  const { market: marketSlug } = await params;
  const market = fromMarketSlug(marketSlug);

  if (market !== "US") {
    redirect("/tenx-hunter/us/hot-monitor");
  }

  let response: SocialHotStocksResponse;
  try {
    response = await loadSocialHotStocks();
  } catch (error) {
    return (
      <TenxPageShell
        market="US"
        title="TenX Hunter · 热门美股监控"
        subtitle="ApeWisdom 社交媒体热股榜，统计 Reddit 股票社区过去 24 小时提及和点赞。"
        marketLabel={marketLabel("US")}
        pipelineStage="hot-monitor"
      >
        <TenxHotUsMonitorClient initialResponse={null} initialError={getSocialHotErrorMessage(error)} />
      </TenxPageShell>
    );
  }

  return (
    <TenxPageShell
      market="US"
      title="TenX Hunter · 热门美股监控"
      subtitle="把 Reddit 社区提及次数、24 小时变化和点赞数压缩成一个实时社交热榜。"
      marketLabel={`${marketLabel("US")} · Hot Monitor`}
      pipelineStage="hot-monitor"
    >
      <TenxHotUsMonitorClient initialResponse={response} />
    </TenxPageShell>
  );
}
