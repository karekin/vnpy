import SmartAllocationRoutePage from "@/components/smart-allocation/SmartAllocationRoutePage";

export const metadata = {
  title: "每日 Wheel 推荐 | 智能仓位管理",
};

export default async function SmartAllocationWheelRecommendationsPage() {
  return <SmartAllocationRoutePage view="wheelRecommendations" />;
}
