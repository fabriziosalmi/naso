import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  // CI has no long-running dev server, and there is no frontend service in
  // docker-compose.yml either, so without this Playwright navigated to a port
  // nothing was listening on and every run died with ERR_CONNECTION_REFUSED.
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
});
