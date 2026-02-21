"use client";

import { cbQuantNavItems } from "@/components/cb-quant/navigation";
import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function CbQuantNavigation() {
  const pathname = usePathname();

  return (
    <div className="mb-6 rounded-2xl border border-gray-200 bg-white p-3 dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex flex-wrap gap-2">
        {cbQuantNavItems.map((item) => {
          const active = pathname === item.path;
          return (
            <Link
              key={item.path}
              href={item.path}
              className={clsx(
                "rounded-lg border px-3 py-2 text-sm font-medium transition",
                active
                  ? "border-brand-500 bg-brand-50 text-brand-700 dark:border-brand-400 dark:bg-brand-500/20 dark:text-brand-300"
                  : "border-gray-200 bg-white text-gray-600 hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
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
