import SmartAllocationRoutePage from "@/components/smart-allocation/SmartAllocationRoutePage";

export const metadata = {
  title: "期权策略管理 | 智能仓位管理",
};

export default async function SmartAllocationOptionsStrategiesPage() {
  return <SmartAllocationRoutePage view="optionStrategies" />;
}
