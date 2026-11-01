import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdirSync } from 'node:fs';

// The browser test server gives the agent LABELLED SYNTHETIC providers (shortlist.agent.synthetic): invented companies
// on .example domains, scripted model answers and no network.

const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1);

async function openAssumptions(page: Page) {
  if (await page.locator('.agent-assumed[open]').count() === 0) await page.locator('.agent-assumed > summary').click();
}

async function startRun(page: Page, website: string) {
  await page.goto('/?flow=agent');
  const field = page.getByLabel('Your company website');
  await expect(field).toBeVisible();
  await expect(page.getByRole('button', { name: 'Find 1 company' })).toBeVisible();
  await field.fill(website);
  await page.locator('#agent-count').selectOption('5');
  await page.getByRole('button', { name: 'Find 5 companies' }).click();
  await expect(page).toHaveURL(/[?&]agent=[0-9a-f]{32}/);
}

test('a website alone produces a live board with three verdicts and quoted evidence', async ({ page }, info) => {
  await startRun(page, 'seller.example');
  await expect(page.getByText('Synthetic test data.')).toBeVisible();
  const shortlisted = page.locator('.column-shortlisted');
  const needsLook = page.locator('.column-needs_look');
  const rejected = page.locator('.column-rejected');
  await expect(shortlisted.getByRole('heading', { name: 'Trailgear Outfitters' })).toBeVisible({ timeout: 30000 });
  await expect(needsLook.getByRole('heading', { name: 'Oak and Pine' })).toBeVisible();
  await expect(needsLook).toContainText('No current need or timing evidence (none dated within 180 days, no open job post)');
  await expect(rejected.getByRole('heading', { name: 'Bright Kettle' })).toBeVisible();
  // Each company is one row; its quotes and checks open on request.
  await expect(rejected.locator('.agent-row-panel').first()).toBeHidden();
  await rejected.getByRole('button', { name: 'Details' }).click();
  const reason = rejected.locator('.agent-quote-text').first();
  await expect(reason).toHaveText('“Customer support powered by RivalDesk”');
  expect(await reason.getAttribute('href')).toBe('https://brightkettle.example/#:~:text=Customer%20support%20powered%20by%20RivalDesk');
  await expect(page.getByRole('status').first()).toContainText('Done: 1 shortlisted, 1 needs a look, 1 rejected');

  // The pinned monitor shows every step done and the run's numbers; the activity log lists each step.
  const monitor = page.getByRole('region', { name: 'What the agent is doing' });
  await expect(monitor).toContainText('Finished');
  await expect(monitor.locator('.agent-stepper .step-done')).toHaveCount(6);
  await expect(monitor.locator('.agent-monitor-stats')).toContainText('3/');
  await expect(page.locator('.agent-log li').first()).toContainText('Done: 1 shortlisted');
  const steps = page.getByRole('button', { name: /^Steps \(\d+\)$/ });
  if (await steps.isVisible()) {  // phone: the log opens as a sheet from the monitor
    await steps.click();
    await expect(page.locator('#agent-feed')).toBeVisible();
    await page.getByRole('button', { name: 'Close steps' }).click();
    await expect(page.locator('#agent-feed')).toBeHidden();
  } else {
    await expect(page.locator('#agent-feed')).toBeVisible();
  }

  // A Shortlisted company carries why now and an opening line, checked against its quotes; others carry none.
  await shortlisted.getByRole('button', { name: 'Details' }).click();
  const pitch = shortlisted.getByRole('region', { name: 'Why now and an opening line' });
  await expect(pitch).toContainText('We are hiring two customer support agents');
  await expect(pitch).toContainText('Checked against the quotes by Muse Spark Open');
  await expect(pitch.getByRole('button', { name: 'Copy opening line' })).toBeVisible();
  await expect(page.locator('.column-needs_look, .column-rejected').locator('.agent-pitch')).toHaveCount(0);

  // What we assumed: every item opens its quote; nothing had to be typed.
  await openAssumptions(page);
  const assumptions = page.locator('.agent-assumptions');
  await expect(assumptions.getByRole('heading', { name: 'What we assumed' })).toBeVisible();
  // The size the seller serves is always shown, marked as inferred, and can be changed without typing anything else.
  await expect(assumptions.getByRole('button', { name: /^Small and mid-sized online stores, about 5 to 200 people, Inferred/ })).toBeVisible();
  await expect(assumptions.locator('summary', { hasText: 'Change the company size' })).toBeVisible();
  await assumptions.getByRole('button', { name: /^Help desk software for online stores/ }).click();
  const popover = page.locator('.agent-popover:popover-open');
  await expect(popover).toContainText('Northwind Desk is help desk software for online stores.');
  expect(await popover.locator('.agent-quote-text').getAttribute('href')).toContain('https://seller.example/#:~:text=');
  await page.keyboard.press('Escape');
  await expect(page.locator('.agent-popover:popover-open')).toHaveCount(0);

  // Evidence chips on a card open the job post quote with its date.
  await shortlisted.getByRole('button', { name: /Hiring customer support agents, Need/ }).click();
  await expect(page.locator('.agent-popover:popover-open')).toContainText('We are hiring two customer support agents');
  await expect(page.locator('.agent-popover:popover-open')).toContainText('Job post');
  await page.keyboard.press('Escape');

  await expect(page.locator('.agent-telemetry')).toContainText('model calls');
  await expect(page.locator('.agent-telemetry')).toContainText('$');
  expect(await noOverflow(page)).toBe(true);
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-board.png`, fullPage: true });
});

test('optional corrections re-check saved evidence: removing a competitor moves its user out of Rejected', async ({ page }) => {
  await startRun(page, 'https://seller.example/');
  const rejected = page.locator('.column-rejected');
  await expect(rejected.getByRole('heading', { name: 'Bright Kettle' })).toBeVisible({ timeout: 30000 });
  await openAssumptions(page);
  await page.locator('.agent-assumptions').getByRole('button', { name: /^RivalDesk, Direct/ }).click();
  await page.locator('.agent-popover:popover-open').getByRole('button', { name: 'Not a competitor' }).click();
  await expect(page.locator('.column-needs_look').getByRole('heading', { name: 'Bright Kettle' })).toBeVisible({ timeout: 30000 });
  await expect(rejected.getByRole('heading', { name: 'Bright Kettle' })).toHaveCount(0);
  await expect(page.locator('.agent-log')).toContainText('Activity');
});

test('a vague site offers clickable readings instead of a required text box', async ({ page }) => {
  await startRun(page, 'vague.example');
  const choice = page.locator('.agent-choice');
  await expect(choice.getByRole('heading', { name: 'Which reading is closest?' })).toBeVisible({ timeout: 30000 });
  await expect(choice.locator('.agent-reading')).toHaveCount(2);
  await expect(choice.locator('input:visible')).toHaveCount(0);
  await choice.getByRole('button', { name: /Workflow automation software/ }).click();
  await expect(page.locator('.agent-monitor.status-complete')).toBeVisible({ timeout: 30000 });
  await openAssumptions(page);
  await expect(page.locator('.agent-assumptions').getByRole('button', { name: /^Workflow automation software/ })).toBeVisible({ timeout: 30000 });
  expect(await noOverflow(page)).toBe(true);
});

test('the start page works from the keyboard and saved classic runs keep their own page', async ({ page }, info) => {
  await page.goto('/?flow=agent');
  await expect(page.getByLabel('Your company website')).toBeVisible();
  expect(await noOverflow(page)).toBe(true);
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-agent-start.png`, fullPage: true });
  await page.getByLabel('Your company website').focus();
  await page.keyboard.type('seller.example');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/[?&]agent=/);
  await expect(page.getByRole('heading', { name: 'seller.example' })).toBeFocused();
  await page.goto('/?classic=1');
  await expect(page.getByLabel('Company name or website', { exact: true })).toBeVisible();
  expect(await noOverflow(page)).toBe(true);
});
