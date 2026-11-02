import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';

// The public agent demo (shortlist.agent.public) served by scripts/public_demo_test_server.py with LABELLED SYNTHETIC
// providers: invented .example companies, no network, no spending.
test.use({ baseURL: 'http://127.0.0.1:8017' });

const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);

test('video mode renames every company and says so, and outreach still reaches the real company', async ({ page }) => {
  await page.goto('/?video=1');
  await expect(page.getByRole('note').filter({ hasText: 'Video mode: company names changed' })).toBeVisible();
  await page.getByLabel('Your company website').fill('seller.example');
  await page.getByRole('button', { name: /^Find/ }).click();
  const shortlisted = page.locator('.column-shortlisted');
  await expect(shortlisted.locator('article')).toHaveCount(1, { timeout: 30000 });
  await expect(page.getByRole('status').first()).toContainText('Done:', { timeout: 30000 });
  const text = await page.locator('main').innerText();
  expect(text).not.toMatch(/Trailgear|Bright Kettle|Oak and Pine|trailgear\.example/);  // the synthetic companies' real names
  await shortlisted.getByRole('button', { name: 'Draft outreach' }).click();
  await expect(page.getByRole('dialog', { name: 'First message' }).locator('.agent-email-subject')).not.toBeEmpty({ timeout: 15000 });
  await page.keyboard.press('Escape');
  await page.goto('/?video=0');
  await expect(page.getByText('Video mode: company names changed')).toHaveCount(0);
});

test('a business without a website describes itself, and the search quotes its own words', async ({ page }, info) => {
  await page.goto('/');
  const open = page.getByRole('button', { name: "I don't have a website" });
  await open.click();
  const dialog = page.getByRole('dialog', { name: 'Describe your business' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel('What do you sell or want to build?')).toBeFocused();
  await page.keyboard.press('Escape');  // closes from the keyboard
  await expect(dialog).toBeHidden();
  await open.click();
  await dialog.getByRole('button', { name: 'Find 1 company' }).click();  // empty: says what is missing, starts nothing
  await expect(dialog.getByRole('alert')).toContainText('what you sell');
  await expect(page).not.toHaveURL(/agent=/);
  // The labelled synthetic seller (shortlist.agent.synthetic.DESCRIBED_SELLER), typed as a visitor would.
  await dialog.getByLabel('What do you sell or want to build?').fill('Help desk software for online stores. Answer every customer email and chat from one shared inbox.');
  await dialog.getByLabel('Who is your ideal customer?').fill('Customer support teams at online retailers that still answer from shared Gmail inboxes.');
  await dialog.getByLabel(/Which markets or geography/).fill('North America and Europe');
  await dialog.getByLabel(/Business name/).fill('Northwind Desk');
  expect(await noOverflow(page)).toBe(true);
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-describe.png` });
  await dialog.getByRole('button', { name: 'Find 1 company' }).click();
  await expect(page).toHaveURL(/[?&]agent=[0-9a-f]{32}/);
  await expect(page.getByRole('heading', { level: 1, name: 'Northwind Desk' })).toBeVisible();
  await expect(page.locator('.column-shortlisted').getByRole('heading', { name: 'Trailgear Outfitters' })).toBeVisible({ timeout: 30000 });
  // What it assumed rests on the visitor's own words, labelled as such and not linked to any page.
  await page.locator('.agent-assumed > summary').click();
  await expect(page.getByText('From your description of your business.')).toBeVisible();
  await page.locator('.agent-assumption-list .agent-chip').first().click();
  const quote = page.locator('.agent-popover:popover-open .agent-quote').first();
  await expect(quote).toContainText('From your description');
  await expect(quote.getByRole('link')).toHaveCount(0);
  await page.keyboard.press('Escape');
  expect(await noOverflow(page)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-described-board.png`, fullPage: true });
});

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
  const email = page.getByRole('dialog', { name: 'First message' });
  await expect(email).toBeVisible();  // opens at once, then shows the email when it is written
  await expect(email.locator('.agent-email-subject')).not.toBeEmpty({ timeout: 15000 });
  await expect(email).toContainText('Hi Trailgear Outfitters team,');
  await expect(email).toContainText('Every claim matches the evidence');
  expect(await noOverflow(page)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-public-email.png` });
  // The same message for LinkedIn, short enough for a connection note and checked with the email.
  await email.getByRole('tab', { name: 'LinkedIn' }).click();
  await expect(email.locator('.agent-email-body')).toContainText('Open to a chat?');
  await expect(email).toContainText('/300 characters');
  await expect(email.getByRole('button', { name: 'Copy message' })).toBeVisible();
  await email.getByRole('tab', { name: 'Email' }).click();
  await page.keyboard.press('Escape');
  await expect(email).toBeHidden();
  await expect(shortlisted.getByRole('button', { name: 'Draft outreach' })).toHaveCount(0);
  await expect(shortlisted.getByRole('button', { name: 'View message' })).toBeVisible();
  // It keeps its optional corrections.
  await page.locator('.agent-assumed > summary').click();
  await expect(page.locator('summary', { hasText: 'Add a competitor' })).toBeVisible();
  // How many to find is chosen once, when the search starts; for more, a new search skips companies already researched.
  await expect(page.locator('.agent-results .count-picker')).toHaveCount(0);
  await expect(page.locator('.agent-shared')).toHaveCount(0);
  expect(await noOverflow(page)).toBe(true);
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-public-board.png`, fullPage: true });

  // Your shortlist gathers Shortlisted companies from this browser's searches, with the drafted email.
  await page.getByRole('link', { name: 'Your shortlist' }).click();
  await expect(page.getByRole('heading', { name: 'Your shortlist' })).toBeVisible();
  await expect(page.locator('.ys-list').getByRole('heading', { name: 'Trailgear Outfitters' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Your searches' }).getByRole('link', { name: 'seller.example' })).toBeVisible();
  await page.locator('.ys-list').getByRole('button', { name: 'View message' }).click();
  await expect(page.getByRole('dialog', { name: 'First message' })).toContainText('Hi Trailgear Outfitters team,');
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

  // The start page offers this browser's last search; another visitor's browser offers none.
  await page.getByRole('link', { name: 'GTM Shortlist' }).click();
  const last = page.getByRole('navigation', { name: 'Your searches' }).getByRole('link', { name: /Your last search: seller\.example/ });
  await expect(last).toBeVisible();
  await last.click();
  await expect(page.locator('.column-rejected').getByRole('heading', { name: 'Bright Kettle' })).toBeVisible();

  // Anyone else with the link reads the same shortlist without edit controls.
  const visitor = await browser.newContext({ viewport: page.viewportSize() ?? undefined });
  const shared = await visitor.newPage();
  await shared.goto(page.url());
  await expect(shared.getByText("You're viewing a shared shortlist.")).toBeVisible();
  await expect(shared.locator('.column-rejected').getByRole('heading', { name: 'Bright Kettle' })).toBeVisible();
  await expect(shared.locator('summary', { hasText: 'Add a competitor' })).toHaveCount(0);
  await expect(shared.getByRole('button', { name: 'Draft outreach' })).toHaveCount(0);
  await shared.locator('.column-shortlisted').getByRole('button', { name: 'View message' }).click();
  await expect(shared.getByRole('dialog', { name: 'First message' })).toContainText('Hi Trailgear Outfitters team,');
  await shared.keyboard.press('Escape');
  await expect(shared.locator('.count-picker')).toHaveCount(0);
  await shared.goto('/');
  await expect(shared.getByRole('navigation', { name: 'Your searches' })).toHaveCount(0);
  await shared.getByRole('link', { name: 'Your shortlist' }).click();
  await expect(shared.getByText('No Shortlisted companies yet.')).toBeVisible();
  await shared.goto(page.url());
  expect(await noOverflow(shared)).toBe(true);
  await shared.screenshot({ path: `.impeccable/review/${info.project.name}-agent-public-shared.png`, fullPage: true });
  await visitor.close();
});
