import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

export async function openCompany(page: Page, index = 0) {
  const company = page.locator('.company-item').nth(index);
  if (await company.getAttribute('open') === null) await company.locator('.company-row').click();
  await expect(company).toHaveAttribute('open', '');
  return company;
}
