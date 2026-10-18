import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

// Labelled synthetic checkpoints use the real API and persisted confirmation/reuse commands.
test.beforeEach(async ({ page }) => {
  await page.route('https://**/*', route => route.abort());
  await page.route('**/favicon.ico', route => route.abort());
});

test('broad target advice updates on edits and opens saved campaigns with the keyboard', async ({ page }, info) => {
  const response = await page.request.post('/api/sellers', { data: { seller_url: 'https://breadth-campaign.example/',
    request_key: 'labelled-breadth-' + Date.now(), experience_version: 2 } });
  const { id } = await response.json();
  await page.goto('/?run=' + id);
  await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible({ timeout: 15000 });
  await page.getByRole('button', { name: 'Edit who to look for' }).press('Enter');
  await page.getByLabel('Who should we look for?').fill('B2B SaaS companies seeking predictable acquisition');
  const note = page.locator('#target-breadth-note');
  await expect(note).toContainText('This target is broad.');
  const suggestions = page.getByRole('button', { name: 'Pick a suggested campaign' });
  await suggestions.focus();
  await expect(suggestions).toBeFocused();
  await suggestions.press('Enter');
  await expect(page.locator('.confirmation-context')).toHaveAttribute('open', '');
  const firstCampaign = page.getByRole('button', { name: 'Apply Labelled campaign 1', exact: true });
  await expect(firstCampaign).toBeFocused();
  await expect(firstCampaign).toBeInViewport();
  await page.getByRole('button', { name: 'Apply Labelled campaign 1', exact: true }).press('Enter');
  await expect(page.getByLabel('Who should we look for?')).toHaveValue(/Private AI/);
  await expect(note).toHaveCount(0);
  await page.getByLabel('Who should we look for?').fill('B2B SaaS companies seeking predictable acquisition');
  await expect(note).toBeVisible();
  const target = page.getByLabel('Who should we look for?');
  await target.focus();
  expect(await target.getAttribute('aria-describedby')).toBe('target-breadth-note');
  await expect(target).toBeFocused();
  mkdirSync('.impeccable/review', { recursive: true });
  await target.scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: '.impeccable/review/' + info.project.name + '-target-broad.png', fullPage: true });
  await target.fill('B2B software companies with channel partner networks');
  await expect(note).toHaveCount(0);
});

test('broad advice allows confirmation without campaigns', async ({ page }) => {
  const response = await page.request.post('/__fixture_broad_target?campaigns=false');
  const { id } = await response.json();
  await page.goto('/?run=' + id);
  await expect(page.locator('#target-breadth-note')).toContainText('This target is broad.');
  await expect(page.getByRole('button', { name: 'Pick a suggested campaign' })).toHaveCount(0);
  await page.getByLabel('Companies in this batch').selectOption('3');  // The default is one company; these flows check several.
  await page.getByRole('button', { name: 'Confirm target and discover', exact: true }).press('Enter');
  await expect(page.getByRole('heading', { name: '2 companies researched' })).toBeVisible({ timeout: 15000 });
  const run = await (await page.request.get('/api/runs/' + id)).json();
  expect(run.profile.target).toContain('B2B and SaaS companies seeking');
});

for (const empty of [false, true]) {
  test('low-yield ' + (empty ? 'empty' : 'one-company') + ' review explains saved facts and reuses the offer without research', async ({ page }, info) => {
    const response = await page.request.post('/__fixture_low_yield?empty=' + empty);
    const { id } = await response.json();
    await page.goto('/?run=' + id);
    const coverage = page.getByRole('region', { name: 'Discovery coverage' });
    await expect(coverage).toContainText('Discovery saved ' + (empty ? '0 company candidates' : '1 company candidate') + ' for this target.');
    await expect(coverage).toContainText('1 service provider was set aside');
    await expect(coverage).toContainText('A narrower target usually finds more companies.');
    await expect(coverage).not.toContainText('articles');
    const reuse = coverage.getByRole('button', { name: 'Reuse this offer' });
    await expect(page.getByRole('button', { name: 'Reuse this offer' })).toHaveCount(1);
    await reuse.focus();
    await expect(reuse).toBeFocused();
    await reuse.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    mkdirSync('.impeccable/review', { recursive: true });
    await page.screenshot({ path: '.impeccable/review/' + info.project.name + '-low-yield-' + (empty ? 'empty' : 'one') + '.png', fullPage: true });
    await reuse.press('Enter');
    await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible();
    const newId = new URL(page.url()).searchParams.get('run');
    expect(newId).not.toBe(id);
    const copied = await (await page.request.get('/api/runs/' + newId)).json();
    expect(copied.attempts).toEqual([]);
    expect(copied.profile).toBeNull();
    expect(copied.status).toBe('awaiting_confirmation');
    const original = await (await page.request.get('/api/runs/' + id)).json();
    expect(original.profile.target).toBe('B2B SaaS companies');
    expect(original.records).toHaveLength(empty ? 0 : 1);
  });
}
