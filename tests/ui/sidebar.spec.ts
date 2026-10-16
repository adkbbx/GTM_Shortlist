import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test('navigation remains compact through resize and drawer transitions', async ({ page }) => {
  const fixture = await page.request.post('/__fixture_held_run');
  const { id } = await fixture.json();
  try {
    await page.setViewportSize({ width: 1366, height: 800 });
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Collapse sidebar', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Collapse sidebar', exact: true }).click();
    for (const width of [1366, 1024, 851, 850, 731, 701, 700, 390, 320, 851, 1366]) {
      await page.setViewportSize({ width, height: 800 });
      const expand = page.getByRole('button', { name: 'Expand sidebar', exact: true });
      await expect(expand).toBeVisible();
      const before = await page.locator('.main').boundingBox();
      await expand.click();
      if (width <= 850) {
        const dialog = page.getByRole('dialog', { name: 'Your workspace' });
        await expect(dialog).toBeVisible();
        await expect(dialog.getByRole('button', { name: 'Close saved runs', exact: true })).toBeFocused();
        const box = await dialog.boundingBox();
        expect(box!.width).toBeLessThanOrEqual(width - 32);
        expect((await page.locator('.main').boundingBox())!.y).toBe(before!.y);
        expect(before!.y).toBe(56);
        expect((await page.locator('.research-sidebar').boundingBox())!.height).toBe(56);
        await page.keyboard.press('Shift+Tab');
        await expect(dialog.getByRole('navigation').getByRole('button').last()).toBeFocused();
        await page.keyboard.press('Tab');
        await expect(dialog.getByRole('button', { name: 'Close saved runs', exact: true })).toBeFocused();
        await page.keyboard.press('Escape');
        await expect(dialog).not.toBeVisible();
        await expect(expand).toBeFocused();
      } else {
        const sidebar = await page.locator('.research-sidebar').boundingBox();
        const header = await page.locator('.sidebar-header').boundingBox();
        expect(header!.y - sidebar!.y).toBeLessThan(24);
        await page.getByRole('button', { name: 'Collapse sidebar', exact: true }).click();
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
    await page.getByRole('button', { name: 'Expand sidebar', exact: true }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.setViewportSize({ width: 1366, height: 800 });
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(await page.evaluate(() => document.body.style.overflow)).not.toBe('hidden');
    await page.getByLabel('Company name or website', { exact: true }).fill('Preserved company');
    await page.getByRole('button', { name: 'Expand sidebar', exact: true }).click();
    await expect(page.getByLabel('Company name or website', { exact: true })).toHaveValue('Preserved company');
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});

test('saved research navigation collapses and expands without changing the run', async ({ page }, info) => {
  const fixture = await page.request.post('/__fixture_held_run');
  const { id } = await fixture.json();
  try {
    await page.goto(`/?run=${id}`);
    const sidebar = page.locator('.research-sidebar');
    if (info.project.name === 'phone') {
      await page.getByRole('button', { name: 'Expand sidebar', exact: true }).click();
      await expect(page.getByRole('dialog', { name: 'Your workspace' })).toBeVisible();
    }
    await expect(sidebar.locator('[aria-current=page]')).toHaveCount(1);
    await page.getByRole('button', { name: info.project.name === 'phone' ? 'Close saved runs' : 'Collapse sidebar', exact: true }).click();
    const expand = page.getByRole('button', { name: 'Expand sidebar', exact: true });
    await expect(expand).toHaveAttribute('aria-expanded', 'false');
    await expect(page).toHaveURL(new RegExp(id));
    if (info.project.name === 'phone') await expect(page.getByRole('dialog')).not.toBeVisible();
    else expect((await sidebar.boundingBox())!.width).toBe(64);
    mkdirSync('.impeccable/review', { recursive: true });
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-sidebar-collapsed.png` });
    await expand.press('Enter');
    await expect(sidebar.getByRole('navigation', { name: 'Research history' })).toBeVisible();
    await expect(page.getByRole('button', { name: info.project.name === 'phone' ? 'Close saved runs' : 'Collapse sidebar', exact: true })).toBeFocused();
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
    if (info.project.name === 'phone') await page.getByRole('button', { name: 'Expand sidebar', exact: true }).click();
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
    await expect(page.getByRole('button', { name: 'New shortlist', exact: true })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await expect(page.getByRole('button', { name: 'Start research', exact: true })).toBeDisabled();
    const demo = await page.getByRole('button', { name: 'Try the demo', exact: true }).boundingBox();
    expect(demo).not.toBeNull();
    expect((demo?.y ?? Infinity) + (demo?.height ?? 0)).toBeLessThanOrEqual(687);
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});
