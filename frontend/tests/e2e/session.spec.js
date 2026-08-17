import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { test, expect } from '@playwright/test';

// The credentials `make bootstrap` generated and `init_db.py` provisioned. Read
// from the repository .env rather than hardcoded: every run has a different
// password, which is the point of generating them.
function adminCredentials() {
  try {
    const env = readFileSync(resolve(process.cwd(), '..', '.env'), 'utf8');
    const read = (key) => env.match(new RegExp(`^${key}=(.*)$`, 'm'))?.[1]?.trim();
    const email = read('NASO_ADMIN_EMAIL');
    const password = read('NASO_ADMIN_PASSWORD');
    return email && password ? { email, password } : null;
  } catch {
    return null;
  }
}

// This is the regression test for the defect that made the SPA unusable: the
// session lives in an `httpOnly` cookie, `isAuthenticated` started `false` on
// every mount, and nothing asked the API whether the cookie was still good — so
// every page reload dropped the operator back to the login form. The store had
// a `fetchMe()` action for exactly this and nothing called it, while
// `GET /users/me` did not exist and answered 405.
//
// It can only be proven in a browser: the assertion is about what survives a
// real reload, with a real cookie jar, against the real API.
test('a signed-in session survives a page reload', async ({ page }) => {
  const creds = adminCredentials();
  test.skip(!creds, 'No NASO_ADMIN_* in ../.env — run `make bootstrap` first.');

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Operator sign-in' })).toBeVisible({
    timeout: 15_000,
  });

  await page.locator('input[type="email"]').fill(creds.email);
  await page.locator('input[type="password"]').fill(creds.password);
  await page.getByRole('button', { name: 'Authenticate' }).click();

  // Logged in: the sign-in heading is gone.
  await expect(page.getByRole('heading', { name: 'Operator sign-in' })).toBeHidden({
    timeout: 15_000,
  });

  await page.reload();

  // The whole point. Before the fix this reliably showed the login form again.
  await expect(page.getByRole('heading', { name: 'Operator sign-in' })).toBeHidden({
    timeout: 15_000,
  });
});

test('signing out survives a reload too', async ({ page }) => {
  const creds = adminCredentials();
  test.skip(!creds, 'No NASO_ADMIN_* in ../.env — run `make bootstrap` first.');

  await page.goto('/');
  await page.locator('input[type="email"]').fill(creds.email);
  await page.locator('input[type="password"]').fill(creds.password);
  await page.getByRole('button', { name: 'Authenticate' }).click();
  await expect(page.getByRole('heading', { name: 'Operator sign-in' })).toBeHidden({
    timeout: 15_000,
  });

  // Clearing the cookie is what a logout does server-side; asserting on the
  // reload afterwards checks the restore path fails closed, which matters more
  // than the button that triggers it.
  await page.context().clearCookies();
  await page.reload();

  await expect(page.getByRole('heading', { name: 'Operator sign-in' })).toBeVisible({
    timeout: 15_000,
  });
});
