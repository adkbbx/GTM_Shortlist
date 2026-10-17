import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test('historical article is excluded from company review while saved evidence stays inspectable', async ({ page }, info) => {
  await page.route('**/favicon.ico', route => route.abort());
  const { id } = await (await page.request.post('/__fixture_historical_article')).json();
  const before = await (await page.request.get(`/api/runs/${id}`)).json();
  expect(before.records[0].source_issue).toBeTruthy();
  expect(before.progress.companies).toBe(0);
  const mutations: string[] = [];
  page.on('request', request => {
    if (request.url().includes('/api/') && request.method() !== 'GET') mutations.push(request.url());
  });
  await page.goto(`/?run=${id}`);
  await expect(page.getByRole('heading', { name: '0 companies researched' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Excluded saved sources' })).toContainText('publisher.example');
  await expect(page.getByRole('button', { name: 'Accept company', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: /Inspect evidence/ }).click();
  const panel = page.getByRole('region', { name: 'Inspect evidence saved information' });
  await expect(panel).toContainText('Excluded source');
  await expect(panel.getByRole('link', { name: 'Labelled test source' })).toBeVisible();
  await page.getByRole('button', { name: /Review and draft/ }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('region', { name: 'Review and draft saved information' })).toContainText('Excluded source');
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-excluded-company-source.png`, fullPage: true });
  for (const width of [850, 851, 731, 390, 1366]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  const exported = await (await page.request.get(`/api/runs/${id}/export?format=json`)).json();
  expect(exported.records).toHaveLength(0);
  expect(exported.withheld_records).toHaveLength(1);
  expect(await (await page.request.get(`/api/runs/${id}`)).json()).toEqual(before);
  expect(mutations).toHaveLength(0);
});
