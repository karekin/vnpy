import type { Metadata } from "next";
import SmartAllocationRoutePage from "@/components/smart-allocation/SmartAllocationRoutePage";

export const metadata: Metadata = {
  title: "季度复盘 | 智能仓位管理",
};

export default async function SmartAllocationReviewPage() {
  return <SmartAllocationRoutePage view="review" />;
}
