import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { mkdirSync, readFileSync } from 'node:fs';
import { openCompany } from './shortlist';

async function noOverflow(page: Page) {
  const layout = await page.evaluate(() => ({ width: window.innerWidth, scroll: document.documentElement.scrollWidth,
    outside: [...document.querySelectorAll('body *')].filter(element => element.getBoundingClientRect().right > window.innerWidth + 1)
      .map(element => `${element.tagName}.${element.className}`).slice(0, 12),
  }));
  expect(layout.scroll, JSON.stringify(layout)).toBeLessThanOrEqual(layout.width + 1);
}

async function capture(page: Page, path: string) {
  mkdirSync('.impeccable/review', { recursive: true });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
    window.scrollTo(0, 0);
  });
  await page.screenshot({ path, fullPage: true });
}

test('market observations and editable campaigns persist into confirmed targeting', async ({ page }, info) => {
  await page.goto('/');
  await page.getByLabel('Company name or website', { exact: true }).fill('https://market-seller.example/');
  await page.getByRole('button', { name: 'Start research' }).click();
  await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.research-recap > summary')).toContainText('Offer draft saved. Your confirmation is next.');
  await page.getByText('Explore campaign ideas and source context', { exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Choose a campaign direction' })).toBeVisible();
  await expect(page.locator('.competitor-list li')).toHaveCount(15);
  await expect(page.locator('.campaign-choice')).toHaveCount(6);
  await page.getByText('Inspect the saved company page', { exact: true }).click();
  await expect(page.locator('.seller-source blockquote')).toContainText('TEST FIXTURE');
  await page.getByRole('button', { name: 'Apply Labelled campaign 3', exact: true }).press('Enter');
  await expect(page.getByLabel('Who should we look for?')).toHaveValue('Private AI B2B SaaS startups in test segment 3');
  await expect(page.getByLabel('Search keywords', { exact: true })).toHaveValue('AI business software test segment 3');
  await page.getByLabel('Search keywords', { exact: true }).fill('AI business software edited search segment');
  await page.getByLabel('Who should we look for?').fill('Private AI B2B SaaS startups in edited test segment');
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-market-campaigns.png`);
  const identity = new URL(page.url()).searchParams.get('run');
  const before = await (await page.request.get(`/api/runs/${identity}`)).json();
  expect(before.profile).toBeNull();
  expect(before.records).toHaveLength(0);
  await page.getByRole('button', { name: 'Confirm target and discover' }).click();
  await expect(page.getByRole('heading', { name: '2 companies researched' })).toBeVisible({ timeout: 15000 });
  await openCompany(page);
  const overview = page.locator('.company-sheet').first().getByRole('region', { name: 'Company overview' });
  await expect(overview).toContainText('AI software for business operations');
  await expect(overview).toContainText('Headquartered in Canada.');
  await expect(overview).toContainText('24 employees, as stated on the saved page.');
  await overview.locator('summary').filter({ hasText: '24 employees, as stated on the saved page.' }).press('Enter');
  await expect(overview.locator('details[open] blockquote')).toHaveText('Our team has 24 employees.');
  await expect(overview.locator('details[open] .source-meta')).toContainText('Retrieved');
  await openCompany(page, 1);
  await expect(page.locator('.company-sheet').nth(1).getByRole('region', { name: 'Company overview' }))
    .toContainText('Not established from saved sources');
  await expect(page.locator('.company-sheet').nth(1).getByRole('region', { name: 'People to consider' }))
    .toContainText('No current team roles established');
  await openCompany(page);
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-company-overview.png`);
  const people = page.locator('.company-sheet').first().getByRole('region', { name: 'People to consider' });
  await expect(people.getByRole('heading', { name: 'Alex Morgan', exact: true })).toBeVisible();
  await expect(people.locator('.person-identity')).toContainText('CEO');
  await people.locator('summary').press('Enter');
  await expect(people.locator('details[open] blockquote')).toHaveText('Alex Morgan is our CEO.');
  await expect(people.locator('.source-meta')).toContainText('Retrieved');
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-people.png`);
  const editor = page.locator('.company-sheet').first().getByRole('region', { name: 'Email draft', exact: true });
  await editor.getByRole('button', { name: 'Create starting draft' }).press('Enter');
  await expect(editor.getByLabel('Message', { exact: true })).toHaveValue(/Alex Morgan/);
  await editor.getByLabel('Subject', { exact: true }).fill('A focused acquisition experiment');
  await editor.getByLabel('Message', { exact: true }).fill('Hi Alex,\n\nWould a focused acquisition experiment be useful?\n\nSam');
  let failDraft = true;
  await page.route('**/email-draft', async route => {
    if (failDraft) { failDraft = false; await route.fulfill({ status: 503, json: { detail: 'Labelled draft outage; your edits are still here.' } }); }
    else await route.continue();
  });
  await editor.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(editor.getByRole('alert')).toContainText('Labelled draft outage');
  await expect(editor.getByLabel('Message', { exact: true })).toHaveValue(/Hi Alex/);
  await editor.getByRole('button', { name: 'Save draft', exact: true }).press('Enter');
  await expect(editor.getByRole('status')).toContainText('Draft saved');
  await editor.getByText('Sources used for the starting draft', { exact: true }).click();
  await expect(editor.locator('.draft-basis')).toContainText('Alex Morgan is our CEO.');
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-email-draft.png`);
  await editor.screenshot({ path: `.impeccable/review/${info.project.name}-email-draft-detail.png` });
  await page.locator('.company-sheet').first().getByText('Why this company was researched', { exact: true }).click();
  await expect(page.locator('.selection-reason').first()).toContainText('Hiring · dated company statement');
  await expect(page.locator('.selection-reason').first()).toContainText('Matches campaign signal type');
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-source-signals.png`);
  await page.reload();
  await expect(page.locator('.company-overview').first()).toContainText('24 employees');
  await openCompany(page);
  await expect(page.locator('.people-research').first()).toContainText('Alex Morgan');
  await expect(editor.getByLabel('Subject', { exact: true })).toHaveValue('A focused acquisition experiment');
  await expect(editor.getByLabel('Message', { exact: true })).toHaveValue(/Hi Alex/);
  const saved = await (await page.request.get(`/api/runs/${identity}`)).json();
  expect(saved.campaign_name).toBe('Labelled campaign 3');
  expect(saved.profile.target).toBe('Private AI B2B SaaS startups in edited test segment');
  expect(saved.discovery_terms).toBe('AI business software edited search segment');
  expect(saved.market.campaigns).toHaveLength(6);
  expect(saved.attempts.filter((a: { kind: string }) => a.kind === 'search')).toHaveLength(3);
  expect(saved.attempts.filter((a: { kind: string }) => a.kind === 'model')).toHaveLength(6);
  const draft = saved.records[0].email_draft;
  const elsewhere = await page.request.post(`/api/runs/${identity}/records/${saved.records[0].research.id}/email-draft`, {
    data: { request_key: `other-tab-${info.project.name}`, previous_id: draft.id, subject: 'Saved in another tab', body: 'A newer saved message.' },
  });
  expect(elsewhere.ok()).toBeTruthy();
  await editor.getByLabel('Subject', { exact: true }).fill('My stale edit');
  await editor.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(editor.getByRole('alert')).toContainText('changed elsewhere');
  await expect(editor.getByLabel('Subject', { exact: true })).toHaveValue('My stale edit');
  await editor.getByRole('button', { name: 'Load saved draft', exact: true }).click();
  await expect(editor.getByLabel('Subject', { exact: true })).toHaveValue('Saved in another tab');
});

test('research activity follows the real worker and respects reduced motion', async ({ page }, info) => {
  const fixture = await page.request.post('/__fixture_held_run');
  const { id } = await fixture.json();
  try {
    await page.goto(`/?run=${id}`);
    await expect(page.locator('.real-latest')).toContainText('Reading example-2.com', { timeout: 15000 });
    await page.locator('.real-history > summary').click();
    await expect(page.getByRole('list', { name: 'Saved research checkpoints' })).toContainText('Saved research for example-1.com');
    await page.locator('.agent-activity').scrollIntoViewIfNeeded();
    await expect(page.locator('.agent-activity')).toHaveClass(/is-working/);
    await expect(page.locator('.research-visual')).toHaveAttribute('data-mode', 'working');
    await expect.poll(() => page.locator('.research-flow').evaluate(element => getComputedStyle(element).animationName)).toBe('research-flow');
    await page.getByRole('button', { name: 'Pause animations', exact: true }).click();
    await expect(page.locator('.real-research')).toHaveAttribute('data-reduced', 'true');
    expect(await page.locator('.research-flow').evaluate(element => getComputedStyle(element).animationName)).toBe('none');
    await page.getByRole('button', { name: 'Resume animations', exact: true }).click();
    await expect(page.locator('.demo-scene-top > span').first()).toHaveText('Worker active');
    await page.getByText('Saved offer summary', { exact: true }).click();
    await expect(page.locator('.real-saved-offer')).toContainText('customer acquisition');
    await expect(page.getByRole('progressbar')).toHaveCount(0);
    await noOverflow(page);
    await capture(page, `.impeccable/review/${info.project.name}-agent-activity.png`);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    expect(await page.locator('.research-flow').evaluate(element => getComputedStyle(element).animationName)).toBe('none');
    await page.request.post(`/__fixture_release/${id}`);
    await expect(page.locator('.real-stage-list [aria-current=step]')).toContainText('Review and draft', { timeout: 15000 });
    await expect(page.locator('.agent-activity')).not.toHaveClass(/is-working/);
    await openCompany(page);
    await page.getByText('Why this company was researched', { exact: true }).first().click();
    await expect(page.locator('.selection-reason').first()).toContainText('do not establish fit or buying intent');
  } finally { await page.request.post(`/__fixture_release/${id}`); }
});

test('stopping actual held research keeps completed sheets and ignores an older progress response', async ({ page }, info) => {
  const fixture = await page.request.post('/__fixture_held_run');
  expect(fixture.ok()).toBeTruthy();
  const { id } = await fixture.json();
  let releaseOld: (() => void) | undefined;
  try {
    await page.goto(`/?run=${id}`);
    await expect(page.locator('.real-latest')).toContainText('Reading example-2.com', { timeout: 15000 });
    await page.locator('.real-history > summary').click();
    await expect(page.getByRole('list', { name: 'Saved research checkpoints' })).toContainText('Saved research for example-1.com');
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
    await openCompany(page);
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
    await openCompany(page);
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
  expect((await page.request.post('/__fixture_corrupt_provider')).ok()).toBeTruthy();
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Local search settings could not be read');
  const trigger = page.getByRole('button', { name: 'Connect Tavily', exact: true });
  await trigger.press('Enter');
  const keyInput = page.getByLabel('Tavily API key', { exact: true });
  await expect(keyInput).toHaveAttribute('type', 'password');
  await expect(keyInput).toBeFocused();
  const key = 'tvly-labelled-browser-fixture-not-real';
  await keyInput.fill(key);
  await page.route('**/api/local/tavily', route => route.fulfill({ status: 503, json: { detail: 'Labelled temporary settings failure' } }), { times: 1 });
  await page.getByRole('button', { name: 'Save search key' }).click();
  await expect(page.getByRole('alert').filter({ hasText: 'Labelled temporary settings failure' })).toBeVisible();
  await expect(keyInput).toHaveValue(key);
  const savedRequest = page.waitForResponse(response => new URL(response.url()).pathname === '/api/local/tavily');
  await page.getByRole('button', { name: 'Save search key' }).click();
  const response = await savedRequest;
  expect(response.status()).toBe(200);
  await expect(page.getByRole('alert')).toHaveCount(0);
  expect(await response.text()).not.toContain(key);
  await expect(keyInput).toHaveCount(0);
  const saved = page.getByRole('status').filter({ hasText: 'Tavily key saved' });
  await expect(saved).toBeFocused();
  const update = page.getByRole('button', { name: 'Update search key', exact: true });
  await expect(update).toHaveAttribute('aria-expanded', 'false');
  await page.getByRole('button', { name: 'Continue to your website' }).press('Enter');
  await expect(page.getByLabel('Company name or website', { exact: true })).toBeFocused();
  expect(await page.evaluate(() => JSON.stringify([localStorage, sessionStorage]))).not.toContain(key);
  expect(await page.locator('body').textContent()).not.toContain(key);
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-tavily-saved.png`);
  await page.setViewportSize({ width: 320, height: 740 });
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-tavily-large-text.png`);
  await update.press('Enter');
  await expect(keyInput).toHaveValue('');
  await page.getByRole('button', { name: 'Close setup' }).press('Enter');
  await expect(update).toBeFocused();
  await page.reload();
  await expect(update).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('status').filter({ hasText: 'Search key saved' })).toBeVisible();
  await update.click();
  await expect(keyInput).toHaveValue('');
});

test('failed offer summary explains next steps on saved runs', async ({ page }, info) => {
  const response = await page.request.post('/__fixture_failed_offer');
  expect(response.ok()).toBeTruthy();
  const { id } = await response.json();
  await page.goto(`/?run=${id}`);
  const notice = page.getByRole('status').filter({ hasText: "We couldn't create a usable offer summary" });
  await expect(notice).toContainText("Company search hasn't started");
  await expect(notice).toContainText('product or services page');
  const recap = page.locator('.research-recap > summary');
  await expect(recap).toContainText('Offer summary unavailable. Enter your offer and target.');
  await expect(recap).not.toContainText('Offer draft saved');
  await expect(page.getByLabel('What do you sell?')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Confirm target and discover' })).toBeVisible();
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-failed-offer-guidance.png`);
  await page.reload();
  await expect(notice).toBeVisible();
  await expect(recap).toContainText('Offer summary unavailable. Enter your offer and target.');
  await page.getByRole('button', { name: 'New shortlist', exact: true }).press('Enter');
  await expect(page.getByLabel('Company name or website', { exact: true })).toBeVisible();
});

test('seller field accepts domains and full HTTPS URLs', async ({ page }, info) => {
  for (const value of ['eygentic.com', 'https://eygentic.com']) {
    await page.goto('/');
    await page.getByLabel('Company name or website', { exact: true }).fill(value);
    await expect(page).toHaveTitle('GTM Shortlist');
    await expect(page.getByRole('banner')).not.toContainText(/eygentic/i);
    if (value === 'eygentic.com') {
      await noOverflow(page);
      await capture(page, `.impeccable/review/${info.project.name}-bare-domain-input.png`);
    }
    const request = page.waitForResponse(response => new URL(response.url()).pathname === '/api/sellers' && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Start research' }).click();
    const response = await request;
    expect(response.status()).toBe(201);
    expect((await response.json()).seller_url).toBe('https://eygentic.com/');
    await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('button', { name: /Eygentic brief/ })).toHaveCount(0);
    await expect(page.getByLabel('What do you sell?')).toHaveValue('Test fixture: customer acquisition experiments for software businesses');
    await noOverflow(page);
  }
  await capture(page, `.impeccable/review/${info.project.name}-domain-input-confirmation.png`);
});

for (const company of ['Example Software', 'Eygentic']) {
test(`company name ${company} waits for website choice, retries and survives reload`, async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByLabel('Company name or website', { exact: true }).fill(company);
  const created = page.waitForResponse(response => new URL(response.url()).pathname === '/api/sellers');
  await page.getByRole('button', { name: 'Start research' }).click();
  const run = await (await created).json();
  expect(run.seller_url).toBeNull();
  expect(run.company_name).toBe(company);
  await expect(page.getByRole('heading', { name: `Which website belongs to ${company}?` })).toBeVisible();
  const matches = page.getByRole('list', { name: 'Company website matches' });
  await expect(matches.locator('li')).toHaveCount(2);
  await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toHaveCount(0);
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-company-name-matches.png`);
  await page.reload();
  await expect(matches).toBeVisible();
  await page.route(`**/api/runs/${run.id}/website`, route => route.fulfill({ status: 503, json: { detail: 'Labelled website save failure' } }), { times: 1 });
  await page.getByRole('button', { name: 'Use example-1.com', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('Labelled website save failure');
  await page.getByRole('button', { name: 'Use example-1.com', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible({ timeout: 15000 });
  await expect(page.getByLabel('What do you sell?')).not.toHaveValue('');
  const saved = await (await page.request.get(`/api/runs/${run.id}`)).json();
  expect(saved.seller_url).toBe('https://example-1.com/');
  expect(saved.attempts.filter((attempt: { kind: string }) => attempt.kind === 'search')).toHaveLength(2);
  expect(saved.profile).toBeNull();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible();
  await noOverflow(page);
  await capture(page, `.impeccable/review/${info.project.name}-company-name-chosen.png`);
  expect(errors).toEqual([]);
});
}

test('empty or unavailable company lookup accepts a manual website', async ({ page }, info) => {
  for (const company of ['No matches fixture', 'Lookup unavailable fixture']) {
    await page.goto('/');
    await page.getByLabel('Company name or website', { exact: true }).fill(company);
    await page.getByRole('button', { name: 'Start research' }).click();
    await expect(page.getByRole('heading', { name: `Which website belongs to ${company}?` })).toBeVisible();
    await expect(page.getByRole('list', { name: 'Company website matches' })).toHaveCount(0);
    await expect(page.getByRole('status').filter({ hasText: "website below to continue" })).toBeVisible();
    await page.getByLabel('Company website', { exact: true }).fill('eygentic.com');
    await noOverflow(page);
    await capture(page, `.impeccable/review/${info.project.name}-company-lookup-fallback.png`);
    await page.getByRole('button', { name: 'Use this website', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible({ timeout: 15000 });
  }
});

test('saved seller → confirmation → evidence → review → export survives reload', async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  mkdirSync('.impeccable/review', { recursive: true });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Find companies that fit your offer.' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start research' })).toBeEnabled();
  await noOverflow(page);
  await capture(page, `.impeccable/review/${testInfo.project.name}-start.png`);
  await page.getByLabel('Company name or website', { exact: true }).fill('https://eygentic.com/');
  await page.getByRole('button', { name: 'Start research' }).click();
  await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.research-recap')).not.toHaveAttribute('open');
  await expect(page.locator('.confirmation-context')).not.toHaveAttribute('open');
  await expect(page.locator('.real-research')).not.toBeVisible();
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
  await expect(page.getByRole('heading', { name: 'Your research, step by step' })).toBeVisible({ timeout: 10000 });
  await page.locator('.real-research details').filter({ hasText: 'Saved research checkpoints' }).locator('summary').click();
  await expect(page.getByRole('list', { name: 'Saved research checkpoints' })).toBeVisible();
  await noOverflow(page);
  await capture(page, `.impeccable/review/${testInfo.project.name}-progress.png`);
  await expect(page.getByRole('heading', { name: '2 companies researched' })).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.research-recap')).not.toHaveAttribute('open');
  await expect(page.locator('.real-research')).not.toBeVisible();
  const first = page.locator('.company-sheet').first();
  await openCompany(page);
  await first.locator('.findings .evidence > summary').first().click();
  await expect(first.locator('.findings .evidence blockquote').first()).toContainText('artificial intelligence software');
  await expect(first.locator('.findings').getByText('Publication date unknown').first()).toBeVisible();
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
  await openCompany(page);
  await expect(first.getByText('Saved: accepted')).toBeVisible();
  await expect(first.getByLabel('Review note')).toHaveValue('Accepted after inspecting the fixture passage');
  await page.locator('.research-recap > summary').click();
  await page.locator('.real-history > summary').click();
  await expect(page.getByRole('list', { name: 'Saved research checkpoints' })).toContainText('Checking that the evidence supports');
  await page.locator('.real-history > summary').click();
  await page.locator('.research-recap > summary').click();
  await first.locator('.findings .evidence > summary').first().click();
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
  expect(exported.records[0].research.company_facts).toHaveLength(3);
  expect(exported.records[0].research.people[0].name).toBe('Alex Morgan');
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
  expect(readFileSync(csvPath, 'utf-8')).toContain('Offers AI software to businesses');
  expect(readFileSync(csvPath, 'utf-8')).toContain('Source links');
  expect(readFileSync(csvPath, 'utf-8')).toContain('What needs checking');
  expect(readFileSync(csvPath, 'utf-8')).not.toContain('sources_json');
  const [excel] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: 'Export Excel' }).click()]);
  expect(excel.suggestedFilename()).toMatch(/\.xlsx$/);
  const excelPath = testInfo.outputPath('accepted.xlsx');
  await excel.saveAs(excelPath);
  expect(readFileSync(excelPath).subarray(0, 2).toString()).toBe('PK');
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
  await openCompany(page);
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
  await expect(page.getByText('Waiting for a worker', { exact: true })).toBeVisible();
  await expect(page.getByText('Your run is saved. Processing will continue when a research worker connects.', { exact: true })).toBeVisible();
  await expect(page.locator('.agent-activity')).not.toHaveClass(/is-working/);
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
  await expect(page.getByRole('heading', { name: 'Understand offer', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Confirm what a good fit means' })).toBeVisible({ timeout: 10000 });
  expect(maximum).toBe(1);
});

test('small screen, large text, keyboard and reduced motion remain usable', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.getByLabel('Company name or website', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start research' })).toBeEnabled();
  await noOverflow(page);
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  await noOverflow(page);
  const input = page.getByLabel('Company name or website', { exact: true });
  await input.focus();
  await expect(input).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Start research' })).toBeFocused();
  expect(await page.getByRole('button', { name: 'Start research' }).evaluate(el => el.getBoundingClientRect().height)).toBeGreaterThanOrEqual(44);
});

test('unsafe seller URL shows an actionable error', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Company name or website', { exact: true }).fill('https://127.1');
  await page.getByRole('button', { name: 'Start research' }).click();
  await expect(page.getByRole('alert')).toContainText('Check the fields');
  await expect(page.getByLabel('Company name or website', { exact: true })).toHaveValue('https://127.1');
});

test('optional demo explains evidence without creating research', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('region', { name: 'See how a shortlist takes shape.' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Try the demo', exact: true }).click();
  const demo = page.getByRole('region', { name: 'See how a shortlist takes shape.' });
  if (await demo.locator('.demo-stage-list').getAttribute('open') === null) {
    await demo.locator('.demo-stage-list > summary').click();
  }
  await demo.getByRole('button', { name: /5 Inspect evidence/ }).click();
  await demo.getByRole('button', { name: 'Inspect example passage', exact: true }).press('Enter');
  await expect(demo.getByText('Synthetic example passage', { exact: true })).toBeVisible();
  await expect(demo.getByText('Illustrative sample · invented companies and passages · no live research')).toBeVisible();
  await noOverflow(page);
});
