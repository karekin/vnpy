import type { TenxMarket } from "@/components/tenx-hunter/types";

export type TenxNavItem = {
  name: string;
  path: string;
};

export function tenxNavItems(market: string): TenxNavItem[] {
  const base = `/tenx-hunter/${market.toLowerCase()}`;
  return [
    { name: "Workspace", path: base },
    ...(market.toUpperCase() === "US" ? [{ name: "Hot Monitor", path: `${base}/hot-monitor` }] : []),
    { name: "Discover", path: `${base}/discover` },
    { name: "Themes", path: `${base}/themes` },
    { name: "Watchlist", path: `${base}/watchlist` },
    { name: "Alerts", path: `${base}/alerts` },
  ];
}

export const tenxMarketTabs: Array<{ label: string; market: TenxMarket }> = [
  { label: "US", market: "US" },
  { label: "A股", market: "CN" },
];
