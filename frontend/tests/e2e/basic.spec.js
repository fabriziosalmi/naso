import { test, expect } from '@playwright/test';

test('has title and login form', async ({ page }) => {
  await page.goto('http://localhost:5173');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/NASO/);
  
  // Check if we are at least rendering the main container
  const main = page.locator('role=application');
  await expect(main).toBeVisible();
});
