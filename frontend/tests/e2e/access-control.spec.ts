import { expect, test } from "@playwright/test";
import { authenticateTestUser, installApiMocks } from "./fixtures";

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
