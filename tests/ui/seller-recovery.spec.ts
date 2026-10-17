import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

for (const keepValid of [false, true]) {
  test(`saved seller response keeps summary and requests criterion edits, retained=${keepValid}`, async ({ page }, info) => {
    const { id } = await (await page.request.post(`/__fixture_recoverable_offer?keep_valid=${keepValid}`)).json();
    const before = await (await page.request.get(`/api/runs/${id}`)).json();
    const mutations: string[] = [];
    page.on('request', request => {
      if (request.url().includes('/api/') && request.method() !== 'GET') mutations.push(request.url());
    });
    await page.goto(`/?run=${id}`);
    const form = page.getByRole('region', { name: 'Confirm what a good fit means' });
    // A usable offer and target read as text; only the criteria that need attention open for editing.
    const offer = form.locator('.target-text').first();
    await expect(offer).toHaveText(before.draft.offer);
    await expect(form.locator('.target-text').nth(1)).toHaveText(before.draft.target);
    await expect(form).toContainText('No new model call was made.');
    const criteria = form.locator('fieldset').filter({ has: page.locator('legend', { hasText: 'Fit criteria' }) });
    await expect(criteria).toContainText('These checks guide company research and determine fit');
    await expect(criteria).toContainText('Unsupported suggestions were removed');
    const criterion = page.getByRole('textbox', { name: 'Criterion 1', exact: true });
    await expect(criterion).toHaveValue(keepValid ? 'Sells consumer products through an online store' : '');
    await criteria.getByText(`Review ${keepValid ? 5 : 6} removed suggestions`, { exact: true }).press('Enter');
    await expect(criteria).toContainText('Requires sophisticated data analysis');
    await expect(criteria).toContainText('Assumes internal needs or performance');
    await page.reload();
    await expect(offer).toHaveText(before.draft.offer);
    await expect(criterion).toHaveValue(keepValid ? 'Sells consumer products through an online store' : '');
    if (!keepValid) {
      await page.getByRole('button', { name: 'Confirm target and discover' }).click();
      expect(await criterion.evaluate(input => input.matches(':invalid'))).toBe(true);
      expect(mutations).toHaveLength(0);
    }
    await criterion.fill('Sells consumer products through an online store');
    await expect(criterion).toBeFocused();
    mkdirSync('.impeccable/review', { recursive: true });
    await criteria.getByText(`Review ${keepValid ? 5 : 6} removed suggestions`, { exact: true }).click();
    await criteria.scrollIntoViewIfNeeded();
    expect(await form.evaluate(element => { const bounds = element.getBoundingClientRect(); return bounds.left >= 0 && bounds.right <= innerWidth; })).toBe(true);
    await page.evaluate(() => { const form = document.querySelector(".confirmation"); if (form) scrollTo(0, form.getBoundingClientRect().top + scrollY - 16); });
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-seller-recovery-${keepValid}.png` });
    for (const width of [731, 850, 851, 390, 1366]) {
      await page.setViewportSize({ width, height: 900 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
    expect(await (await page.request.get(`/api/runs/${id}`)).json()).toEqual(before);
    expect(mutations).toHaveLength(0);
  });
}
