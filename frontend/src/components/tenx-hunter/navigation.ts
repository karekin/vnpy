import type { TenxMarket } from "@/components/tenx-hunter/types";

export type TenxNavItem = {
  name: string;
  path: string;
  group: "pipeline" | "context";
  step?: string;
  stageLabel?: string;
};

export function tenxNavItems(market: string): TenxNavItem[] {
  const base = `/tenx-hunter/${market.toLowerCase()}`;
  if (market.toUpperCase() === "US") {
    return [
      { name: "Hot Monitor", path: `${base}/hot-monitor`, group: "pipeline", step: "01", stageLabel: "线索" },
      { name: "Discover", path: `${base}/discover`, group: "pipeline", step: "02", stageLabel: "发现" },
      { name: "Earnings", path: `${base}/earnings`, group: "pipeline", step: "03", stageLabel: "财报" },
      { name: "Watchlist", path: `${base}/watchlist`, group: "pipeline", step: "04", stageLabel: "观察" },
      { name: "Alerts", path: `${base}/alerts`, group: "pipeline", step: "05", stageLabel: "提醒" },
      { name: "Themes", path: `${base}/themes`, group: "context", stageLabel: "主题" },
      { name: "Sentiment", path: `${base}/sentiment`, group: "context", stageLabel: "情绪" },
      { name: "Political Signals", path: `${base}/political-signals`, group: "context", stageLabel: "政治" },
    ];
  }

  return [
    { name: "Discover", path: `${base}/discover`, group: "pipeline", step: "01", stageLabel: "发现" },
    { name: "Earnings", path: `${base}/earnings`, group: "pipeline", step: "02", stageLabel: "财报" },
    { name: "Watchlist", path: `${base}/watchlist`, group: "pipeline", step: "03", stageLabel: "观察" },
    { name: "Alerts", path: `${base}/alerts`, group: "pipeline", step: "04", stageLabel: "提醒" },
    { name: "Themes", path: `${base}/themes`, group: "context", stageLabel: "主题" },
  ];
}

export const tenxMarketTabs: Array<{ label: string; market: TenxMarket }> = [
  { label: "US", market: "US" },
  { label: "A股", market: "CN" },
];
