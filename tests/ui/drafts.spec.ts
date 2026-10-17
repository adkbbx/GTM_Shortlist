import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { hosted } from './hosted';

// Drafts before signup, switched on by the operator. Turnstile and the draft endpoints are labelled stand-ins: the
// browser check passes at once, and the "worker" finishes the draft on the third read.
const draftId = '0f4e2b8a-1c3d-4e5f-8a9b-0c1d2e3f4a5b';
const claimToken = 'labelled-claim-token-for-this-browser-only';

async function switchedOn(page: Page) {
  await hosted(page, { email_code: true, draft_site_key: '0x4AAAAAAAlabelled' });
  await page.route('https://challenges.cloudflare.com/turnstile/v0/api.js**', route => route.fulfill({ contentType: 'text/javascript',
    body: 'window.turnstile = { render(host, options) { setTimeout(() => options.callback("labelled-turnstile-token"), 50); return "labelled-widget"; }, remove() {} };' }));
}

const events = [
  { label: 'Saved the page from eygentic.com', state: 'succeeded', created_at: '2026-10-18T10:00:01+00:00' },
  { label: 'Drafting what you sell, who to look for and fit checks', state: 'started', created_at: '2026-10-18T10:00:02+00:00' },
];
const draft = { offer: 'Labelled draft: onboarding reviews for B2B software teams', target: 'B2B software companies with a customer onboarding process',
  criteria: [{ id: 'software', description: 'Sells software to business customers', required: true }], unknowns: [] };

test('a website drafts live before signup, and that draft becomes the first run after sign-in', async ({ page }, info) => {
  await switchedOn(page);
  const calls: string[] = [];
  page.on('request', request => { const path = new URL(request.url()).pathname; if (path.startsWith('/api/') && path !== '/api/auth/setup') calls.push(`${request.method()} ${path}`); });
  let started: { website?: string; browser_id?: string; turnstile_token?: string } = {};
  await page.route('**/api/drafts', route => { started = route.request().postDataJSON(); return route.fulfill({ status: 201, json: { id: draftId, claim_token: claimToken } }); });
  let reads = 0;
  await page.route(`**/api/drafts/${draftId}`, route => {
    expect(route.request().headers()['x-draft-claim']).toBe(claimToken);
    reads += 1;
    return route.fulfill({ json: reads < 3 ? { status: 'running', website: 'https://eygentic.com/', events: events.slice(0, reads) }
      : { status: 'ready', website: 'https://eygentic.com/', draft, events: [...events.slice(0, 1), { ...events[1], state: 'succeeded', label: 'Drafted your offer, target and fit checks' }] } });
  });
  let claims = 0;
  await page.route(`**/api/drafts/${draftId}/claim`, async route => {
    expect(route.request().headers()['x-draft-claim']).toBe(claimToken);
    claims += 1;
    if (claims === 1) return route.fulfill({ status: 409, json: { detail: 'Your draft is still being written. Try again in a moment' } });
    // The claimed run, created on the labelled fixture server as the hosted API would from the saved draft.
    return route.fulfill({ response: await page.request.post('/api/sellers', { data: { seller_url: 'https://eygentic.com/', request_key: `labelled-claim-${Date.now()}`, experience_version: 2 } }) });
  });

  await page.goto('/');
  await page.getByRole('combobox', { name: 'Start with your company' }).fill('eygentic.com');
  await page.getByRole('combobox', { name: 'Start with your company' }).press('Enter');
  await expect(page).toHaveURL(/\?draft=1$/);
  await expect(page.getByRole('list', { name: 'Draft progress' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Here is what we understood' })).toBeVisible();
  await expect(page.locator('.draft-result')).toContainText('onboarding reviews for B2B software teams');
  await expect(page.locator('.draft-result')).toContainText('Sells software to business customers');
  expect(started.website).toBe('eygentic.com');
  expect(started.turnstile_token).toBe('labelled-turnstile-token');
  expect(started.browser_id).toMatch(/^[0-9a-f-]{36}$/);
  expect(calls.filter(call => !call.includes('/api/drafts'))).toEqual([]);  // Nothing but the draft before signup.
  mkdirSync('.impeccable/review', { recursive: true });
  await page.evaluate(async () => { await document.fonts.ready; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-draft-ready.png`, fullPage: true });

  await page.getByRole('button', { name: 'Save and find companies' }).click();
  await expect(page).toHaveURL(/\?auth=signup$/);
  await expect(page.getByRole('status')).toContainText('Your draft for eygentic.com is saved in this browser');
  await page.getByLabel('Email', { exact: true }).fill('landing@example.test');
  await page.getByRole('button', { name: 'Email me a sign-in code' }).click();
  await page.getByLabel('6-digit code').fill('123456');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\?run=/, { timeout: 15_000 });
  expect(claims).toBe(2);  // Waited while the draft was still being written, then claimed it once.
  expect(calls.filter(call => call === 'POST /api/sellers')).toEqual([]);  // No second page read or model call.
  expect(await page.evaluate(() => localStorage.getItem('shortlist-landing-draft'))).toBeNull();
});

test('a company name, or a refused draft, goes straight to sign-up as before', async ({ page }) => {
  await switchedOn(page);
  const drafts: string[] = [];
  await page.route('**/api/drafts', route => { drafts.push(route.request().url()); return route.fulfill({ status: 429, json: { detail: 'You have already drafted a company today. Sign in to keep going' } }); });
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Start with your company' }).fill('Eygentic');
  await page.getByRole('combobox', { name: 'Start with your company' }).press('Enter');
  await expect(page).toHaveURL(/\?auth=signup$/);
  expect(drafts).toEqual([]);  // Looking up a company name is a search, which waits for an account.

  await page.goBack();
  await page.getByRole('combobox', { name: 'Start with your company' }).fill('eygentic.com');
  await page.getByRole('combobox', { name: 'Start with your company' }).press('Enter');
  await expect(page.getByRole('heading', { name: 'Your draft needs an account' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('already drafted a company today');
  await page.getByRole('button', { name: 'Create your free account' }).click();
  await expect(page).toHaveURL(/\?auth=signup$/);
  await expect(page.getByRole('status')).toContainText('Research for eygentic.com starts as soon as you');
});
