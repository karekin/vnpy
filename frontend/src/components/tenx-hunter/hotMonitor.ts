import type { SocialHotStockItem, SocialHotStocksResponse } from "@/components/tenx-hunter/socialHotApi";

export type TenxHotStockRow = {
  rank: number;
  symbol: string;
  name: string;
  mentions: number;
  mentions24hAgo: number | null;
  mentionChange: number | null;
  mentionChangePct: number | null;
  upvotes: number;
  rank24hAgo: number | null;
  rankChange: number | null;
  heatScore: number;
  sourceUrl: string;
};

function buildHeatScore(item: SocialHotStockItem) {
  const growthBonus = item.mentionChange && item.mentionChange > 0 ? item.mentionChange * 1.5 : 0;
  const upvoteSignal = Math.sqrt(Math.max(0, item.upvotes)) * 3;
  return Math.round(item.mentions + growthBonus + upvoteSignal);
}

export function buildHotStockRows(response: SocialHotStocksResponse, limit = 50): TenxHotStockRow[] {
  return response.items.slice(0, limit).map((item) => ({
    rank: item.rank,
    symbol: item.symbol,
    name: item.name,
    mentions: item.mentions,
    mentions24hAgo: item.mentions24hAgo,
    mentionChange: item.mentionChange,
    mentionChangePct: item.mentionChangePct,
    upvotes: item.upvotes,
    rank24hAgo: item.rank24hAgo,
    rankChange: item.rankChange,
    heatScore: buildHeatScore(item),
    sourceUrl: item.sourceUrl,
  }));
}

export function formatCompactNumber(value: number) {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function formatSignedNumber(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined) return "N/A";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

export function formatSignedPercent(value: number | null | undefined) {
  if (value === null || value === undefined) return "N/A";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}
