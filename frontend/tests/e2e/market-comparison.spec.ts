import { expect, test, type Page, type Route } from "@playwright/test";
import { authenticateTestUser, installApiMocks } from "./fixtures";

type Source = "SUGGESTED" | "PINNED" | "MANUAL";

const basePlaces = [
  { restaurant_id: 2, name: "Lotus Garden", google_rating: 4.3, user_rating_count: 74, collected_review_count: 6 },
  { restaurant_id: 3, name: "Quiet Corner Cafe", google_rating: null, user_rating_count: null, collected_review_count: 0 },
  { restaurant_id: 4, name: "Ember Grill", google_rating: 4.6, user_rating_count: 210, collected_review_count: 9 },
];

const gapRows = [
  {
    aspect: "food", own_score: 3.2, own_mentions: 6, competitor_avg: 4.4, competitors_scored: 2,
    leader: { restaurant_id: 4, name: "Ember Grill", score: 4.8 }, gap_vs_avg: -1.2, gap_vs_leader: -1.6,
    status: "LEARN", insufficient_reason: null,
  },
  {
    aspect: "service", own_score: 4.7, own_mentions: 5, competitor_avg: 3.1, competitors_scored: 2,
    leader: { restaurant_id: 2, name: "Lotus Garden", score: 3.4 }, gap_vs_avg: 1.6, gap_vs_leader: 1.3,
    status: "ATTACK", insufficient_reason: null,
  },
  {
    aspect: "price", own_score: 4.0, own_mentions: 1, competitor_avg: 4.1, competitors_scored: 1,
    leader: { restaurant_id: 4, name: "Ember Grill", score: 4.1 }, gap_vs_avg: null, gap_vs_leader: null,
    status: "INSUFFICIENT_DATA", insufficient_reason: "Not enough data: 1 of your reviews mention price; at least 3 are needed.",
  },
];

async function installMarketMocks(page: Page, role: "OWNER" | "ANALYST") {
  const selections = new Map<number, "PINNED" | "DISMISSED" | "MANUAL">();
  const calls: string[] = [];

  function competitiveSet() {
    const kept = basePlaces.filter((place) => ["PINNED", "MANUAL"].includes(selections.get(place.restaurant_id) ?? ""));
    const suggested = basePlaces.filter((place) => !selections.has(place.restaurant_id));
    const competitors = [
      ...kept.map((place) => ({ place, source: selections.get(place.restaurant_id) as Source })),
      ...suggested.map((place) => ({ place, source: "SUGGESTED" as Source })),
    ].map(({ place, source }) => ({
      ...place,
      address: null,
      distance_m: null,
      cuisine: null,
      price_level: null,
      source,
      scorable: place.collected_review_count > 0,
      reasons: [source === "PINNED" ? "Pinned by you" : `${place.collected_review_count} collected reviews, compared on the same criteria`],
    }));
    return {
      restaurant_id: 1,
      generated_at: "2026-11-21T10:00:00Z",
      competitors,
      dismissed: basePlaces.filter((place) => selections.get(place.restaurant_id) === "DISMISSED")
        .map((place) => ({ restaurant_id: place.restaurant_id, name: place.name })),
      matching_count: competitors.length,
      scored_competitor_count: competitors.filter((item) => item.scorable).length,
      min_suggestions: 5,
      max_suggestions: 10,
      can_edit: role === "OWNER",
      notice: `Only ${competitors.length} matching places were found (target: 5). Try expanding the radius or relaxing the cuisine filter once location and cuisine data are available.`,
      data_limitations: ["Distance, cuisine and price level are not in the current data, so suggestions are not limited by radius, cuisine or price yet."],
    };
  }

  await page.route(/localhost:8000\/restaurants\/\d+\/competitors/, async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    calls.push(`${request.method()} ${path}`);
    if (request.method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET, POST, PUT, DELETE, OPTIONS",
          "access-control-allow-headers": "authorization, content-type",
        },
      });
      return;
    }
    const reply = (body: unknown, status = 200) => route.fulfill({
      status, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: JSON.stringify(body),
    });

    if (path === "/restaurants/1/competitors" && request.method() === "GET") return reply(competitiveSet());
    if (path === "/restaurants/1/competitors/gap") {
      return reply({
        restaurant_id: 1, generated_at: "2026-11-21T10:00:00Z", min_reviews_per_criterion: 3, tie_margin: 0.3,
        weak_competitor_avg: 3.5, competitors_considered: 2, rows: gapRows,
      });
    }
    if (path === "/restaurants/1/competitors/gap/food/explain") {
      return reply({
        aspect: "food", status: "LEARN", model: "heuristic",
        explanation: "Guests who mention food rate Ember Grill 4.8/5, while Hearth & Honey averages 3.2/5 across 6 reviews.",
        evidence: [
          { review_id: 41, restaurant_id: 4, restaurant_name: "Ember Grill", is_own: false, rating: 5, text: "The grilled fish was delicious and fresh.", published_at: "2026-10-01T10:00:00Z" },
          { review_id: 12, restaurant_id: 1, restaurant_name: "Hearth & Honey", is_own: true, rating: 2, text: "The food arrived cold and bland.", published_at: "2026-10-02T10:00:00Z" },
        ],
      });
    }
    if (path === "/restaurants/1/competitors/candidates") {
      return reply(basePlaces.filter((place) => !["PINNED", "MANUAL"].includes(selections.get(place.restaurant_id) ?? ""))
        .map((place) => ({ ...place, address: null })));
    }
    const selectionMatch = path.match(/^\/restaurants\/1\/competitors\/(\d+)$/);
    if (selectionMatch && request.method() === "PUT") {
      selections.set(Number(selectionMatch[1]), request.postDataJSON().status);
      return reply(competitiveSet());
    }
    if (selectionMatch && request.method() === "DELETE") {
      selections.delete(Number(selectionMatch[1]));
      return reply(competitiveSet());
    }
    return reply({ detail: `Unmocked endpoint: ${request.method()} ${path}` }, 404);
  });
  return calls;
}

async function openMarketComparison(page: Page) {
  await page.goto("/");
  await authenticateTestUser(page);
  await page.getByRole("button", { name: "Market comparison" }).click();
  await expect(page.getByRole("heading", { name: "Competitive set" })).toBeVisible();
}

test("owners see suggested competitors with reasons and a low-match notice", async ({ page }) => {
  await installApiMocks(page, { role: "OWNER" });
  await installMarketMocks(page, "OWNER");
  await openMarketComparison(page);

  const rows = page.getByTestId("competitor-row");
  await expect(rows).toHaveCount(3);
  await expect(rows.first()).toContainText("Lotus Garden");
  await expect(rows.first()).toContainText("6 collected reviews, compared on the same criteria");
  await expect(rows.first()).toContainText("Not available");
  await expect(page.getByRole("status").filter({ hasText: "Only 3 matching places" })).toContainText("expanding the radius");
});

test("owners can pin, dismiss, restore and manually add competitors", async ({ page }) => {
  await installApiMocks(page, { role: "OWNER" });
  await installMarketMocks(page, "OWNER");
  await openMarketComparison(page);
  const rows = page.getByTestId("competitor-row");

  await page.getByRole("button", { name: "Pin Ember Grill" }).click();
  await expect(rows.first()).toContainText("Ember Grill");
  await expect(rows.first()).toContainText("Pinned");
  await expect(page.getByRole("button", { name: "Unpin Ember Grill" })).toBeVisible();

  await page.getByRole("button", { name: "Dismiss Lotus Garden" }).click();
  await expect(rows).toHaveCount(2);
  await expect(page.getByText("Dismissed (1):")).toBeVisible();

  await page.getByRole("button", { name: "Add competitor" }).click();
  const dialog = page.getByRole("dialog", { name: "Add a competitor" });
  await dialog.getByRole("listitem").filter({ hasText: "Lotus Garden" }).getByRole("button", { name: "Add" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(rows).toHaveCount(3);
  await expect(rows.filter({ hasText: "Lotus Garden" })).toContainText("Added manually");
  await expect(page.getByText("Dismissed (1):")).toHaveCount(0);

  await page.getByRole("button", { name: "Dismiss Quiet Corner Cafe" }).click();
  await page.getByRole("button", { name: "Restore Quiet Corner Cafe" }).click();
  await expect(rows).toHaveCount(3);
});

test("the gap table labels criteria, sorts by gap and explains with review quotes", async ({ page }) => {
  await installApiMocks(page, { role: "OWNER" });
  await installMarketMocks(page, "OWNER");
  await openMarketComparison(page);

  const food = page.getByTestId("gap-row-food");
  await expect(food).toHaveClass(/gap-behind/);
  await expect(food).toContainText("Learn from rivals");
  await expect(food).toContainText("-1.2");
  await expect(page.getByTestId("gap-row-service")).toHaveClass(/gap-ahead/);
  await expect(page.getByTestId("gap-row-service")).toContainText("Attack opportunity");
  const price = page.getByTestId("gap-row-price");
  await expect(price).toContainText("Not enough data");
  await expect(price).toContainText("at least 3 are needed");
  await expect(price.getByRole("button", { name: /Why/ })).toHaveCount(0);

  await page.getByLabel("Sort criteria").selectOption("ahead-first");
  await expect(page.locator(".gap-table tbody tr").first()).toHaveAttribute("data-testid", "gap-row-service");
  await page.getByLabel("Sort criteria").selectOption("behind-first");
  await expect(page.locator(".gap-table tbody tr").first()).toHaveAttribute("data-testid", "gap-row-food");

  await food.getByRole("button", { name: /Why/ }).click();
  await expect(page.getByText("Guests who mention food rate Ember Grill 4.8/5")).toBeVisible();
  const quotes = page.locator(".gap-evidence li");
  await expect(quotes).toHaveCount(2);
  await expect(quotes.first()).toContainText("Ember Grill");
  await expect(quotes.nth(1)).toContainText("Your guest");
});

test("analysts can view the market comparison but cannot change the competitive set", async ({ page }) => {
  await installApiMocks(page, { role: "ANALYST" });
  await installMarketMocks(page, "ANALYST");
  await page.goto("/");
  await authenticateTestUser(page);
  await page.getByRole("button", { name: "Market comparison" }).click();
  await page.getByLabel("Restaurant to compare").selectOption("1");

  await expect(page.getByText(/View only/)).toBeVisible();
  await expect(page.getByTestId("competitor-row")).toHaveCount(3);
  await expect(page.getByRole("button", { name: /^Pin / })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Dismiss / })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add competitor" })).toHaveCount(0);
});

test("administrators do not see market comparison", async ({ page }) => {
  await installApiMocks(page, { role: "ADMIN" });
  await page.goto("/");
  await authenticateTestUser(page);

  await expect(page.getByRole("button", { name: "Review insights" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Market comparison" })).toHaveCount(0);
});
