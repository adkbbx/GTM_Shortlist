import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test('standalone demo completes without research requests and returns to preserved input', async ({ page }, info) => {
  await page.goto('/');
  await page.getByLabel('Company name or website', { exact: true }).fill('https://preserved.example');
  await expect(page.getByRole('region', { name: 'See how a shortlist takes shape.' })).toHaveCount(0);
  const requests: string[] = [];
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) requests.push(request.url()); });
  await page.getByRole('link', { name: 'Try the demo', exact: true }).click();
  await expect(page).toHaveURL(/demo=1/);
  await expect(page.getByRole('button', { name: 'Start research', exact: true })).toHaveCount(0);
  await expect(page.getByText('Synthetic example · invented companies and passages')).toBeVisible();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm example target', exact: true }).click();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect example passage', exact: true }).click();
  await page.getByRole('button', { name: 'Review this example', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Demo complete', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Accept example', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Accept example', exact: true })).toHaveAttribute('aria-pressed', 'true');
  expect(requests).toEqual([]);
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-standalone-demo.png`, fullPage: true });
  await page.getByRole('link', { name: 'Return to workspace', exact: true }).click();
  await expect(page.getByLabel('Company name or website', { exact: true })).toHaveValue('https://preserved.example');
});

test('demo remains readable with reduced motion and enlarged phone text', async ({ page }, info) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/?demo=1');
  await expect(page.getByRole('button', { name: /^(Previous|Pause|Next|Reduce motion|Close example)$/ })).toHaveCount(0);
  await page.setViewportSize({ width: 320, height: 844 });
  await page.locator('html').evaluate(element => { element.style.fontSize = '200%'; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('link', { name: 'Back to workspace', exact: true }).press('Enter');
  await expect(page.getByLabel('Company name or website', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  mkdirSync('.impeccable/review', { recursive: true });
  await page.setViewportSize(info.project.use.viewport ?? { width: 390, height: 844 });
  await page.locator('html').evaluate(element => { element.style.fontSize = ''; });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-simplified-entry.png` });
});
