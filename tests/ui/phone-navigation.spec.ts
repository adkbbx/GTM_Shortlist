import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { openSettings } from './navigation';

test('phone header has saved runs and Settings, with new research only inside a run', async ({ page }, info) => {
  await page.route('**/favicon.ico', route => route.abort());
  await page.route('https://cdn.brandfetch.io/**', route => route.abort());
  await page.route('https://api.brandfetch.io/**', route => route.abort());
  const { id } = await (await page.request.post('/__fixture_held_run')).json();
  const run = await (await page.request.get(`/api/runs/${id}`)).json();
  await page.route('**/api/runs', route => route.fulfill({ json: [run] }));
  mkdirSync('.impeccable/review', { recursive: true });
  try {
    await page.goto('/');
    await page.getByLabel('Company name or website', { exact: true }).fill('Preserved company');
    // Resize the same mounted page, including the 850/851px transition.
    for (const width of [1366, 851, 850, 731, 390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      const phone = width <= 850;
      const menu = page.getByRole('button', { name: 'Saved runs', exact: true });
      await expect(menu).toBeVisible({ visible: phone });
      await expect(page.getByRole('button', { name: 'New shortlist', exact: true })).toBeVisible({ visible: !phone });
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      expect(await page.locator('header.topbar').evaluate(element => element.getBoundingClientRect().height)).toBe(56);
      expect(await page.evaluate(() => getComputedStyle(document.querySelector('.research-sidebar')!, '::after').content)).toBe('none');
      if (!phone) {
        const settings = page.getByRole('button', { name: 'Settings', exact: true });
        await expect(settings.locator('span')).toHaveText('Settings');
        await expect(settings.locator('span')).toBeVisible();
        await expect(settings.locator('svg')).toHaveCount(1);
        await expect(settings).toHaveCSS('border-radius', '8px');
        expect((await settings.boundingBox())!.width).toBeGreaterThan(90);
        await expect(page.locator('.local-label')).toHaveCSS('border-left-width', '0px');
        await expect(page.locator('.local-label')).toHaveCSS('padding-left', '0px');
      }
      if (phone) {
        const box = await menu.boundingBox();
        expect(box!.x).toBeLessThan(24);
        expect(box!.y).toBeLessThan(56);
        expect(box!.width).toBeGreaterThanOrEqual(44);
        await menu.press('Enter');
        const drawer = page.getByRole('dialog', { name: 'Your workspace', exact: true });
        await expect(drawer.getByRole('button', { name: 'Settings', exact: true })).toBeVisible();
        await expect(drawer.getByRole('button', { name: 'Settings', exact: true }).locator('svg')).toHaveCount(1);
        if (width === 390 && info.project.name === 'phone') {
          await expect.poll(async () => (await drawer.boundingBox())?.x).toBe(0);
          await page.screenshot({ path: '.impeccable/review/phone-navigation-drawer.png' });
        }
        await drawer.getByRole('button', { name: 'Settings', exact: true }).click();
        await expect(drawer).not.toBeVisible();
        await expect(page.getByRole('dialog', { name: 'Settings', exact: true })).toBeVisible();
        await page.keyboard.press('Escape');
        await expect(menu).toBeFocused();
        await expect(page.getByLabel('Company name or website', { exact: true })).toHaveValue('Preserved company');
      }
    }
    await page.setViewportSize(info.project.name === 'phone' ? { width: 390, height: 844 } : { width: 1366, height: 900 });
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-navigation-entry.png`, fullPage: true });
    await page.goto(`/?run=${id}`);
    const fresh = page.getByRole('button', { name: 'New shortlist', exact: true });
    await expect(fresh).toBeVisible();
    if (info.project.name === 'phone') {
      const box = await fresh.boundingBox();
      expect(box!.y).toBeLessThan(56);
      expect(box!.x).toBeGreaterThan(320);
    }
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-navigation-run.png` });
    await page.locator('header.topbar').screenshot({ path: `.impeccable/review/${info.project.name}-navigation-header.png` });
    await fresh.press('Enter');
    await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
    if (info.project.name === 'phone') await expect(page.getByRole('button', { name: 'New shortlist', exact: true })).toHaveCount(0);
    await openSettings(page);
    await expect(page.getByRole('dialog', { name: 'Settings', exact: true })).toContainText('Company search');
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});

test('empty history exposes Settings and drawer New shortlist without a header plus', async ({ page }, info) => {
  await page.route('**/api/runs', route => route.fulfill({ json: [] }));
  if (info.project.name === 'laptop') {
    await page.goto('/');
    await expect(page.locator('.research-sidebar')).toBeHidden();
    const settings = page.getByRole('button', { name: 'Settings', exact: true });
    await expect(settings.locator('span')).toHaveText('Settings');
    await openSettings(page);
    await page.getByRole('button', { name: 'Close settings', exact: true }).click();
    await expect(settings).toBeFocused();
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Saved runs', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Your workspace', exact: true })).toContainText('Your saved runs will appear here.');
  await expect(page.getByRole('button', { name: 'Settings', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'New shortlist', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'New shortlist', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Your workspace', exact: true })).not.toBeVisible();
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
});
