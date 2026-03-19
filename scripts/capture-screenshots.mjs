#!/usr/bin/env node
/**
 * Capture dashboard screenshots using Playwright.
 *
 * Prerequisites:
 *   1. Backend running on http://localhost:8000
 *   2. Dashboard running on http://localhost:3000
 *   3. npx playwright install chromium
 *
 * Usage:
 *   node scripts/capture-screenshots.mjs
 */

import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, '..', 'docs', 'images');

const API = 'http://localhost:8000';
const DASHBOARD = 'http://localhost:3000';

// ── helpers ──────────────────────────────────────────────────────────

async function apiPost(path, body = {}, token = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    console.warn(`  POST ${path} → ${res.status}: ${text.slice(0, 200)}`);
  }
  return res;
}

async function apiPut(path, body = {}, token = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(body),
  });
  return res;
}

async function apiGet(path, token = null) {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { headers });
  return res;
}

// ── main ─────────────────────────────────────────────────────────────

async function main() {
  if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

  // 1. Login
  console.log('→ Logging in…');
  const loginRes = await apiPost('/api/v1/auth/login', {
    email: 'admin@example.com',
    password: 'admin123',
  });
  const { access_token: token } = await loginRes.json();
  console.log('  ✓ Got JWT token');

  // 2. Dismiss onboarding wizard
  console.log('→ Dismissing onboarding wizard…');
  await apiPut(
    '/api/v1/auth/me',
    { preferences: { onboarding_completed: true } },
    token
  );
  console.log('  ✓ Onboarding marked complete');

  // 3. Seed data
  console.log('→ Seeding data…');
  await apiPost('/api/v1/seed/integrations', {}, token);
  console.log('  ✓ Integrations seeded');
  await apiPost('/api/v1/seed/marketplace-agents', {}, token);
  console.log('  ✓ Marketplace agents seeded');
  await apiPost('/api/v1/seed/workflows', {}, token);
  console.log('  ✓ Workflows seeded');

  // 4. Get a seeded workflow ID for the designer page
  console.log('→ Fetching workflow list…');
  const wfRes = await apiGet('/api/workflows', token);
  const wfData = await wfRes.json();
  const workflows = wfData.workflows || wfData.items || wfData;
  const firstWorkflow = Array.isArray(workflows) ? workflows[0] : null;
  const workflowId = firstWorkflow?.id;
  console.log(`  ✓ Using workflow: ${firstWorkflow?.name || 'none'} (${workflowId})`);

  // 5. Launch browser
  console.log('→ Launching Chromium…');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    deviceScaleFactor: 2,
    colorScheme: 'light',
  });
  const page = await context.newPage();

  // Set auth token in localStorage before navigating
  await page.goto(DASHBOARD, { waitUntil: 'domcontentloaded' });
  await page.evaluate((t) => {
    localStorage.setItem('auth_token', t);
  }, token);

  // Screenshot definitions
  const screenshots = [
    {
      name: 'dashboard-overview',
      route: '/dashboard',
      waitFor: '.recharts-wrapper, [class*="metric"], [class*="card"]',
      description: 'Dashboard Overview',
    },
    {
      name: 'workflow-designer',
      route: workflowId
        ? `/workflows/builder?id=${workflowId}`
        : '/workflows/builder',
      waitFor: '.react-flow__nodes, .react-flow, [class*="react-flow"]',
      description: 'Workflow Designer',
    },
    {
      name: 'integrations',
      route: '/integrations',
      waitFor: '[class*="card"], [class*="grid"], [class*="integration"]',
      description: 'Integrations',
    },
    {
      name: 'marketplace',
      route: '/marketplace',
      waitFor: '[class*="card"], [class*="agent"], [class*="grid"]',
      description: 'Agent Marketplace',
    },
    {
      name: 'cost-management',
      route: '/costs',
      waitFor: '.recharts-wrapper, [class*="chart"], [class*="cost"]',
      description: 'Cost Management',
    },
  ];

  // 6. Capture each screenshot
  for (const ss of screenshots) {
    console.log(`→ Capturing: ${ss.description} (${ss.route})…`);
    await page.goto(`${DASHBOARD}${ss.route}`, {
      waitUntil: 'networkidle',
      timeout: 15000,
    });

    // Wait for key elements to render
    try {
      await page.waitForSelector(ss.waitFor, { timeout: 8000 });
    } catch {
      console.warn(`  ⚠ Selector "${ss.waitFor}" not found, taking screenshot anyway`);
    }

    // Extra buffer for animations/transitions
    await page.waitForTimeout(2000);

    const outPath = join(OUT_DIR, `${ss.name}.png`);
    await page.screenshot({ path: outPath, fullPage: false });

    // Check file size
    const { size } = await import('fs').then((fs) =>
      fs.promises.stat(outPath)
    );
    const sizeKB = Math.round(size / 1024);
    console.log(`  ✓ Saved ${ss.name}.png (${sizeKB} KB)`);
  }

  await browser.close();
  console.log(`\n✓ All screenshots saved to ${OUT_DIR}`);
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
