import { test, expect } from '@playwright/test';

test('has title and login form', async ({ page }) => {
  await page.goto('/');

  await expect(page).toHaveTitle(/NASO/);
  // The "NASO" brand heading on this page sits in a `lg:hidden` block, so it
  // is not rendered at Playwright's default 1280x720 viewport. "Operator
  // sign-in" is the heading the desktop layout actually shows.
  await expect(page.getByRole('heading', { name: 'Operator sign-in' })).toBeVisible();
  await expect(page.locator('input[type="email"]')).toBeVisible();
  await expect(page.locator('input[type="password"]')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Authenticate' })).toBeVisible();
});
