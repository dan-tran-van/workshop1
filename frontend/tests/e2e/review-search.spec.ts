import { expect, test, type Route } from "@playwright/test";
import { authenticateTestUser, installApiMocks } from "./fixtures";

test.describe("Review search", () => {
  test("displays semantic results, filters by scope and min match, and supports keyword fallback", async ({ page }) => {
    await installApiMocks(page);
    await authenticateTestUser(page);

    const searchCalls: string[] = [];
    await page.route(/localhost:8000\/reviews\/search/, async (route: Route) => {
      const request = route.request();
      if (request.method() === "OPTIONS") {
        await route.fulfill({
          status: 204,
          headers: {
            "access-control-allow-origin": "*",
            "access-control-allow-methods": "GET, OPTIONS",
            "access-control-allow-headers": "authorization, content-type",
          },
        });
        return;
      }

      const url = new URL(request.url());
      searchCalls.push(url.search);
      const q = url.searchParams.get("q") ?? "";
      const minSim = url.searchParams.get("min_similarity");

      if (q === "stone cold") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: { "access-control-allow-origin": "*" },
          body: JSON.stringify({
            query: q,
            mode: "keyword_fallback",
            model: null,
            results: [
              {
                id: 102,
                restaurant_id: 1,
                restaurant_name: "Hearth & Table",
                author_name: "Marcus Lee",
                rating: 2.0,
                text: "The dish arrived stone cold.",
                published_at: "2026-11-20T12:00:00Z",
                similarity: null,
                match_type: "keyword",
              },
            ],
          }),
        });
        return;
      }

      const results = [
        {
          id: 101,
          restaurant_id: 1,
          restaurant_name: "Hearth & Table",
          author_name: "Alice Nguyen",
          rating: 2.0,
          text: "Soup was lukewarm by the time it reached our table.",
          published_at: "2026-11-22T12:00:00Z",
          similarity: 0.92,
          match_type: "semantic",
        },
        ...(minSim
          ? []
          : [
              {
                id: 103,
                restaurant_id: 2,
                restaurant_name: "Cedar Kitchen",
                author_name: "Sarah Jenkins",
                rating: 4.0,
                text: "Quick lunch and hot bread.",
                published_at: "2026-11-18T12:00:00Z",
                similarity: 0.31,
                match_type: "semantic",
              },
            ]),
      ];

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify({
          query: q,
          mode: "semantic",
          model: "text-embedding-3-small",
          results,
        }),
      });
    });

    await page.goto("/");
    await page.getByRole("button", { name: "Review search" }).click();

    await page.getByRole("button", { name: "cold food" }).click();
    await expect(page.getByText("2 matching reviews")).toBeVisible();
    await expect(page.getByText("Semantic (text-embedding-3-small)")).toBeVisible();
    await expect(page.getByText("92% match")).toBeVisible();
    await expect(page.getByText("Soup was lukewarm by the time it reached our table.")).toBeVisible();

    await page.getByLabel("Minimum similarity").selectOption("0.6");
    await expect(page.getByText("1 matching review")).toBeVisible();
    expect(searchCalls.some((qs) => qs.includes("min_similarity=0.6"))).toBe(true);

    await page.getByLabel("Search reviews").fill("stone cold");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.getByText("Keyword fallback (LIKE)")).toBeVisible();
    await expect(page.getByText("Keyword match")).toBeVisible();
    await expect(page.getByText("The dish arrived stone cold.")).toBeVisible();
  });

  test("renders cleanly on mobile viewport without horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await installApiMocks(page);
    await authenticateTestUser(page);

    await page.route(/localhost:8000\/reviews\/search/, async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": "*" },
        body: JSON.stringify({
          query: "friendly staff",
          mode: "semantic",
          model: "text-embedding-3-small",
          results: [
            {
              id: 201,
              restaurant_id: 1,
              restaurant_name: "Hearth & Table",
              author_name: "James Wilson",
              rating: 5.0,
              text: "Friendly people and great service.",
              published_at: "2026-11-21T10:00:00Z",
              similarity: 0.63,
              match_type: "semantic",
            },
          ],
        }),
      });
    });

    await page.goto("/");
    await page.getByLabel("Open navigation").click().catch(() => {});
    await page.getByRole("button", { name: "Review search" }).click();
    await page.getByRole("button", { name: "friendly staff" }).click();
    await expect(page.getByText("63% match")).toBeVisible();

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(overflow).toBe(false);
  });
});
