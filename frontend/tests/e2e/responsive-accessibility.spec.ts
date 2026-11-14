import { expect, test } from "@playwright/test";
import { analysis, installApiMocks } from "./fixtures";

test("FE-20 keeps listing, details, and insights usable at supported viewport sizes", async ({ page }) => {
  await installApiMocks(page, { initialAnalysis: analysis });
  await page.goto("/");

  for (const width of [375, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole("heading", { name: /Good morning/ })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("button", { name: /Hearth & Honey/ }).click();
    await expect(page.getByRole("heading", { name: "Hearth & Honey", level: 2 })).toBeVisible();
    await expect(page.getByText(/The meal was lovely\./)).toBeVisible();
    await expectNoHorizontalOverflow(page);

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
  const unnamedControls = await page.locator("a, button, input, select, textarea").evaluateAll((controls) =>
    controls
      .filter((control) => {
        const labelledBy = control.getAttribute("aria-labelledby")
          ?.split(/\s+/)
          .map((id) => document.getElementById(id)?.textContent ?? "")
          .join(" ");
        const formLabels = (control as HTMLInputElement).labels
          ? Array.from((control as HTMLInputElement).labels ?? []).map((label) => label.textContent ?? "").join(" ")
          : "";
        const label = control.getAttribute("aria-label")
          || labelledBy
          || control.getAttribute("title")
          || control.textContent
          || (control as HTMLInputElement).placeholder
          || formLabels;
        return !label?.trim();
      })
      .map((control) => control.outerHTML),
  );
  expect(unnamedControls).toEqual([]);

  let insightsFocused = false;
  for (let index = 0; index < 20; index += 1) {
    await page.keyboard.press("Tab");
    if (await page.getByRole("button", { name: "Review insights" }).evaluate((button) => button === document.activeElement)) {
      insightsFocused = true;
      break;
    }
  }
  expect(insightsFocused).toBeTruthy();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Review insights" })).toBeVisible();

  await page.getByRole("button", { name: "Overview" }).focus();
  await page.keyboard.press("Space");
  await expect(page.getByRole("heading", { name: /Good morning/ })).toBeVisible();

  let searchFocused = false;
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  for (let index = 0; index < 20; index += 1) {
    await page.keyboard.press("Tab");
    if (await page.getByRole("textbox", { name: "Search restaurants" }).evaluate((input) => input === document.activeElement)) {
      searchFocused = true;
      break;
    }
  }
  expect(searchFocused).toBeTruthy();
  const search = page.getByRole("textbox", { name: "Search restaurants" });
  await expect(search).toBeFocused();
  const outlineStyle = await page.getByRole("textbox", { name: "Search restaurants" }).evaluate((input) =>
    getComputedStyle(input).outlineStyle,
  );
  expect(outlineStyle).not.toBe("none");
  await page.keyboard.press("Shift+Tab");
  await expect(page.getByRole("button", { name: "View all" }).first()).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(search).toBeFocused();
});

async function expectNoHorizontalOverflow(page: import("@playwright/test").Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}
