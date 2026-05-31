import { fromMarketSlug, getTenxErrorMessage, loadTenxMarketSentiment, marketLabel } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxMarketSentimentDashboard from "@/components/tenx-hunter/TenxMarketSentimentDashboard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { redirect } from "next/navigation";

type PageProps = {
  params: Promise<{ market: string }>;
};

export default async function TenxMarketSentimentPage({ params }: PageProps) {
  const { market: marketSlug } = await params;
  const market = fromMarketSlug(marketSlug);

  if (market !== "US") {
    redirect("/tenx-hunter/us/sentiment");
  }

  let snapshot = null;
  let error: string | null = null;

  try {
    snapshot = await loadTenxMarketSentiment(market);
  } catch (loadError) {
    error = getTenxErrorMessage(loadError);
  }

  return (
    <TenxPageShell
      market={market}
      title="TenX Hunter · Sentiment"
      subtitle="把市场过热、恐惧、信用压力和跨市场风险偏好放在同一张复核面板里。"
      marketLabel={`${marketLabel("US")} · Market Sentiment`}
    >
      {snapshot ? (
        <TenxMarketSentimentDashboard snapshot={snapshot} />
      ) : (
        <TenxDataStateCard
          title="市场情绪数据暂不可用"
          message="无法拉取实时情绪源。请检查后端服务与外部数据源连接。"
          detail={error ?? undefined}
        />
      )}
    </TenxPageShell>
  );
}
