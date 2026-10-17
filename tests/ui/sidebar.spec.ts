import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test.beforeEach(async ({ page }) => {
  await page.route('**/favicon.ico', route => route.abort());
});

test('shell reaches the viewport bottom and footer uses the remaining space', async ({ page }) => {
  const fixture = await page.request.post('/__fixture_held_run');
  const { id } = await fixture.json();
  try {
    for (const viewport of [{ width: 1542, height: 1290 }, { width: 1366, height: 1000 }, { width: 390, height: 1100 }]) {
      await page.setViewportSize(viewport);
      await page.goto('/');
      await expect(page.getByRole('button', { name: viewport.width <= 850 ? 'Saved runs' : 'Hide saved runs', exact: true })).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      const geometry = await page.evaluate(() => {
        const rect = (selector: string) => document.querySelector(selector)!.getBoundingClientRect().toJSON();
        return { shell: rect('#root'), header: rect('.topbar'), sidebar: rect('.research-sidebar'), main: rect('.main'), footer: rect('.workspace-footer') };
      });
      expect(geometry.shell.bottom).toBeGreaterThanOrEqual(viewport.height - 1);
      expect(geometry.footer.bottom).toBeGreaterThanOrEqual(viewport.height - (viewport.width <= 850 ? 130 : 50));
      expect(geometry.footer.width).toBeGreaterThan(Math.min(600, viewport.width - 48));
      if (viewport.width > 850) {
        expect(geometry.sidebar.bottom).toBe(geometry.shell.bottom);
        expect(geometry.header.width).toBe(viewport.width);
        expect(geometry.header.x).toBe(geometry.sidebar.x);
        const colors = await page.evaluate(() => ['.topbar', '.research-sidebar'].map(selector => getComputedStyle(document.querySelector(selector)!).backgroundColor));
        expect(colors[0]).toBe(colors[1]);
      }
    }
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});

test('navigation remains compact through resize and drawer transitions', async ({ page }) => {
  const fixture = await page.request.post('/__fixture_held_run');
  const { id } = await fixture.json();
  try {
    await page.setViewportSize({ width: 1366, height: 800 });
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Hide saved runs', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Hide saved runs', exact: true }).click();
    for (const width of [1366, 1024, 851, 850, 731, 701, 700, 390, 320, 851, 1366]) {
      await page.setViewportSize({ width, height: 800 });
      const expand = page.getByRole('button', { name: /^(Show saved runs|Saved runs)$/ });
      await expect(expand).toBeVisible();
      const before = await page.locator('.main').boundingBox();
      await expand.click();
      if (width <= 850) {
        const dialog = page.getByRole('dialog', { name: 'Your workspace' });
        await expect(dialog).toBeVisible();
        await expect(dialog.getByRole('button', { name: 'Close saved runs', exact: true })).toBeFocused();
        const box = await dialog.boundingBox();
        // Transformed Chromium bounds may include a few millionths of a pixel.
        expect(box!.width).toBeLessThanOrEqual(width - 32 + 0.01);
        expect((await page.locator('.main').boundingBox())!.y).toBe(before!.y);
        expect(before!.y).toBe(56);
        expect((await page.locator('header.topbar').boundingBox())!.height).toBe(56);
        await page.keyboard.press('Shift+Tab');
        await expect(dialog.getByRole('button', { name: 'Settings', exact: true })).toBeFocused();
        await page.keyboard.press('Tab');
        await expect(dialog.getByRole('button', { name: 'Close saved runs', exact: true })).toBeFocused();
        await page.keyboard.press('Escape');
        await expect(dialog).not.toBeVisible();
        await expect(expand).toBeFocused();
      } else {
        const sidebar = await page.locator('.research-sidebar').boundingBox();
        const toggle = page.getByRole('button', { name: 'Hide saved runs', exact: true });
        const box = await toggle.boundingBox();
        expect(box!.y).toBe(6);
        expect(box!.x + box!.width).toBe(sidebar!.x + sidebar!.width - 12);
        await expect(toggle).toHaveAttribute('title', 'Hide saved runs');
        await page.getByRole('button', { name: 'Hide saved runs', exact: true }).click();
      }
      const geometry = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth > innerWidth,
        input: document.querySelector('#website')!.getBoundingClientRect().width,
        heading: document.querySelector('h1')!.getBoundingClientRect().width,
      }));
      expect(geometry.overflow).toBe(false);
      expect(geometry.input).toBeGreaterThan(200);
      expect(geometry.heading).toBeGreaterThan(Math.min(280, width - 48));
    }
    await page.setViewportSize({ width: 790, height: 800 });
    await page.getByRole('button', { name: /^(Show saved runs|Saved runs)$/ }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.setViewportSize({ width: 1366, height: 800 });
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(await page.evaluate(() => document.body.style.overflow)).not.toBe('hidden');
    await page.getByLabel('Company name or website', { exact: true }).fill('Preserved company');
    await page.getByRole('button', { name: /^(Show saved runs|Saved runs)$/ }).click();
    await expect(page.getByLabel('Company name or website', { exact: true })).toHaveValue('Preserved company');
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});

test('saved research navigation collapses and expands without changing the run', async ({ page }, info) => {
  const fixture = await page.request.post('/__fixture_held_run');
  const { id } = await fixture.json();
  try {
    await page.goto(`/?run=${id}`);
    const sidebar = page.locator('.research-sidebar');
    const toggle = page.locator('header.topbar .desktop-history-toggle');
    const initialToggle = info.project.name === 'laptop' ? await toggle.boundingBox() : null;
    if (initialToggle) {
      const brand = await page.locator('header.topbar .brand').boundingBox();
      expect(initialToggle.x).toBeGreaterThan(brand!.x + brand!.width);
      expect(initialToggle.x + initialToggle.width).toBe((await sidebar.boundingBox())!.x + (await sidebar.boundingBox())!.width - 12);
      expect(await toggle.evaluate(element => element.previousElementSibling?.classList.contains('brand'))).toBe(true);
      await expect(toggle.locator('path')).toHaveAttribute('d', 'm15 6-6 6 6 6');
      await toggle.hover();
      await expect(toggle).toHaveCSS('background-color', 'rgb(53, 49, 43)');
    }
    if (info.project.name === 'phone') {
      await page.getByRole('button', { name: /^(Show saved runs|Saved runs)$/ }).click();
      await expect(page.getByRole('dialog', { name: 'Your workspace' })).toBeVisible();
    }
    await expect(sidebar.locator('[aria-current=page]')).toHaveCount(1);
    await page.getByRole('button', { name: info.project.name === 'phone' ? 'Close saved runs' : 'Hide saved runs', exact: true }).click();
    const expand = page.getByRole('button', { name: /^(Show saved runs|Saved runs)$/ });
    await expect(expand).toHaveAttribute('aria-expanded', 'false');
    if (initialToggle) {
      expect(await expand.boundingBox()).toEqual(initialToggle);
      await expect(expand).toHaveAttribute('title', 'Show saved runs');
      await expect(expand.locator('path')).toHaveAttribute('d', 'm9 6 6 6-6 6');
    }
    await expect(page).toHaveURL(new RegExp(id));
    if (info.project.name === 'phone') await expect(page.getByRole('dialog')).not.toBeVisible();
    else {
      await expect(sidebar).toBeHidden();
      expect((await page.locator('.main').boundingBox())!.width).toBe((await page.locator('.workspace').boundingBox())!.width);
    }
    mkdirSync('.impeccable/review', { recursive: true });
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-sidebar-collapsed.png` });
    await expand.press('Enter');
    if (initialToggle) expect(await toggle.boundingBox()).toEqual(initialToggle);
    await expect(sidebar.getByRole('navigation', { name: 'Research history' })).toBeVisible();
    await expect(page.getByRole('button', { name: info.project.name === 'phone' ? 'Close saved runs' : 'Hide saved runs', exact: true })).toBeFocused();
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-sidebar-expanded.png` });
    if (info.project.name === 'phone') {
      // Selecting a saved run dismisses the drawer and restores the workspace.
      await sidebar.locator('[aria-current=page]').click();
      await expect(page.getByRole('dialog')).not.toBeVisible();
      await expect(page).toHaveURL(new RegExp(id));
    }
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});

test('long saved history scrolls without compressing or overlapping rows', async ({ page }, info) => {
  const fixture = await page.request.post('/__fixture_held_run');
  const { id } = await fixture.json();
  try {
    const response = await page.request.get(`/api/runs/${id}`);
    const run = await response.json();
    await page.route('**/api/runs', route => route.fulfill({ json: Array.from({ length: 25 }, (_, index) => ({ ...run, id: index === 0 ? id : `history-${index}`, company_name: `Saved company ${index + 1}` })) }));
    await page.goto(`/?run=${id}`);
    if (info.project.name === 'phone') await page.getByRole('button', { name: /^(Show saved runs|Saved runs)$/ }).click();
    const rows = page.getByRole('navigation', { name: 'Research history' }).getByRole('button');
    await expect(rows).toHaveCount(25);
    const geometry = await rows.evaluateAll(elements => elements.map(element => {
      const rect = element.getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom, height: rect.height, content: element.scrollHeight, box: element.clientHeight };
    }));
    expect(geometry.every(row => row.height >= 48 && row.content <= row.box + 1)).toBe(true);
    expect(geometry.slice(1).every((row,index) => row.top >= geometry[index].bottom)).toBe(true);
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});


test('tablet preview keeps the available demo within the first viewport', async ({ page }) => {
  const fixture = await page.request.post('/__fixture_held_run');
  const { id } = await fixture.json();
  try {
    await page.setViewportSize({ width: 734, height: 687 });
    await page.route('http://127.0.0.1:8015/', async route => {
      const response = await route.fetch();
      const source = await response.text();
      await route.fulfill({ response, body: source.replace('</head>', '<meta name="shortlist-preview-workspace" content="http://127.0.0.1:8019/"></head>') });
    });
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Saved runs', exact: true })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await expect(page.getByRole('button', { name: 'Start research', exact: true })).toBeDisabled();
    const demo = await page.getByRole('link', { name: 'Try the demo', exact: true }).boundingBox();
    expect(demo).not.toBeNull();
    expect((demo?.y ?? Infinity) + (demo?.height ?? 0)).toBeLessThanOrEqual(687);
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});
