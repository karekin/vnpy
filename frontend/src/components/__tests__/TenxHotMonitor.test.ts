import { buildHotStockRows, formatCompactNumber, formatSignedNumber, formatSignedPercent } from "@/components/tenx-hunter/hotMonitor";
import { loadSocialHotStocks, type SocialHotStocksResponse } from "@/components/tenx-hunter/socialHotApi";

function response(): SocialHotStocksResponse {
  return {
    source: "apewisdom",
    sourceLabel: "ApeWisdom",
    sourceUrl: "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1",
    sourceFilter: "all-stocks",
    windowHours: 24,
    refreshSeconds: 300,
    generatedAt: "2026-05-30 10:00 UTC",
    count: 2,
    page: 1,
    pageSize: 50,
    totalPages: 1,
    returnedCount: 2,
    cacheStatus: "live",
    snapshotId: 1,
    persistedAt: "2026-05-30 10:00 UTC",
    items: [
      {
        source: "apewisdom",
        sourceFilter: "all-stocks",
        sourceUrl: "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1",
        rank: 1,
        symbol: "NVDA",
        name: "NVIDIA",
        mentions: 350,
        upvotes: 1721,
        rank24hAgo: 5,
        mentions24hAgo: 332,
        mentionChange: 18,
        mentionChangePct: 5.4,
        rankChange: 4,
      },
      {
        source: "apewisdom",
        sourceFilter: "all-stocks",
        sourceUrl: "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1",
        rank: 2,
        symbol: "MSFT",
        name: "Microsoft",
        mentions: 280,
        upvotes: 1200,
        rank24hAgo: 1,
        mentions24hAgo: 400,
        mentionChange: -120,
        mentionChangePct: -30,
        rankChange: -1,
      },
    ],
  };
}

describe("Tenx hot monitor", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  test("builds rows from ApeWisdom social mention data", () => {
    const rows = buildHotStockRows(response());

    expect(rows.map((row) => row.symbol)).toEqual(["NVDA", "MSFT"]);
    expect(rows[0]).toMatchObject({
      rank: 1,
      symbol: "NVDA",
      mentions: 350,
      mentionChange: 18,
      rankChange: 4,
    });
    expect(rows[0].heatScore).toBeGreaterThan(rows[0].mentions);
  });

  test("formats monitor numbers for display", () => {
    expect(formatCompactNumber(1721)).toBe("1.7K");
    expect(formatSignedNumber(18)).toBe("+18");
    expect(formatSignedNumber(-1.25, 2)).toBe("-1.25");
    expect(formatSignedPercent(5.41)).toBe("+5.4%");
    expect(formatSignedPercent(null)).toBe("N/A");
  });

  test("requests ApeWisdom data with explicit pagination params", async () => {
    const apiPayload = {
      source: "apewisdom",
      source_label: "ApeWisdom",
      source_url: "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1",
      source_filter: "all-stocks",
      window_hours: 24,
      refresh_seconds: 300,
      generated_at: "2026-05-30 10:00 UTC",
      count: 2,
      page: 3,
      page_size: 25,
      total_pages: 10,
      returned_count: 1,
      cache_status: "persisted-cache",
      snapshot_id: 12,
      persisted_at: "2026-05-30 10:00 UTC",
      items: [
        {
          source: "apewisdom",
          source_filter: "all-stocks",
          source_url: "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1",
          rank: 51,
          symbol: "ARM",
          name: "Arm Holdings",
          mentions: 23,
          upvotes: 212,
          rank_24h_ago: 45,
          mentions_24h_ago: 35,
          mention_change: -12,
          mention_change_pct: -34.3,
          rank_change: -6,
        },
      ],
    };
    const fetchMock = jest.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => apiPayload,
    } as Response);

    const result = await loadSocialHotStocks({ page: 3, pageSize: 25, refresh: true });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/social-hot-stocks?source=apewisdom&filter=all-stocks&page=3&page_size=25&refresh=true"),
      expect.any(Object),
    );
    expect(result).toMatchObject({
      page: 3,
      pageSize: 25,
      totalPages: 10,
      cacheStatus: "persisted-cache",
      items: [{ symbol: "ARM" }],
    });
  });
});
