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
 *
 * Pacing: each screen opens with a centered chapter card (title + one line on
 * a dimmed backdrop) that fades out, then the UI holds clean and unobstructed.
 * The card explains what the viewer is looking at; the hold gives them time
 * to actually look at it. Stills are captured card-free.
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
// How long the chapter card stays fully visible, and how long the UI then
// holds clean before the next move. Card + fades + hold ≈ 7s per screen:
// enough to read a line AND look at the interface it described.
const CARD_HOLD = 2400;
const CARD_FADE = 400;
const CLEAN_HOLD = 3800;

/**
 * Centered chapter card on a dimmed backdrop, faded in and out around the
 * clean hold. Styled after the app's own dark zinc surfaces so it reads as
 * part of the product, not a subtitle track pasted on top.
 */
async function chapterCard(page, { kicker = 'NASO FORENSIC ENGINE', title, line }) {
  await page.evaluate(
    ({ kicker, title, line, fade }) => {
      const overlay = document.createElement('div');
      overlay.id = '__naso_demo_card';
      overlay.style.cssText = [
        'position:fixed', 'inset:0', 'z-index:2147483647',
        'display:flex', 'align-items:center', 'justify-content:center',
        'background:rgba(3,3,5,0.62)', 'backdrop-filter:blur(6px)',
        `transition:opacity ${fade}ms ease`, 'opacity:0',
        'font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
      ].join(';');
      const card = document.createElement('div');
      card.style.cssText = [
        'max-width:680px', 'margin:0 24px', 'padding:36px 44px', 'text-align:center',
        'background:rgba(24,24,27,0.96)', 'border:1px solid rgba(255,255,255,0.08)',
        'border-radius:18px', 'box-shadow:0 24px 80px rgba(0,0,0,0.55)',
      ].join(';');
      card.innerHTML = `
        <div style="font-size:12px;letter-spacing:0.22em;color:#0A84FF;font-weight:600;margin-bottom:14px;">${kicker}</div>
        <div style="font-size:30px;line-height:1.2;color:#fafafa;font-weight:700;margin-bottom:12px;">${title}</div>
        <div style="font-size:16px;line-height:1.55;color:#a1a1aa;">${line}</div>`;
      overlay.appendChild(card);
      document.body.appendChild(overlay);
      requestAnimationFrame(() => { overlay.style.opacity = '1'; });
    },
    { kicker, title, line, fade: CARD_FADE },
  );
  await page.waitForTimeout(CARD_FADE + CARD_HOLD);
  await page.evaluate((fade) => {
    const overlay = document.getElementById('__naso_demo_card');
    if (overlay) {
      overlay.style.opacity = '0';
      setTimeout(() => overlay.remove(), fade + 50);
    }
  }, CARD_FADE);
  await page.waitForTimeout(CARD_FADE + 100);
}

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
  await chapterCard(page, {
    title: 'NASO Forensic Engine',
    line: 'Open-source breach monitoring, dark-web reconnaissance and identity correlation — with a local AI co-analyst. Nothing leaves your machine.',
  });
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
  await page.waitForTimeout(BEAT);
  await chapterCard(page, {
    title: 'Operations Dashboard',
    line: 'Live severity, sources and tenant KPIs the moment you sign in — every number backed by a record you can drill into.',
  });
  await page.waitForTimeout(CLEAN_HOLD);
  await shot(page, '02-dashboard');

  for (const [label, name, title, line] of [
    ['Neural Topology', '03-topology',
      'Neural Topology',
      'Breach events correlated into an identity graph — masters, aliases and merges laid out as the network they really are.'],
    ['Master Identities', '04-identities',
      'Master Identities',
      'Every monitored identity with its breach history, risk score and VIP protection — evidence-merged, never guessed.'],
    ['Dark Recon Probe', '05-dark-recon',
      'Dark-Web Recon',
      'Live probes over a rotating Tor cluster — findings land in the same pipeline as every other source.'],
    ['Audit Logs', '06-audit',
      'Tamper-Evident Audit Ledger',
      'Every action hash-chained to the one before it. The chain verifies, or it tells you exactly where it broke.'],
    ['AI Co-Analyst', '07-ai-analyst',
      'Local AI Co-Analyst',
      'An agentic analyst with real tools — search, correlate, verify the ledger — on a local model. Zero data leaves the machine.'],
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
    await page.waitForTimeout(name.includes('topology') ? BEAT * 2 : BEAT);
    await chapterCard(page, { title, line });
    await page.waitForTimeout(CLEAN_HOLD);
    await shot(page, name);
  }

  console.log('· back to the dashboard, then reload — the session survives it');
  await page.getByRole('link', { name: 'Dashboard' }).first().click();
  await page.waitForTimeout(BEAT);
  await page.reload();
  await page.waitForTimeout(BEAT * 2);
  await shot(page, '08-after-reload');
  await chapterCard(page, {
    kicker: 'OPEN SOURCE',
    title: 'github.com/fabriziosalmi/naso',
    line: 'Self-hosted, multi-tenant, audit-grade. Star it, break it, tell us what we missed.',
  });
  await page.waitForTimeout(600);

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
