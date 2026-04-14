import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import TenxNavigation from "@/components/tenx-hunter/TenxNavigation";
import React from "react";

type TenxPageShellProps = {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  marketLabel?: string;
};

export default function TenxPageShell({
  title,
  subtitle,
  children,
  marketLabel = "US Growth Tech / AI Infrastructure",
}: TenxPageShellProps) {
  return (
    <div className="min-w-0 overflow-x-hidden">
      <PageBreadcrumb pageTitle={title} />
      <div className="mb-6 overflow-hidden rounded-2xl border border-gray-200 bg-white px-5 py-6 dark:border-gray-800 dark:bg-white/[0.03] xl:px-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-sm leading-6 text-gray-600 dark:text-gray-300">{subtitle}</p>
          </div>
          <div className="inline-flex items-center rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700 dark:bg-brand-500/15 dark:text-brand-300">
            {marketLabel}
          </div>
        </div>
      </div>
      <TenxNavigation />
      <div className="min-w-0 space-y-6">{children}</div>
    </div>
  );
}
