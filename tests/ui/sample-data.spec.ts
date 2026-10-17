import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

// A first local run without keys: the setup card offers sample data, which runs the real API, worker and database on
// invented companies. Every screen keeps the label, and nothing reaches a reserved sample address.
test('sample data runs the whole flow without keys and stays labelled', async ({ page }, info) => {
  test.setTimeout(120_000);
  await page.route('**/favicon.ico', route => route.abort());
  await page.route('**/api/health', route => route.fulfill({ json: { mode: 'local', search_ready: false, gemma_ready: false, worker_online: true, local_search_error: null } }));
  const reached: string[] = [];
  page.on('request', request => { if (new URL(request.url()).hostname.endsWith('.example')) reached.push(request.url()); });
  mkdirSync('.impeccable/review', { recursive: true });
  const capture = async (name: string) => {
    await page.evaluate(async () => { await document.fonts.ready; });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-sample-${name}.png` });
  };
  const label = page.getByRole('note').filter({ hasText: 'Sample data' });
  const main = page.locator('main');

  await page.goto('/');
  const setup = page.getByRole('region', { name: 'Set up local research in two steps' });
  await expect(setup.getByText('No keys yet?')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Try the demo' })).toHaveCount(0);  // One way to try it, not two.
  await capture('setup');
  await setup.getByRole('button', { name: 'Try it with sample data' }).click();
  await expect(label).toBeVisible();
  await expect(page).toHaveURL(/\?run=/);

  await expect(page.getByRole('heading', { name: 'Confirm your target', level: 1 })).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('.confirmation .intro')).toContainText('Drafted from the sample company page');
  await expect(page.getByText('Company search is not configured')).toHaveCount(0);
  await expect(main).not.toContainText('.example');
  await capture('confirm');
  await page.getByRole('button', { name: 'Confirm target and discover' }).click();

  await expect(page.getByRole('heading', { name: 'Review your shortlist', level: 1 })).toBeVisible({ timeout: 60_000 });
  await expect(label).toBeVisible();
  const rows = page.locator('.company-row');
  await expect(rows).toHaveCount(3);
  await expect(page.locator('.shortlist-domain')).toHaveText(['Sample company', 'Sample company', 'Sample company']);
  await expect(page.locator('.company-row .site-icon.is-mark svg')).toHaveCount(3);
  await expect(main).toContainText('Needs verification');
  await expect(main).not.toContainText('.example');
  await expect(page.getByRole('button', { name: 'Reuse this offer' })).toHaveCount(0);
  await expect(page.locator('.research-recap')).not.toHaveAttribute('open');  // The shortlist comes first.
  await capture('results');

  await rows.first().click();
  const sheet = page.locator('.company-sheet').first();
  await expect(sheet).toContainText('Sample company · invented');
  await expect(sheet.locator('a[href*=".example"]')).toHaveCount(0);
  await sheet.locator('.evidence summary').first().click();
  await expect(sheet.locator('.source-meta').first()).toContainText('sample page');
  await capture('sheet');

  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Export CSV' }).click();
  expect((await download).suggestedFilename()).toMatch(/^shortlist-sample-.+\.csv$/);
  expect(reached).toEqual([]);
});
