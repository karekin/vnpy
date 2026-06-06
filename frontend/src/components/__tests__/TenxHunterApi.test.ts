import {
  createDiscoverCandidate,
  getTenxErrorMessage,
  getOverviewMetrics,
  getThemeBySlug,
  getTimelineForSymbol,
  loadTenxEarningsLens,
  loadTenxAlerts,
  loadTenxPoliticalSignals,
  loadTenxResearchCard,
  loadTenxResearchReport,
  loadTenxWorkspaceSnapshot,
  uploadTenxResearchReport,
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
        freshness: {
          updated_at: "2026-04-12 08:15 UTC",
          data_complete: true,
          source_summary: "demo",
          coverage: "workspace",
        },
        available_actions: [],
        candidates: [
          {
            market: "US",
            symbol: "NVDA",
            name: "NVIDIA",
            sector: "Semiconductors",
            theme: "AI Infra",
            stage: "acceleration",
            lifecycle_stage: { key: "acceleration", label: "业绩加速", summary: "summary" },
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
            why_selected: { summary: "Growth and evidence both rank near the top of the universe.", bullets: ["增长分 92"] },
            score_breakdown: [],
            freshness: {
              updated_at: "2026-04-12 08:15 UTC",
              data_complete: true,
              source_summary: "demo",
              coverage: "workspace",
            },
            available_actions: [],
          },
        ],
        themes: [
          {
            market: "US",
            slug: "ai-infra",
            name: "AI Infra",
            heat: 94,
            trend: "rising",
            driver: "Capex and demand validation remain strong.",
            evidence: ["Cloud capex held up."],
            related_symbols: ["NVDA"],
            freshness: {
              updated_at: "2026-04-12 08:15 UTC",
              data_complete: true,
              source_summary: "demo",
              coverage: "workspace",
            },
          },
        ],
        watchlist: [
          {
            market: "US",
            symbol: "NVDA",
            name: "NVIDIA",
            thesis_status: "strengthening",
            alert_type: "candidate_upgrade",
            last_event: "Fresh demand confirmation from hyperscaler spending commentary.",
            next_check: "Next earnings call",
            risk_level: "medium",
            score: 94,
            available_actions: [],
          },
        ],
        timeline: [
          {
            id: "evt-1",
            market: "US",
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

    const snapshot = await loadTenxWorkspaceSnapshot("US");
    const metrics = getOverviewMetrics(snapshot);

    expect(metrics).toHaveLength(4);
    expect(metrics[0]).toMatchObject({ label: "今日候选", value: String(snapshot.candidates.length) });
    expect(snapshot.candidates[0]).toMatchObject({
      symbol: "NVDA",
      scoreChange: 3.2,
      riskLevel: "medium",
      flowStatus: "candidate",
    });
  });

  test("maps political signal disclosures and mention evidence grades", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        market: "US",
        person: "trump",
        snapshot_at: "2026-05-31 04:00 UTC",
        thesis: "Track political signals separately from social heat.",
        freshness: {
          updated_at: "2026-05-31 04:00 UTC",
          data_complete: true,
          source_summary: "Open Cabinet",
          coverage: "Trump monitor",
        },
        disclosure: {
          source: "Open Cabinet / OGE",
          source_url: "https://open-cabinet.org/officials/trump-donald-j",
          filing_type: "OGE 278-T",
          latest_filing_date: "May 14, 2026",
          transaction_window: "Jan 1, 2025 – Mar 30, 2026",
          total_trades: 5011,
          purchases: 3713,
          sales: 1298,
          late_filings: 4656,
          late_filing_pct: 92.9,
          detail: "Ranges only.",
        },
        recent_trades: [
          {
            date: "Mar 30, 2026",
            symbol: "ACME",
            description: "ACME CORP",
            trade_type: "Purchase",
            amount: "$15K-$50K",
            is_late: true,
            source_url: "https://example.com/report.pdf",
          },
        ],
        mentions: [
          {
            symbol: "IBM",
            name: "International Business Machines",
            event_date: "2026-05-30",
            event_type: "reported-quote",
            status: "needs-verification",
            evidence_grade: "D",
            headline: "Screenshot says Trump mentioned IBM",
            summary: "Needs original source.",
            source: "user screenshot",
            source_url: "",
            verification_note: "No primary source.",
            next_action: "Verify original quote.",
            watchlist_rule: "Do not enter watchlist yet.",
          },
        ],
        monitoring_rules: ["D grade stays in verification queue."],
        notes: ["Do not treat screenshots as evidence."],
      }),
    });

    const snapshot = await loadTenxPoliticalSignals("US");

    expect(snapshot.disclosure.totalTrades).toBe(5011);
    expect(snapshot.recentTrades[0]).toMatchObject({ symbol: "ACME", isLate: true });
    expect(snapshot.mentions[0]).toMatchObject({ symbol: "IBM", evidenceGrade: "D" });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/api/v1/tenx-hunter/political-signals?market=US&person=trump",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  test("maps research cards from the live API", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        market: "US",
        symbol: "NVDA",
        name: "NVIDIA",
        sector: "Semiconductors",
        theme: "AI Infra",
        stage: "acceleration",
        lifecycle_stage: { key: "acceleration", label: "业绩加速", summary: "summary" },
        score: 94,
        thesis_summary: "AI demand remains supported by recent capex commentary.",
        selection_reason: "The company remains a primary beneficiary of AI infra buildout.",
        stage_reason: "Validation remains broad across demand signals.",
        crowding_note: "Crowding risk exists, but evidence remains strong.",
        score_drivers: ["增长分 92", "证据分 88"],
        why_selected: { summary: "summary", bullets: ["增长分 92"] },
        score_breakdown: [],
        facts: ["Revenue growth remains elevated."],
        thesis_points: ["Capex continues to support demand."],
        risk_items: [{ title: "Expectation bar is high.", severity: "medium", trigger: "trigger", note: "note" }],
        next_watch_points: ["Next earnings call"],
        evidence_items: [
          {
            id: "evt-1",
            source: "Recent earnings call",
            published_at: "2026-04-12 08:15 UTC",
            title: "Recent earnings call",
            note: "Management reiterated sustained demand.",
            linked_to: [],
          },
        ],
        freshness: {
          updated_at: "2026-04-12 08:15 UTC",
          data_complete: true,
          source_summary: "demo",
          coverage: "research",
        },
        available_actions: [],
      }),
    });

    const card = await loadTenxResearchCard("US", "NVDA");

    expect(card).not.toBeNull();
    expect(card?.symbol).toBe("NVDA");
    expect(card?.evidenceItems.length).toBeGreaterThan(0);
  });

  test("returns null for real 404 research responses", async () => {
    mockedFetch.mockResolvedValue({
      ok: false,
      status: 404,
    });

    await expect(loadTenxResearchCard("US", "UNKNOWN")).resolves.toBeNull();
  });

  test("maps and uploads research markdown reports", async () => {
    mockedFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        report_id: "report-nvda",
        market: "US",
        symbol: "NVDA",
        title: "NVDA 完整投研报告",
        source_filename: "nvda.md",
        content_markdown: "# NVDA 完整投研报告\n\n- AI demand remains strong.",
        word_count: 38,
        status: "active",
        created_at: "2026-05-30 08:00 UTC",
        updated_at: "2026-05-30 08:00 UTC",
      }),
    });

    const report = await loadTenxResearchReport("US", "NVDA");
    expect(report).toMatchObject({
      reportId: "report-nvda",
      symbol: "NVDA",
      title: "NVDA 完整投研报告",
    });

    mockedFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ok: true,
        message: "NVDA 投研报告已保存到知识库。",
        report: {
          report_id: "report-nvda",
          market: "US",
          symbol: "NVDA",
          title: "NVDA 完整投研报告",
          source_filename: "nvda.md",
          content_markdown: "# NVDA 完整投研报告",
          word_count: 12,
          status: "active",
          created_at: "2026-05-30 08:00 UTC",
          updated_at: "2026-05-30 08:01 UTC",
        },
      }),
    });

    const upload = await uploadTenxResearchReport("US", "NVDA", new File(["# NVDA"], "nvda.md", { type: "text/markdown" }));
    expect(upload.report.sourceFilename).toBe("nvda.md");
  });

  test("creates manual discover candidates from hot monitor leads", async () => {
    mockedFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ok: true,
        message: "ASTS 已加入发现池。",
      }),
    });

    const result = await createDiscoverCandidate("US", {
      symbol: "ASTS",
      name: "AST SpaceMobile Inc",
      source: "hot-monitor",
      theme: "Satellite Connectivity",
      thesis: "Reddit 热点线索进入候选验证。",
      sourcePayload: { mentions: 36 },
    });

    expect(result.ok).toBe(true);
    expect(mockedFetch).toHaveBeenCalledWith(
      "/api/v1/tenx-hunter/discover",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("\"symbol\":\"ASTS\""),
      }),
    );
  });

  test("maps event-driven alert metadata from the live API", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        market: "US",
        freshness: {
          updated_at: "2026-05-30 06:57 UTC",
          data_complete: true,
          source_summary: "demo",
          coverage: "alerts",
        },
        available_actions: [],
        items: [
          {
            id: "rule-asts",
            market: "US",
            symbol: "ASTS",
            title: "Falcon 9 launch cadence capacity check",
            summary: "事件层：发射次数与卫星数量假设变化",
            severity: "P2",
            alert_type: "event-driven-options",
            source: "user-draft",
            created_at: "2026-05-30 06:57 UTC",
            next_action: "补公司披露和期权结构证据",
            evidence_grade: "D",
            confidence: "low",
            status: "draft",
            due_at: "2026-06-03",
            source_note: "社群截图线索，只能作为待验证提醒。",
            event_layer: ["Falcon 9 合同/发射节奏可能影响产能预期"],
            structure_layer: ["检查价格是否接近关键支撑/阻力"],
            execution_layer: ["未补齐最大亏损前不进入期权表达"],
            invalidation_signals: ["公司披露不支持 10-12 次发射假设"],
          },
        ],
      }),
    });

    const alerts = await loadTenxAlerts("US");

    expect(alerts.items[0]).toMatchObject({
      symbol: "ASTS",
      evidenceGrade: "D",
      confidence: "low",
      sourceNote: "社群截图线索，只能作为待验证提醒。",
      eventLayer: ["Falcon 9 合同/发射节奏可能影响产能预期"],
      invalidationSignals: ["公司披露不支持 10-12 次发射假设"],
    });
  });

  test("maps earnings lens shortline and options rows from the live API", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        market: "US",
        snapshot_at: "2026-06-05",
        freshness: {
          updated_at: "2026-06-05",
          data_complete: true,
          source_summary: "SEC / Polygon / Yahoo + TenX 聚合",
          coverage: "earnings lens",
        },
        shortline: [
          {
            market: "US",
            symbol: "NVDA",
            name: "NVIDIA",
            theme: "AI Infra",
            stage: "acceleration",
            flow_status: "watch-ready",
            flow_status_label: "可晋级观察",
            score: 94,
            score_change: 3.2,
            risk_level: "medium",
            momentum: "strengthening",
            next_event: "FY26 Q1 earnings",
            next_earnings_date: "2026-06-12",
            days_to_earnings: 7,
            fiscal_period: "Q1",
            time_of_day: "AMC",
            eps_estimate: 0.89,
            revenue_estimate: 28000000000,
            currency: "USD",
            earnings_quality: "ok",
            source_vendor: "yahoo-finance",
            shortline_signal: "进入财报准备窗口，检查估值、预期和反证。",
            action_label: "准备清单",
          },
        ],
        options: [
          {
            market: "US",
            symbol: "NVDA",
            name: "NVIDIA",
            next_earnings_date: "2026-06-12",
            days_to_earnings: 7,
            score: 94,
            underlying_price: 188.63,
            nearest_expiration: "2026-06-19",
            expiration_count: 4,
            contract_count: 420,
            total_call_volume: 120000,
            total_put_volume: 80000,
            call_put_volume_ratio: 1.5,
            total_call_open_interest: 500000,
            total_put_open_interest: 300000,
            call_put_open_interest_ratio: 1.67,
            avg_implied_volatility: 0.62,
            max_pain_strike: 180,
            liquidity_score: 82,
            flow_score: 68,
            option_selection_score: 76,
            flow_sentiment: "bullish",
            data_quality_flag: "ok",
            updated_at: "2026-06-05 12:00 UTC",
            option_signal: "期权流动性和评分可复核，可进入结构筛选。",
            action_label: "结构筛选",
          },
        ],
        notes: [],
      }),
    });

    const lens = await loadTenxEarningsLens("US");

    expect(lens.shortline[0]).toMatchObject({
      symbol: "NVDA",
      flowStatus: "watch-ready",
      nextEarningsDate: "2026-06-12",
      revenueEstimate: 28000000000,
      actionLabel: "准备清单",
    });
    expect(lens.options[0]).toMatchObject({
      symbol: "NVDA",
      callPutVolumeRatio: 1.5,
      avgImpliedVolatility: 0.62,
      optionSelectionScore: 76,
      flowSentiment: "bullish",
    });
    expect(mockedFetch).toHaveBeenCalledWith(
      "/api/v1/tenx-hunter/earnings-lens?market=US",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  test("surfaces backend failures instead of falling back to mock data", async () => {
    mockedFetch.mockResolvedValue({
      ok: false,
      status: 503,
    });

    await expect(loadTenxWorkspaceSnapshot("US")).rejects.toThrow("HTTP 503");
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
        freshness: {
          updated_at: "2026-04-12 08:15 UTC",
          data_complete: true,
          source_summary: "demo",
          coverage: "workspace",
        },
        available_actions: [],
        candidates: [
          {
            market: "US",
            symbol: "MU",
            name: "Micron",
            sector: "Memory",
            theme: "AI Compute",
            stage: "validation",
            lifecycle_stage: { key: "validation", label: "逻辑验证", summary: "summary" },
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
            why_selected: { summary: "Memory leverage improved.", bullets: ["证据分 85"] },
            score_breakdown: [],
            freshness: {
              updated_at: "2026-04-12 08:15 UTC",
              data_complete: true,
              source_summary: "demo",
              coverage: "workspace",
            },
            available_actions: [],
          },
        ],
        themes: [
          {
            market: "US",
            slug: "ai-compute",
            name: "AI Compute",
            heat: 91,
            trend: "rising",
            driver: "Demand remains strong.",
            evidence: ["Pricing improved."],
            related_symbols: ["MU"],
            freshness: {
              updated_at: "2026-04-12 08:15 UTC",
              data_complete: true,
              source_summary: "demo",
              coverage: "workspace",
            },
          },
        ],
        watchlist: [],
        timeline: [
          {
            id: "evt-mu-1",
            market: "US",
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

    const snapshot = await loadTenxWorkspaceSnapshot("US");
    const theme = getThemeBySlug("ai-compute", snapshot);
    const timeline = getTimelineForSymbol("MU", snapshot);

    expect(theme?.name).toBe("AI Compute");
    expect(timeline.some((item) => item.symbol === "MU")).toBe(true);
  });
});
