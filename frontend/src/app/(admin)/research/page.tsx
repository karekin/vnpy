import type { Metadata } from "next";
import OpenClawMobileApp from "@/components/openclaw-mobile/OpenClawMobileApp";

export const metadata: Metadata = {
  title: "OpenClaw 标的研究库 | vn.py",
  description: "OpenClaw 移动端标的研究库与主题知识库。",
};

export default function ResearchPage() {
  return <OpenClawMobileApp view="research" />;
}
