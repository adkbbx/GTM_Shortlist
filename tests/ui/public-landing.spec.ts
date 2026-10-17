import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const authOrigin = 'https://shortlist-auth.example';
const userId = 'b9999999-1111-4444-8888-333333333333';

/** Hosted mode with a labelled fake auth service; the research API stays the local fixture server. */
async function hosted(page: Page) {
  const expiry = Math.floor(Date.now() / 1000) + 3600;
  const token = `${Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url')}.${Buffer.from(JSON.stringify({ sub: userId, exp: expiry, role: 'authenticated' })).toString('base64url')}.labelled-landing-fixture`;
  await page.route('**/api/auth/setup', route => route.fulfill({ json: { mode: 'hosted', supabase_url: authOrigin, publishable_key: 'sb_publishable_fixture', redirect_url: 'http://127.0.0.1:8015/' } }));
  await page.route(`${authOrigin}/auth/v1/**`, route => {
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' };
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    return route.fulfill({ headers, json: { access_token: token, token_type: 'bearer', expires_in: 3600, expires_at: expiry, refresh_token: 'labelled-refresh',
      user: { id: userId, aud: 'authenticated', role: 'authenticated', email: 'landing@example.test', email_confirmed_at: '2026-10-14T00:00:00Z', app_metadata: {}, user_metadata: {}, identities: [], created_at: '2026-10-14T00:00:00Z' } } });
  });
  await page.route('**/api/runs', route => route.request().method() === 'GET' ? route.fulfill({ json: [] }) : route.fallback());
}
async function capture(page: Page, path: string) {
  mkdirSync('.impeccable/review', { recursive: true });
  await page.evaluate(async () => { await document.fonts.ready; });
  await page.screenshot({ path });
}

test('anonymous hosted visitors get the landing page, and the research they started begins once they sign in', async ({ page }, info) => {
  await hosted(page);
  const research: string[] = [];
  page.on('request', request => { const path = new URL(request.url()).pathname; if (path.startsWith('/api/') && path !== '/api/auth/setup') research.push(`${request.method()} ${path}`); });
  await page.goto('/');
  await expect(page.locator('#pl-hero-title')).toContainText('Find who fits.');
  await expect(page.getByRole('region', { name: 'Illustrative sample shortlist' })).toBeVisible();
  await page.waitForTimeout(2500);
  await capture(page, `.impeccable/review/${info.project.name}-public-landing.png`);
  expect(research).toEqual([]);

  await page.getByLabel('Start with your company', { exact: true }).fill('acme-analytics.example');
  await expect(page.locator('.pl-g-sub').first()).toHaveText('Fits acme-analytics.example');
  await page.getByLabel('Start with your company', { exact: true }).press('Enter');
  await expect(page).toHaveURL(/\?auth=signup$/);
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('Research for acme-analytics.example starts as soon as you confirm your email and sign in');
  expect(research).toEqual([]);

  await page.getByRole('button', { name: 'Back to sign in' }).click();
  await page.getByLabel('Email', { exact: true }).fill('landing@example.test');
  await page.getByLabel('Password', { exact: true }).fill('labelled-fixture-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  // No second Start research: the press on the landing page starts exactly one run after sign-in.
  await expect(page).toHaveURL(/\?run=/);
  await expect(page.getByLabel('Company name or website', { exact: true })).toHaveCount(0);
  expect(research.filter(call => call === 'POST /api/sellers')).toHaveLength(1);
});

test('an email code signs a landing visitor in on the same tab and their research starts once', async ({ page }, info) => {
  await hosted(page);
  // Both optional methods switched on, as the operator would after configuring Supabase.
  await page.route('**/api/auth/setup', route => route.fulfill({ json: { mode: 'hosted', supabase_url: authOrigin, publishable_key: 'sb_publishable_fixture', redirect_url: 'http://127.0.0.1:8015/', email_code: true, google: true } }));
  const auth: string[] = [];
  page.on('request', request => { const url = new URL(request.url()); if (url.origin === authOrigin) auth.push(url.pathname + url.search); });
  const starts: string[] = [];
  page.on('request', request => { if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/sellers') starts.push(request.url()); });
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Start with your company' }).fill('https://eygentic.com/');
  await page.getByRole('combobox', { name: 'Start with your company' }).press('Enter');
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeVisible();
  await expect(page.getByLabel('Password', { exact: true })).toHaveCount(0);
  await page.getByLabel('Email', { exact: true }).fill('landing@example.test');
  await page.getByRole('button', { name: 'Email me a sign-in code' }).click();
  await expect(page.getByLabel('6-digit code')).toBeFocused();
  expect(auth.some(call => call.startsWith('/auth/v1/otp'))).toBe(true);
  await capture(page, `.impeccable/review/${info.project.name}-email-code.png`);
  await page.getByLabel('6-digit code').fill('12a34 56');
  await expect(page.getByLabel('6-digit code')).toHaveValue('123456');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\?run=/);
  expect(auth.some(call => call.startsWith('/auth/v1/verify'))).toBe(true);
  expect(starts).toHaveLength(1);
});

test('Google sign-in goes to the provider, and a password stays available', async ({ page }) => {
  await hosted(page);
  await page.route('**/api/auth/setup', route => route.fulfill({ json: { mode: 'hosted', supabase_url: authOrigin, publishable_key: 'sb_publishable_fixture', redirect_url: 'http://127.0.0.1:8015/', email_code: true, google: true } }));
  await page.goto('/?auth=signin');
  await page.getByRole('button', { name: 'Use a password instead' }).click();
  await expect(page.getByLabel('Password', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Email me a code instead' }).click();
  await expect(page.getByLabel('Password', { exact: true })).toHaveCount(0);
  const authorize = page.waitForRequest(request => request.url().startsWith(`${authOrigin}/auth/v1/authorize`));
  await page.getByRole('button', { name: 'Continue with Google' }).click();
  expect(new URL((await authorize).url()).searchParams.get('provider')).toBe('google');
});

test('the local landing preview starts research in one press and opens the run', async ({ page }) => {
  await page.route('**/api/runs', route => route.request().method() === 'GET' ? route.fulfill({ json: [] }) : route.fallback());
  const starts: string[] = [];
  page.on('request', request => { if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/sellers') starts.push(request.url()); });
  await page.goto('/?landing=1');
  await page.getByRole('combobox', { name: 'Start with your company' }).fill('https://eygentic.com/');
  await page.getByRole('button', { name: 'Start research', exact: true }).first().click();
  await expect(page).toHaveURL(/\?run=/);
  expect(starts).toHaveLength(1);
  await expect(page.locator('#pl-hero-title')).toHaveCount(0);
});

test('header sign-in opens the account form and browser back returns to the landing page', async ({ page }) => {
  await hosted(page);
  await page.goto('/');
  await page.getByRole('banner').getByRole('link', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to your shortlist' })).toBeVisible();
  await expect(page).toHaveURL(/\?auth=signin$/);
  await page.goBack();
  await expect(page.locator('#pl-hero-title')).toBeVisible();
  // An empty submit keeps the visitor on the page and puts the cursor in the field.
  await page.getByRole('button', { name: 'Start research', exact: true }).first().click();
  await expect(page.getByLabel('Start with your company', { exact: true })).toBeFocused();
  await expect(page).not.toHaveURL(/auth=/);
});

test('the landing field offers Brandfetch company suggestions when the installation configures a public ID', async ({ page }) => {
  await hosted(page);
  await page.route('**/favicon.ico', route => route.abort());
  await page.route('https://cdn.brandfetch.io/**', route => route.abort());
  const lookups: string[] = [];
  await page.route('https://api.brandfetch.io/**', route => {
    lookups.push(new URL(route.request().url()).pathname);
    return route.fulfill({ json: [{ name: 'Clay (synthetic)', domain: 'clay.example' }, { name: 'Clay Studio (synthetic)', domain: 'clay-studio.example' }] });
  });
  // Runtime public configuration, as the server injects it, keeps this independent of a developer's ID.
  await page.route('http://127.0.0.1:8015/', async route => {
    const response = await route.fetch();
    await route.fulfill({ response, body: (await response.text()).replace('<head>', '<head><meta name="shortlist-company-suggestions-client-id" content="synthetic-public-client-id">') });
  });
  const research: string[] = [];
  page.on('request', request => { const path = new URL(request.url()).pathname; if (path.startsWith('/api/') && path !== '/api/auth/setup') research.push(path); });
  await page.goto('/');
  const field = page.getByRole('combobox', { name: 'Start with your company' });
  await field.fill('clay');
  await expect(page.getByRole('option')).toHaveCount(2);
  expect(lookups.at(-1)).toBe('/v2/search/clay');
  // Keyboard selection: scrolling to reach an option would close the list, as comboboxes do.
  await field.press('ArrowDown');
  await field.press('Enter');
  await expect(field).toHaveValue('clay.example');
  await expect(page.locator('.pl-g-sub').first()).toHaveText('Fits clay.example');
  expect(research).toEqual([]);
});

test('a saved-run link without a session opens sign-in, not the public landing page', async ({ page }) => {
  await hosted(page);
  await page.goto('/?run=labelled-saved-run');
  await expect(page.getByRole('heading', { name: 'Sign in to your shortlist' })).toBeVisible();
  await expect(page.locator('#pl-hero-title')).toHaveCount(0);
});

test('the pinned story steps forward and back from its stepper', async ({ page }, info) => {
  await hosted(page);
  await page.goto('/');
  await page.getByRole('button', { name: 'Step 4: Companies' }).click();
  await expect(page.getByRole('heading', { name: 'Discover companies' })).toBeVisible({ timeout: 6000 });
  await expect(page.getByRole('button', { name: 'Step 4: Companies' })).toHaveAttribute('aria-current', 'step');
  await page.getByRole('button', { name: 'Step 2: Market' }).click();
  await expect(page.getByRole('heading', { name: 'Explore the market' })).toBeVisible({ timeout: 6000 });
  await expect(page.getByRole('heading', { name: 'Discover companies' })).toBeHidden();
  const clipped = await page.evaluate(() => {
    const stage = document.querySelector('.pl-story-stage')?.getBoundingClientRect(), active = document.querySelector('.pl-stage.active')?.getBoundingClientRect();
    return !stage || !active ? 'missing' : active.bottom - stage.bottom;
  });
  expect(typeof clipped === 'number' && clipped <= 1).toBe(true);
  await capture(page, `.impeccable/review/${info.project.name}-landing-story.png`);
});

test('reduced motion shows the whole story statically without smooth scrolling or overflow', async ({ page }, info) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await hosted(page);
  await page.goto('/');
  await expect(page.locator('#pl-hero-title')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.classList.contains('lenis'))).toBe(false);
  for (const heading of ['Understand your offer', 'Explore the market', 'Confirm the target', 'Discover companies', 'Inspect the evidence', 'Make the call'])
    await expect(page.getByRole('heading', { name: heading })).toBeVisible();
  await expect(page.getByText('Confirmed by you', { exact: true })).toBeVisible();
  await expect(page.getByText('Accepted by you', { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 320, height: 740 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.setViewportSize(info.project.use.viewport ?? { width: 390, height: 844 });
});
