import { expect, test } from '@playwright/test';

test('workshop shader pauses, respects reduced motion and retains a static fallback', async ({ page }) => {
  await page.goto('/');
  const field = page.locator('.workshop-field');
  await expect(field).toBeVisible();
  await expect(field.locator('svg')).toBeVisible();
  const canvas = field.locator('canvas');
  await expect.poll(async () => field.getAttribute('data-enhanced')).toBe('true');
  await canvas.scrollIntoViewIfNeeded();
  await expect(canvas).toHaveAttribute('data-state', 'playing');
  await field.getByRole('button', { name: 'Pause visual', exact: true }).click();
  await expect(canvas).toHaveAttribute('data-state', 'static');
  await field.getByRole('button', { name: 'Play visual', exact: true }).click();
  await expect(canvas).toHaveAttribute('data-state', 'playing');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(canvas).toHaveAttribute('data-state', 'static');
  await expect(field.locator('svg')).toBeVisible();
  await page.setViewportSize({ width: 320, height: 844 });
  await page.locator('html').evaluate(element => { element.style.fontSize = '200%'; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('workshop remains usable with WebGL unavailable', async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, ...args: Parameters<typeof original>) {
      if (String(args[0]).startsWith('webgl')) return null;
      return original.apply(this, args);
    } as typeof original;
  });
  await page.goto('/');
  await expect(page.locator('.workshop-field svg')).toBeVisible();
  await expect(page.locator('.workshop-field')).toHaveAttribute('data-enhanced', 'false');
  await expect(page.getByRole('button', { name: 'Start research', exact: true })).toBeEnabled();
});


test('decorative GPU work stops offscreen and resumes when visible again', async ({ page }) => {
  await page.goto('/');
  const canvas = page.locator('.workshop-field canvas');
  await canvas.scrollIntoViewIfNeeded();
  await expect(canvas).toHaveAttribute('data-state', 'playing');
  await page.getByRole('button', { name: 'Try the demo', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'See how a shortlist takes shape.' })).toBeVisible();
  await expect(canvas).toHaveAttribute('data-state', 'static');
  await canvas.scrollIntoViewIfNeeded();
  await expect(canvas).toHaveAttribute('data-state', 'playing');
});
