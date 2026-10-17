import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

export async function openSettings(page: Page) {
  if (await page.getByRole('dialog', { name: 'Settings', exact: true }).isVisible()) return;
  const settings = page.getByRole('button', { name: 'Settings', exact: true });
  if ((page.viewportSize()?.width ?? 1366) <= 850) {
    const menu = page.getByRole('button', { name: 'Saved runs', exact: true });
    if (await menu.getAttribute('aria-expanded') !== 'true') await menu.click();
  }
  await settings.click();
  await expect(page.getByRole('dialog', { name: 'Settings', exact: true })).toBeVisible();
}

export async function openAccount(page: Page) {
  if (await page.getByRole('dialog', { name: 'Your account', exact: true }).isVisible()) return;
  const trigger = page.getByRole('button', { name: 'Open account tray', exact: true });
  if ((page.viewportSize()?.width ?? 1366) > 850) {
    await expect(trigger).toBeVisible();
    await trigger.click();
  }
  else {
    await page.getByRole('button', { name: 'Saved runs', exact: true }).click();
    await page.getByRole('button', { name: 'Account', exact: true }).click();
  }
  await expect(page.getByRole('dialog', { name: 'Your account', exact: true })).toBeVisible();
}
