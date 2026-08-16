import { test, expect } from '@playwright/test';

test('has title and login form', async ({ page }) => {
  await page.goto('/');

  // Static markup from index.html — available as soon as the document loads.
  await expect(page).toHaveTitle(/NASO/);

  // Everything below is rendered by React, and this is the first assertion
  // that waits for it, so it carries the cold-start budget.
  //
  // `page.goto` resolves when the document loads; the app then pulls its
  // module graph through Vite's dev server, which transforms each module on
  // first request. On a CI runner that is also building two images and running
  // seven containers, that first paint has taken longer than the 5s default —
  // producing a failure that looks like a missing element and is really a
  // missing millisecond. The static title assertion above passing while this
  // one timed out is the signature.
  //
  // The "NASO" brand heading on this page sits in a `lg:hidden` block, so it
  // is not rendered at Playwright's default 1280x720 viewport. "Operator
  // sign-in" is the heading the desktop layout actually shows.
  await expect(page.getByRole('heading', { name: 'Operator sign-in' })).toBeVisible({
    timeout: 30_000,
  });

  // React has mounted by now, so these keep the default timeout — if one of
  // them fails it is a real regression, not a slow start.
  await expect(page.locator('input[type="email"]')).toBeVisible();
  await expect(page.locator('input[type="password"]')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Authenticate' })).toBeVisible();
});
