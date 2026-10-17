import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { installIconFixtures, syntheticIcon } from './site-icons';

const companies = [
  { name: 'Clay (synthetic)', domain: 'clay.example', icon: 'https://cdn.brandfetch.io/synthetic-clay.svg' },
  { name: 'Clay Studio (synthetic)', domain: 'clay-studio.example', icon: 'https://cdn.brandfetch.io/synthetic-studio.svg' },
  { name: 'Clay Homes (synthetic)', domain: 'clay-homes.example', icon: 'https://cdn.brandfetch.io/synthetic-homes.svg' },
];

test.beforeEach(async ({ page }) => {
  await page.route('**/favicon.ico', route => route.abort());
  await page.route('https://cdn.brandfetch.io/**', route => route.abort());
  await installIconFixtures(page, {
    'https://cdn.brandfetch.io/synthetic-clay.svg': syntheticIcon('#b4501c'),
    'https://cdn.brandfetch.io/synthetic-studio.svg': syntheticIcon('#245c8a'),
    'https://cdn.brandfetch.io/synthetic-homes.svg': null,
  });
  await page.route('https://api.brandfetch.io/**', route => route.abort());
  await page.route('**/api/runs', route => route.fulfill({ json: [] }));
  // Runtime public configuration keeps this suite independent of a developer's ID.
  await page.route('http://127.0.0.1:8015/', async route => {
    const response = await route.fetch();
    await route.fulfill({ response, body: (await response.text()).replace('<head>', '<head><meta name="shortlist-company-suggestions-client-id" content="synthetic-public-client-id">') });
  });
});

test('new company suggestions support keyboard selection and responsive layouts without research', async ({ page }, info) => {
  const lookups: string[] = [];
  const mutations: string[] = [];
  page.on('request', request => { if (request.method() === 'POST' && request.url().includes('/api/')) mutations.push(request.url()); });
  await page.route('https://api.brandfetch.io/**', route => {
    lookups.push(new URL(route.request().url()).pathname);
    return route.fulfill({ json: [...companies, companies[0], { name: 'Unsafe synthetic item', domain: 'localhost:8019' }] });
  });
  await page.goto('/');
  const input = page.getByRole('combobox', { name: 'Company name or website' });
  expect(lookups).toEqual([]);
  await input.fill('c');
  await expect(page.locator('.company-suggestion')).toHaveCount(0);
  expect(lookups).toEqual([]);
  await input.fill('clay');
  await expect(page.getByRole('option')).toHaveCount(3);
  await expect(page.getByRole('option').first()).toContainText('Clay (synthetic)');
  await expect(page.locator('.company-suggestion img')).toHaveCount(2);
  for (const icon of await page.locator('.company-suggestion img').all()) {
    await expect.poll(() => icon.evaluate(image => image instanceof HTMLImageElement ? image.naturalWidth : 0)).toBe(24);
  }
  await expect(page.locator('.company-suggestion').last().locator('.site-icon')).toHaveText('C');
  await expect(page.locator('.company-suggestions-source')).toHaveText('Company suggestions');
  for (const width of [1366, 851, 850, 731, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByRole('listbox', { name: 'Company suggestions' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width + 1);
    const popup = await page.locator('.company-suggestions').boundingBox();
    expect(popup!.x).toBeGreaterThanOrEqual(0);
    expect(popup!.x + popup!.width).toBeLessThanOrEqual(width + 1);
  }
  await page.setViewportSize(info.project.name === 'phone' ? { width: 390, height: 844 } : { width: 1366, height: 900 });
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-company-suggestions.png`, fullPage: true });
  await page.locator('.company-suggestions').screenshot({ path: `.impeccable/review/${info.project.name}-company-suggestion-icons.png` });
  await input.press('ArrowDown');
  await expect(input).toHaveAttribute('aria-activedescendant', /.+/);
  await input.press('Enter');
  await expect(input).toHaveValue('clay.example');
  await expect(input).toBeFocused();
  await expect(input).toHaveAttribute('aria-expanded', 'false');
  expect(mutations).toEqual([]);
  expect(lookups).toEqual(['/v2/search/clay']);
  await input.fill('clay');
  await expect(page.getByRole('option')).toHaveCount(3);
  await input.press('Escape');
  await expect(input).toHaveValue('clay');
  await expect(input).toHaveAttribute('aria-expanded', 'false');
  await input.fill('an-unlisted-company.example');
  await input.press('Tab');
  await expect(input).toHaveValue('an-unlisted-company.example');
  expect(mutations).toEqual([]);
});

test('a suggestion without a directory logo uses the icon its own website declares', async ({ page }) => {
  const declared = 'https://declared.example/assets/logo.png';
  await installIconFixtures(page, { [declared]: syntheticIcon('#1f7a4d') });
  await page.route('https://api.brandfetch.io/**', route => route.fulfill({ json: [{ name: 'Declared (synthetic)', domain: 'declared.example' }] }));
  const lookups: string[] = [];
  await page.route('**/api/site-icon/**', route => { lookups.push(new URL(route.request().url()).pathname); return route.fulfill({ json: { url: declared } }); });
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Company name or website' }).fill('declared');
  const icon = page.locator('.company-suggestion img');
  await expect(icon).toHaveAttribute('data-requested-icon', declared);
  await expect.poll(() => icon.evaluate(image => image instanceof HTMLImageElement ? image.naturalWidth : 0)).toBe(24);
  expect(lookups).toEqual(['/api/site-icon/declared.example']);
});

test('website entry closes suggestions and does not query the company directory', async ({ page }) => {
  const lookups: string[] = [];
  await page.route('https://api.brandfetch.io/**', route => {
    lookups.push(route.request().url());
    return route.fulfill({ json: companies });
  });
  await page.goto('/');
  const input = page.getByRole('combobox', { name: 'Company name or website' });
  await input.fill('clay');
  await expect(page.getByRole('option')).toHaveCount(3);
  await page.clock.install();
  for (const website of ['https://clay.example/', 'clay.example', 'www.clay.example', 'http://clay.example/path']) {
    await input.fill(website);
    await page.clock.runFor(400);
    await expect(input).toHaveAttribute('aria-expanded', 'false');
    await expect(page.getByRole('button', { name: 'Start research', exact: true })).toBeVisible();
    await input.press('Tab');
    await expect(page.getByRole('button', { name: 'Start research', exact: true })).toBeFocused();
    await input.focus();
  }
  expect(lookups).toHaveLength(1);
});

test('without directory configuration, manual company entry stays available', async ({ page }) => {
  await page.route('http://127.0.0.1:8015/', async route => {
    const response = await route.fetch();
    await route.fulfill({ response, body: (await response.text()).replace('<head>', '<head><meta name="shortlist-company-suggestions-client-id" content="">') });
  });
  const directoryRequests: string[] = [];
  page.on('request', request => { if (request.url().startsWith('https://api.brandfetch.io/')) directoryRequests.push(request.url()); });
  await page.goto('/');
  const input = page.getByRole('combobox', { name: 'Company name or website' });
  await input.fill('seller');
  await expect(page.locator('.company-suggestion')).toHaveCount(0);
  await input.press('Tab');
  await expect(input).toHaveValue('seller');
  await expect(page.getByRole('button', { name: 'Start research', exact: true })).toBeEnabled();
  await expect(input).toHaveAttribute('aria-expanded', 'false');
  expect(directoryRequests).toEqual([]);
});

test('directory errors preserve free text and late responses cannot replace a new query', async ({ page }) => {
  let release: (() => void) | undefined;
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route('https://api.brandfetch.io/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/clay')) { await held; await route.fulfill({ json: companies }).catch(() => {}); }
    else if (path.endsWith('/north')) await route.fulfill({ json: [{ name: 'North (synthetic)', domain: 'north.example' }] });
    else await route.fulfill({ status: 429, json: { error: 'quota_exceeded' } });
  });
  try {
    await page.goto('/');
    const input = page.getByRole('combobox', { name: 'Company name or website' });
    const requested = page.waitForRequest('https://api.brandfetch.io/v2/search/clay?c=synthetic-public-client-id');
    await input.fill('clay'); await requested;
    await input.fill('north');
    await expect(page.getByRole('option')).toHaveCount(1);
    await expect(page.getByRole('option')).toContainText('North (synthetic)');
    release?.();
    await expect(page.getByRole('option')).toHaveCount(1);
    await expect(page.getByRole('option')).not.toContainText('Clay');
    await input.fill('unlisted');
    await expect(page.getByRole('status')).toContainText('suggestions are unavailable');
    await expect(input).toHaveValue('unlisted');
    await page.locator('h1').click();
    await expect(input).toHaveAttribute('aria-expanded', 'false');
    await expect(page.getByRole('button', { name: 'Start research', exact: true })).toBeEnabled();
  } finally { release?.(); }
});
