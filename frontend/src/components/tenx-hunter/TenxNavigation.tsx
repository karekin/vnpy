"use client";

import { tenxMarketTabs, tenxNavItems } from "@/components/tenx-hunter/navigation";
import { fromMarketSlug } from "@/components/tenx-hunter/api";
import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowRight, Compass, Gauge, LayoutDashboard } from "lucide-react";

type Props = {
  market: string;
};

export default function TenxNavigation({ market }: Props) {
  const pathname = usePathname();
  const items = tenxNavItems(market);
  const normalizedMarket = fromMarketSlug(market);
  const marketRootPath = `/tenx-hunter/${normalizedMarket.toLowerCase()}`;
  const overviewItems = items.filter((item) => item.group === "overview");
  const pipelineItems = items.filter((item) => item.group === "pipeline");
  const contextItems = items.filter((item) => item.group === "context");

  const isActive = (path: string) =>
    pathname === path ||
    (path !== marketRootPath && pathname.startsWith(`${path}/`)) ||
    (path === marketRootPath && pathname.startsWith(`${path}/research/`));

  const renderCompactLink = (item: (typeof items)[number]) => {
    const active = isActive(item.path);
    return (
      <Link
        key={item.path}
        href={item.path}
        className={clsx(
          "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold transition",
          active
            ? "border-brand-500 bg-brand-50 text-brand-700 dark:border-brand-400 dark:bg-brand-500/20 dark:text-brand-300"
            : "border-gray-200 bg-white text-gray-600 hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300",
        )}
      >
        <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
        {item.name}
      </Link>
    );
  };

  return (
    <div className="mb-6 rounded-2xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[auto_minmax(0,1fr)]">
        <div className="flex flex-wrap items-center gap-2">
          {tenxMarketTabs.map((item) => {
            const href = `/tenx-hunter/${item.market.toLowerCase()}`;
            const active = normalizedMarket === item.market;
            return (
              <Link
                key={item.market}
                href={href}
                className={clsx(
                  "inline-flex h-9 min-w-14 items-center justify-center rounded-full border px-3 text-xs font-semibold transition",
                  active
                    ? "border-brand-500 bg-brand-50 text-brand-700 dark:border-brand-400 dark:bg-brand-500/20 dark:text-brand-300"
                    : "border-gray-200 bg-white text-gray-600 hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300",
                )}
              >
                {item.label}
              </Link>
            );
          })}
          {overviewItems.map(renderCompactLink)}
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="rounded-xl border border-gray-100 bg-gray-50 p-2 dark:border-gray-800 dark:bg-gray-900/50">
            <div className="mb-2 flex items-center gap-2 px-1 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
              <Compass className="h-3.5 w-3.5" aria-hidden="true" />
              主流程
            </div>
            <div className="flex flex-wrap items-stretch gap-2">
              {pipelineItems.map((item, index) => {
                const active = isActive(item.path);
                return (
                  <div key={item.path} className="flex min-w-0 items-center gap-2">
                    <Link
                      href={item.path}
                      className={clsx(
                        "inline-flex min-h-14 min-w-32 items-center gap-3 rounded-lg border px-3 py-2 text-left transition",
                        active
                          ? "border-brand-500 bg-white text-brand-700 shadow-sm dark:border-brand-400 dark:bg-brand-500/15 dark:text-brand-300"
                          : "border-gray-200 bg-white text-gray-700 hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:bg-gray-950/30 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300",
                      )}
                    >
                      <span
                        className={clsx(
                          "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                          active ? "bg-brand-100 text-brand-700 dark:bg-brand-500/20 dark:text-brand-300" : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
                        )}
                      >
                        {item.step}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold">{item.name}</span>
                        <span className="mt-0.5 block text-xs text-gray-500 dark:text-gray-400">{item.stageLabel}</span>
                      </span>
                    </Link>
                    {index < pipelineItems.length - 1 ? (
                      <ArrowRight className="hidden h-4 w-4 shrink-0 text-gray-300 dark:text-gray-600 md:block" aria-hidden="true" />
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-xl border border-gray-100 bg-gray-50 p-2 dark:border-gray-800 dark:bg-gray-900/50">
            <div className="mb-2 flex items-center gap-2 px-1 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
              <Gauge className="h-3.5 w-3.5" aria-hidden="true" />
              信号看板
            </div>
            <div className="flex flex-wrap gap-2 lg:max-w-80">
              {contextItems.map((item) => {
                const active = isActive(item.path);
                return (
                  <Link
                    key={item.path}
                    href={item.path}
                    className={clsx(
                      "inline-flex min-h-10 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold transition",
                      active
                        ? "border-brand-500 bg-white text-brand-700 shadow-sm dark:border-brand-400 dark:bg-brand-500/15 dark:text-brand-300"
                        : "border-gray-200 bg-white text-gray-600 hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:bg-gray-950/30 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300",
                    )}
                  >
                    <span className="text-xs text-gray-500 dark:text-gray-400">{item.stageLabel}</span>
                    <span>{item.name}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
