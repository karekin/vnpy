import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import SmartAllocationDashboard, { type SmartAllocationView } from "@/components/smart-allocation/SmartAllocationDashboard";
import { loadSmartAllocationDashboard } from "@/components/smart-allocation/api";

const titles: Record<SmartAllocationView, string> = {
  overview: "账户结构与目标",
  profile: "账户结构与目标",
  waterfall: "现金流瀑布",
  rebalance: "再平衡建议",
  leaps: "LEAPS 候选池",
  wheel: "Wheel 现金流",
  wheelRecommendations: "每日 Wheel 推荐",
  guardrails: "风控巡检",
  review: "季度复盘",
};

export default async function SmartAllocationRoutePage({ view }: { view: SmartAllocationView }) {
  const dashboard = await loadSmartAllocationDashboard();

  return (
    <div className="min-w-0 overflow-x-hidden">
      <PageBreadcrumb pageTitle={`智能仓位管理 / ${titles[view]}`} />
      <SmartAllocationDashboard dashboard={dashboard} activeView={view} />
    </div>
  );
}
