import type { Metadata } from "next";
import SmartAllocationRoutePage from "@/components/smart-allocation/SmartAllocationRoutePage";

export const metadata: Metadata = {
  title: "Wheel 现金流 | 智能仓位管理",
};

export default async function SmartAllocationWheelPage() {
  return <SmartAllocationRoutePage view="wheel" />;
}
