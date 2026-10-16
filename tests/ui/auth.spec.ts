import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const userId = 'a8888888-1111-4444-8888-222222222222';
const authOrigin = 'https://shortlist-auth.example';
const now = () => Math.floor(Date.now() / 1000);
function token(expiry: number, label = 'signin') {
  return `${Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url')}.${Buffer.from(JSON.stringify({ sub: userId, exp: expiry, role: 'authenticated', label })).toString('base64url')}.labelled-test-signature`;
}
function session(expiry = now() + 3600, label = 'signin') {
  return { access_token: token(expiry, label), token_type: 'bearer', expires_in: 3600, expires_at: expiry,
    refresh_token: 'labelled-test-refresh', user: { id: userId, aud: 'authenticated', role: 'authenticated',
      email: 'fixture@example.test', email_confirmed_at: '2026-10-14T00:00:00Z',
      app_metadata: {}, user_metadata: {}, identities: [], created_at: '2026-10-14T00:00:00Z' } };
}
async function fixture(page: Page, unconfirmed = false) {
  const calls: string[] = [];
  let rejectSignin = false;
  let rejectSignout = false;
  const mailRedirects: string[] = [];
  await page.route('**/api/auth/setup', route => route.fulfill({ json: { mode: 'hosted', supabase_url: authOrigin,
    publishable_key: 'sb_publishable_fixture', redirect_url: 'http://127.0.0.1:8015/' } }));
  await page.route(`${authOrigin}/auth/v1/**`, async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (['/signup', '/recover', '/resend'].some(path => url.pathname.endsWith(path))) mailRedirects.push(url.searchParams.get('redirect_to') ?? '');
    calls.push(url.pathname + url.search);
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' };
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    if (url.pathname.endsWith('/logout') && rejectSignout) return route.fulfill({ status: 400, headers,
      json: { code: 'labelled_failure', msg: 'Could not sign out. Please retry.' } });
    if (url.pathname.endsWith('/token')) {
      if (rejectSignin && url.searchParams.get('grant_type') === 'password') return route.fulfill({ status: 400, headers,
        json: { code: 'invalid_credentials', msg: 'Invalid login credentials' } });
      const signed = session(now() + 3600, url.searchParams.get('grant_type') ?? 'signin');
      return route.fulfill({ headers, json: unconfirmed ? { ...signed, user: { ...signed.user, email_confirmed_at: null } } : signed });
    }
    if (url.pathname.endsWith('/signup')) return route.fulfill({ headers, json: { user: session().user, session: null } });
    if (url.pathname.endsWith('/user')) return route.fulfill({ headers, json: session().user });
    return route.fulfill({ headers, json: {} });
  });
  return { calls, mailRedirects, reject: () => { rejectSignin = true; }, accept: () => { rejectSignin = false; },
    rejectSignout: () => { rejectSignout = true; }, acceptSignout: () => { rejectSignout = false; } };
}
async function signIn(page: Page) {
  await page.getByLabel('Email', { exact: true }).fill('fixture@example.test');
  await page.getByLabel('Password', { exact: true }).fill('labelled-fixture-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByLabel('Company name or website', { exact: true })).toBeVisible();
}
async function capture(page: Page, path: string) {
  mkdirSync('.impeccable/review', { recursive: true });
  await page.evaluate(async () => { await document.fonts.ready; });
  await page.screenshot({ path, fullPage: true });
}

async function checkPasswordHintFocus(page: Page, label: string, screenshot: string) {
  await page.getByLabel(label, { exact: true }).focus();
  const clearance = await page.getByLabel(label, { exact: true }).evaluate(input => {
    const hint = input.nextElementSibling;
    if (!(hint instanceof HTMLElement)) throw new Error('Password hint is missing');
    const style = getComputedStyle(input);
    return hint.getBoundingClientRect().top - input.getBoundingClientRect().bottom
      - parseFloat(style.outlineWidth) - parseFloat(style.outlineOffset);
  });
  expect(clearance).toBeGreaterThanOrEqual(4);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await capture(page, screenshot);
}

for (const failure of [
  { status: 503, contentType: 'text/html', body: '<!DOCTYPE html><title>Starting up</title>' },
  { status: 200, contentType: 'text/html', body: '<!DOCTYPE html><title>App shell</title>' },
  { status: 200, contentType: 'application/json', body: '{broken' },
]) {
  test(`account setup recovers from ${failure.status} ${failure.contentType}`, async ({ page }, info) => {
    await fixture(page);
    await page.route('**/api/auth/setup', route => route.fulfill(failure));
    await page.goto('/');
    await expect(page.getByRole('alert')).toContainText('We could not connect to the app service');
    await expect(page.getByRole('alert')).not.toContainText('Unexpected token');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await capture(page, `.impeccable/review/${info.project.name}-account-service-error.png`);
    await page.unroute('**/api/auth/setup');
    await fixture(page);
    await page.getByRole('button', { name: 'Retry account access' }).click();
    await expect(page.getByRole('heading', { name: 'Sign in to your shortlist' })).toBeVisible();
  });
}

test('signup confirmation, sign-in errors and password reset remain usable', async ({ page }, info) => {
  const backend = await fixture(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Sign in to your shortlist' })).toBeVisible();
  await capture(page, `.impeccable/review/${info.project.name}-signin.png`);
  await page.getByRole('button', { name: 'Create an account' }).click();
  await page.getByLabel('Email', { exact: true }).press('Tab');
  await expect(page.getByLabel('Password', { exact: true })).toBeFocused();
  await checkPasswordHintFocus(page, 'Password', `.impeccable/review/${info.project.name}-signup-focus.png`);
  await capture(page, `.impeccable/review/${info.project.name}-signup.png`);
  await page.getByLabel('Email', { exact: true }).fill('fixture@example.test');
  await page.getByLabel('Password', { exact: true }).fill('labelled-fixture-password');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('confirmation link');
  await expect(page.getByRole('heading', { name: 'Check your inbox' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create account', exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Password', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Resend confirmation email' }).click();
  await expect(page.getByRole('status')).toContainText('new confirmation link');
  await capture(page, `.impeccable/review/${info.project.name}-signup-confirmation.png`);
  await page.getByRole('button', { name: 'Use a different email', exact: true }).click();
  await expect(page.getByLabel('Email', { exact: true })).toHaveValue('fixture@example.test');
  await expect(page.getByLabel('Password', { exact: true })).toHaveValue('');
  await page.getByRole('button', { name: 'Back to sign in' }).click();
  backend.reject();
  await page.getByLabel('Password', { exact: true }).fill('labelled-fixture-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Invalid login credentials');
  await page.getByRole('button', { name: 'Forgot password?' }).click();
  await page.getByRole('button', { name: 'Send reset link' }).click();
  await expect(page.getByRole('status')).toContainText('If this email has an account');
  expect(backend.mailRedirects).toEqual(Array(3).fill('http://127.0.0.1:8015/'));
  await capture(page, `.impeccable/review/${info.project.name}-password-reset.png`);
  await page.setViewportSize({ width: 320, height: 740 });
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test('signed-in requests and exports carry tokens; sign-out clears the workspace', async ({ page }) => {
  await fixture(page);
  await page.goto('/');
  const requests: { url: string; bearer: string | undefined }[] = [];
  page.on('request', request => { if (request.url().includes('/api/') && !request.url().includes('/auth/setup'))
    requests.push({ url: request.url(), bearer: request.headers()['authorization'] }); });
  await signIn(page);
  await page.getByLabel('Company name or website', { exact: true }).fill('https://eygentic.com/');
  await page.getByRole('button', { name: 'Start research' }).click();
  await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible({ timeout: 15000 });
  const runId = new URL(page.url()).searchParams.get('run');
  expect(runId).toBeTruthy();
  await page.getByRole('button', { name: 'Confirm target and discover' }).click();
  await expect(page.getByRole('heading', { name: '2 companies researched' })).toBeVisible({ timeout: 15000 });
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Export JSON' }).click();
  await download;
  expect(requests.some(request => request.url.includes('/export?format=json'))).toBe(true);
  const excelDownload = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Export Excel' }).click();
  expect((await excelDownload).suggestedFilename()).toMatch(/\.xlsx$/);
  expect(requests.some(request => request.url.includes('/export?format=xlsx'))).toBe(true);
  expect(requests.length).toBeGreaterThan(2);
  expect(requests.every(request => request.bearer?.startsWith('Bearer '))).toBe(true);
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to your shortlist' })).toBeVisible();
  await expect(page.getByRole('complementary', { name: 'Saved research' })).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Sign in to your shortlist' })).toBeVisible();
});

test('expired stored session refreshes and API rejection returns to sign-in', async ({ page }) => {
  const backend = await fixture(page);
  await page.addInitScript(expired => localStorage.setItem('sb-shortlist-auth-auth-token', JSON.stringify(expired)), session(now() - 60));
  await page.goto('/');
  await expect(page.getByLabel('Company name or website', { exact: true })).toBeVisible();
  expect(backend.calls.some(call => call.includes('grant_type=refresh_token'))).toBe(true);
  await page.route('**/api/runs', route => route.fulfill({ status: 401, json: { detail: 'Labelled expired session' } }));
  // The rejected in-flight read may already have removed the workspace. Reload
  // exercises the same verified-session rejection without clicking stale UI.
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Sign in to your shortlist' })).toBeVisible();
  await expect(page.getByRole('status')).toContainText('session needs verification');
});

test('PKCE recovery opens a new-password form and updates the account', async ({ page }, info) => {
  const backend = await fixture(page);
  await page.addInitScript(() => localStorage.setItem('sb-shortlist-auth-auth-token-code-verifier', JSON.stringify('labelled-verifier/recovery')));
  await page.goto('/?code=labelled-recovery-code');
  await expect(page.getByRole('heading', { name: 'Choose a new password' })).toBeVisible();
  await checkPasswordHintFocus(page, 'New password', `.impeccable/review/${info.project.name}-recovery-focus.png`);
  await capture(page, `.impeccable/review/${info.project.name}-new-password.png`);
  await page.getByLabel('New password', { exact: true }).fill('updated-fixture-password');
  await page.getByRole('button', { name: 'Save new password' }).click();
  await expect(page.getByLabel('Company name or website', { exact: true })).toBeVisible();
  expect(backend.calls.some(call => call.includes('grant_type=pkce'))).toBe(true);
  expect(backend.calls.some(call => call.endsWith('/user'))).toBe(true);
});

test('unconfirmed account can retry failed sign-out without entering research', async ({ page }) => {
  const backend = await fixture(page, true);
  await page.goto('/');
  await page.getByLabel('Email', { exact: true }).fill('fixture@example.test');
  await page.getByLabel('Password', { exact: true }).fill('labelled-fixture-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Confirm your email' })).toBeVisible();
  await expect(page.getByLabel('Company name or website', { exact: true })).toHaveCount(0);
  backend.rejectSignout();
  await page.getByRole('button', { name: 'Back to sign in' }).click();
  await expect(page.getByRole('alert')).toContainText('Could not sign out');
  // Current SDK removes the local session even when server revocation fails.
  await expect(page.getByRole('heading', { name: 'Sign in to your shortlist' })).toBeVisible();
  backend.acceptSignout();
  await page.getByLabel('Email', { exact: true }).fill('fixture@example.test');
  await page.getByLabel('Password', { exact: true }).fill('labelled-fixture-password');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Confirm your email' })).toBeVisible();
  await page.getByRole('button', { name: 'Back to sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Sign in to your shortlist' })).toBeVisible();
});
