import { expect, test } from "@playwright/test";
import {
  analysis,
  authenticateTestUser,
  installApiMocks,
  olderAnalysis,
  pastAnalysis,
} from "./fixtures";

test("administrators can access user management and data sync", async ({ page }) => {
  await installApiMocks(page, { role: "ADMIN" });
  await page.goto("/");
  await authenticateTestUser(page);

  await expect(page.getByRole("button", { name: "Data sync" })).toBeVisible();
  await expect(page.getByRole("button", { name: "User access" })).toBeVisible();
  await page.getByRole("button", { name: "User access" }).click();
  await expect(page.getByRole("heading", { name: "Create a user" })).toBeVisible();
});

test("analysts can view insights but do not see administration actions", async ({ page }) => {
  await installApiMocks(page, { role: "ANALYST" });
  await page.goto("/");
  await authenticateTestUser(page);

  await expect(page.getByRole("button", { name: "Review insights" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Data sync" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "User access" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add restaurant" })).toHaveCount(0);
});

test("owners only see their assigned restaurants and can add their own", async ({ page }) => {
  await installApiMocks(page, { role: "OWNER" });
  await page.goto("/");
  await authenticateTestUser(page);

  await expect(page.getByRole("button", { name: /Hearth & Honey/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Lotus Garden/ })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add restaurant" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Data sync" })).toHaveCount(0);
});

test("owners can compare 6 criteria on assigned restaurants using their own history and launch comparison from Review insights", async ({ page }) => {
  await installApiMocks(page, {
    role: "OWNER",
    initialAnalysis: analysis,
    analysisHistory: [
      { id: 21, created_at: "2026-11-14T11:00:00Z", analysis },
      { id: 20, created_at: "2026-11-08T09:00:00Z", analysis: pastAnalysis },
      { id: 19, created_at: "2026-11-01T10:00:00Z", analysis: olderAnalysis },
    ],
  });
  await page.goto("/");
  await authenticateTestUser(page);

  await expect(page.getByRole("button", { name: /Lotus Garden/ })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Criteria comparison summary" })).toBeVisible();
  await expect(page.locator(".aspect-card").filter({ hasText: "Fresh, seasonal dishes." })).toContainText("+0.4");

  await page.getByRole("button", { name: "Chart" }).click();
  await expect(page.getByRole("region", { name: "6 criteria comparison chart" })).toBeVisible();
  await page.getByRole("button", { name: "Cards" }).click();

  await page.getByRole("button", { name: "Review insights" }).click();
  const olderRow = page.locator(".insights-results table tbody tr").nth(2);
  await olderRow.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByRole("combobox", { name: "Compare with past analysis" })).toHaveValue(String(olderAnalysis.id));
  await expect(page.locator(".aspect-card").filter({ hasText: "Fresh, seasonal dishes." })).toContainText("+0.8");
});

test("analysts can compare 6 criteria across locations using their own history without seeing admin controls", async ({ page }) => {
  await installApiMocks(page, {
    role: "ANALYST",
    initialAnalysis: analysis,
    analysisHistory: [
      { id: 30, created_at: "2026-11-14T11:00:00Z", analysis },
      { id: 29, created_at: "2026-11-08T10:00:00Z", analysis: pastAnalysis },
    ],
  });
  await page.goto("/");
  await authenticateTestUser(page);

  await expect(page.getByRole("button", { name: "Data sync" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "User access" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add restaurant" })).toHaveCount(0);

  const summary = page.getByRole("region", { name: "Criteria comparison summary" });
  await expect(summary).toBeVisible();
  await expect(summary).toContainText("3 improved");

  await page.getByRole("button", { name: "Chart" }).click();
  await expect(page.getByRole("region", { name: "6 criteria comparison chart" })).toBeVisible();
  await page.getByRole("button", { name: "Cards" }).click();

  await page.getByRole("button", { name: /Lotus Garden/ }).click();
  await expect(page.getByRole("heading", { name: "Lotus Garden", level: 2 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Criteria comparison summary" })).toHaveCount(0);

  await page.getByRole("button", { name: "Review insights" }).click();
  const pastRow = page.locator(".insights-results table tbody tr").nth(1);
  await pastRow.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByRole("heading", { name: "Hearth & Honey", level: 2 })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Compare with past analysis" })).toHaveValue(String(pastAnalysis.id));
});
