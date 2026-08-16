import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',

  // Builds the app and serves the bundle, rather than running the dev server.
  //
  // The dev server was the source of a flake that failed CI twice and passed
  // it twice on identical trees: `vite` transforms the module graph on demand,
  // per request, so the time from `page.goto` resolving to React mounting
  // depends on how loaded the machine is. On this runner the same job also
  // builds two images and runs seven containers. Observed: 3.3s on an idle
  // machine, 6.9s on a quiet CI run, and past 30s on a busy one.
  //
  // Raising the timeout was the wrong lever — the first attempt raised the
  // assertion budget to 30s while leaving Playwright's *test* timeout at its
  // 30s default, so the test was killed before the assertion could use what it
  // had been given. Serving static files removes the variable instead of
  // widening the window around it, and has the side benefit of exercising the
  // production bundle, chunk splitting and all, rather than the dev pipeline
  // no user ever runs.
  //
  // The API proxy is mirrored onto `preview` in vite.config.js so the app
  // behaves the same here as in dev.
  webServer: {
    command: 'npm run build && npm run preview -- --port 5173 --strictPort',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    // The build is inside this budget, and it is a real production build of an
    // app that bundles force-graph, recharts and Prism.
    timeout: 180 * 1000,
  },

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },

  // Comfortably above what a static-file mount needs, so a failure here means
  // something is actually broken rather than merely slow.
  timeout: 60 * 1000,

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
