import { loadInvestmentCopilotDailyBrief } from "@/components/investment-copilot/api";

describe("Investment Copilot API", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  test("uses the same-origin proxy in the browser by default", async () => {
    const fetchMock = jest.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ generated_at: "2026-05-30 06:36 UTC" }),
    } as Response);

    await loadInvestmentCopilotDailyBrief("US");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/investment-copilot/daily-brief?market=US",
      expect.objectContaining({ cache: "no-store" }),
    );
  });
});
