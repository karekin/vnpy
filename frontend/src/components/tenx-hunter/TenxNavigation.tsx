"use client";

import { tenxMarketTabs, tenxNavItems } from "@/components/tenx-hunter/navigation";
import { fromMarketSlug } from "@/components/tenx-hunter/api";
import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BellRing, Binoculars, CalendarDays, ChartNoAxesColumnIncreasing, ChevronRight, Compass, Flame, Gauge, GitBranch, Info, ListChecks, Radar, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

type Props = {
  market: string;
};

export function TenxMarketViewSwitch({ market }: Props) {
  const pathname = usePathname();
  const normalizedMarket = fromMarketSlug(market);
  const currentRootPath = `/tenx-hunter/${normalizedMarket.toLowerCase()}`;

  const getSwitchHref = (targetMarket: typeof normalizedMarket) => {
    const targetRootPath = `/tenx-hunter/${targetMarket.toLowerCase()}`;
    const suffix = pathname.startsWith(currentRootPath) ? pathname.slice(currentRootPath.length) : "";
    const targetPath = suffix ? `${targetRootPath}${suffix}` : targetRootPath;
    const supportedPaths = new Set(tenxNavItems(targetMarket).map((item) => item.path));

    if (
      supportedPaths.has(targetPath) ||
      suffix.startsWith("/alerts/") ||
      suffix.startsWith("/research/")
    ) {
      return targetPath;
    }

    return targetRootPath;
  };

  return (
    <div
      className="inline-flex h-9 items-center gap-1 rounded-lg border border-gray-200 bg-white p-1 shadow-xs dark:border-gray-700 dark:bg-gray-900"
      aria-label="TenX Hunter market view switch"
    >
      <span className="px-2 text-xs font-semibold text-gray-500 dark:text-gray-400">视角</span>
      {tenxMarketTabs.map((item) => {
        const active = normalizedMarket === item.market;
        return (
          <Link
            key={item.market}
            href={getSwitchHref(item.market)}
            className={clsx(
              "inline-flex h-7 min-w-11 items-center justify-center rounded-md px-2.5 text-xs font-semibold transition",
              active
                ? "bg-brand-500 text-white shadow-sm dark:bg-brand-500 dark:text-white"
                : "text-gray-600 hover:bg-brand-50 hover:text-brand-700 dark:text-gray-300 dark:hover:bg-brand-500/10 dark:hover:text-brand-200",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}

/* ── Right-side drawer for flow state machine explanation ── */

const flowStages = [
  { id: "hot-lead", label: "Hot Monitor", icon: Flame, detail: "社交热度只进入线索层，不能直接进观察池。", tone: "blue" as const },
  { id: "candidate", label: "Discover", icon: GitBranch, detail: "候选池评分排序，财报窗口和期权链作为晋级前的事件验证层。", tone: "slate" as const },
  { id: "watch-ready", label: "晋级门槛", icon: ListChecks, detail: "阶段、证据、风险和动量全部通过后才可晋级。", tone: "green" as const },
  { id: "watching", label: "Watchlist", icon: Binoculars, detail: "只展示已确认持续跟踪的股票。", tone: "green" as const },
  { id: "alerting", label: "Alerts", icon: BellRing, detail: "进入观察池后自动挂接事件追踪。", tone: "red" as const },
];

function FlowDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  return (
    <div
      className={clsx(
        "fixed inset-0 z-50 transition-colors duration-300",
        open ? "visible bg-black/40" : "invisible bg-black/0",
      )}
      onClick={onClose}
      aria-hidden="true"
    >
      <aside
        className={clsx(
          "absolute right-0 top-0 flex h-full w-full max-w-md flex-col overflow-y-auto bg-white shadow-2xl transition-transform duration-300 dark:bg-gray-950",
          open ? "translate-x-0" : "translate-x-full",
        )}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="研究流转状态机说明"
      >
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-800">
          <div>
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">研究流转状态机</h2>
            <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">热度线索不能越级，观察池只接收通过晋级门槛的标的。</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-5 px-5 py-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {flowStages.map((stage) => {
              const Icon = stage.icon;
              return (
                <div key={stage.id} className="rounded-lg border border-gray-200 p-3 dark:border-gray-800">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-50 text-gray-600 dark:bg-gray-900 dark:text-gray-300">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="text-sm font-semibold text-gray-900 dark:text-white">{stage.label}</span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-gray-500 dark:text-gray-400">{stage.detail}</p>
                </div>
              );
            })}
          </div>

          <div className="space-y-2 rounded-lg bg-gray-50 p-4 dark:bg-gray-900/60">
            <h3 className="text-xs font-semibold text-gray-700 dark:text-gray-300">流转规则</h3>
            <ul className="space-y-2 text-xs leading-5 text-gray-600 dark:text-gray-400">
              <li>热度线索：排名升温、来源不止单一噪音、能映射到主题或事件。</li>
              <li>候选验证：进入 validation / acceleration，且至少 2 条证据。</li>
              <li>观察晋级：风险不为 high，动量不为 cooling，并由人工确认。</li>
              <li>事件提醒：加入观察池后自动创建 P2 事件追踪规则。</li>
            </ul>
          </div>

          <div className="rounded-lg border border-brand-200 bg-brand-50/50 p-3 dark:border-brand-500/20 dark:bg-brand-500/5">
            <p className="text-xs font-medium text-brand-700 dark:text-brand-300">
              流转路径：Hot Monitor → Discover → Watchlist → Alerts
            </p>
          </div>
        </div>
      </aside>
    </div>
  );
}

/* ── Main navigation component ── */

export default function TenxNavigation({ market }: Props) {
  const pathname = usePathname();
  const items = tenxNavItems(market);
  const normalizedMarket = fromMarketSlug(market);
  const marketRootPath = `/tenx-hunter/${normalizedMarket.toLowerCase()}`;
  const pipelineItems = items.filter((item) => item.group === "pipeline");
  const contextItems = items.filter((item) => item.group === "context");
  const contextIcons = [Radar, Gauge, ChartNoAxesColumnIncreasing, CalendarDays];

  const [drawerOpen, setDrawerOpen] = useState(false);
  const openDrawer = useCallback(() => setDrawerOpen(true), []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  const isActive = (path: string) =>
    pathname === path ||
    (path !== marketRootPath && pathname.startsWith(`${path}/`)) ||
    (path === marketRootPath && pathname.startsWith(`${path}/research/`));

  return (
    <>
      <nav className="mb-5 rounded-xl border border-gray-200 bg-white p-3 shadow-xs dark:border-gray-800 dark:bg-white/[0.03]" aria-label="TenX Hunter navigation">
        <div className="flex flex-col gap-3">
          {contextItems.length ? (
            <div
              className="flex min-w-0 flex-wrap items-center gap-1.5 rounded-lg border border-gray-100 bg-gray-50/70 px-2 py-1.5 dark:border-gray-800 dark:bg-gray-900/35"
              aria-label="TenX Hunter signal boards"
            >
              <div className="flex shrink-0 items-center gap-2 px-1 text-xs font-semibold text-gray-500 dark:text-gray-400">
                <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
                信号看板
              </div>
              {contextItems.map((item, index) => {
                const active = isActive(item.path);
                const Icon = contextIcons[index] ?? Gauge;
                return (
                  <Link
                    key={item.path}
                    href={item.path}
                    className={clsx(
                      "inline-flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs font-semibold transition",
                      active
                        ? "border-brand-500 bg-white text-brand-700 shadow-sm dark:border-brand-400 dark:bg-brand-500/15 dark:text-brand-200"
                        : "border-gray-200 bg-white text-gray-600 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700 dark:border-gray-700 dark:bg-gray-950/30 dark:text-gray-300 dark:hover:border-brand-400/50 dark:hover:bg-brand-500/10 dark:hover:text-brand-200",
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                    <span className="whitespace-nowrap">{item.name}</span>
                  </Link>
                );
              })}
            </div>
          ) : null}

          <div
            className="rounded-lg border border-gray-100 bg-gray-50/70 px-2.5 py-2 dark:border-gray-800 dark:bg-gray-900/35"
            aria-label="TenX Hunter main workflow"
          >
            <div className="flex min-w-0 items-center gap-2">
              <div className="flex shrink-0 items-center gap-2 px-1 text-xs font-semibold text-gray-500 dark:text-gray-400">
                <Compass className="h-3.5 w-3.5" aria-hidden="true" />
                主流程
              </div>
              <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto pb-0.5 2xl:overflow-visible [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
                {pipelineItems.map((item, index) => {
                  const active = isActive(item.path);
                  return (
                    <div key={item.path} className="flex shrink-0 items-center">
                      <Link
                        href={item.path}
                        className={clsx(
                          "group inline-flex h-9 shrink-0 items-center gap-2 rounded-lg border px-2.5 text-sm transition",
                          active
                            ? "border-brand-500 bg-white text-brand-700 shadow-sm dark:border-brand-400 dark:bg-brand-500/15 dark:text-brand-200"
                            : item.group === "context"
                              ? "border-gray-200/80 bg-white/70 text-gray-600 hover:border-brand-200 hover:bg-white hover:text-brand-700 dark:border-gray-700/80 dark:bg-gray-950/30 dark:text-gray-300 dark:hover:border-brand-400/50 dark:hover:bg-gray-950/50 dark:hover:text-brand-200"
                              : "border-transparent bg-transparent text-gray-600 hover:border-gray-200 hover:bg-white hover:text-brand-700 dark:text-gray-300 dark:hover:border-gray-700 dark:hover:bg-gray-950/40 dark:hover:text-brand-200",
                        )}
                      >
                        <span
                          className={clsx(
                            "inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[11px] font-bold",
                            active ? "bg-brand-500 text-white" : "bg-white text-gray-500 ring-1 ring-gray-200 group-hover:text-brand-600 dark:bg-gray-800 dark:text-gray-300 dark:ring-gray-700",
                          )}
                        >
                          {item.step}
                        </span>
                        <span className="whitespace-nowrap font-semibold">{item.name}</span>
                      </Link>
                      {index < pipelineItems.length - 1 ? (
                        <ChevronRight className="mx-0.5 hidden h-3.5 w-3.5 shrink-0 text-gray-300 dark:text-gray-600 xl:block" aria-hidden="true" />
                      ) : null}
                    </div>
                  );
                })}
              </div>
              <button
                type="button"
                onClick={openDrawer}
                className="ml-1 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-gray-400 transition hover:bg-white hover:text-brand-600 dark:text-gray-500 dark:hover:bg-gray-900 dark:hover:text-brand-300"
                aria-label="查看研究流转说明"
                title="研究流转说明"
              >
                <Info className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </nav>

      <FlowDrawer open={drawerOpen} onClose={closeDrawer} />
    </>
  );
}
