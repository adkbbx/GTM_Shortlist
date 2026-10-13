import { defineConfig } from '@playwright/test';

const python = process.platform === 'win32' ? '.venv\\Scripts\\python.exe' : '.venv/bin/python';
export default defineConfig({
  testDir: './tests/ui', timeout: 45000, fullyParallel: false, workers: 1,
  use: { baseURL: 'http://127.0.0.1:8015', trace: 'retain-on-failure' },
  projects: [
    { name: 'laptop', use: { viewport: { width: 1366, height: 900 } } },
    { name: 'phone', use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: { command: `${python} scripts/ui_test_server.py`, url: 'http://127.0.0.1:8015/api/health', reuseExistingServer: false },
});
