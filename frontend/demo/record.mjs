/**
 * Scripted demo recorder.
 *
 * Drives the real UI against a real stack and writes a video plus a set of
 * stills to `frontend/demo/out/`. Scripted rather than hand-captured so the
 * material can be regenerated when the interface changes, instead of quietly
 * ageing into a screenshot of software that no longer looks like this.
 *
 *   make up && docker exec naso-api python init_db.py && make demo
 *   cd frontend && npm run build && npm run preview -- --port 5173 &
 *   node demo/record.mjs
 *
 * Credentials come from the repository `.env`, the same place `make bootstrap`
 * put them; nothing is hardcoded and nothing is committed.
 */

import { readFileSync, mkdirSync, renameSync, readdirSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from '@playwright/test';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, 'out');
const BASE = process.env.DEMO_BASE_URL ?? 'http://localhost:5173';

function credentials() {
  const env = readFileSync(resolve(HERE, '..', '..', '.env'), 'utf8');
  const read = (key) => env.match(new RegExp(`^${key}=(.*)$`, 'm'))?.[1]?.trim();
  const email = read('NASO_ADMIN_EMAIL');
  const password = read('NASO_ADMIN_PASSWORD');
  if (!email || !password) {
    throw new Error('NASO_ADMIN_EMAIL / NASO_ADMIN_PASSWORD not found in .env — run `make bootstrap`.');
  }
  return { email, password };
}

// Slow enough to read, fast enough to keep. The pauses are the whole
// difference between a recording and a flicker.
const BEAT = 1400;

async function shot(page, name) {
  await page.screenshot({ path: join(OUT, `${name}.png`) });
  console.log(`  captured ${name}.png`);
}

async function main() {
  const { email, password } = credentials();
  mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2, // retina stills; the video stays at viewport size
    recordVideo: { dir: OUT, size: { width: 1440, height: 900 } },
    colorScheme: 'dark',
  });
  // Mark the onboarding tour as already seen, before any script runs. It opens
  // on first login with a nine-step overlay that dims the page and swallows
  // clicks — clicking "Skip" afterwards is a race, and losing it means every
  // navigation below silently finds nothing. `naso_tour_version` / '2' are
  // OnboardingTour.jsx's own constants.
  await context.addInitScript(() => {
    try {
      window.localStorage.setItem('naso_tour_version', '2');
    } catch { /* storage unavailable — the click fallback below still applies */ }
  });

  const page = await context.newPage();

  console.log('· sign-in');
  await page.goto(BASE);
  await page.getByRole('heading', { name: 'Operator sign-in' }).waitFor({ timeout: 30_000 });
  await shot(page, '01-login');
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.waitForTimeout(600);
  await page.getByRole('button', { name: 'Authenticate' }).click();
  await page.getByRole('heading', { name: 'Operator sign-in' }).waitFor({ state: 'hidden', timeout: 30_000 });
  await page.waitForTimeout(BEAT);

  // The onboarding tour opens on first login with a nine-step overlay that
  // dims the page and swallows clicks. Leaving it up does not just look
  // cluttered: every navigation below silently finds nothing.
  const skip = page.getByRole('button', { name: /^Skip$/ });
  if (await skip.count()) {
    console.log('  dismissing the onboarding tour');
    await skip.first().click();
    await page.waitForTimeout(600);
  }
  await page.waitForTimeout(BEAT * 2);
  await shot(page, '02-dashboard');

  for (const [label, name] of [
    ['Neural Topology', '03-topology'],
    ['Master Identities', '04-identities'],
    ['Dark Recon Probe', '05-dark-recon'],
    ['Audit Logs', '06-audit'],
    ['AI Co-Analyst', '07-ai-analyst'],
  ]) {
    console.log(`· ${label}`);
    // By the sidebar label, not by the file name. Getting these two the wrong
    // way round searches for a link called "03-topology", finds nothing, and
    // reports it as a missing nav entry.
    const link = page.getByRole('link', { name: label }).first();
    if ((await link.count()) === 0) {
      console.log(`  (no nav entry named ${label}, skipping)`);
      continue;
    }
    await link.click();
    // The topology graph animates into place; everything else settles fast.
    await page.waitForTimeout(name.includes('topology') ? BEAT * 3 : BEAT * 2);
    await shot(page, name);
  }

  console.log('· back to the dashboard, then reload — the session survives it');
  await page.getByRole('link', { name: 'Dashboard' }).first().click();
  await page.waitForTimeout(BEAT);
  await page.reload();
  await page.waitForTimeout(BEAT * 2);
  await shot(page, '08-after-reload');

  await context.close();
  await browser.close();

  const video = readdirSync(OUT).find((f) => f.endsWith('.webm'));
  if (video) {
    renameSync(join(OUT, video), join(OUT, 'naso-demo.webm'));
    console.log('\nvideo: frontend/demo/out/naso-demo.webm');
  }
  console.log(`stills: frontend/demo/out/*.png`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
