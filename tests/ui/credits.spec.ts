import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { mkdirSync, readFileSync } from 'node:fs';

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: 'wait' });
});

async function hostedFixture(page: Page) {
  const identity = randomUUID();
  const expiry = Math.floor(Date.now() / 1000) + 3600;
  const token = `${Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url')}.${Buffer.from(JSON.stringify({ sub: identity, exp: expiry, role: 'authenticated' })).toString('base64url')}.labelled-credit-fixture`;
  await page.route('https://app.example/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname + new URL(request.url()).search;
    const response = await page.request.fetch('http://127.0.0.1:8016' + path, {
      method: request.method(), data: request.postDataBuffer() ?? undefined,
      headers: { ...request.headers(), host: 'app.example', origin: 'https://app.example' },
    });
    await route.fulfill({ response });
  });
  await page.route('https://shortlist-auth.example/auth/v1/**', route => route.fulfill({
    headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*' },
    json: { access_token: token, token_type: 'bearer', refresh_token: 'labelled-refresh', expires_in: 3600, expires_at: expiry,
      user: { id: identity, aud: 'authenticated', role: 'authenticated', email: 'credits@example.test',
        email_confirmed_at: '2026-10-14T00:00:00Z', app_metadata: {}, user_metadata: {}, identities: [], created_at: '2026-10-14T00:00:00Z' } },
  }));
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill('credits@example.test');
  await page.getByLabel('Password', { exact: true }).fill('labelled-fixture-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByLabel('Seller website', { exact: true })).toBeVisible();
}
async function capture(page: Page, path: string) {
  mkdirSync('.impeccable/review', { recursive: true });
  await page.evaluate(async () => { await document.fonts.ready; });
  await page.evaluate(async () => {
    window.scrollTo(0, 0);
    await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
  });
  await page.screenshot({ path, fullPage: true });
}

test('real hosted API and Postgres settle partial research; review/export are free', async ({ page }, info) => {
  await hostedFixture(page);
  await expect(page.getByText('3 credits available', { exact: true })).toBeVisible();
  await page.getByLabel('Seller website', { exact: true }).fill('https://eygentic.com/');
  await page.getByRole('button', { name: 'Understand my offer' }).click();
  await expect(page.getByLabel('Companies in this batch')).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('Maximum 3 credits · 3 available')).toBeVisible();
  await capture(page, `.impeccable/review/${info.project.name}-credit-confirmation.png`);
  await page.getByRole('button', { name: 'Confirm target and discover' }).click();
  await expect(page.getByRole('heading', { name: '2 companies researched' })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('1 credit used · 0 reserved · 2 returned')).toBeVisible();
  await expect(page.getByText('2 credits available', { exact: true })).toBeVisible();
  await expect(page.getByText('1 research credit used')).toHaveCount(1);
  await expect(page.getByText('No research credit charged')).toHaveCount(1);
  await page.getByRole('button', { name: 'Accept company', exact: true }).first().click();
  await expect(page.getByText('Saved: accepted')).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Export JSON' }).click();
  const downloaded = await download;
  const path = await downloaded.path();
  expect(path).toBeTruthy();
  const exported = JSON.parse(readFileSync(path!, 'utf8'));
  expect(exported.records.map((record: { credits_used: number }) => record.credits_used)).toEqual([1, 0]);
  await page.reload();
  await expect(page.getByText('2 credits available', { exact: true })).toBeVisible();
  await expect(page.getByText('Saved: accepted')).toBeVisible();
  await capture(page, `.impeccable/review/${info.project.name}-credit-results.png`);
});

test('selected batch size sets the actual worker limit and quoted cost', async ({ page }) => {
  await hostedFixture(page);
  await page.getByLabel('Seller website', { exact: true }).fill('https://eygentic.com/');
  await page.getByRole('button', { name: 'Understand my offer' }).click();
  await expect(page.getByLabel('Companies in this batch')).toBeVisible({ timeout: 15000 });
  await page.getByLabel('Companies in this batch').selectOption('1');
  await expect(page.getByText('Maximum 1 credit · 3 available')).toBeVisible();
  await page.getByRole('button', { name: 'Confirm target and discover' }).click();
  await expect(page.getByRole('heading', { name: '1 company researched' })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('1 credit used · 0 reserved · 0 returned')).toBeVisible();
  await expect(page.getByText('2 credits available', { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 320, height: 740 });
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  const layout = await page.evaluate(() => ({ width: window.innerWidth, scroll: document.documentElement.scrollWidth,
    outside: [...document.querySelectorAll('body *')].filter(element => !element.closest('.sidebar') && element.getBoundingClientRect().right > window.innerWidth + 1)
      .map(element => `${element.tagName}.${element.className}`).slice(0, 12),
  }));
  expect(layout.scroll, JSON.stringify(layout)).toBeLessThanOrEqual(layout.width + 1);
});

test('deletion has explicit confirmation, retry recovery and unchanged credits', async ({ page }, info) => {
  const originalViewport = page.viewportSize();
  await hostedFixture(page);
  await page.getByLabel('Seller website', { exact: true }).fill('https://eygentic.com/');
  await page.getByRole('button', { name: 'Understand my offer' }).click();
  await expect(page.getByLabel('Companies in this batch')).toBeVisible({ timeout: 15000 });
  await page.getByLabel('Companies in this batch').selectOption('1');
  await page.getByRole('button', { name: 'Confirm target and discover' }).click();
  await expect(page.getByRole('heading', { name: '1 company researched' })).toBeVisible({ timeout: 15000 });
  const runId = new URL(page.url()).searchParams.get('run');
  expect(runId).toBeTruthy();
  await page.getByRole('button', { name: 'Delete saved research' }).click();
  await expect(page.getByRole('button', { name: 'Keep research' })).toBeFocused();
  await page.getByRole('button', { name: 'Keep research' }).click();
  await expect(page.getByRole('heading', { name: '1 company researched' })).toBeVisible();
  await page.getByRole('button', { name: 'Delete saved research' }).click();
  await capture(page, `.impeccable/review/${info.project.name}-delete-confirmation.png`);
  await page.setViewportSize({ width: 320, height: 740 });
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  const enlarged = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
  expect(enlarged.scroll).toBeLessThanOrEqual(enlarged.width + 1);
  await page.evaluate(() => { document.documentElement.style.fontSize = ''; });
  if (originalViewport) await page.setViewportSize(originalViewport);
  // A failed mutation keeps research visible and offers a retry.
  await page.route(`https://app.example/api/runs/${runId}`, async route => {
    if (route.request().method() === 'DELETE') await route.fulfill({ status: 503, json: { detail: 'Deletion unavailable. Try again.' } });
    else await route.fallback();
  });
  await page.getByRole('button', { name: 'Delete permanently' }).click();
  await expect(page.getByRole('alert')).toHaveText('Deletion unavailable. Try again.');
  await expect(page.getByRole('heading', { name: '1 company researched' })).toBeVisible();
  await page.unroute(`https://app.example/api/runs/${runId}`);
  await page.getByRole('button', { name: 'Delete permanently' }).click();
  await expect(page.getByText('Saved research deleted. Your credit balance is unchanged.')).toBeVisible();
  await expect(page.getByText('2 credits available', { exact: true })).toBeVisible();
  expect(new URL(page.url()).searchParams.has('run')).toBe(false);
  await expect(page.getByText('Your research will stay here after you close the browser.')).toHaveCount(1);
  await expect(page.locator('.saved-run')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Understand my offer' })).toBeEnabled();
  await capture(page, `.impeccable/review/${info.project.name}-deleted-workspace.png`);
  await page.reload();
  await expect(page.getByLabel('Seller website', { exact: true })).toBeVisible();
  await expect(page.getByText('2 credits available', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '1 company researched' })).toHaveCount(0);
  await page.goto(`/?run=${runId}`);
  await expect(page.getByLabel('Seller website', { exact: true })).toBeVisible();
  await expect(page.getByText('Loading saved research…')).toHaveCount(0);
});

test('optional setup call opens a clean external link; click is not a booked appointment', async ({ page }, info) => {
  await hostedFixture(page);
  await page.getByLabel('Seller website', { exact: true }).fill('https://eygentic.com/');
  await page.getByRole('button', { name: 'Understand my offer' }).click();
  await expect(page.getByLabel('Companies in this batch')).toBeVisible({ timeout: 15000 });
  await page.getByLabel('Companies in this batch').selectOption('1');
  await page.getByRole('button', { name: 'Confirm target and discover' }).click();
  await expect(page.getByRole('heading', { name: '1 company researched' })).toBeVisible({ timeout: 15000 });
  const link = page.getByRole('link', { name: 'Book an optional setup call' });
  await expect(link).toHaveAttribute('href', 'https://cal.example/eygentic/setup-fixture');
  await capture(page, `.impeccable/review/${info.project.name}-optional-setup.png`);
  await page.context().route('https://cal.example/**', async route => {
    expect(route.request().headers().referer).toBeUndefined();
    await route.fulfill({ contentType: 'text/html', body: '<h1>Labelled external booking fixture</h1>' });
  });
  const clicked = page.waitForResponse(response => response.url().endsWith('/booking-click') && response.status() === 204);
  const popupPromise = page.waitForEvent('popup');
  await link.click();
  const popup = await popupPromise;
  await expect(popup.getByRole('heading', { name: 'Labelled external booking fixture' })).toBeVisible();
  expect(popup.url()).toBe('https://cal.example/eygentic/setup-fixture');
  await clicked;
  await expect(page.getByText('2 credits available', { exact: true })).toBeVisible();
  await expect(page.getByText('Call booked', { exact: true })).toHaveCount(0);
  await popup.close();
  let tracked = 0;
  page.on('request', request => { if (request.url().endsWith('/booking-click')) tracked++; });
  await page.evaluate(() => Object.defineProperty(navigator, 'doNotTrack', { value: '1', configurable: true }));
  const privatePopup = page.waitForEvent('popup');
  await link.click();
  const untracked = await privatePopup;
  await expect(untracked.getByRole('heading', { name: 'Labelled external booking fixture' })).toBeVisible();
  expect(tracked).toBe(0);
  await untracked.close();
  await page.context().unrouteAll({ behavior: 'wait' });
});
