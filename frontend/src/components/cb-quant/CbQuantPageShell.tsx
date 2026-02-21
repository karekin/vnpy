import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import React from "react";

type CbQuantPageShellProps = {
  title: string;
  subtitle: string;
  children: React.ReactNode;
};

export default function CbQuantPageShell({
  title,
  subtitle,
  children,
}: CbQuantPageShellProps) {
  return (
    <div className="min-w-0 overflow-x-hidden">
      <PageBreadcrumb pageTitle={title} />
      <div className="mb-6 overflow-hidden rounded-2xl border border-gray-200 bg-white px-5 py-6 dark:border-gray-800 dark:bg-white/[0.03] xl:px-8">
        <p className="text-sm leading-6 text-gray-600 dark:text-gray-300">{subtitle}</p>
      </div>
      <div className="min-w-0 space-y-6">{children}</div>
    </div>
  );
}
