import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

// The frame is full-bleed and the root size follows clamp(100%, min(.8vw, 1.45vh), 200%), so 1080p, 1440p and 4K
// monitors show the same proportions instead of a small island in the middle of the screen.
const expectedRoot = (width: number, height: number) => Math.min(32, Math.max(16, Math.min(width * 0.008, height * 0.0145)));

for (const [width, height] of [[1920, 1080], [2560, 1440], [3840, 2160]]) {
  test(`workspace and landing hold their layout at ${width}x${height}`, async ({ page }, info) => {
    test.skip(info.project.name !== 'laptop', 'Desktop monitor sizes only.');
    await page.setViewportSize({ width, height });
    await page.goto('/');
    await expect(page.getByLabel('Company name or website', { exact: true })).toBeVisible();
    const frame = await page.evaluate(() => {
      const bar = document.querySelector('header.topbar')!.getBoundingClientRect();
      return { left: bar.left, width: bar.width, overflow: document.documentElement.scrollWidth > innerWidth + 1, root: parseFloat(getComputedStyle(document.documentElement).fontSize) };
    });
    expect(frame.left).toBe(0);
    expect(Math.round(frame.width)).toBe(width);
    expect(frame.overflow).toBe(false);
    expect(frame.root).toBeCloseTo(expectedRoot(width, height), 1);
    mkdirSync('.impeccable/review', { recursive: true });
    await page.screenshot({ path: `.impeccable/review/workspace-${width}x${height}.png` });

    await page.goto('/?landing=1');
    await expect(page.locator('#pl-hero-title')).toBeVisible();
    await page.waitForTimeout(2000);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    const hero = await page.evaluate(() => {
      const box = (selector: string) => document.querySelector(selector)!.getBoundingClientRect();
      return { intake: box('.pl-intake'), shortlist: box('.pl-shortlist'), viewport: innerHeight };
    });
    // The company card and the shortlist sit on one centre line and fit the first screen.
    expect(Math.abs((hero.intake.top + hero.intake.bottom) / 2 - (hero.shortlist.top + hero.shortlist.bottom) / 2)).toBeLessThan(2);
    expect(hero.shortlist.bottom).toBeLessThan(hero.viewport);
    await page.screenshot({ path: `.impeccable/review/landing-${width}x${height}.png` });
  });
}
