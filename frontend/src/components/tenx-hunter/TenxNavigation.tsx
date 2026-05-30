"use client";

import { tenxMarketTabs, tenxNavItems } from "@/components/tenx-hunter/navigation";
import { fromMarketSlug } from "@/components/tenx-hunter/api";
import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";

type Props = {
  market: string;
};

export default function TenxNavigation({ market }: Props) {
  const pathname = usePathname();
  const items = tenxNavItems(market);
  const normalizedMarket = fromMarketSlug(market);
  const marketRootPath = `/tenx-hunter/${normalizedMarket.toLowerCase()}`;

  return (
    <div className="mb-6 space-y-3 rounded-2xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex flex-wrap gap-2">
        {tenxMarketTabs.map((item) => {
          const href = `/tenx-hunter/${item.market.toLowerCase()}`;
          const active = normalizedMarket === item.market;
          return (
            <Link
              key={item.market}
              href={href}
              className={clsx(
                "rounded-full border px-3 py-1 text-xs font-semibold transition",
                active
                  ? "border-brand-500 bg-brand-50 text-brand-700 dark:border-brand-400 dark:bg-brand-500/20 dark:text-brand-300"
                  : "border-gray-200 bg-white text-gray-600 hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => {
          const active =
            pathname === item.path ||
            (item.path !== marketRootPath && pathname.startsWith(`${item.path}/`)) ||
            (item.path === marketRootPath && pathname.startsWith(`${item.path}/research/`));
          return (
            <Link
              key={item.path}
              href={item.path}
              className={clsx(
                "rounded-lg border px-3 py-2 text-sm font-medium transition",
                active
                  ? "border-brand-500 bg-brand-50 text-brand-700 dark:border-brand-400 dark:bg-brand-500/20 dark:text-brand-300"
                  : "border-gray-200 bg-white text-gray-600 hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300",
              )}
            >
              {item.name}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
