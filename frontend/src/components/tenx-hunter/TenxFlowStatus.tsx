import StatusTag from "@/components/cb-quant/StatusTag";
import type { TenxCandidate, TenxFlowStatus } from "@/components/tenx-hunter/types";

type TagTone = "green" | "yellow" | "red" | "blue" | "slate";

export function getFlowTone(status: TenxFlowStatus): TagTone {
  if (status === "alerting") return "red";
  if (status === "watching" || status === "watch-ready") return "green";
  if (status === "blocked") return "yellow";
  if (status === "hot-lead") return "blue";
  return "slate";
}

export function getFlowLabel(status: TenxFlowStatus) {
  return {
    "hot-lead": "热度线索",
    candidate: "候选验证",
    "watch-ready": "可晋级观察",
    watching: "观察池",
    alerting: "事件提醒中",
    blocked: "暂不晋级",
  }[status];
}

export function CandidateFlowTag({ candidate }: { candidate: TenxCandidate }) {
  return <StatusTag label={candidate.flowStatusLabel || getFlowLabel(candidate.flowStatus)} tone={getFlowTone(candidate.flowStatus)} />;
}
