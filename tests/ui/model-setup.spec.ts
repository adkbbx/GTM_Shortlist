import { expect, test } from '@playwright/test';
import { mkdirSync } from 'node:fs';

test('hosted model guide lists choices only on request and recovers from key and empty-list errors', async ({ page }, info) => {
  let lookups = 0;
  let saved = false;
  const serviceStarts: string[] = [];
  const health = () => ({ mode: 'local', search_ready: true, gemma_ready: saved, worker_online: false, local_search_error: null });
  page.on('request', request => { if (request.url().includes('/api/local/service/start')) serviceStarts.push(request.url()); });
  await page.route('**/api/health', route => route.fulfill({ json: health() }));
  await page.route('**/api/local/model/models', route => {
    lookups += 1;
    expect(route.request().postDataJSON().base_url).toBe('https://openrouter.ai/api/v1');
    if (lookups === 1) return route.fulfill({ status: 409, json: { detail: 'The server did not accept access. Check the API key and your provider account.' } });
    return route.fulfill({ json: { models: lookups === 2 ? [] : ['google/labelled-gemma-fixture'] } });
  });
  await page.route('**/api/local/model', route => {
    expect(route.request().postDataJSON()).toEqual({ base_url: 'https://openrouter.ai/api/v1', model: 'google/labelled-gemma-fixture', key: 'labelled-hosted-key-not-real' });
    saved = true;
    return route.fulfill({ json: health() });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Research model: Not configured', exact: true }).click();
  await page.getByRole('radio', { name: 'Hosted provider', exact: true }).check();
  await expect(page.getByRole('button', { name: 'Find available models', exact: true })).toBeDisabled();
  expect(lookups).toBe(0);
  await expect(page.getByRole('link', { name: 'OpenRouter API key', exact: true })).toHaveAttribute('href', 'https://openrouter.ai/settings/keys');
  const key = page.getByLabel('Model API key', { exact: true });
  await key.fill('labelled-hosted-key-not-real');
  await page.getByRole('button', { name: 'Find available models', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('did not accept access');
  await page.getByRole('button', { name: 'Find available models', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('No models were returned');
  await expect(page.getByRole('button', { name: 'Save research model', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Find available models', exact: true }).click();
  await page.getByLabel('Choose your Gemma model', { exact: true }).selectOption('google/labelled-gemma-fixture');
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-guided-hosted-model.png`, fullPage: true });
  await page.setViewportSize({ width: 320, height: 740 });
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(321);
  await page.getByRole('button', { name: 'Save research model', exact: true }).scrollIntoViewIfNeeded();
  await page.getByRole('button', { name: 'Save research model', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Research model: Configured', exact: true })).toBeFocused();
  expect(await page.evaluate(() => JSON.stringify([localStorage, sessionStorage]))).not.toContain('labelled-hosted-key-not-real');
  expect(serviceStarts).toEqual([]);
});

test('local presets and advanced manual fallback avoid guessing or automatic connection attempts', async ({ page }, info) => {
  let lookups = 0;
  page.on('request', request => { if (request.url().includes('/api/local/model/models')) lookups += 1; });
  await page.route('**/api/local/model', route => {
    expect(route.request().postDataJSON()).toEqual({ base_url: 'http://localhost:9000/v1', model: 'labelled-custom-gemma', key: '' });
    return route.fulfill({ json: { mode: 'local', search_ready: true, gemma_ready: true, worker_online: false, local_search_error: null } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: /^Research model:/ }).click();
  await page.getByRole('radio', { name: 'On this computer', exact: true }).check();
  await page.getByLabel('Which app runs your model?', { exact: true }).selectOption('ollama');
  await page.getByText('Change server address or authentication', { exact: true }).click();
  await expect(page.getByLabel('Server address', { exact: true })).toHaveValue('http://localhost:11434/v1');
  await page.getByLabel('Which app runs your model?', { exact: true }).selectOption('custom-local');
  await page.getByLabel('Server address', { exact: true }).fill('http://localhost:9000/v1');
  await page.getByText('Enter a model ID manually', { exact: true }).click();
  await page.getByLabel('Model ID', { exact: true }).fill('labelled-custom-gemma');
  await page.setViewportSize({ width: 320, height: 740 });
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(321);
  await page.getByRole('button', { name: 'Save research model', exact: true }).scrollIntoViewIfNeeded();
  mkdirSync('.impeccable/review', { recursive: true });
  await page.screenshot({ path: `.impeccable/review/${info.project.name}-guided-manual-model-large.png`, fullPage: true });
  await page.getByRole('button', { name: 'Save research model', exact: true }).click();
  expect(lookups).toBe(0);
});
