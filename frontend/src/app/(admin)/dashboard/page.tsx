import type { Metadata } from "next";
import OpenClawMobileApp from "@/components/openclaw-mobile/OpenClawMobileApp";

export const metadata: Metadata = {
  title: "OpenClaw 投资总览 | vn.py",
  description: "OpenClaw 移动端投资总览，展示今日摘要、风险提醒和研究入口。",
};

export default function DashboardPage() {
  return <OpenClawMobileApp view="dashboard" />;
}
