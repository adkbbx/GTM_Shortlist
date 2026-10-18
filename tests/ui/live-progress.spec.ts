import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test('an active run shows its live step, a moving timer and an estimate, and keeps the view on the current stage', async ({ page }, info) => {
  const { id } = await (await page.request.post('/__fixture_held_run')).json();
  try {
    await page.goto(`/?run=${id}`);
    const live = page.locator('.live-progress');
    await expect(live).toBeVisible({ timeout: 15000 });
    await expect(live.locator('.live-step')).toContainText(/Reading|Searching|Assessing|Checking|Understanding|Waiting|Saving/);
    const elapsed = live.locator('.live-elapsed');
    const first = await elapsed.textContent();
    await expect.poll(() => elapsed.textContent(), { timeout: 5000 }).not.toBe(first);
    // While the live row shows, every stage button is locked to the current step.
    await expect(page.locator('.stage-review:not([aria-disabled="true"])')).toHaveCount(0);
    await expect(page.locator('.demo-rail-note')).toContainText('Following the current step');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    mkdirSync('.impeccable/review', { recursive: true });
    await page.screenshot({ path: `.impeccable/review/${info.project.name}-live-progress.png`, fullPage: true });
  } finally {
    await page.request.post(`/__fixture_release/${id}`);
  }
  // Once the run finishes, the live row goes and earlier stages open again.
  await expect(page.locator('.live-progress')).toHaveCount(0, { timeout: 30000 });
});

test('motion stops for visitors who reduce motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const { id } = await (await page.request.post('/__fixture_held_run')).json();
  try {
    await page.goto(`/?run=${id}`);
    const pulse = page.locator('.live-pulse');
    await expect(pulse).toBeVisible({ timeout: 15000 });
    expect(await pulse.evaluate(element => getComputedStyle(element).animationName)).toBe('none');
  } finally {
    await page.request.post(`/__fixture_release/${id}`);
  }
});
