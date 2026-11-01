import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';

// The public agent demo (shortlist.agent.public) served by scripts/public_demo_test_server.py with LABELLED SYNTHETIC
// providers: invented .example companies, no network, no spending.
test.use({ baseURL: 'http://127.0.0.1:8017' });

const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);

test('the public demo starts from a website alone, caps the size and shares a read-only link', async ({ page, browser }, info) => {
  await page.goto('/?flow=classic');
  await expect(page.getByLabel('Your company website')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Earlier research' })).toHaveCount(0);
  await expect(page.getByText('Public demo: up to 5 companies per search.')).toBeVisible();
  await expect(page.locator('#agent-count option')).toHaveText(['1', '3', '5']);
  await expect(page.getByRole('button', { name: 'Find 1 company' })).toBeVisible();  // one company by default
  await expect(page.getByText('Built with Muse Spark Open.')).toBeVisible();
  expect(await noOverflow(page)).toBe(true);
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-public-start.png`, fullPage: true });

  await page.getByLabel('Your company website').fill('seller.example');
  await page.locator('#agent-count').selectOption('5');
  await page.getByRole('button', { name: 'Find 5 companies' }).click();
  await expect(page).toHaveURL(/[?&]agent=[0-9a-f]{32}/);
  await expect(page.locator('.column-rejected').getByRole('heading', { name: 'Bright Kettle' })).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole('status').first()).toContainText('Done: 1 shortlisted, 1 needs a look, 1 rejected');
  expect(await page.getByRole('link', { name: 'Download CSV' }).getAttribute('href')).toMatch(/^\/api\/agent\/runs\/[0-9a-f]{32}\/shortlist\.csv$/);
  const share = page.getByRole('link', { name: 'Share on X' });
  expect(await share.getAttribute('href')).toMatch(/^https:\/\/x\.com\/intent\/post\?text=An\+agent\+found\+1\+company.*&url=.*agent%3D[0-9a-f]{32}$/);
  // The browser that started the search drafts outreach for a Shortlisted company: subject and email, checked.
  const shortlisted = page.locator('.column-shortlisted');
  await shortlisted.getByRole('button', { name: 'Draft outreach' }).click();
  const email = shortlisted.getByRole('region', { name: 'Outreach email' });
  await expect(email).toBeVisible({ timeout: 15000 });
  await expect(email.locator('.agent-email-subject')).not.toBeEmpty();
  await expect(email).toContainText('Hi Trailgear Outfitters team,');
  await expect(email).toContainText('checked against the quotes by Muse Spark Open');
  await expect(shortlisted.getByRole('button', { name: 'Draft outreach' })).toHaveCount(0);
  // It keeps its optional corrections.
  await page.locator('.agent-assumed > summary').click();
  await expect(page.locator('summary', { hasText: 'Add a competitor' })).toBeVisible();
  await expect(page.locator('.agent-count-control select')).toBeVisible();
  await expect(page.locator('.agent-shared')).toHaveCount(0);
  expect(await noOverflow(page)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-public-board.png`, fullPage: true });

  // The start page lists this browser's own searches; another visitor's browser lists none.
  await page.getByRole('link', { name: 'GTM Shortlist' }).click();
  const yours = page.getByRole('region', { name: 'Your searches' });
  await expect(yours.getByRole('link', { name: 'seller.example' })).toBeVisible();
  await yours.getByRole('link', { name: 'seller.example' }).click();
  await expect(page.locator('.column-rejected').getByRole('heading', { name: 'Bright Kettle' })).toBeVisible();

  // Anyone else with the link reads the same shortlist without edit controls.
  const visitor = await browser.newContext({ viewport: page.viewportSize() ?? undefined });
  const shared = await visitor.newPage();
  await shared.goto(page.url());
  await expect(shared.getByText('You are viewing a shared shortlist.')).toBeVisible();
  await expect(shared.locator('.column-rejected').getByRole('heading', { name: 'Bright Kettle' })).toBeVisible();
  await expect(shared.locator('summary', { hasText: 'Add a competitor' })).toHaveCount(0);
  await expect(shared.getByRole('button', { name: 'Draft outreach' })).toHaveCount(0);
  await shared.locator('.column-shortlisted').getByRole('button', { name: 'Details' }).click();
  await expect(shared.getByRole('region', { name: 'Outreach email' })).toContainText('Hi Trailgear Outfitters team,');
  await expect(shared.locator('.agent-count-control')).toHaveCount(0);
  await shared.goto('/');
  await expect(shared.getByRole('region', { name: 'Your searches' })).toHaveCount(0);
  await shared.goto(page.url());
  expect(await noOverflow(shared)).toBe(true);
  await shared.screenshot({ path: `.impeccable/review/${info.project.name}-agent-public-shared.png`, fullPage: true });
  await visitor.close();
});
