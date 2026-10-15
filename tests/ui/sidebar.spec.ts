import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test('saved research navigation collapses and expands without changing the run', async ({ page }, info) => {
  const fixture = await page.request.post('/__fixture_held_run');
  expect(fixture.ok()).toBeTruthy();
  const { id } = await fixture.json();
  try {
    await page.goto(`/?run=${id}`);
    const sidebar = page.getByRole('complementary', { name: 'Saved research' });
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


test('long saved history scrolls without compressing or overlapping rows', async ({ page }) => {
  const fixture = await page.request.post('/__fixture_held_run');
  const { id } = await fixture.json();
  try {
    const response = await page.request.get(`/api/runs/${id}`);
    const run = await response.json();
    await page.route('**/api/runs', route => route.fulfill({ json: Array.from({ length: 25 }, (_, index) => ({ ...run, id: index === 0 ? id : `history-${index}`, company_name: `Saved company ${index + 1}` })) }));
    await page.goto(`/?run=${id}`);
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
