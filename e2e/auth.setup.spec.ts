import { expect, test as setup } from "@playwright/test";

import { AUTH_STATE, E2E_PASSWORD, E2E_USER } from "./playwright.config";

/** Logs in once through the real UI form and persists the session cookie
 * for every smoke test (also keeps the in-memory login rate limiter happy). */
setup("login as owner", async ({ page }) => {
  await page.goto("/login");
  await page.fill("#username", E2E_USER);
  await page.fill("#password", E2E_PASSWORD);
  await page.click("form button[type=submit]");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator("h1.page-title")).toContainText(/\w+/);

  await page.context().storageState({ path: AUTH_STATE });
});
