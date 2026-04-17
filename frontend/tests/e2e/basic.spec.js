import { test, expect } from '@playwright/test';

test('has title and login form', async ({ page }) => {
  await page.goto('/');

  await expect(page).toHaveTitle(/NASO/);
  await expect(page.getByRole('heading', { name: 'NASO' })).toBeVisible();
  await expect(page.locator('input[type="email"]')).toBeVisible();
  await expect(page.locator('input[type="password"]')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Authenticate' })).toBeVisible();
});
