import { defineConfig } from '@playwright/test';

const python = process.platform === 'win32' ? '.venv\\Scripts\\python.exe' : '.venv/bin/python';
const hosted = Boolean(process.env.SHORTLIST_UI_TEST_PG_URL);
export default defineConfig({
  testDir: './tests/ui', timeout: 45000, fullyParallel: false, workers: 1,
  use: { baseURL: 'http://127.0.0.1:8015', trace: 'retain-on-failure' },
  projects: [
    { name: 'laptop', testIgnore: /credits.spec.ts/, use: { viewport: { width: 1366, height: 900 } } },
    { name: 'phone', testIgnore: /credits.spec.ts/, use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
    ...(hosted ? [
      { name: 'hosted-laptop', testMatch: /credits.spec.ts/, use: { baseURL: 'https://app.example', viewport: { width: 1366, height: 900 } } },
      { name: 'hosted-phone', testMatch: /credits.spec.ts/, use: { baseURL: 'https://app.example', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
    ] : []),
  ],
  webServer: [
    { command: `${python} scripts/ui_test_server.py`, url: 'http://127.0.0.1:8015/api/health', reuseExistingServer: false },
    ...(hosted ? [{ command: `${python} scripts/hosted_ui_test_server.py`, url: 'http://127.0.0.1:8016/__fixture_ready', reuseExistingServer: false }] : []),
  ],
});
