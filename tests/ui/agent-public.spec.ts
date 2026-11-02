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
  await expect(page.getByText('Free demo: up to 5 companies per search.')).toBeVisible();
  await expect(page.getByRole('group', { name: 'Companies to find' }).getByRole('radio')).toHaveCount(3);
  await expect(page.getByRole('radio', { name: '1', exact: true })).toBeChecked();
  await expect(page.getByRole('button', { name: 'Find 1 company' })).toBeVisible();  // one company by default
  expect(await noOverflow(page)).toBe(true);
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-public-start.png`, fullPage: true });

  await page.getByLabel('Your company website').fill('seller.example');
  await page.getByRole('radio', { name: '5', exact: true }).check();
  await page.getByRole('button', { name: 'Find 5 companies' }).click();
  await expect(page).toHaveURL(/[?&]agent=[0-9a-f]{32}/);
  await expect(page.locator('.column-rejected').getByRole('heading', { name: 'Bright Kettle' })).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole('status').first()).toContainText('Done: 1 shortlisted, 1 needs a look, 1 rejected');
  expect(await page.getByRole('link', { name: 'Download CSV' }).getAttribute('href')).toMatch(/^\/api\/agent\/runs\/[0-9a-f]{32}\/shortlist\.csv$/);
  await expect(page.getByRole('link', { name: 'Share on X' })).toHaveCount(0);
  // The browser that started the search drafts outreach for a Shortlisted company: subject and email, checked.
  const shortlisted = page.locator('.column-shortlisted');
  await shortlisted.getByRole('button', { name: 'Draft outreach' }).click();
  const email = page.getByRole('dialog', { name: 'Outreach email' });
  await expect(email).toBeVisible();  // opens at once, then shows the email when it is written
  await expect(email.locator('.agent-email-subject')).not.toBeEmpty({ timeout: 15000 });
  await expect(email).toContainText('Hi Trailgear Outfitters team,');
  await expect(email).toContainText('Every claim matches the evidence');
  expect(await noOverflow(page)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-public-email.png` });
  await page.keyboard.press('Escape');
  await expect(email).toBeHidden();
  await expect(shortlisted.getByRole('button', { name: 'Draft outreach' })).toHaveCount(0);
  await expect(shortlisted.getByRole('button', { name: 'View email' })).toBeVisible();
  // It keeps its optional corrections.
  await page.locator('.agent-assumed > summary').click();
  await expect(page.locator('summary', { hasText: 'Add a competitor' })).toBeVisible();
  await expect(page.locator('.agent-results .count-picker')).toBeVisible();
  await expect(page.locator('.agent-shared')).toHaveCount(0);
  expect(await noOverflow(page)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-public-board.png`, fullPage: true });

  // Your shortlist gathers Shortlisted companies from this browser's searches, with the drafted email.
  await page.getByRole('link', { name: 'Your shortlist' }).click();
  await expect(page.getByRole('heading', { name: 'Your shortlist' })).toBeVisible();
  await expect(page.locator('.ys-list').getByRole('heading', { name: 'Trailgear Outfitters' })).toBeVisible();
  await page.locator('.ys-list').getByRole('button', { name: 'View email' }).click();
  await expect(page.getByRole('dialog', { name: 'Outreach email' })).toContainText('Hi Trailgear Outfitters team,');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('link', { name: 'Your shortlist' })).toHaveCount(0);  // no link to the page you are on
  expect(await noOverflow(page)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-your-shortlist.png`, fullPage: true });

  // The free demo server forgets searches when it restarts: this browser's copy keeps its Shortlisted companies.
  await page.route('**/api/agent/runs/*', route => route.request().method() === 'GET'
    ? route.fulfill({ status: 404, json: { detail: 'This search is no longer here' } }) : route.fallback());
  await page.reload();
  await expect(page.locator('.ys-list').getByRole('heading', { name: 'Trailgear Outfitters' })).toBeVisible();
  await expect(page.getByRole('note')).toContainText('no longer on the server');
  await expect(page.locator('.ys-list').getByRole('button', { name: 'Open search' })).toHaveCount(0);
  await page.unroute('**/api/agent/runs/*');

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
  await expect(shared.getByText("You're viewing a shared shortlist.")).toBeVisible();
  await expect(shared.locator('.column-rejected').getByRole('heading', { name: 'Bright Kettle' })).toBeVisible();
  await expect(shared.locator('summary', { hasText: 'Add a competitor' })).toHaveCount(0);
  await expect(shared.getByRole('button', { name: 'Draft outreach' })).toHaveCount(0);
  await shared.locator('.column-shortlisted').getByRole('button', { name: 'View email' }).click();
  await expect(shared.getByRole('dialog', { name: 'Outreach email' })).toContainText('Hi Trailgear Outfitters team,');
  await shared.keyboard.press('Escape');
  await expect(shared.locator('.count-picker')).toHaveCount(0);
  await shared.goto('/');
  await expect(shared.getByRole('region', { name: 'Your searches' })).toHaveCount(0);
  await shared.getByRole('link', { name: 'Your shortlist' }).click();
  await expect(shared.getByText('No Shortlisted companies yet.')).toBeVisible();
  await shared.goto(page.url());
  expect(await noOverflow(shared)).toBe(true);
  await shared.screenshot({ path: `.impeccable/review/${info.project.name}-agent-public-shared.png`, fullPage: true });
  await visitor.close();
});
