import type { Metadata } from "next";
import SmartAllocationRoutePage from "@/components/smart-allocation/SmartAllocationRoutePage";

export const metadata: Metadata = {
  title: "再平衡建议 | 智能仓位管理",
};

export default async function SmartAllocationRebalancePage() {
  return <SmartAllocationRoutePage view="rebalance" />;
}
