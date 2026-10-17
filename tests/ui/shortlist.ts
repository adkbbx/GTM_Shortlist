import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

/** The shortlist is ordered by evidence, not research order; find a company by the name shown in its row. */
export async function openCompanyNamed(page: Page, name: string) {
  const company = page.locator('.company-item').filter({ has: page.locator('.shortlist-name', { hasText: name }) });
  if (await company.getAttribute('open') === null) await company.locator('.company-row').click();
  await expect(company).toHaveAttribute('open', '');
  return company;
}

export async function openCompany(page: Page, index = 0) {
  const company = page.locator('.company-item').nth(index);
  if (await company.getAttribute('open') === null) await company.locator('.company-row').click();
  await expect(company).toHaveAttribute('open', '');
  return company;
}
