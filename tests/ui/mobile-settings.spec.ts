import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { openSettings } from './navigation';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/runs', route => route.fulfill({ json: [] }));
  await page.route('**/api/health', route => route.fulfill({ json: { mode: 'local', search_ready: true, gemma_ready: false, worker_online: false, local_search_error: null } }));
  await page.route('https://api.brandfetch.io/**', route => route.abort());
  await page.route('https://cdn.brandfetch.io/**', route => route.abort());
});

test('phone Settings is a centered modal with reachable controls and safe resize', async ({ page }) => {
  const mutations: string[] = [];
  page.on('request', request => { if (request.method() !== 'GET' && request.url().includes('/api/')) mutations.push(request.url()); });
  mkdirSync('.impeccable/review', { recursive: true });
  await page.setViewportSize({ width: 1366, height: 900 });
  await page.goto('/');
  await page.getByLabel('Company name or website', { exact: true }).fill('Preserved input');
  await openSettings(page);
  const settings = page.getByRole('dialog', { name: 'Settings', exact: true });
  expect(await settings.evaluate(element => element.matches(':modal'))).toBe(false);
  expect((await settings.boundingBox())!.width).toBe(480);
  await page.screenshot({ path: '.impeccable/review/laptop-settings-placement.png' });
  await page.getByRole('button', { name: 'Close settings', exact: true }).click();
  for (const width of [850, 731, 390, 320]) {
    await page.getByLabel('Company name or website', { exact: true }).focus();
    await page.setViewportSize({ width, height: 844 });
    await expect(page.getByLabel('Company name or website', { exact: true })).toBeFocused();
    await openSettings(page);
    await expect(settings).toHaveAttribute('aria-modal', 'true');
    expect(await settings.evaluate(element => element.matches(':modal'))).toBe(true);
    const box = await settings.boundingBox();
    expect(box!.width).toBe(Math.min(480, width - 32));
    expect(box!.x).toBeCloseTo((width - box!.width) / 2, 0);
    expect(box!.y).toBeCloseTo((844 - box!.height) / 2, 0);
    expect(box!.y).toBeGreaterThanOrEqual(16);
    expect(box!.height).toBeLessThanOrEqual(812);
    // Content height varies with font metrics; retain a visible modal gutter.
    expect(box!.height).toBeLessThan(844 - 64);
    await expect(settings).toHaveCSS('border-radius', '12px');
    await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe('hidden');
    expect(await settings.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    if (width === 390) await page.screenshot({ path: '.impeccable/review/phone-settings-modal.png' });
    await page.getByRole('button', { name: 'Research model: Not configured', exact: true }).click();
    await settings.evaluate(element => { element.scrollTop = element.scrollHeight; });
    const close = page.getByRole('button', { name: 'Close settings', exact: true });
    const closeBox = await close.boundingBox();
    expect(closeBox!.y).toBeGreaterThanOrEqual(box!.y);
    expect(closeBox!.y).toBeLessThan(box!.y + 56);
    await close.focus();
    await close.press('Shift+Tab');
    expect(await settings.evaluate(element => element.contains(document.activeElement))).toBe(true);
    await page.keyboard.press('Escape');
    await expect(settings).not.toBeVisible();
    await expect(page.getByRole('button', { name: 'Saved runs', exact: true })).toBeFocused();
    await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe('hidden');
    await expect(page.getByLabel('Company name or website', { exact: true })).toHaveValue('Preserved input');
  }
  await openSettings(page);
  await page.getByRole('button', { name: 'Research model: Not configured', exact: true }).click();
  await page.getByRole('radio', { name: 'Hosted provider', exact: true }).check();
  await page.setViewportSize({ width: 851, height: 844 });
  await expect(settings).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe('hidden');
  expect(await settings.evaluate(element => element.matches(':modal'))).toBe(false);
  await expect(page.getByRole('radio', { name: 'Hosted provider', exact: true })).toBeChecked();
  await page.setViewportSize({ width: 850, height: 844 });
  await expect(settings).toBeVisible();
  expect(await settings.evaluate(element => element.matches(':modal'))).toBe(true);
  await expect(page.getByRole('radio', { name: 'Hosted provider', exact: true })).toBeChecked();
  await page.keyboard.press('Escape');
  await expect(settings).not.toBeVisible();
  expect(mutations).toEqual([]);
});

test('drawer toggle stays in place, animates both ways and respects reduced motion', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/');
  const menu = page.getByRole('button', { name: 'Saved runs', exact: true });
  const original = await menu.boundingBox();
  const drawer = page.getByRole('dialog', { name: 'Your workspace', exact: true });
  await menu.click();
  await expect.poll(async () => (await drawer.boundingBox())?.x).toBe(0);
  const close = page.getByRole('button', { name: 'Close saved runs', exact: true });
  expect(await close.boundingBox()).toEqual(original);
  await expect(close.locator('.middle')).toHaveCSS('opacity', '0');
  await expect(close.locator('.first')).toHaveCSS('transition-duration', '0.18s, 0.12s');
  await close.click();
  await expect(drawer).not.toBeVisible();
  await expect(menu).toBeFocused();
  // Handoff between the closing drawer and Settings must keep one scroll lock.
  await openSettings(page);
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe('hidden');
  await page.keyboard.press('Escape');
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe('hidden');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await menu.click();
  await expect(drawer).toHaveCSS('transition-duration', '0s');
  await expect(close.locator('.first')).toHaveCSS('transition-duration', '0s');
  await close.click();
  await expect(drawer).not.toBeVisible();
});
