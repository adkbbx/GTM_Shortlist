import { test, expect } from '@playwright/test';

test('sample is independent of real research and preserves website input', async ({ page }) => {
  await page.goto('/');
  const entry = page.getByRole('group', { name: 'Explore an example' });
  await expect(page.getByRole('button', { name: 'Try the demo', exact: true })).toBeVisible();
  const mutations: string[] = [];
  page.on('request', request => { if (request.method() !== 'GET' && request.url().includes('/api/')) mutations.push(request.url()); });
  const input = page.getByLabel('Company name or website', { exact: true });
  await input.fill('https://preserved.example');
  await expect(page.getByRole('button', { name: 'Research my website', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Try the demo', exact: true }).click();
  const demo = page.getByRole('region', { name: 'See how a shortlist takes shape.' });
  if (await demo.locator('.demo-stage-list').getAttribute('open') === null) {
    await demo.locator('.demo-stage-list > summary').click();
  }
  await demo.getByRole('button', { name: /5 Inspect evidence/ }).click();
  await expect(demo.getByRole('heading', { name: 'Inspect evidence', exact: true })).toBeVisible();
  await demo.getByRole('button', { name: 'Inspect example passage', exact: true }).click();
  await expect(demo.getByText('Synthetic example passage', { exact: true })).toBeVisible();
  await demo.getByRole('button', { name: 'Review this example' }).click();
  await demo.getByRole('button', { name: 'Accept example', exact: true }).click();
  await expect(demo.getByRole('button', { name: 'Accept example' })).toHaveAttribute('aria-pressed', 'true');
  await demo.getByRole('button', { name: 'Explore an example draft' }).click();
  await demo.getByLabel('Example subject', { exact: true }).fill('My sample edit');
  await demo.getByRole('button', { name: 'Research my website', exact: true }).click();
  await expect(input).toBeFocused();
  await expect(input).toHaveValue('https://preserved.example');
  await demo.getByRole('button', { name: 'Close example' }).click();
  await expect(page.getByRole('button', { name: 'Try the demo', exact: true })).toBeFocused();
  expect(mutations).toEqual([]);
  expect(await entry.count()).toBe(1);
});

test('playback advances then waits for example confirmation and source inspection', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Try the demo', exact: true }).click();
  const demo = page.getByRole('region', { name: 'See how a shortlist takes shape.' });
  await expect(demo.getByRole('heading', { name: 'Confirm target', exact: true })).toBeVisible({ timeout: 12000 });
  await expect(demo.getByRole('button', { name: 'Confirm example target' })).toBeVisible();
  await demo.getByRole('button', { name: 'Confirm example target' }).click();
  // Focus/hover intentionally pauses playback. Resume from its dedicated control.
  if (await demo.getByRole('button', { name: 'Resume', exact: true }).isVisible()) await demo.getByRole('button', { name: 'Resume', exact: true }).click();
  await expect(demo.getByRole('heading', { name: 'Inspect evidence', exact: true })).toBeVisible({ timeout: 8000 });
  await expect(demo.getByRole('button', { name: 'Inspect example passage', exact: true })).toHaveAttribute('aria-expanded', 'false');
});

test('reduced motion keeps the informative result visible and stages usable', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await page.getByRole('button', { name: 'Try the demo', exact: true }).press('Enter');
  const demo = page.getByRole('region', { name: 'See how a shortlist takes shape.' });
  await expect(demo.getByRole('heading', { name: 'Review and draft', exact: true })).toBeVisible();
  await expect(demo.locator('.demo-playback [role=status]')).toContainText('Reduced motion');
  await demo.getByRole('button', { name: 'Previous', exact: true }).press('Enter');
  await expect(demo.getByRole('heading', { name: 'Inspect evidence', exact: true })).toBeVisible();
  expect(await demo.locator('.demo-scene').evaluate(element => getComputedStyle(element).animationName)).toBe('none');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('first visit presents one real task and keeps the sample optional', async ({ page }) => {
  // Other scenarios create saved runs in the shared fixture server. This case
  // explicitly represents a new account's empty history, not a returning one.
  await page.route('**/api/runs', route => route.fulfill({ json: [] }));
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Start research', exact: true })).toHaveCount(1);
  await expect(page.getByLabel('Company name or website', { exact: true })).toBeVisible();
  await expect(page.getByRole('complementary', { name: 'Saved research' })).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'See how a shortlist takes shape.' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'A shortlist with a paper trail.' })).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'How research works' })).toHaveCount(0);
  const primary = page.getByRole('button', { name: 'Start research', exact: true });
  const example = page.getByRole('button', { name: 'Try the demo', exact: true });
  await expect(primary).toBeEnabled();
  await page.setViewportSize({ width: 320, height: 844 });
  await page.locator('html').evaluate(element => { element.style.fontSize = '200%'; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByLabel('Company name or website', { exact: true }).focus();
  await page.keyboard.press('Tab');
  await expect(primary).toBeFocused();
  expect(await primary.evaluate(element => getComputedStyle(element).backgroundColor)).not.toBe(
    await example.evaluate(element => getComputedStyle(element).backgroundColor));
  await page.getByRole('button', { name: 'Try the demo', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'See how a shortlist takes shape.' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});


test('motion can be disabled during playback without hiding the result', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Try the demo', exact: true }).click();
  const demo = page.getByRole('region', { name: 'See how a shortlist takes shape.' });
  await demo.getByRole('button', { name: 'Reduce motion', exact: true }).click();
  await expect(demo.getByRole('heading', { name: 'Review and draft', exact: true })).toBeVisible();
  expect(await demo.locator('.demo-scene').evaluate(element => getComputedStyle(element).animationName)).toBe('none');
  await demo.getByRole('button', { name: 'Previous', exact: true }).click();
  await expect(demo.getByRole('heading', { name: 'Inspect evidence', exact: true })).toBeVisible();
});
