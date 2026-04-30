import type { Metadata } from "next";
import SmartAllocationRoutePage from "@/components/smart-allocation/SmartAllocationRoutePage";

export const metadata: Metadata = {
  title: "风控巡检 | 智能仓位管理",
};

export default async function SmartAllocationGuardrailsPage() {
  return <SmartAllocationRoutePage view="guardrails" />;
}
