import {
  getTenxErrorMessage,
  getOverviewMetrics,
  getThemeBySlug,
  getTimelineForSymbol,
  loadTenxResearchCard,
  loadTenxWorkspaceSnapshot,
} from "@/components/tenx-hunter/api";

describe("TenxHunter API adapter", () => {
  const mockedFetch = global.fetch as jest.Mock;

  beforeEach(() => {
    mockedFetch.mockReset();
  });

  test("builds stable overview metrics from the live workspace snapshot payload", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        market: "US",
        universe: "US Growth Hunt · 17 names",
        universe_strategy: "bucketed-growth-research",
        universe_description: "Preset research universe driven by real source ingestion.",
        universe_buckets: [
          {
            slug: "ai-infra-core",
            label: "AI Infra Core",
            rationale: "Core AI infra names sourced from preset universe config.",
            symbol_count: 5,
            sample_symbols: ["NVDA", "AMD", "ARM", "ANET"],
          },
        ],
        snapshot_at: "2026-04-12 08:15 UTC",
        candidates: [
          {
            symbol: "NVDA",
            name: "NVIDIA",
            sector: "Semiconductors",
            theme: "AI Infra",
            stage: "acceleration",
            score: 94,
            score_change: 3.2,
            price: 188.63,
            price_change_pct: 2.6,
            market_cap_label: "$3.1T",
            evidence_count: 5,
            risk_level: "medium",
            momentum: "strengthening",
            next_event: "FY26 Q1 earnings",
            thesis: "Demand validation remains intact.",
            key_signal: "Cloud capex stayed elevated.",
            selection_reason: "Growth and evidence both rank near the top of the universe.",
            stage_reason: "Acceleration because validation remains broad and recent.",
            crowding_note: "Still expensive, but evidence breadth remains unusually strong.",
            score_drivers: ["增长分 92", "证据分 88", "主题分 79"],
          },
        ],
        themes: [
          {
            slug: "ai-infra",
            name: "AI Infra",
            heat: 94,
            trend: "rising",
            driver: "Capex and demand validation remain strong.",
            evidence: ["Cloud capex held up."],
            related_symbols: ["NVDA"],
          },
        ],
        watchlist: [
          {
            symbol: "NVDA",
            name: "NVIDIA",
            thesis_status: "strengthening",
            alert_type: "candidate_upgrade",
            last_event: "Fresh demand confirmation from hyperscaler spending commentary.",
            next_check: "Next earnings call",
            risk_level: "medium",
            score: 94,
          },
        ],
        timeline: [
          {
            id: "evt-1",
            symbol: "NVDA",
            date: "2026-04-12",
            title: "Cloud leaders maintain AI capex",
            type: "earnings",
            summary: "Recent commentary kept demand validation intact.",
          },
        ],
        copilot_prompts: ["What would invalidate this thesis next?"],
      }),
    });

    const snapshot = await loadTenxWorkspaceSnapshot();
    const metrics = getOverviewMetrics(snapshot);

    expect(metrics).toHaveLength(4);
    expect(metrics[0]).toMatchObject({ label: "今日候选", value: String(snapshot.candidates.length) });
    expect(snapshot.candidates[0]).toMatchObject({
      symbol: "NVDA",
      scoreChange: 3.2,
      riskLevel: "medium",
    });
  });

  test("maps research cards from the live API", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        symbol: "NVDA",
        name: "NVIDIA",
        sector: "Semiconductors",
        theme: "AI Infra",
        stage: "acceleration",
        score: 94,
        thesis_summary: "AI demand remains supported by recent capex commentary.",
        selection_reason: "The company remains a primary beneficiary of AI infra buildout.",
        stage_reason: "Validation remains broad across demand signals.",
        crowding_note: "Crowding risk exists, but evidence remains strong.",
        score_drivers: ["增长分 92", "证据分 88"],
        facts: ["Revenue growth remains elevated."],
        thesis_points: ["Capex continues to support demand."],
        risks: ["Expectation bar is high."],
        next_checkpoints: ["Next earnings call"],
        evidence: [
          {
            source: "Recent earnings call",
            published_at: "2026-04-12 08:15 UTC",
            note: "Management reiterated sustained demand.",
          },
        ],
      }),
    });

    const card = await loadTenxResearchCard("NVDA");

    expect(card).not.toBeNull();
    expect(card?.symbol).toBe("NVDA");
    expect(card?.evidence.length).toBeGreaterThan(0);
  });

  test("returns null for real 404 research responses", async () => {
    mockedFetch.mockResolvedValue({
      ok: false,
      status: 404,
    });

    await expect(loadTenxResearchCard("UNKNOWN")).resolves.toBeNull();
  });

  test("surfaces backend failures instead of falling back to mock data", async () => {
    mockedFetch.mockResolvedValue({
      ok: false,
      status: 503,
    });

    await expect(loadTenxWorkspaceSnapshot()).rejects.toThrow("HTTP 503");
    expect(getTenxErrorMessage(new Error("backend down"))).toBe("backend down");
  });

  test("returns theme and timeline lookups for follow-up drilling", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        market: "US",
        universe: "US Growth Hunt · 17 names",
        universe_strategy: "bucketed-growth-research",
        universe_description: "Preset research universe.",
        universe_buckets: [],
        snapshot_at: "2026-04-12 08:15 UTC",
        candidates: [
          {
            symbol: "MU",
            name: "Micron",
            sector: "Memory",
            theme: "AI Compute",
            stage: "validation",
            score: 88,
            score_change: 1.8,
            price: 140.12,
            price_change_pct: 1.3,
            market_cap_label: "$150B",
            evidence_count: 4,
            risk_level: "medium",
            momentum: "strengthening",
            next_event: "HBM shipment update",
            thesis: "HBM remains supply constrained.",
            key_signal: "Pricing improved.",
            selection_reason: "Memory leverage improved.",
            stage_reason: "Evidence breadth improved.",
            crowding_note: "Still cyclical.",
            score_drivers: ["证据分 85"],
          },
        ],
        themes: [
          {
            slug: "ai-compute",
            name: "AI Compute",
            heat: 91,
            trend: "rising",
            driver: "Demand remains strong.",
            evidence: ["Pricing improved."],
            related_symbols: ["MU"],
          },
        ],
        watchlist: [],
        timeline: [
          {
            id: "evt-mu-1",
            symbol: "MU",
            date: "2026-04-12",
            title: "HBM pricing improves",
            type: "price",
            summary: "Supply constraints improved pricing power.",
          },
        ],
        copilot_prompts: [],
      }),
    });

    const snapshot = await loadTenxWorkspaceSnapshot();
    const theme = getThemeBySlug("ai-compute", snapshot);
    const timeline = getTimelineForSymbol("MU", snapshot);

    expect(theme?.name).toBe("AI Compute");
    expect(timeline.some((item) => item.symbol === "MU")).toBe(true);
  });
});
