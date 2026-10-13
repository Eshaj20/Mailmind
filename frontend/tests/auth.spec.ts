import { expect, test } from "@playwright/test";

test("renders the authentication screen", async ({ page }) => {
  await page.goto("/#/auth");

  await expect(page.getByRole("heading", { name: "Create your workspace" })).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
});
