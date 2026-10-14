import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';

async function noOverflow(page: Page) {
  const layout = await page.evaluate(() => ({ width: window.innerWidth, scroll: document.documentElement.scrollWidth,
    outside: [...document.querySelectorAll('body *')].filter(element => element.getBoundingClientRect().right > window.innerWidth + 1)
      .map(element => `${element.tagName}.${element.className}`).slice(0, 12),
  }));
  expect(layout.scroll, JSON.stringify(layout)).toBeLessThanOrEqual(layout.width + 1);
}

async function capture(page: Page, path: string) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
    window.scrollTo(0, 0);
  });
  await page.screenshot({ path, fullPage: true });
}

test('stopping actual held research keeps completed sheets and ignores an older progress response', async ({ page }, info) => {
  const fixture = await page.request.post('/__fixture_held_run');
  expect(fixture.ok()).toBeTruthy();
  const { id } = await fixture.json();
  let releaseOld: (() => void) | undefined;
  try {
    await page.goto(`/?run=${id}`);
    await expect(page.getByRole('list', { name: 'Saved research checkpoints' })).toContainText('Saved research for example-1.com', { timeout: 15000 });
    let oldRequested: (() => void) | undefined;
    let oldFulfilled: (() => void) | undefined;
    const oldRequest = new Promise<void>(resolve => { oldRequested = resolve; });
    const fulfilled = new Promise<void>(resolve => { oldFulfilled = resolve; });
    const heldResponse = new Promise<void>(resolve => { releaseOld = resolve; });
    let holdNextRead = true;
    let failNextStop = true;
    // Keep routing patterns fixed while a request is held: changing interception
    // patterns can let Chromium handle that paused request before fulfill().
    await page.route('**/api/runs/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if (path === `/api/runs/${id}/stop` && failNextStop) {
        failNextStop = false;
        await route.fulfill({ status: 503, json: { detail: 'Labelled temporary stop failure' } });
        return;
      }
      if (path !== `/api/runs/${id}` || !holdNextRead) { await route.continue(); return; }
      holdNextRead = false;
      const response = await page.request.get(route.request().url());
      const body = await response.json();
      oldRequested?.();
      await heldResponse;
      await route.fulfill({ json: body });
      oldFulfilled?.();
    });
    await oldRequest;
    await page.getByRole('button', { name: 'Stop this run', exact: true }).press('Enter');
    await expect(page.getByRole('button', { name: 'Keep researching' })).toBeFocused();
    await noOverflow(page);
    await capture(page, `.impeccable/review/${info.project.name}-stop-confirmation.png`);
    await page.getByRole('button', { name: 'Keep researching' }).press('Enter');
    await expect(page.getByRole('button', { name: 'Stop this run', exact: true })).toBeFocused();
    await page.getByRole('button', { name: 'Stop this run', exact: true }).click();
    await page.getByRole('button', { name: 'Stop research', exact: true }).click();
    await expect(page.getByRole('alert')).toHaveText('Labelled temporary stop failure');
    await page.getByRole('button', { name: 'Stop research', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Research stopped', exact: true })).toBeFocused();
    releaseOld?.();
    await fulfilled;
    await page.unrouteAll({ behavior: 'wait' });
    await expect(page.getByRole('heading', { name: 'Research stopped', exact: true })).toBeVisible();
    await expect(page.locator('.company-sheet')).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Stop this run', exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Accept company', exact: true }).click();
    await expect(page.getByText('Saved: accepted')).toBeVisible();
    const download = page.waitForEvent('download');
    await page.getByRole('link', { name: 'Export JSON' }).click();
    const path = await (await download).path();
    expect(path).toBeTruthy();
    const exported = JSON.parse(readFileSync(path!, 'utf8'));
    expect(exported.termination).toBe('user_stopped');
    expect(exported.records).toHaveLength(1);
    await page.request.post(`/__fixture_release/${id}`);
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Research stopped', exact: true })).toBeVisible();
    await expect(page.getByText('Saved: accepted')).toBeVisible();
    await noOverflow(page);
    await capture(page, `.impeccable/review/${info.project.name}-stop-results.png`);
  } finally {
    releaseOld?.();
    await page.request.post(`/__fixture_release/${id}`);
    await page.unrouteAll({ behavior: 'wait' });
  }
});

test('local masked Tavily setup saves privately, recovers and clears browser input', async ({ page }, info) => {
  await page.goto('/');
  const trigger = page.getByRole('button', { name: 'Connect Tavily', exact: true });
  await trigger.press('Enter');
  const keyInput = page.getByLabel('Tavily API key', { exact: true });
  await expect(keyInput).toHaveAttribute('type', 'password');
  await expect(keyInput).toBeFocused();
  const key = 'tvly-labelled-browser-fixture-not-real';
  await keyInput.fill(key);
  await page.route('**/api/local/tavily', route => route.fulfill({ status: 503, json: { detail: 'Labelled temporary settings failure' } }), { times: 1 });
  await page.getByRole('button', { name: 'Save search key' }).click();
  await expect(page.getByRole('alert')).toHaveText('Labelled temporary settings failure');
  await expect(keyInput).toHaveValue(key);
  const savedRequest = page.waitForResponse(response => new URL(response.url()).pathname === '/api/local/tavily');
  await page.getByRole('button', { name: 'Save search key' }).click();
  const response = await savedRequest;
  expect(response.status()).toBe(200);
  expect(await response.text()).not.toContain(key);
  await expect(keyInput).toHaveValue('');
  const saved = page.getByRole('status').filter({ hasText: 'Tavily key saved' });
  await expect(saved).toBeFocused();
  expect(await page.evaluate(() => JSON.stringify([localStorage, sessionStorage]))).not.toContain(key);
  expect(await page.locator('body').textContent()).not.toContain(key);
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-tavily-saved.png`);
  await page.setViewportSize({ width: 320, height: 740 });
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-tavily-large-text.png`);
  await page.getByRole('button', { name: 'Close setup' }).press('Enter');
  await expect(trigger).toBeFocused();
  await trigger.press('Enter');
  await expect(keyInput).toHaveValue('');
  await page.reload();
  await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  await trigger.click();
  await expect(keyInput).toHaveValue('');
});

test('saved seller → confirmation → evidence → review → export survives reload', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  mkdirSync('.impeccable/review', { recursive: true });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'What is your company website?' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Understand my offer' })).toBeEnabled();
  await noOverflow(page);
  await capture(page, `.impeccable/review/${testInfo.project.name}-start.png`);
  await page.getByLabel('Seller website', { exact: true }).fill('https://eygentic.com/');
  await page.getByRole('button', { name: 'Understand my offer' }).click();
  await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible({ timeout: 15000 });
  await page.getByLabel('What do you sell?').fill('Test fixture edited offer: acquisition experiments for software businesses');
  await page.getByLabel('Exclude from consideration').fill('Companies headquartered in Canada\nPublicly listed companies');
  const required = page.getByRole('checkbox', { name: 'Required', exact: true }).first();
  const control = await required.evaluate(element => ({
    width: element.getBoundingClientRect().width, height: element.getBoundingClientRect().height,
    padding: getComputedStyle(element).padding,
    targetHeight: element.closest('label')?.getBoundingClientRect().height ?? 0,
  }));
  expect(control.width).toBe(20);
  expect(control.height).toBe(20);
  expect(control.padding).toBe('0px');
  expect(control.targetHeight).toBeGreaterThanOrEqual(44);
  await required.focus();
  await page.keyboard.press('Space');
  await expect(required).not.toBeChecked();
  await page.keyboard.press('Space');
  await expect(required).toBeChecked();
  await page.emulateMedia({ forcedColors: 'active' });
  await expect(required).toBeVisible();
  await expect(required).toBeFocused();
  await page.emulateMedia({ forcedColors: 'none' });
  await noOverflow(page);
  await capture(page, `.impeccable/review/${testInfo.project.name}-confirmation.png`);
  await page.getByRole('button', { name: 'Confirm target and discover' }).click();
  await expect(page.getByRole('heading', { name: 'Building your shortlist' })).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole('list', { name: 'Saved research checkpoints' })).toBeVisible();
  await noOverflow(page);
  await capture(page, `.impeccable/review/${testInfo.project.name}-progress.png`);
  await expect(page.getByRole('heading', { name: '2 companies researched' })).toBeVisible({ timeout: 15000 });
  const first = page.locator('.company-sheet').first();
  await first.locator('summary').first().click();
  await expect(first.locator('blockquote').first()).toContainText('artificial intelligence software');
  await expect(first.getByText('Publication date unknown').first()).toBeVisible();
  const ownership = first.locator('.findings .finding').nth(1);
  await ownership.locator('summary').click();
  await expect(ownership.locator('blockquote')).toHaveText('Example Labs is a privately held startup.');
  await expect(ownership.locator('.source-meta a')).toHaveAttribute('href', 'https://example-1.com/about');
  await expect(first.locator('.qualification')).toContainText('Does not fit');
  const exclusionChecks = first.locator('.exclusion-checks');
  await expect(exclusionChecks.getByText('Matched', { exact: true })).toBeVisible();
  await expect(exclusionChecks.getByText('Ruled out', { exact: true })).toBeVisible();
  await exclusionChecks.locator('summary').first().click();
  await expect(exclusionChecks.locator('blockquote').first()).toHaveText('Example Labs is headquartered in Canada.');
  await first.getByLabel('Review note').fill('Accepted after inspecting the fixture passage');
  await first.getByRole('button', { name: 'Accept company' }).click();
  await expect(first.getByText('Saved: accepted')).toBeVisible();
  await page.reload();
  await expect(first.getByText('Saved: accepted')).toBeVisible();
  await expect(first.getByLabel('Review note')).toHaveValue('Accepted after inspecting the fixture passage');
  await page.locator('.progress-history > summary').click();
  await expect(page.getByRole('list', { name: 'Saved research checkpoints' })).toContainText('Checking that the evidence supports');
  await page.locator('.progress-history > summary').click();
  await first.locator('summary').first().click();
  await first.locator('.exclusion-checks summary').first().click();
  await noOverflow(page);
  await capture(page, `.impeccable/review/${testInfo.project.name}-results.png`);
  await page.getByLabel('Accepted only').check();
  await capture(page, `.impeccable/review/${testInfo.project.name}-export-filter.png`);
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: 'Export JSON' }).click()]);
  const outputPath = testInfo.outputPath('accepted.json');
  await download.saveAs(outputPath);
  const exported = JSON.parse(readFileSync(outputPath, 'utf-8'));
  expect(exported.records).toHaveLength(1);
  expect(exported.records[0].review.decision).toBe('accepted');
  expect(exported.records[0].research.sources[0].text).toContain('TEST FIXTURE');
  expect(exported.records[0].research.sources).toHaveLength(3);
  expect(exported.records[0].research.sources[1].url).toContain('/about');
  expect(exported.records[0].research.findings[1].evidence[0].source_id).toBe(exported.records[0].research.sources[1].id);
  expect(exported.profile.offer).toContain('edited offer');
  expect(exported.records[0].research.exclusion_findings[0].status).toBe('matched');
  expect(exported.records[0].research.qualification).toBe('does_not_fit');
  expect(exported.records[0].research.exclusion_findings[0].evidence[0].passage).toContain('Canada');
  expect(exported.note).toContain('not buying intent');
  const [csv] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: 'Export CSV' }).click()]);
  const csvPath = testInfo.outputPath('accepted.csv');
  await csv.saveAs(csvPath);
  expect(readFileSync(csvPath, 'utf-8')).toContain('artificial intelligence software');
  expect(readFileSync(csvPath, 'utf-8')).toContain('sources_json');
  expect(readFileSync(csvPath, 'utf-8')).toContain('exclusion_findings_json');
  const runId = new URL(page.url()).searchParams.get('run');
  const response = await page.request.post('/__fixture_operator_review', { data: {
    run_id: runId, record_id: exported.records[0].research.id, request_key: `operator-fixture-${testInfo.project.name}`,
    previous_id: null, annotation: { outcome: 'reviewed', reviewer: `Labelled fixture reviewer ${'x'.repeat(70)}`,
      note: 'TEST FIXTURE service note. The supplied source was inspected. This does not change the customer decision.',
      source_ids: [exported.records[0].research.sources[0].id] },
  } });
  expect(response.ok()).toBeTruthy();
  await page.reload();
  const serviceReview = first.getByRole('region', { name: 'Service review', exact: true });
  await expect(serviceReview.getByText('Evidence reviewed', { exact: true })).toBeVisible();
  await expect(serviceReview.getByText('TEST FIXTURE service note.', { exact: false })).toBeVisible();
  await expect(first.getByText('Saved: accepted')).toBeVisible();
  await expect(first.locator('.qualification')).toContainText('Does not fit');
  await expect(serviceReview.getByRole('link')).toHaveAttribute('rel', 'noopener noreferrer');
  await expect(serviceReview.getByRole('link')).toHaveAttribute('href', exported.records[0].research.sources[0].url);
  await noOverflow(page);
  await capture(page, `.impeccable/review/${testInfo.project.name}-service-review.png`);
  expect(errors).toEqual([]);
});

test('queued run explains an offline worker without pretending to research', async ({ page }, testInfo) => {
  const response = await page.request.post('/api/sellers', { data: {
    seller_url: 'https://eygentic.com/', request_key: `offline-${testInfo.project.name}-${Date.now()}`,
  } });
  const queued = await response.json();
  const snapshot = { ...queued, status: 'queued', stage: 'seller', progress: {
    ...queued.progress, worker_online: false, events: [],
  } };
  await page.route('**/api/runs', route => route.fulfill({ json: [snapshot] }));
  await page.route(`**/api/runs/${queued.id}`, route => route.fulfill({ json: snapshot }));
  await page.goto(`/?run=${queued.id}`);
  await expect(page.getByRole('heading', { name: 'Research is waiting for a worker' })).toBeVisible();
  await expect(page.getByText('The local worker is offline.', { exact: false })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Saved research checkpoints' })).toHaveCount(0);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await noOverflow(page);
  await capture(page, `.impeccable/review/${testInfo.project.name}-worker-offline.png`);
});

test('slow checkpoint responses stay serialized and recover into confirmation', async ({ page }, testInfo) => {
  const response = await page.request.post('/api/sellers', { data: {
    seller_url: 'https://eygentic.com/', request_key: `slow-${testInfo.project.name}-${Date.now()}`,
  } });
  const queued = await response.json();
  const snapshot = { ...queued, status: 'running', stage: 'seller', progress: {
    ...queued.progress, worker_online: true, events: [{
      id: 1, phase: 'seller', label: 'Reading your company website', state: 'started', detail: null,
      created_at: queued.created_at,
    }],
  } };
  let inFlight = 0;
  let maximum = 0;
  let polls = 0;
  await page.route('**/api/runs', route => route.fulfill({ json: [snapshot] }));
  await page.route(`**/api/runs/${queued.id}`, async route => {
    inFlight += 1; maximum = Math.max(maximum, inFlight); polls += 1;
    const completed = polls >= 2;
    await new Promise(resolve => setTimeout(resolve, 1800));
    await route.fulfill({ json: completed ? { ...snapshot, status: 'awaiting_confirmation', stage: 'confirmation' } : snapshot });
    inFlight -= 1;
  });
  await page.goto(`/?run=${queued.id}`);
  await expect(page.getByRole('heading', { name: 'Understanding your company' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible({ timeout: 10000 });
  expect(maximum).toBe(1);
});

test('small screen, large text, keyboard and reduced motion remain usable', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.getByLabel('Seller website', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Understand my offer' })).toBeEnabled();
  await noOverflow(page);
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await noOverflow(page);
  const input = page.getByLabel('Seller website', { exact: true });
  await input.focus();
  await expect(input).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Understand my offer' })).toBeFocused();
  expect(await page.getByRole('button', { name: 'Understand my offer' }).evaluate(el => el.getBoundingClientRect().height)).toBeGreaterThanOrEqual(44);
});

test('unsafe seller URL shows an actionable error', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Seller website', { exact: true }).fill('https://127.1');
  await page.getByRole('button', { name: 'Understand my offer' }).click();
  await expect(page.getByRole('alert')).toContainText('Check the fields');
  await expect(page.getByLabel('Seller website', { exact: true })).toHaveValue('https://127.1');
});

test('research preview explains evidence and unknowns without inventing results', async ({ page }) => {
  await page.goto('/');
  const preview = page.getByRole('complementary', { name: 'A closer look, before outreach.' });
  const evidence = preview.getByRole('button', { name: 'Evidence', exact: true });
  const unknowns = preview.getByRole('button', { name: 'Unknowns', exact: true });
  await expect(evidence).toHaveAttribute('aria-pressed', 'true');
  await unknowns.click();
  await expect(unknowns).toHaveAttribute('aria-pressed', 'true');
  await expect(preview.getByRole('heading', { name: 'Missing evidence stays visible.' })).toBeVisible();
  await expect(preview.getByText('A guide to the output, not a company result.')).toBeVisible();
  await expect(unknowns.evaluate(element => element.getBoundingClientRect().height)).resolves.toBeGreaterThanOrEqual(44);
  await evidence.focus();
  await page.keyboard.press('Enter');
  await expect(preview.getByRole('heading', { name: 'Every assessment has a trail.' })).toBeVisible();
  await noOverflow(page);
});
