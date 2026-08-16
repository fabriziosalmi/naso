import { test, expect } from '@playwright/test';

test('has title and login form', async ({ page }) => {
  await page.goto('/');

  // Static markup from index.html — available as soon as the document loads.
  await expect(page).toHaveTitle(/NASO/);

  // Everything below is rendered by React, and this is the first assertion
  // that waits for it. The suite runs against the built bundle rather than the
  // dev server (see playwright.config.js), so this is a static file fetch and
  // a mount, not an on-demand transform of the whole module graph — 15s is
  // generous rather than hopeful.
  //
  // The "NASO" brand heading on this page sits in a `lg:hidden` block, so it
  // is not rendered at Playwright's default 1280x720 viewport. "Operator
  // sign-in" is the heading the desktop layout actually shows.
  await expect(page.getByRole('heading', { name: 'Operator sign-in' })).toBeVisible({
    timeout: 15_000,
  });

  // React has mounted by now, so these keep the default timeout — if one of
  // them fails it is a real regression, not a slow start.
  await expect(page.locator('input[type="email"]')).toBeVisible();
  await expect(page.locator('input[type="password"]')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Authenticate' })).toBeVisible();
});
