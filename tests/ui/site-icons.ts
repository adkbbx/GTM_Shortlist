import type { Page } from '@playwright/test';

/** Substitute image bytes at both React image source assignment boundaries. */
export async function installIconFixtures(page: Page, fixtures: Record<string, string | null>) {
  await page.addInitScript(fixtures => {
    const iconValue = (image: HTMLImageElement, value: string) => {
      if (!(value in fixtures)) return value;
      image.dataset.requestedIcon = value;
      return fixtures[value] ?? 'data:image/png;base64,invalid';
    };
    const original = Element.prototype.setAttribute;
    Element.prototype.setAttribute = function (name: string, value: string) {
      original.call(this, name, this instanceof HTMLImageElement && name === 'src' ? iconValue(this, value) : value);
    };
    const descriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src')!;
    Object.defineProperty(HTMLImageElement.prototype, 'src', { ...descriptor, set(value: string) {
      descriptor.set!.call(this, iconValue(this, value));
    } });
  }, fixtures);
}

export const syntheticIcon = (color: string) => 'data:image/svg+xml,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><rect width="24" height="24" rx="5" fill="${color}"/><path d="M7 8h10M7 12h7M7 16h10" stroke="white" stroke-width="2"/></svg>`);
