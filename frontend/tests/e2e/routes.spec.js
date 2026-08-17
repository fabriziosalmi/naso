import { test, expect } from '@playwright/test';

// Every client-side route has to survive being loaded directly — a reload, a
// bookmark, a link somebody pasted into a chat. Two of them did not.
//
// The dev/preview proxy matched API prefixes by string prefix, so `/ai`
// swallowed `/ai-analyst` and `/identities` collided with the route of the same
// name exactly. Loading either one left the application and rendered the API's
// answer in the browser:
//
//     {"detail":"Not Found"}
//
// It was found in the last frame of a recorded demo, which is a poor substitute
// for a test.
const ROUTES = ['/', '/topology', '/identities', '/dark-search', '/audit', '/ai-analyst', '/docs'];

for (const route of ROUTES) {
  test(`${route} loads the application, not the API`, async ({ page }) => {
    const response = await page.goto(route);

    // The document itself must be HTML from the SPA, never a JSON API reply.
    const contentType = response?.headers()['content-type'] ?? '';
    expect(contentType, `${route} served ${contentType}`).toContain('text/html');

    const body = await page.locator('body').innerText();
    expect(body, `${route} rendered a raw API response`).not.toContain('"detail"');

    // React mounted: unauthenticated visitors land on the sign-in screen, and
    // that is the same for every route.
    await expect(page.getByRole('heading', { name: 'Operator sign-in' })).toBeVisible({
      timeout: 15_000,
    });
  });
}
