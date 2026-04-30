import type { Metadata } from "next";
import SmartAllocationRoutePage from "@/components/smart-allocation/SmartAllocationRoutePage";

export const metadata: Metadata = {
  title: "现金流瀑布 | 智能仓位管理",
};

export default async function SmartAllocationWaterfallPage() {
  return <SmartAllocationRoutePage view="waterfall" />;
}
