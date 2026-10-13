import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';

async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}

test('saved seller → confirmation → evidence → review → export survives reload', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  mkdirSync('.impeccable/review', { recursive: true });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'What is your company website?' })).toBeVisible();
  await noOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `.impeccable/review/${testInfo.project.name}-start.png`, fullPage: true });
  await page.getByLabel('Seller website', { exact: true }).fill('https://eygentic.com/');
  await page.getByRole('button', { name: 'Understand my offer' }).click();
  await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible({ timeout: 15000 });
  await page.getByLabel('What do you sell?').fill('Test fixture edited offer: acquisition experiments for software businesses');
  await noOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `.impeccable/review/${testInfo.project.name}-confirmation.png`, fullPage: true });
  await page.getByRole('button', { name: 'Confirm target and discover' }).click();
  await expect(page.getByRole('heading', { name: '2 companies researched' })).toBeVisible({ timeout: 15000 });
  const first = page.locator('.company-sheet').first();
  await first.locator('summary').first().click();
  await expect(first.locator('blockquote').first()).toContainText('artificial intelligence software');
  await expect(first.getByText('Publication date unknown').first()).toBeVisible();
  await first.getByLabel('Review note').fill('Accepted after inspecting the fixture passage');
  await first.getByRole('button', { name: 'Accept company' }).click();
  await expect(first.getByText('Saved: accepted')).toBeVisible();
  await page.reload();
  await expect(first.getByText('Saved: accepted')).toBeVisible();
  await expect(first.getByLabel('Review note')).toHaveValue('Accepted after inspecting the fixture passage');
  await first.locator('summary').first().click();
  await noOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `.impeccable/review/${testInfo.project.name}-results.png`, fullPage: true });
  await page.getByLabel('Accepted only').check();
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: 'Export JSON' }).click()]);
  const outputPath = testInfo.outputPath('accepted.json');
  await download.saveAs(outputPath);
  const exported = JSON.parse(readFileSync(outputPath, 'utf-8'));
  expect(exported.records).toHaveLength(1);
  expect(exported.records[0].review.decision).toBe('accepted');
  expect(exported.records[0].research.sources[0].text).toContain('TEST FIXTURE');
  expect(exported.profile.offer).toContain('edited offer');
  expect(exported.note).toContain('not buying intent');
  const [csv] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: 'Export CSV' }).click()]);
  const csvPath = testInfo.outputPath('accepted.csv');
  await csv.saveAs(csvPath);
  expect(readFileSync(csvPath, 'utf-8')).toContain('artificial intelligence software');
  expect(readFileSync(csvPath, 'utf-8')).toContain('sources_json');
  expect(errors).toEqual([]);
});

test('small screen, large text, keyboard and reduced motion remain usable', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.getByLabel('Seller website', { exact: true })).toBeVisible();
  await noOverflow(page);
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await noOverflow(page);
  const input = page.getByLabel('Seller website', { exact: true });
  await input.focus();
  await expect(input).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Understand my offer' })).toBeFocused();
  expect(await page.getByRole('button', { name: 'Understand my offer' }).evaluate(el => el.getBoundingClientRect().height)).toBeGreaterThanOrEqual(44);
});

test('unsafe seller URL shows an actionable error', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Seller website', { exact: true }).fill('https://127.1');
  await page.getByRole('button', { name: 'Understand my offer' }).click();
  await expect(page.getByRole('alert')).toContainText('Check the fields');
  await expect(page.getByLabel('Seller website', { exact: true })).toHaveValue('https://127.1');
});
