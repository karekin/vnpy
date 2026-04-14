import { getTenxErrorMessage, loadTenxWorkspaceSnapshot } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxHunterDiscoverClient from "@/components/tenx-hunter/TenxHunterDiscoverClient";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";

export default async function TenxHunterDiscoverPage() {
  try {
    const snapshot = await loadTenxWorkspaceSnapshot();
    return <TenxHunterDiscoverClient snapshot={snapshot} />;
  } catch (error) {
    return (
      <TenxPageShell
        title="TenX Hunter · Discover"
        subtitle="围绕美股成长科技做候选发现，先看谁值得研究，再进入研究卡片。这里的排序代表研究优先级，而非直接交易建议。"
      >
        <TenxDataStateCard
          title="TenX 实时候选池暂不可用"
          message="前端已经不再回退到任何 mock 数据。请确认 vnpy.web API、PostgreSQL，以及 TenX data pipeline 都已经启动并完成真实数据构建。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }
}
