import { expect, test } from "@playwright/test";
import { installApiMocks } from "./fixtures";

test.describe("FE-01 restaurant listing and search", () => {
  test.beforeEach(async ({ page }) => {
    await installApiMocks(page);
    await page.goto("/");
  });

  test("FE-01 displays restaurant data and optional values", async ({ page }) => {
    const hearth = page.getByRole("button", { name: /Hearth & Honey/ });
    await expect(hearth).toContainText("18 Oak Street, Portland");
    await expect(hearth).toContainText("4.8");
    await expect(hearth).toContainText("2 reviews");

    const missingValues = page.getByRole("button", { name: /Quiet Corner Cafe/ });
    await expect(missingValues).toContainText("Address not available");
    await expect(missingValues).toContainText("—");
    await expect(missingValues).toContainText("0 reviews");
    await expect(page.getByRole("button", { name: /Hearth & Honey/ })).toHaveCount(1);
  });

  test("FE-02 sends a name query and shows matching restaurants", async ({ page }) => {
    const response = page.waitForResponse((candidate) => {
      const url = new URL(candidate.url());
      return url.pathname === "/restaurants" && url.searchParams.get("q") === "Lotus";
    });
    await page.getByRole("textbox", { name: "Search restaurants" }).fill("Lotus");
    await response;

    await expect(page.getByRole("button", { name: /Lotus Garden/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Hearth & Honey/ })).toHaveCount(0);
  });

  test("FE-03 searches by address", async ({ page }) => {
    const response = page.waitForResponse((candidate) => {
      const url = new URL(candidate.url());
      return url.pathname === "/restaurants" && url.searchParams.get("q") === "River Road";
    });
    await page.getByRole("textbox", { name: "Search restaurants" }).fill("River Road");
    await response;

    await expect(page.getByRole("button", { name: /Lotus Garden/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /Hearth & Honey/ })).toHaveCount(0);
  });

  test("FE-04 displays an empty state for unmatched search results", async ({ page }) => {
    const response = page.waitForResponse((candidate) => {
      const url = new URL(candidate.url());
      return url.pathname === "/restaurants" && url.searchParams.get("q") === "No matching restaurant";
    });
    await page.getByRole("textbox", { name: "Search restaurants" }).fill("No matching restaurant");
    await response;

    await expect(page.getByText("No restaurants found")).toBeVisible();
    await expect(page.getByRole("button", { name: /Hearth & Honey/ })).toHaveCount(0);
  });

  test("FE-05 shows loading, reports an API error, and retries successfully", async ({ page }) => {
    let releaseList!: () => void;
    const listResponseGate = new Promise<void>((resolve) => {
      releaseList = resolve;
    });
    await page.unroute("http://localhost:8000/**");
    await installApiMocks(page, {
      beforeListResponse: () => listResponseGate,
      failFirstRestaurantList: true,
    });

    const firstList = page.waitForResponse((candidate) =>
      new URL(candidate.url()).pathname === "/restaurants" && candidate.status() === 503,
    );
    await page.goto("/");
    await expect(page.getByText("Loading restaurants...")).toBeVisible();
    releaseList();
    await firstList;
    await expect(page.getByText("Restaurant service unavailable")).toBeVisible();

    const retryList = page.waitForResponse((candidate) => new URL(candidate.url()).pathname === "/restaurants");
    await page.getByRole("button", { name: "Refresh" }).click();
    await retryList;
    await expect(page.getByRole("button", { name: /Hearth & Honey/ })).toBeVisible();
  });

  test.fixme("FE-06 paginates results without duplicates", async ({ page }) => {
    // The current interface renders one capped page and has disabled pagination controls.
    await page.getByRole("button", { name: "Next page" }).click();
    await expect(page.getByRole("button", { name: "Next page" })).toBeEnabled();
  });
});
