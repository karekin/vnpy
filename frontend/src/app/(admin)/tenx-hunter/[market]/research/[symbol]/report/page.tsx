import { fromMarketSlug, loadTenxResearchCard, loadTenxResearchReport, marketLabel } from "@/components/tenx-hunter/api";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import TenxResearchReportPanel from "@/components/tenx-hunter/TenxResearchReportPanel";
import type { TenxResearchCard, TenxResearchReport } from "@/components/tenx-hunter/types";

export default async function TenxHunterResearchReportPage({
  params,
}: {
  params: Promise<{ market: string; symbol: string }>;
}) {
  const { market: marketSlug, symbol } = await params;
  const market = fromMarketSlug(marketSlug);
  const normalizedSymbol = symbol.toUpperCase();

  let card: TenxResearchCard | null = null;
  let report: TenxResearchReport | null = null;
  try {
    card = await loadTenxResearchCard(market, normalizedSymbol);
  } catch {
    card = null;
  }
  try {
    report = await loadTenxResearchReport(market, normalizedSymbol);
  } catch {
    report = null;
  }

  return (
    <TenxPageShell
      market={market}
      title={`Research Report · ${normalizedSymbol}`}
      subtitle={card?.thesisSummary ?? "手动投研报告进入知识库后，会绑定到对应股票研究卡片。"}
      marketLabel={`${marketLabel(market)} · ${card?.theme ?? normalizedSymbol}`}
    >
      <TenxResearchReportPanel market={market} symbol={normalizedSymbol} initialReport={report} showContent />
    </TenxPageShell>
  );
}
