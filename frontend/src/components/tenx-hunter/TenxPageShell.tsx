import PageBreadcrumb from "@/components/common/PageBreadCrumb";
import TenxLineageDrawer from "@/components/tenx-hunter/TenxLineageDrawer";
import TenxNavigation, { TenxMarketViewSwitch } from "@/components/tenx-hunter/TenxNavigation";
import type { TenxMarket } from "@/components/tenx-hunter/types";
import React from "react";

type TenxPageShellProps = {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  marketLabel?: string;
  market: TenxMarket;
  pipelineStage?: string;
};

export default function TenxPageShell({
  title,
  subtitle,
  children,
  market,
  marketLabel = "US Growth Tech / AI Infrastructure",
  pipelineStage,
}: TenxPageShellProps) {
  return (
    <div className="min-w-0 overflow-x-hidden">
      <PageBreadcrumb
        pageTitle={title}
        action={
          <div className="flex items-center gap-2">
            <TenxMarketViewSwitch market={market} />
            {pipelineStage ? <TenxLineageDrawer stageId={pipelineStage} /> : null}
          </div>
        }
        description={
          <>
            <span>{subtitle}</span>
            <span className="mx-2 text-gray-300 dark:text-gray-700">·</span>
            <span className="font-medium text-gray-500 dark:text-gray-400">{marketLabel}</span>
          </>
        }
      />
      <TenxNavigation market={market} />
      <div className="min-w-0 space-y-6">{children}</div>
    </div>
  );
}
