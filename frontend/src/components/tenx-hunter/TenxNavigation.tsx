"use client";

import { tenxMarketTabs, tenxNavItems } from "@/components/tenx-hunter/navigation";
import { fromMarketSlug } from "@/components/tenx-hunter/api";
import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChartNoAxesColumnIncreasing, ChevronRight, Compass, Gauge, Radar } from "lucide-react";

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

export default function TenxNavigation({ market }: Props) {
  const pathname = usePathname();
  const items = tenxNavItems(market);
  const normalizedMarket = fromMarketSlug(market);
  const marketRootPath = `/tenx-hunter/${normalizedMarket.toLowerCase()}`;
  const pipelineItems = items.filter((item) => item.group === "pipeline");
  const contextItems = items.filter((item) => item.group === "context");
  const contextIcons = [Radar, Gauge, ChartNoAxesColumnIncreasing];

  const isActive = (path: string) =>
    pathname === path ||
    (path !== marketRootPath && pathname.startsWith(`${path}/`)) ||
    (path === marketRootPath && pathname.startsWith(`${path}/research/`));

  return (
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
          </div>
        </div>
      </div>
    </nav>
  );
}
