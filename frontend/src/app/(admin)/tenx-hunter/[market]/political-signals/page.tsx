import { fromMarketSlug, getTenxErrorMessage, loadTenxPoliticalSignals, marketLabel } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import TenxPoliticalSignalsDashboard from "@/components/tenx-hunter/TenxPoliticalSignalsDashboard";
import { redirect } from "next/navigation";

type PageProps = {
  params: Promise<{ market: string }>;
};

export default async function TenxPoliticalSignalsPage({ params }: PageProps) {
  const { market: marketSlug } = await params;
  const market = fromMarketSlug(marketSlug);

  if (market !== "US") {
    redirect("/tenx-hunter/us/political-signals");
  }

  let snapshot = null;
  let error: string | null = null;

  try {
    snapshot = await loadTenxPoliticalSignals(market);
  } catch (loadError) {
    error = getTenxErrorMessage(loadError);
  }

  return (
    <TenxPageShell
      market={market}
      title="TenX Hunter · Political Signals"
      subtitle="持续跟踪特朗普相关持仓披露、公开点名股票和政策受益线索，先判证据等级，再决定是否进入观察池。"
      marketLabel={`${marketLabel("US")} · Trump Monitor`}
    >
      {snapshot ? (
        <TenxPoliticalSignalsDashboard snapshot={snapshot} />
      ) : (
        <TenxDataStateCard
          title="政治信号数据暂不可用"
          message="无法拉取披露数据或线索队列。请检查后端服务与外部数据源连接。"
          detail={error ?? undefined}
        />
      )}
    </TenxPageShell>
  );
}
