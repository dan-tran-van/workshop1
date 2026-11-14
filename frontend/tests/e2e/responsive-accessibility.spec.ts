import { expect, test } from "@playwright/test";
import { analysis, installApiMocks } from "./fixtures";

test("FE-20 keeps listing, details, and insights usable at supported viewport sizes", async ({ page }) => {
  await installApiMocks(page, { initialAnalysis: analysis });
  await page.goto("/");

  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("heading", { name: /Good morning/ })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("button", { name: /Lotus Garden/ }).click();
    await expect(page.getByRole("heading", { name: "Lotus Garden", level: 2 })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("button", { name: /Hearth & Honey/ }).click();
    await expect(page.getByText(analysis.result_json.summary)).toBeVisible();
    await page.getByRole("button", { name: "Review insights" }).click();
    await expect(page.getByRole("heading", { name: "Review insights" })).toBeVisible();
    await expect(page.getByText(analysis.result_json.summary)).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("button", { name: "Overview" }).click();
  }
});

test("FE-20 keeps long reviews readable and interactive controls keyboard accessible", async ({ page }) => {
  await installApiMocks(page, { initialAnalysis: analysis });
  await page.goto("/");

  await expect(page.getByText(/The meal was lovely\./)).toBeVisible();
  const unnamedButtons = await page.locator("button").evaluateAll((buttons) =>
    buttons
      .filter((button) => {
        const label = button.getAttribute("aria-label") || button.getAttribute("title") || button.textContent || "";
        return label.trim().length === 0;
      })
      .map((button) => button.outerHTML),
  );
  expect(unnamedButtons).toEqual([]);

  let searchFocused = false;
  for (let index = 0; index < 20; index += 1) {
    await page.keyboard.press("Tab");
    if (await page.getByRole("textbox", { name: "Search restaurants" }).evaluate((input) => input === document.activeElement)) {
      searchFocused = true;
      break;
    }
  }
  expect(searchFocused).toBeTruthy();
  await expect(page.getByRole("textbox", { name: "Search restaurants" })).toBeFocused();
  const outlineStyle = await page.getByRole("textbox", { name: "Search restaurants" }).evaluate((input) =>
    getComputedStyle(input).outlineStyle,
  );
  expect(outlineStyle).not.toBe("none");
});

async function expectNoHorizontalOverflow(page: import("@playwright/test").Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}
