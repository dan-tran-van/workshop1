import { expect, test } from "@playwright/test";
import { analysis, analysisResult, installApiMocks } from "./fixtures";

test.describe("FE-03 AI analysis", () => {
  test.beforeEach(async ({ page }) => {
    await installApiMocks(page);
    await page.goto("/");
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
});
