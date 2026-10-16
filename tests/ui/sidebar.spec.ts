import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test('navigation stays usable while resizing across both layout boundaries', async ({ page }) => {
  const fixture = await page.request.post('/__fixture_held_run');
  const { id } = await fixture.json();
  try {
    await page.setViewportSize({ width: 1366, height: 800 });
    await page.goto('/');
    const sidebar = page.getByRole('complementary', { name: 'Saved research' });
    await expect(sidebar.getByRole('button', { name: 'New shortlist', exact: true })).toBeVisible();
    for (const width of [1366, 1024, 851, 850, 731, 701, 700, 390, 320, 851, 1366]) {
      await page.setViewportSize({ width, height: 800 });
      // Keep the same mounted component and toggle each mode at every boundary.
      for (const collapsed of [true, false]) {
        await sidebar.getByRole('button', { name: collapsed ? 'Collapse sidebar' : 'Expand sidebar', exact: true }).click();
        const layout = await page.evaluate(() => {
          const rect = (selector: string) => document.querySelector(selector)!.getBoundingClientRect().toJSON();
          return { sidebar: rect('.research-sidebar'), header: rect('.sidebar-header'), action: rect('.new-run'),
            main: rect('.main'), heading: rect('.page-heading h1'), input: rect('#website'),
            navigation: rect('.research-navigation'), overflow: document.documentElement.scrollWidth > innerWidth };
        });
        expect(layout.overflow, `overflow at ${width}/${collapsed}`).toBe(false);
        expect(layout.header.y - layout.sidebar.y, `navigation top at ${width}/${collapsed}`).toBeLessThan(24);
        expect(layout.input.width, `usable input at ${width}/${collapsed}`).toBeGreaterThan(200);
        expect(layout.heading.width, `readable heading at ${width}/${collapsed}`).toBeGreaterThan(Math.min(280, width - 48));
        if (width <= 850) {
          expect(layout.main.y).toBeGreaterThanOrEqual(layout.sidebar.bottom - 1);
          expect(layout.header.right).toBeLessThanOrEqual(layout.action.x + 1);
        } else {
          expect(layout.main.x).toBeGreaterThanOrEqual(layout.sidebar.right - 1);
          expect(layout.action.y).toBeGreaterThanOrEqual(layout.header.bottom);
        }
        if (!collapsed) expect(layout.navigation.y).toBeGreaterThanOrEqual(layout.action.bottom);
      }
    }
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});

test('saved research navigation collapses and expands without changing the run', async ({ page }, info) => {
  const fixture = await page.request.post('/__fixture_held_run');
  expect(fixture.ok()).toBeTruthy();
  const { id } = await fixture.json();
  try {
    await page.goto(`/?run=${id}`);
    const sidebar = page.getByRole('complementary', { name: 'Saved research' });
    if (info.project.name === 'phone') {
      await expect(sidebar.getByRole('navigation', { name: 'Research history' })).not.toBeVisible();
      await sidebar.getByRole('button', { name: 'Expand sidebar', exact: true }).click();
    }
    await expect(sidebar.getByRole('button', { name: 'New shortlist', exact: true })).toBeVisible();
    await expect(sidebar.locator('[aria-current=page]')).toHaveCount(1);
    const initial = await sidebar.evaluate(element => element.getBoundingClientRect());
    if (info.project.name === 'laptop') expect(await page.locator('.brand').evaluate(element => element.getBoundingClientRect().width)).toBe(initial.width);
    await sidebar.getByRole('button', { name: 'Collapse sidebar', exact: true }).click();
    const expand = sidebar.getByRole('button', { name: 'Expand sidebar', exact: true });
    await expect(expand).toHaveAttribute('aria-expanded', 'false');
    await expect(page).toHaveURL(new RegExp(id));
    if (info.project.name === 'phone') {
      await expect(sidebar.getByRole('navigation', { name: 'Research history' })).not.toBeVisible();
    } else {
      const collapsedWidth = await sidebar.evaluate(element => element.getBoundingClientRect().width);
      expect(collapsedWidth).toBeLessThan(initial.width);
      expect(await page.locator('.brand').evaluate(element => element.getBoundingClientRect().width)).toBe(collapsedWidth);
    }
    mkdirSync('.impeccable/review', { recursive: true });
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-sidebar-collapsed.png` });
    await expand.press('Enter');
    await expect(sidebar.getByRole('navigation', { name: 'Research history' })).toBeVisible();
    if (info.project.name === 'phone') {
      const headingLeft = await sidebar.locator('.sidebar-heading').evaluate(element => element.getBoundingClientRect().left);
      expect(headingLeft).toBeLessThanOrEqual(24);
    }
    await expect(sidebar.getByRole('button', { name: 'Collapse sidebar', exact: true })).toBeFocused();
    await expect(sidebar.locator('[aria-current=page]')).toHaveCount(1);
    expect(await sidebar.evaluate(element => getComputedStyle(element).backgroundColor)).toBe('rgb(32, 30, 27)');
    expect(await sidebar.locator('.selected').evaluate(element => getComputedStyle(element).boxShadow)).toBe('none');
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      await page.evaluate(() => window.innerWidth));
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-sidebar-expanded.png` });
  } finally {
    await page.request.post(`/__fixture_release/${id}`);
  }
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
