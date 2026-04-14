import Link from "next/link";
import StatusTag from "@/components/cb-quant/StatusTag";
import { getRelatedCandidatesForTheme, getTenxErrorMessage, loadTenxWorkspaceSnapshot } from "@/components/tenx-hunter/api";
import TenxDataStateCard from "@/components/tenx-hunter/TenxDataStateCard";
import TenxPageShell from "@/components/tenx-hunter/TenxPageShell";
import { TenxSectionCard, getStageTone } from "@/components/tenx-hunter/TenxCards";
import type { TenxWorkspaceSnapshot } from "@/components/tenx-hunter/types";

export default async function TenxHunterThemesPage() {
  let snapshot: TenxWorkspaceSnapshot;
  try {
    snapshot = await loadTenxWorkspaceSnapshot();
  } catch (error) {
    return (
      <TenxPageShell
        title="TenX Hunter · Themes"
        subtitle="主题页先回答“主线是什么、为什么升温、哪些标的是最干净的映射”，再进入个股研究。"
      >
        <TenxDataStateCard
          title="Theme Radar 实时数据暂不可用"
          message="主题页已经停止显示 mock 主题。请确认 TenX 工作台依赖的 API、数据库和真实数据 pipeline 都已就绪。"
          detail={getTenxErrorMessage(error)}
        />
      </TenxPageShell>
    );
  }

  return (
    <TenxPageShell
      title="TenX Hunter · Themes"
      subtitle="主题页先回答“主线是什么、为什么升温、哪些标的是最干净的映射”，再进入个股研究。"
    >
      <div className="space-y-6">
        {snapshot.themes.map((theme) => {
          const related = getRelatedCandidatesForTheme(theme.slug, snapshot);
          return (
            <TenxSectionCard
              key={theme.slug}
              title={theme.name}
              description={theme.driver}
              action={<StatusTag label={`${theme.heat} heat`} tone={theme.trend === "rising" ? "green" : theme.trend === "stable" ? "blue" : "yellow"} />}
            >
              <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr_1fr]">
                <div>
                  <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">主题证据</div>
                  <ul className="mt-3 space-y-3 text-sm leading-6 text-gray-600 dark:text-gray-300">
                    {theme.evidence.map((point) => (
                      <li key={point} className="rounded-xl bg-gray-50 px-4 py-3 dark:bg-gray-900/60">
                        {point}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">相关候选</div>
                  <div className="mt-3 space-y-3">
                    {related.map((candidate) => (
                      <div key={candidate.symbol} className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <Link href={`/tenx-hunter/research/${candidate.symbol}`} className="font-semibold text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-300">
                              {candidate.symbol}
                            </Link>
                            <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">{candidate.name}</div>
                          </div>
                          <StatusTag label={candidate.stage} tone={getStageTone(candidate.stage)} />
                        </div>
                        <p className="mt-3 text-sm leading-6 text-gray-600 dark:text-gray-300">{candidate.keySignal}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </TenxSectionCard>
          );
        })}
      </div>
    </TenxPageShell>
  );
}
