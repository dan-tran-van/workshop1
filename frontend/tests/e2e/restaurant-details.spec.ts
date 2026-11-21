import { expect, test } from "@playwright/test";
import { authenticateTestUser, installApiMocks, reviews } from "./fixtures";

test.describe("FE-02 restaurant details and reviews", () => {
  test.beforeEach(async ({ page }) => {
    await installApiMocks(page);
    await page.goto("/");
    await authenticateTestUser(page);
  });

  test("FE-07 opens details for the selected restaurant ID", async ({ page }) => {
    const detailRequest = page.waitForRequest((request) =>
      new URL(request.url()).pathname === "/restaurants/2",
    );
    await page.getByRole("button", { name: /Lotus Garden/ }).click();
    await detailRequest;

    await expect(page.getByRole("heading", { name: "Lotus Garden", level: 2 })).toBeVisible();
    await expect(page.locator(".detail-address")).toHaveText("240 River Road, Portland");
    await expect(page.getByText("Taylor Chen")).toBeVisible();
  });

  test("FE-08 shows review author, rating, content, and date", async ({ page }) => {
    const review = reviews[0];
    await expect(page.getByText(review.author_name)).toBeVisible();
    await expect(page.getByText(review.text)).toBeVisible();
    await expect(page.getByLabel(`${review.rating} out of 5 stars`)).toBeVisible();
    await expect(page.getByText("Nov 12, 2020")).toBeVisible();

    await page.getByRole("button", { name: /Lotus Garden/ }).click();
    await expect(page.getByText("Fresh food and a welcoming atmosphere.")).toBeVisible();
  });

  test("FE-09 shows a useful empty state for a restaurant without reviews", async ({ page }) => {
    await page.getByRole("button", { name: /Quiet Corner Cafe/ }).click();
    await expect(page.getByText("No reviews have been collected for this location yet.")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Quiet Corner Cafe", level: 2 })).toBeVisible();
  });

  test.fixme("FE-10 paginates reviews without duplicate records", async ({ page }) => {
    // The detail view currently embeds reviews and has no review pagination control.
    await expect(page.getByRole("button", { name: "Next reviews page" })).toBeEnabled();
  });

  test.fixme("FE-11 handles an invalid restaurant detail URL", async ({ page }) => {
    // Deferred until the app has URL-routed restaurant details.
    await page.goto("/restaurants/9999");
    await expect(page.getByText(/not found/i)).toBeVisible();
  });
});
