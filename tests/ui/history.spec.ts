import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { installIconFixtures, syntheticIcon } from './site-icons';

test.use({ timezoneId: 'Asia/Tokyo' });

test('history groups local dates, searches targets and companies, and highlights only the open run', async ({ page }, info) => {
  await page.clock.setFixedTime(new Date('2026-10-17T12:00:00+09:00'));
  await installIconFixtures(page, { 'https://eygentic.com/favicon.ico': syntheticIcon('#b4501c') });
  const { id } = await (await page.request.post('/__fixture_held_run')).json();
  const base = await (await page.request.get(`/api/runs/${id}`)).json();
  const dates = ['2026-10-17T00:01:00+09:00', '2026-10-16T23:59:00+09:00', '2026-10-10T00:00:00+09:00', '2026-10-09T23:59:00+09:00'];
  let runs = Array.from({ length: 16 }, (_, index) => ({
    ...base, id: index ? `synthetic-${index}` : id,
    company_name: index % 2 ? 'Birch Systems' : 'Acme Labs',
    profile: index === 1 ? null : { ...base.profile, target: `Synthetic target ${index}: B2B teams with a long research description` },
    created_at: dates[Math.min(index, 3)], status: index === 1 ? 'awaiting_confirmation' : index === 2 ? 'queued' : index === 3 ? 'running' : index === 4 ? 'partial' : 'ready',
    termination: index === 4 ? 'user_stopped' : null,
  }));
  await page.route('**/api/runs', route => route.fulfill({ json: runs }));
  const mutations: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/') && request.method() !== 'GET') mutations.push(request.url()); });
  try {
    await page.goto(`/?run=${id}`);
    const open = async () => {
      if (info.project.name === 'phone') await page.getByRole('button', { name: 'Saved runs', exact: true }).click();
    };
    await open();
    const history = page.getByRole('navigation', { name: 'Research history' });
    await expect(history).toHaveCSS('display', 'block');
    await expect(history.locator('h3')).toHaveText(['Today', 'Yesterday', 'Previous 7 days', 'Older']);
    await expect(history.locator('time')).toHaveCount(0);
    await expect(history.locator('.run-status')).toHaveText(['Needs confirmation', 'In progress', 'In progress', 'Stopped']);
    await expect(history.locator('.run-name').nth(1)).toHaveText('Birch Systems');
    await expect(history.locator('.run-company')).toHaveCount(16);
    const historyWidth = (await history.boundingBox())!.width;
    const groupBoxes = await history.locator('.history-group').evaluateAll(elements => elements.map(element => {
      const box = element.getBoundingClientRect();
      return { x: box.x, width: box.width };
    }));
    expect(groupBoxes.every(box => Math.abs(box.x - groupBoxes[0].x) < 1 && box.width <= historyWidth)).toBe(true);
    const selected = history.locator('[aria-current=page]');
    await expect(selected).toHaveCSS('background-color', 'rgb(53, 49, 43)');
    expect(await selected.evaluate(element => getComputedStyle(element, '::before').width)).toBe('2px');
    await expect(selected).toHaveCSS('border-width', '0px');
    const selectedIcon = selected.locator('.saved-run-identity');
    await expect(selectedIcon.locator('img')).toBeVisible();
    await expect(selectedIcon).toHaveCSS('border-width', '0px');
    await expect(selectedIcon).toHaveCSS('background-color', 'rgb(247, 247, 245)');
    expect(await selectedIcon.locator('img').evaluate(element => element.getBoundingClientRect().width)).toBeCloseTo(24, 1);
    await expect(selectedIcon).toHaveCSS('opacity', '1');
    const other = history.getByRole('button').nth(1);
    await expect(other.locator('.saved-run-identity')).toHaveCSS('opacity', '0.55');
    await other.focus();
    await page.keyboard.press('Tab');
    await page.keyboard.press('Shift+Tab');
    await expect(other).toBeFocused();
    await expect(other.locator('.saved-run-identity')).toHaveCSS('opacity', '1');
    const search = page.getByRole('searchbox', { name: 'Search saved runs' });
    await search.fill('target 0:');
    await expect(history.getByRole('button')).toHaveCount(1);
    await search.fill('birch');
    await expect(history.getByRole('button')).toHaveCount(8);
    await search.fill('no such saved target');
    await expect(history.getByRole('status')).toHaveText('No saved runs match your search.');
    await search.fill('');
    await expect(history.getByRole('button')).toHaveCount(16);
    await selected.scrollIntoViewIfNeeded();
    mkdirSync('.impeccable/review', { recursive: true });
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-grouped-history.png` });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect(selectedIcon).toHaveCSS('transition-duration', '0s');
    // One company suppresses the second line; exactly 15 runs does not need search.
    runs = runs.slice(0, 15).map(run => ({ ...run, company_name: 'Acme Labs' }));
    await page.reload();
    await open();
    await expect(history.getByRole('button')).toHaveCount(15);
    await expect(history.locator('.run-company')).toHaveCount(0);
    await expect(page.getByRole('searchbox', { name: 'Search saved runs' })).toHaveCount(0);
    expect(mutations).toEqual([]);
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});

test('New shortlist is in the run header and closing desktop history reclaims all its width', async ({ page }, info) => {
  const { id } = await (await page.request.post('/__fixture_held_run')).json();
  try {
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'New shortlist', exact: true })).toHaveCount(0);
    await page.goto(`/?run=${id}`);
    const fresh = page.getByRole('button', { name: 'New shortlist', exact: true });
    await expect(fresh).toBeVisible();
    if (info.project.name === 'laptop') {
      await expect(fresh).toHaveText('New shortlist');
      const next = page.getByRole('button', { name: 'Settings', exact: true });
      expect((await fresh.boundingBox())!.x).toBeLessThan((await next.boundingBox())!.x);
      await expect(page.locator('.research-sidebar').getByRole('button', { name: 'New shortlist', exact: true })).toHaveCount(0);
      await page.getByRole('button', { name: 'Hide saved runs', exact: true }).click();
      await expect(page.locator('.research-sidebar')).toBeHidden();
      expect((await page.locator('.main').boundingBox())!.width).toBe((await page.locator('.workspace').boundingBox())!.width);
      await page.screenshot({ path: '.impeccable/review/laptop-history-hidden.png' });
      await page.getByRole('button', { name: 'Show saved runs', exact: true }).click();
    }
    await fresh.press('Enter');
    await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
    await expect(page.getByRole('button', { name: 'New shortlist', exact: true })).toHaveCount(0);
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});
