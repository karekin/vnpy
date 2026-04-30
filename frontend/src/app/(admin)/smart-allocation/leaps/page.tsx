import type { Metadata } from "next";
import SmartAllocationRoutePage from "@/components/smart-allocation/SmartAllocationRoutePage";

export const metadata: Metadata = {
  title: "LEAPS 候选池 | 智能仓位管理",
};

export default async function SmartAllocationLeapsPage() {
  return <SmartAllocationRoutePage view="leaps" />;
}
