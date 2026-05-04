import StatusTag from "@/components/cb-quant/StatusTag";
import type { TenxPriceMap, TenxPriceSnapshot, TenxRiskLevel, TenxStage, TenxTargetRange } from "@/components/tenx-hunter/types";
import React from "react";

export function getRiskTone(level: TenxRiskLevel) {
  if (level === "high") return "red" as const;
  if (level === "medium") return "yellow" as const;
  return "green" as const;
}

export function getStageTone(stage: TenxStage) {
  if (stage === "acceleration") return "green" as const;
  if (stage === "validation") return "blue" as const;
  if (stage === "falsified") return "red" as const;
  if (stage === "crowded") return "yellow" as const;
  return "slate" as const;
}

export function getPricePostureTone(posture?: string | null) {
  if (posture === "high_risk") return "red" as const;
  if (posture === "crowded" || posture === "near_base_target") return "yellow" as const;
  if (posture === "reasonable_strong") return "green" as const;
  if (posture === "low_position_unverified") return "blue" as const;
  return "slate" as const;
}

function formatPrice(value: number | null | undefined, market?: string) {
  if (value === null || value === undefined) return "N/A";
  return `${market === "CN" ? "¥" : "$"}${value.toFixed(2)}`;
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)}%`;
}

function formatRange(target: Pick<TenxTargetRange, "low" | "high">, market?: string) {
  if (target.low === null || target.high === null) return "N/A";
  return `${formatPrice(target.low, market)}-${formatPrice(target.high, market)}`;
}

type MetricCardProps = {
  label: string;
  value: string;
  delta: string;
};

export function TenxMetricCard({ label, value, delta }: MetricCardProps) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
      <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
      <div className="mt-2 text-3xl font-semibold text-gray-900 dark:text-white">{value}</div>
      <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{delta}</p>
    </div>
  );
}

export function TenxPriceSnapshotStrip({ snapshot, market }: { snapshot?: TenxPriceSnapshot | null; market: string }) {
  if (!snapshot) {
    return (
      <div className="mt-4 rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-500 dark:bg-gray-900/60 dark:text-gray-400">
        Price Map 尚未生成，补跑 TenX pipeline 后会显示目标区间。
      </div>
    );
  }

  return (
    <div className="mt-4 grid gap-3 md:grid-cols-4">
      <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
        <div className="text-xs text-gray-500 dark:text-gray-400">价格姿态</div>
        <div className="mt-2 flex items-center gap-2">
          <StatusTag label={snapshot.postureLabel} tone={getPricePostureTone(snapshot.posture)} />
          <span className="text-xs text-gray-500 dark:text-gray-400">{snapshot.confidence}</span>
        </div>
      </div>
      <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
        <div className="text-xs text-gray-500 dark:text-gray-400">Base 目标区</div>
        <div className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">
          {formatRange({ low: snapshot.baseTargetLow, high: snapshot.baseTargetHigh }, market)}
        </div>
        <div className="mt-1 text-xs text-green-600 dark:text-green-300">{formatPercent(snapshot.upsidePctMid)}</div>
      </div>
      <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
        <div className="text-xs text-gray-500 dark:text-gray-400">Bear 风险区</div>
        <div className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">
          {snapshot.bearZoneLow !== null && snapshot.bearZoneHigh !== null
            ? `${formatPrice(snapshot.bearZoneLow, market)}-${formatPrice(snapshot.bearZoneHigh, market)}`
            : "N/A"}
        </div>
        <div className="mt-1 text-xs text-red-600 dark:text-red-300">{formatPercent(snapshot.downsidePctMid)}</div>
      </div>
      <div className="rounded-xl bg-gray-50 p-3 dark:bg-gray-900/60">
        <div className="text-xs text-gray-500 dark:text-gray-400">Bull 上沿</div>
        <div className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">
          {formatRange({ low: snapshot.bullTargetLow, high: snapshot.bullTargetHigh }, market)}
        </div>
        <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{snapshot.asOfDate}</div>
      </div>
    </div>
  );
}

export function TenxPriceMapPanel({ priceMap }: { priceMap?: TenxPriceMap | null }) {
  if (!priceMap) {
    return (
      <TenxSectionCard title="Price Map" description="价格地图用于建立价格位置感，不构成投资建议。">
        <div className="rounded-xl bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
          暂无 Price Map。请补跑 `run-all` 或 `price-map` 生成目标区间。
        </div>
      </TenxSectionCard>
    );
  }

  return (
    <TenxSectionCard
      title="Price Map"
      description="用区间、情景和无效条件建立价格位置感，不给单点买卖指令。"
      action={<StatusTag label={priceMap.postureLabel} tone={getPricePostureTone(priceMap.posture)} />}
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
          <div className="text-sm text-gray-500 dark:text-gray-400">当前价</div>
          <div className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">
            {formatPrice(priceMap.currentPrice, priceMap.market)}
          </div>
          <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">{priceMap.asOfDate} · {priceMap.confidence}</div>
        </div>
        {[priceMap.bearZone, priceMap.baseTarget, priceMap.bullTarget].map((target) => (
          <div key={target.scenario} className="rounded-2xl border border-gray-200 p-4 dark:border-gray-800">
            <div className="text-sm text-gray-500 dark:text-gray-400">{target.scenario.toUpperCase()} 区间</div>
            <div className="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
              {formatRange(target, priceMap.market)}
            </div>
            <div className={target.scenario === "bear" ? "mt-2 text-xs text-red-600 dark:text-red-300" : "mt-2 text-xs text-green-600 dark:text-green-300"}>
              {formatPercent(target.upsidePctMid)}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-[1.1fr_1fr]">
        <div>
          <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">关键价位</div>
          <div className="mt-3 space-y-2">
            {priceMap.keyLevels.map((level) => (
              <div key={`${level.levelType}-${level.low}-${level.high}`} className="flex items-center justify-between gap-3 rounded-xl bg-gray-50 px-4 py-3 text-sm dark:bg-gray-900/60">
                <div>
                  <div className="font-medium text-gray-800 dark:text-white/90">{level.label}</div>
                  <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{level.source}</div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-gray-900 dark:text-white">
                    {level.low === level.high ? formatPrice(level.low, priceMap.market) : `${formatPrice(level.low, priceMap.market)}-${formatPrice(level.high, priceMap.market)}`}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{formatPercent(level.distancePct)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="text-sm font-semibold text-gray-700 dark:text-gray-200">情景路径</div>
          <div className="mt-3 space-y-3">
            {priceMap.scenarioPaths.map((path) => (
              <div key={path.name} className="rounded-xl border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold text-gray-900 dark:text-white">{path.name}</div>
                  <StatusTag label={`${path.probability}%`} tone={path.targetScenario === "bear" ? "red" : path.targetScenario === "bull" ? "green" : "blue"} />
                </div>
                <p className="mt-2 text-sm leading-6 text-gray-600 dark:text-gray-300">{path.explanation}</p>
                <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">触发：{path.trigger}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-5 rounded-xl bg-gray-50 p-4 text-sm leading-6 text-gray-600 dark:bg-gray-900/60 dark:text-gray-300">
        {priceMap.explanation.next_watch ?? "下一步观察财报兑现、估值拥挤度和关键价位。"}
        {priceMap.explanation.options ? (
          <div className="mt-2 text-gray-500 dark:text-gray-400">{priceMap.explanation.options}</div>
        ) : null}
        {priceMap.explanation.estimates ? (
          <div className="mt-2 text-gray-500 dark:text-gray-400">{priceMap.explanation.estimates}</div>
        ) : null}
        {priceMap.explanation.earnings ? (
          <div className="mt-2 text-gray-500 dark:text-gray-400">{priceMap.explanation.earnings}</div>
        ) : null}
        {priceMap.hitReviews.length > 0 ? (
          <div className="mt-3 border-t border-gray-200 pt-3 text-xs text-gray-500 dark:border-gray-800 dark:text-gray-400">
            最近复盘：{priceMap.hitReviews[0].hitSummary}
          </div>
        ) : null}
      </div>
    </TenxSectionCard>
  );
}

type SectionCardProps = {
  title: string;
  description?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
};

export function TenxSectionCard({ title, description, action, children }: SectionCardProps) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
      <div className="flex flex-col gap-3 border-b border-gray-200 px-5 py-4 dark:border-gray-800 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">{title}</h3>
          {description ? <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{description}</p> : null}
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

type CopilotPanelProps = {
  context: string[];
  prompts: string[];
};

export function CopilotPanel({ context, prompts }: CopilotPanelProps) {
  return (
    <TenxSectionCard
      title="Research Copilot"
      description="工作台先行，对话补充。围绕当前候选、主题和观察池追问，不做开放域泛聊。"
      action={<div className="whitespace-nowrap"><StatusTag label="Copilot" tone="blue" /></div>}
    >
      <div className="space-y-4">
        <div>
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200">当前上下文</h4>
          <ul className="mt-2 space-y-2 text-sm text-gray-600 dark:text-gray-300">
            {context.map((item) => (
              <li key={item} className="rounded-xl bg-gray-50 px-3 py-2 dark:bg-gray-900/60">
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-200">建议追问</h4>
          <div className="mt-2 flex flex-wrap gap-2">
            {prompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="rounded-full border border-gray-200 px-3 py-2 text-left text-sm text-gray-600 transition hover:border-brand-300 hover:text-brand-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-brand-400 dark:hover:text-brand-300"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </div>
    </TenxSectionCard>
  );
}
