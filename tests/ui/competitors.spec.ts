import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test('saved-page peers are set aside with their reason and buyers remain reviewable', async ({ page }, info) => {
  await page.route('**/favicon.ico', route => route.abort());
  await page.route('https://api.brandfetch.io/**', route => route.abort());
  const response = await page.request.post('/__fixture_competitors');
  expect(response.ok()).toBe(true);
  const body: unknown = await response.json();
  if (!body || typeof body !== 'object' || !('id' in body) || typeof body.id !== 'string') throw new Error('Missing fixture run');
  await page.goto('/?run=' + body.id);
  await expect(page.getByRole('heading', { name: '4 companies researched' })).toBeVisible();
  const rows = page.locator('.company-row');
  await expect(rows).toHaveCount(4);
  for (const domain of ['nice.com', 'hitachienergy.com', 'lumen.com', 'front.com']) await expect(rows.filter({ hasText: domain })).toHaveCount(1);
  await expect(rows.filter({ hasText: 'channeltivity.com' })).toHaveCount(0);
  await expect(rows.filter({ hasText: 'channelinstitute.com' })).toHaveCount(0);
  await page.locator('.research-recap > summary').press('Enter');
  const discovery = page.getByRole('list', { name: 'Research stages' }).getByRole('button', { name: /Discover companies/ });
  await discovery.focus();
  await expect(discovery).toBeFocused();
  await page.keyboard.press('Enter');
  const panel = page.getByRole('region', { name: 'Discover companies saved information' });
  for (const domain of ['channeltivity.com', 'channelinstitute.com']) await expect(panel).toContainText('Set aside company: ' + domain);
  await expect(panel.getByText('Offers what you sell; likely a competitor or peer, not a buyer', { exact: true })).toHaveCount(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: '.impeccable/review/' + info.project.name + '-competitor-set-asides.png', fullPage: true });
});
