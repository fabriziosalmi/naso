import { test, expect } from '@playwright/test';

test.describe('NASO Forensic Analyst E2E Flow', () => {
  // Use a default user that should be seeded in the test DB
  const MOCK_USER = {
    email: 'test_analyst@naso-engine.io',
    password: 'securepassword123'
  };

  test.beforeEach(async ({ page }) => {
    // Go to the app entrypoint
    await page.goto('http://localhost:5173');
  });

  test('Complete Investigation Flow (Login -> Topology -> Recon -> Logout)', async ({ page }) => {
    await expect(page.locator('text=Authenticate')).toBeVisible();

    await page.fill('input[type="email"]', MOCK_USER.email);
    await page.fill('input[type="password"]', MOCK_USER.password);
    await page.click('button:has-text("Authenticate")');

    // 3. Assert Backend Token Assignment & Dashboard Route
    // Wait for the UI elements of the Dashboard Header
    await expect(page.locator('text=Operational')).toBeVisible({ timeout: 10000 });

    // 4. Navigate to Master Identities
    await page.click('a[href="/identities"]');
    await expect(page.locator('text=Active Targets')).toBeVisible();

    // 5. Navigate to Topology
    await page.click('a[href="/topology"]');
    // Force graph canvas takes time to render
    await expect(page.locator('canvas')).toBeVisible();

    // 6. Execute Dark Web Recon
    await page.click('a[href="/dark-search"]');
    const searchInput = page.locator('input[placeholder="Enter target vector..."]');
    await expect(searchInput).toBeVisible();
    await searchInput.fill('naso test leak');
    
    // Simulate hitting Enter
    await searchInput.press('Enter');
    
    // Check loading state
    await expect(page.locator('text=Probing onion relays...')).toBeVisible();

    // 7. Test Logout Trigger (Zustand wipe)
    await page.click('button:has-text("Logout")');
    await expect(page.locator('text=Authenticate Operator')).toBeVisible();
  });
});
