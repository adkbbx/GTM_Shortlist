import { openSettings } from './navigation';
import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test.beforeEach(async ({ page }) => {
  await page.route('**/favicon.ico', route => route.abort());
});

test('local settings expose configuration and history identities without provider calls', async ({ page }, info) => {
  const { id } = await (await page.request.post('/__fixture_held_run')).json();
  const run = await (await page.request.get(`/api/runs/${id}`)).json();
  const companies = ['Acme Labs', 'Birch Systems', 'Cedar Works'];
  await page.route('**/api/runs', route => route.fulfill({ json: companies.map((company_name, index) => ({ ...run, id: index ? `history-${index}` : id, company_name })) }));
  let configured = false;
  await page.route('**/api/health', route => route.fulfill({ json: { mode: 'local', search_ready: configured, gemma_ready: configured, worker_online: false, local_search_error: null } }));
  mkdirSync('.impeccable/review', { recursive: true });
  const capture = async (name: string) => {
    await page.evaluate(async () => { await document.fonts.ready; });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-${name}.png` });
  };
  try {
    await page.goto('/');
    await expect(page.locator('.research-sidebar')).toHaveCSS('background-color', 'rgb(32, 30, 27)');
    if (info.project.name === 'phone') {
      const saved = await page.getByRole('button', { name: 'Saved runs', exact: true }).boundingBox();
      expect(saved!.y).toBeLessThan(56);
      expect(saved!.x).toBeLessThan(24);
      await expect(page.getByRole('button', { name: 'New shortlist', exact: true })).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Settings', exact: true })).toHaveCount(0);
    }
    await page.getByLabel('Company name or website', { exact: true }).fill('My company');
    await expect(page.getByRole('button', { name: 'Open Settings', exact: true })).toBeVisible();
    await openSettings(page);
    const settings = page.getByRole('dialog', { name: 'Settings', exact: true });
    await expect(settings.locator('dd').filter({ hasText: /^Not configured$/ })).toHaveCount(3);
    await capture('settings-unconfigured');
    await page.keyboard.press('Escape');
    await expect(settings).not.toBeVisible();
    await expect(page.getByRole('button', { name: info.project.name === 'phone' ? 'Saved runs' : 'Settings', exact: true })).toBeFocused();
    await expect(page.getByLabel('Company name or website', { exact: true })).toHaveValue('My company');
    configured = true;
    await page.reload();
    await expect(page.getByRole('button', { name: 'Open Settings', exact: true })).toHaveCount(0);
    if (info.project.name === 'laptop') await page.getByRole('button', { name: 'Hide saved runs', exact: true }).click();
    if (info.project.name === 'laptop') {
      await expect(page.locator('.saved-run-identity')).toHaveText(['AL', 'BS', 'CW']);
      await expect(page.getByRole('button', { name: /Acme Labs,/ })).toHaveAttribute('title', /Acme Labs/);
    }
    await capture('settings-entry');
    await openSettings(page);
    await expect(settings.locator('dd').filter({ hasText: /^Configured$/ })).toHaveCount(2);
    await expect(settings).toContainText('Research quality has not been tested.');
    await capture('settings-configured');
    await settings.getByRole('button', { name: 'Close settings' }).click();
    await page.getByRole('button', { name: /^(Show saved runs|Saved runs)$/ }).click();
    const history = page.getByRole('navigation', { name: 'Research history' });
    await expect(history.getByRole('button')).toHaveCount(3);
    await expect(history.locator('.run-name')).toHaveText(companies);
    await capture('settings-history');
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});

test('design preview settings show readiness without collecting provider keys', async ({ page }) => {
  await page.route('http://127.0.0.1:8015/', async route => {
    const response = await route.fetch();
    await route.fulfill({ response, body: (await response.text()).replace('</head>', '<meta name="shortlist-preview-workspace" content="http://127.0.0.1:8019/"></head>') });
  });
  await page.goto('/');
  await openSettings(page);
  const settings = page.getByRole('dialog', { name: 'Settings', exact: true });
  await expect(settings).toContainText('Provider changes are disabled in this design preview');
  await expect(settings.getByRole('button', { name: /Set up company search|Manage search key/ })).toHaveCount(0);
  await expect(page.getByLabel('Tavily API key', { exact: true })).toHaveCount(0);
});
