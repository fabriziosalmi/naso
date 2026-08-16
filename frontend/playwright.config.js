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
  // The upload-artifact step in draconian-ci.yml points at playwright-report/,
  // which nothing was writing: the default reporter prints to stdout and
  // leaves no directory behind, so every CI run ended with "No files were
  // found with the provided path" and a failure nobody could inspect
  // afterwards. `list` keeps the console output the validate.sh summary reads;
  // `html` produces the directory the workflow uploads.
  reporter: process.env.CI
    ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]]
    : [['list']],
});
