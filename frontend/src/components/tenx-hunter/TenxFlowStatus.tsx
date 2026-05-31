import StatusTag from "@/components/cb-quant/StatusTag";
import type { TenxCandidate, TenxFlowStatus, TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";
import { BellRing, Binoculars, Flame, GitBranch, ListChecks } from "lucide-react";

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

export function TenxFlowRail({ snapshot }: { snapshot: TenxWorkspaceSnapshot }) {
  const counts = snapshot.candidates.reduce<Record<TenxFlowStatus, number>>(
    (acc, candidate) => {
      acc[candidate.flowStatus] += 1;
      return acc;
    },
    {
      "hot-lead": 0,
      candidate: 0,
      "watch-ready": 0,
      watching: 0,
      alerting: 0,
      blocked: 0,
    },
  );
  counts.watching = Math.max(counts.watching, snapshot.watchlist.length);
  counts.alerting = Math.max(counts.alerting, snapshot.watchlist.filter((item) => item.activeAlertCount > 0).length);

  const stages: Array<{
    id: TenxFlowStatus;
    label: string;
    count: string;
    icon: typeof Flame;
    detail: string;
  }> = [
    {
      id: "hot-lead",
      label: "Hot Monitor",
      count: "外部",
      icon: Flame,
      detail: "社交热度只进入线索层，不能直接进观察池。",
    },
    {
      id: "candidate",
      label: "Discover",
      count: String(counts.candidate + counts["watch-ready"] + counts.blocked),
      icon: GitBranch,
      detail: "候选池按评分、证据和阶段排序。",
    },
    {
      id: "watch-ready",
      label: "晋级门槛",
      count: String(counts["watch-ready"]),
      icon: ListChecks,
      detail: "阶段、证据、风险和动量全部通过后才可晋级。",
    },
    {
      id: "watching",
      label: "Watchlist",
      count: String(snapshot.watchlist.length),
      icon: Binoculars,
      detail: "只展示已确认持续跟踪的股票。",
    },
    {
      id: "alerting",
      label: "Alerts",
      count: String(counts.alerting),
      icon: BellRing,
      detail: "进入观察池后自动挂接事件追踪。",
    },
  ];

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">研究流转状态机</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">热度线索不能越级，观察池只接收通过晋级门槛的标的。</p>
        </div>
        <StatusTag label="Hot Monitor -> Discover -> Watchlist" tone="blue" />
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-5">
        {stages.map((stage) => {
          const Icon = stage.icon;
          return (
            <div key={stage.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-gray-50 text-gray-600 dark:bg-gray-900 dark:text-gray-300">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <StatusTag label={stage.count} tone={getFlowTone(stage.id)} />
              </div>
              <div className="mt-3 text-sm font-semibold text-gray-900 dark:text-white">{stage.label}</div>
              <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">{stage.detail}</p>
            </div>
          );
        })}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 text-xs leading-5 text-gray-600 dark:text-gray-300 lg:grid-cols-4">
        <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">热度线索：排名升温、来源不止单一噪音、能映射到主题或事件。</div>
        <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">候选验证：进入 validation/acceleration，且至少 2 条证据。</div>
        <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">观察晋级：风险不为 high，动量不为 cooling，并由人工确认。</div>
        <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-900/60">事件提醒：加入观察池后自动创建 P2 事件追踪规则。</div>
      </div>
    </section>
  );
}
