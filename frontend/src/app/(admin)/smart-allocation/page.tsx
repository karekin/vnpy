import type { Metadata } from "next";
import SmartAllocationRoutePage from "@/components/smart-allocation/SmartAllocationRoutePage";

export const metadata: Metadata = {
  title: "账户结构与目标 | 智能仓位管理",
  description: "录入账户快照，自动推导目标仓位、账户结构和风控红线。",
};

export default async function SmartAllocationPage() {
  return <SmartAllocationRoutePage view="profile" />;
}
