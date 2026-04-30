import type { Metadata } from "next";
import OpenClawMobileApp from "@/components/openclaw-mobile/OpenClawMobileApp";

export const metadata: Metadata = {
  title: "OpenClaw 持仓分析 | vn.py",
  description: "OpenClaw 移动端持仓与观察池页面。",
};

export default function PortfolioPage() {
  return <OpenClawMobileApp view="portfolio" />;
}
