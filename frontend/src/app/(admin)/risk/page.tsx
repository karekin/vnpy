import type { Metadata } from "next";
import OpenClawMobileApp from "@/components/openclaw-mobile/OpenClawMobileApp";

export const metadata: Metadata = {
  title: "OpenClaw 风险雷达 | vn.py",
  description: "OpenClaw 移动端风险雷达与提醒页面。",
};

export default function RiskPage() {
  return <OpenClawMobileApp view="risk" />;
}
