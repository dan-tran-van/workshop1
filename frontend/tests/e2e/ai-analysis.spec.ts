import { expect, test } from "@playwright/test";
import {
  analysis,
  analysisHistory,
  analysisResult,
  authenticateTestUser,
  installApiMocks,
  olderAnalysis,
  pastAnalysis,
} from "./fixtures";

test.describe("FE-03 AI analysis", () => {
  test.beforeEach(async ({ page }) => {
    await installApiMocks(page);
    await page.goto("/");
    await authenticateTestUser(page);
  });

  test("FE-12 triggers analysis for the selected restaurant and renders its response", async ({ page }) => {
    const analysisRequest = page.waitForRequest((request) =>
      request.method() === "POST" && new URL(request.url()).pathname === "/restaurants/1/analyze",
    );
    await page.getByRole("button", { name: "Analyze reviews" }).click();
    const request = await analysisRequest;
    expect(request.postDataJSON()).toEqual({ force_refresh: false });

    await expect(page.getByText(analysisResult.summary)).toBeVisible();
  });

  test("FE-13 prevents duplicate analysis requests while processing", async ({ page }) => {
    await page.unroute("http://localhost:8000/**");
    await installApiMocks(page, { analysisDelayMs: 300 });
    await page.goto("/");
    await authenticateTestUser(page);

    let requestCount = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && new URL(request.url()).pathname.endsWith("/analyze")) requestCount += 1;
    });
    await page.getByRole("button", { name: "Analyze reviews" }).click();
    const analyzing = page.getByRole("button", { name: "Analyzing..." });
    await expect(analyzing).toBeDisabled();
    await analyzing.click({ force: true });
    await expect(page.getByText(analysisResult.summary)).toBeVisible();
    expect(requestCount).toBe(1);
    await expect(page.getByRole("button", { name: "Refresh analysis" })).toBeEnabled();
  });

  test("FE-14 displays overall sentiment, summary, and estimated rating trend", async ({ page }) => {
    await page.getByRole("button", { name: "Analyze reviews" }).click();
    await expect(page.locator(".section-title-row .sentiment-pill")).toHaveText("Positive");
    await expect(page.getByText(analysisResult.summary)).toBeVisible();
    await expect(page.getByText("Improving", { exact: true })).toBeVisible();
    await expect(page.getByText("Estimated rating trend")).toBeVisible();
  });

  test("FE-15 displays all six review aspects with their own summaries", async ({ page }) => {
    await page.getByRole("button", { name: "Analyze reviews" }).click();
    for (const aspect of analysisResult.aspect_breakdown) {
      const card = page.locator(".aspect-card").filter({ hasText: aspect.summary });
      await expect(card.getByText(new RegExp(`^${aspect.aspect.replace("_", " ")}$`, "i"))).toBeVisible();
      await expect(page.getByText(aspect.summary)).toBeVisible();
    }
  });

  test("FE-16 presents improvements and guest strengths separately", async ({ page }) => {
    await page.getByRole("button", { name: "Analyze reviews" }).click();
    await expect(page.getByText("Room to improve")).toBeVisible();
    await expect(page.getByText(analysisResult.prioritized_improvements[0].recommended_action)).toBeVisible();
    await expect(page.locator(".strengths-block")).toContainText("What guests love");
    await expect(page.locator(".strengths-block")).toContainText("Food");
  });

  test("FE-17 handles empty insight arrays without fabricated insight cards", async ({ page }) => {
    await page.unroute("http://localhost:8000/**");
    await installApiMocks(page, {
      details: {
        1: {
          reviews: [],
          review_count: 0,
        },
      },
      analysisResult: {
        ...analysisResult,
        aspect_breakdown: [],
        prioritized_improvements: [],
        strengths_to_keep: [],
      },
    });
    await page.goto("/");
    await authenticateTestUser(page);
    await page.getByRole("button", { name: "Analyze reviews" }).click();

    await expect(page.getByText(analysisResult.summary)).toBeVisible();
    await expect(page.getByText("No reviews have been collected for this location yet.")).toBeVisible();
    await expect(page.getByText("Room to improve")).toHaveCount(0);
    await expect(page.locator(".strengths-block")).toHaveCount(0);
  });

  test("FE-18 refreshes a cached analysis with force_refresh enabled", async ({ page }) => {
    await page.unroute("http://localhost:8000/**");
    await installApiMocks(page, { initialAnalysis: analysis });
    await page.goto("/");
    await authenticateTestUser(page);

    const refreshedRequest = page.waitForRequest((request) =>
      request.method() === "POST" && new URL(request.url()).pathname === "/restaurants/1/analyze",
    );
    await page.getByRole("button", { name: "Refresh analysis" }).click();
    const request = await refreshedRequest;
    expect(request.postDataJSON()).toEqual({ force_refresh: true });
    await expect(page.getByText("Refreshed analysis: service remains a guest favorite.")).toBeVisible();
  });

  test.fixme("FE-19 displays analysis history newest first", async ({ page }) => {
    // The frontend currently renders only the latest analysis and has no history view.
    await expect(page.getByRole("region", { name: "Analysis history" })).toBeVisible();
  });

  test("FE-20 displays per-user analysis activity on Review insights newest first", async ({ page }) => {
    await page.unroute("http://localhost:8000/**");
    await installApiMocks(page, { analysisHistory });
    await page.goto("/");
    await authenticateTestUser(page);

    await page.getByRole("button", { name: "Review insights" }).click();
    await expect(page.getByRole("region", { name: "Your analysis activity" })).toBeVisible();

    const rows = page.locator(".insights-results table tbody tr");
    await expect(rows).toHaveCount(3);
    await expect(rows.nth(0)).toContainText("Hearth & Honey");
    await expect(rows.nth(1)).toContainText("Lotus Garden");
    await expect(rows.nth(2)).toContainText("Hearth & Honey");
    await expect(rows.nth(0)).toContainText(analysisHistory[0].analysis.result_json.summary);
  });

  test("FE-21 compares current 6 criteria against previous analysis in user history with deltas, sentiment shift, and summary", async ({ page }) => {
    await page.unroute("http://localhost:8000/**");
    await installApiMocks(page, {
      initialAnalysis: analysis,
      analysisHistory: [
        { id: 30, created_at: "2026-11-14T11:00:00Z", analysis },
        { id: 29, created_at: "2026-11-08T09:00:00Z", analysis: pastAnalysis },
        { id: 28, created_at: "2026-11-01T09:00:00Z", analysis: olderAnalysis },
      ],
    });
    await page.goto("/");
    await authenticateTestUser(page);

    const summaryStrip = page.getByRole("region", { name: "Criteria comparison summary" });
    await expect(summaryStrip).toBeVisible();
    await expect(summaryStrip).toContainText("3 improved");
    await expect(summaryStrip).toContainText("1 declined");
    await expect(summaryStrip).toContainText("2 unchanged");
    await expect(summaryStrip).toContainText("+1 reviews");

    const foodCard = page.locator(".aspect-card").filter({ hasText: "Fresh, seasonal dishes." });
    await expect(foodCard).toContainText("+0.4");
    await expect(foodCard).toContainText("vs 4.4 past");

    const waitCard = page.locator(".aspect-card").filter({ hasText: "Some guests mention delays." });
    await expect(waitCard).toContainText("+0.6");
    await expect(waitCard).toContainText("Negative → Mixed");

    const hygieneCard = page.locator(".aspect-card").filter({ hasText: "Guests describe a clean dining room." });
    await expect(hygieneCard).toContainText("-0.3");
    await expect(hygieneCard).toContainText("vs 4.8 past");

    const serviceCard = page.locator(".aspect-card").filter({ hasText: "Warm and attentive staff." });
    await expect(serviceCard).toContainText("0.0");
  });

  test("FE-22 switches past baseline snapshots from user history, toggles chart view, and disables comparison", async ({ page }) => {
    await page.unroute("http://localhost:8000/**");
    await installApiMocks(page, {
      initialAnalysis: analysis,
      analysisHistory: [
        { id: 30, created_at: "2026-11-14T11:00:00Z", analysis },
        { id: 29, created_at: "2026-11-08T09:00:00Z", analysis: pastAnalysis },
        { id: 28, created_at: "2026-11-01T09:00:00Z", analysis: olderAnalysis },
      ],
    });
    await page.goto("/");
    await authenticateTestUser(page);

    const picker = page.getByRole("combobox", { name: "Compare with past analysis" });
    await expect(picker).toHaveValue(String(pastAnalysis.id));

    await picker.selectOption(String(olderAnalysis.id));
    const foodCard = page.locator(".aspect-card").filter({ hasText: "Fresh, seasonal dishes." });
    await expect(foodCard).toContainText("+0.8");
    await expect(foodCard).toContainText("vs 4.0 past");

    await page.getByRole("button", { name: "Chart" }).click();
    const chartRegion = page.getByRole("region", { name: "6 criteria comparison chart" });
    await expect(chartRegion).toBeVisible();
    await expect(chartRegion.locator("svg.criteria-radar-svg")).toBeVisible();
    await expect(chartRegion.locator(".paired-bar-row")).toHaveCount(6);

    await page.getByRole("button", { name: "Cards" }).click();
    await expect(page.locator(".aspect-card")).toHaveCount(6);

    await picker.selectOption("none");
    await expect(page.getByRole("region", { name: "Criteria comparison summary" })).toHaveCount(0);
    await expect(foodCard.locator(".aspect-delta")).toHaveCount(0);
  });

  test("FE-23 ignores other users' snapshots and activates comparison after user refreshes analysis", async ({ page }) => {
    await page.unroute("http://localhost:8000/**");
    await installApiMocks(page, {
      initialAnalysis: pastAnalysis,
      // Restaurant has other snapshots globally, while current user only has pastAnalysis in their own history
      restaurantAnalyses: {
        1: [pastAnalysis, olderAnalysis],
      },
      analysisHistory: [
        { id: 21, created_at: "2026-11-08T09:00:00Z", analysis: pastAnalysis },
      ],
    });
    await page.goto("/");
    await authenticateTestUser(page);

    await expect(page.getByTestId("comparison-single-snapshot")).toBeVisible();
    await expect(page.getByRole("region", { name: "Criteria comparison summary" })).toHaveCount(0);

    await page.getByRole("button", { name: "Refresh analysis" }).click();
    await expect(page.getByText("Refreshed analysis: service remains a guest favorite.")).toBeVisible();
    await expect(page.getByRole("region", { name: "Criteria comparison summary" })).toBeVisible();
    const foodCard = page.locator(".aspect-card").filter({ hasText: "Fresh, seasonal dishes." });
    await expect(foodCard).toContainText("+0.4");
  });

  test("FE-24 opens comparison from Review insights activity table with the selected past run", async ({ page }) => {
    await page.unroute("http://localhost:8000/**");
    await installApiMocks(page, {
      initialAnalysis: analysis,
      analysisHistory: [
        { id: 10, created_at: "2026-11-14T11:00:00Z", analysis },
        { id: 9, created_at: "2026-11-01T10:00:00Z", analysis: olderAnalysis },
      ],
    });
    await page.goto("/");
    await authenticateTestUser(page);

    await page.getByRole("button", { name: "Review insights" }).click();
    const olderRow = page.locator(".insights-results table tbody tr").nth(1);
    await olderRow.getByRole("button", { name: "Compare" }).click();

    await expect(page.getByRole("heading", { name: "Hearth & Honey", level: 2 })).toBeVisible();
    const picker = page.getByRole("combobox", { name: "Compare with past analysis" });
    await expect(picker).toHaveValue(String(olderAnalysis.id));
    await expect(page.locator(".aspect-card").filter({ hasText: "Fresh, seasonal dishes." })).toContainText("+0.8");
  });

  test("FE-25 keeps comparison isolated per restaurant and responsive without horizontal overflow", async ({ page }) => {
    await page.unroute("http://localhost:8000/**");
    await installApiMocks(page, {
      initialAnalysis: analysis,
      analysisHistory: [
        { id: 40, created_at: "2026-11-14T11:00:00Z", analysis },
        { id: 39, created_at: "2026-11-08T09:00:00Z", analysis: pastAnalysis },
      ],
    });
    await page.goto("/");
    await authenticateTestUser(page);

    for (const width of [375, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await expect(page.getByRole("region", { name: "Criteria comparison summary" })).toBeVisible();
      const cardsOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
      expect(cardsOverflow).toBeTruthy();

      await page.getByRole("button", { name: "Chart" }).click();
      await expect(page.getByRole("region", { name: "6 criteria comparison chart" })).toBeVisible();
      const chartOverflow = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth);
      expect(chartOverflow).toBeTruthy();
      await page.getByRole("button", { name: "Cards" }).click();
    }

    await page.getByRole("button", { name: /Lotus Garden/ }).click();
    await expect(page.getByRole("heading", { name: "Lotus Garden", level: 2 })).toBeVisible();
    await expect(page.getByRole("region", { name: "Criteria comparison summary" })).toHaveCount(0);
    await expect(page.getByRole("combobox", { name: "Compare with past analysis" })).toHaveCount(0);
  });
});
