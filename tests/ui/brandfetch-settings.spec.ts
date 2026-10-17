import { openSettings } from './navigation';
import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { installIconFixtures, syntheticIcon } from './site-icons';

test('Brandfetch setup saves immediately, persists and disables without research', async ({ page }, info) => {
  const providerRequests: string[] = [];
  const mutations: string[] = [];
  await page.route('https://api.brandfetch.io/**', route => {
    providerRequests.push(route.request().url());
    return route.fulfill({ json: [{ name: 'Clay (synthetic)', domain: 'clay.example' }] });
  });
  await page.route('https://cdn.brandfetch.io/**', route => route.abort());
  await page.route('**/favicon.ico', route => route.abort());
  await page.route('**/api/runs', route => route.fulfill({ json: [] }));
  page.on('request', request => { if (request.method() === 'POST' && request.url().includes('/api/')) mutations.push(request.url()); });
  await page.goto('/');
  await openSettings(page);
  await page.getByRole('button', { name: 'Brandfetch: Not configured', exact: true }).click();
  await expect(page.getByLabel('Public client ID', { exact: true })).toBeFocused();
  await page.getByLabel('Public client ID', { exact: true }).fill('synthetic-public-id');
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-brandfetch-settings.png` });
  await page.getByRole('button', { name: 'Save Brandfetch', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Brandfetch: Configured', exact: true })).toBeFocused();
  expect(providerRequests).toEqual([]);
  expect(mutations).toEqual([]);
  await page.reload();
  await page.getByRole('combobox', { name: 'Company name or website' }).fill('clay');
  await expect(page.getByRole('option')).toContainText('Clay (synthetic)');
  expect(new URL(providerRequests[0]).searchParams.get('c')).toBe('synthetic-public-id');
  await page.getByRole('combobox').press('Escape');
  await openSettings(page);
  await page.getByRole('button', { name: 'Brandfetch: Configured', exact: true }).click();
  await page.getByRole('button', { name: 'Turn off Brandfetch', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Brandfetch: Not configured', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Close settings', exact: true }).click();
  const requestsBefore = providerRequests.length;
  await page.getByRole('combobox').fill('another');
  await expect(page.getByRole('option')).toHaveCount(0);
  expect(providerRequests.length).toBe(requestsBefore);
  expect(mutations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(info.project.use.viewport!.width);
});

test('saved runs and results use rounded icons with optional Brandfetch fallback', async ({ page }, info) => {
  await page.addInitScript(() => localStorage.setItem('shortlist-brandfetch-public-client-id', 'synthetic-public-id'));
  await page.route('**/favicon.ico', route => route.abort());
  await page.route('https://cdn.brandfetch.io/**', route => route.abort());
  await page.route('https://api.brandfetch.io/**', route => route.abort());
  await installIconFixtures(page, {
    'https://cdn.brandfetch.io/domain/eygentic.com/fallback/404?c=synthetic-public-id': syntheticIcon('#b4501c'),
    'https://cdn.brandfetch.io/domain/example-1.com/fallback/404?c=synthetic-public-id': syntheticIcon('#245c8a'),
    'https://cdn.brandfetch.io/domain/example-2.com/fallback/404?c=synthetic-public-id': null,
  });
  const { id } = await (await page.request.post('/__fixture_held_run')).json();
  try {
    await page.request.post(`/__fixture_release/${id}`);
    await page.goto(`/?run=${id}`);
    await expect(page.locator('.company-item')).toHaveCount(2, { timeout: 15000 });
    const first = page.locator('.company-initial').first();
    await first.scrollIntoViewIfNeeded();
    await expect(first).toHaveCSS('border-radius', '8px');
    await expect(first.locator('img')).toHaveAttribute('referrerpolicy', 'origin');
    await expect(first.locator('img')).toHaveAttribute('data-requested-icon', 'https://cdn.brandfetch.io/domain/example-1.com/fallback/404?c=synthetic-public-id');
    await expect(page.locator('.company-initial').nth(1)).toHaveCSS('border-radius', '8px');
    await expect(page.locator('.company-initial').nth(1).locator('img')).toHaveCount(0);
    mkdirSync('.impeccable/review', { recursive: true });
    await page.locator('.company-shortlist').screenshot({ path: `.impeccable/review/${info.project.name}-rounded-result-icons.png` });
    if (info.project.name === 'phone') await page.getByRole('button', { name: 'Saved runs', exact: true }).click();
    else if (await page.getByRole('button', { name: 'Expand sidebar' }).count()) await page.getByRole('button', { name: 'Expand sidebar' }).click();
    const saved = page.locator('.saved-run-identity').first();
    await expect(saved).toHaveCSS('border-radius', '6px');
    await expect(saved.locator('img')).toHaveAttribute('data-requested-icon', 'https://cdn.brandfetch.io/domain/eygentic.com/fallback/404?c=synthetic-public-id');
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-rounded-saved-icons.png` });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(info.project.use.viewport!.width);
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});

test('Brandfetch storage failures stay editable and preview disables configuration', async ({ page }) => {
  await page.route('https://api.brandfetch.io/**', route => route.abort());
  await page.route('https://cdn.brandfetch.io/**', route => route.abort());
  await page.route('**/favicon.ico', route => route.abort());
  await page.route('**/api/runs', route => route.fulfill({ json: [] }));
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function(key, value) {
      if (key === 'shortlist-brandfetch-public-client-id') throw new Error('Synthetic storage failure');
      return original.call(this, key, value);
    };
  });
  await page.goto('/');
  await openSettings(page);
  await page.getByRole('button', { name: 'Brandfetch: Not configured', exact: true }).click();
  await page.getByLabel('Public client ID', { exact: true }).fill('synthetic-public-id');
  await page.getByRole('button', { name: 'Save Brandfetch', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('could not save');
  await expect(page.getByLabel('Public client ID', { exact: true })).toHaveValue('synthetic-public-id');
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Brandfetch: Not configured', exact: true })).toBeFocused();
  await page.route('http://127.0.0.1:8015/', async route => {
    const response = await route.fetch();
    await route.fulfill({ response, body: (await response.text()).replace('<head>', '<head><meta name="shortlist-preview-workspace" content="http://127.0.0.1:8019/">') });
  });
  await page.reload();
  await openSettings(page);
  await expect(page.getByRole('dialog', { name: 'Settings', exact: true })).toContainText('Disabled in preview');
  await expect(page.getByRole('button', { name: /^Brandfetch:/ })).toHaveCount(0);
});

test('saved research displays declared icons without any provider configuration', async ({ page }, info) => {
  const providerRequests: string[] = [];
  await page.route('https://api.brandfetch.io/**', route => { providerRequests.push(route.request().url()); return route.abort(); });
  await page.route('https://cdn.brandfetch.io/**', route => { providerRequests.push(route.request().url()); return route.abort(); });
  await page.route('**/favicon.ico', route => route.abort());
  await page.route('**/api/runs/*/site-icon/*', route => {
    const domain = new URL(route.request().url()).pathname.split('/').at(-1);
    return route.fulfill({ json: { url: domain === 'eygentic.com' ? 'https://eygentic.com/assets/eygentic_logo.png' : domain === 'example-1.com' ? 'https://example-1.com/assets/icon.png' : null } });
  });
  await installIconFixtures(page, {
    'https://eygentic.com/assets/eygentic_logo.png': syntheticIcon('#b4501c'),
    'https://example-1.com/assets/icon.png': syntheticIcon('#245c8a'),
  });
  const { id } = await (await page.request.post('/__fixture_held_run')).json();
  try {
    await page.request.post(`/__fixture_release/${id}`);
    await page.goto(`/?run=${id}`);
    await expect(page.locator('.company-item')).toHaveCount(2, { timeout: 15000 });
    const image = page.locator('.company-initial img').first();
    await page.locator('.company-initial').first().scrollIntoViewIfNeeded();
    await expect(image).toHaveAttribute('data-requested-icon', 'https://example-1.com/assets/icon.png');
    await expect(image).toHaveAttribute('referrerpolicy', 'no-referrer');
    await expect.poll(() => image.evaluate(element => (element as HTMLImageElement).naturalWidth)).toBe(24);
    await expect(page.locator('.company-initial').first()).toHaveCSS('border-radius', '8px');
    if (info.project.name === 'phone') await page.getByRole('button', { name: 'Saved runs', exact: true }).click();
    else if (await page.getByRole('button', { name: 'Expand sidebar' }).count()) await page.getByRole('button', { name: 'Expand sidebar' }).click();
    const historyImage = page.locator('.saved-run-identity img').first();
    await expect(historyImage).toHaveAttribute('data-requested-icon', 'https://eygentic.com/assets/eygentic_logo.png');
    await expect.poll(() => historyImage.evaluate(element => (element as HTMLImageElement).naturalWidth)).toBe(24);
    await expect(page.locator('.saved-run-identity').first()).toHaveCSS('border-radius', '6px');
    mkdirSync('.impeccable/review', { recursive: true });
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-declared-site-icons.png` });
    expect(providerRequests).toEqual([]);
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});
