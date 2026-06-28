import { defineConfig, devices } from '@playwright/test';

// e2e 針對「已啟動的整體 stack」執行（docker compose up 後的 http://localhost:8501）。
// 預設不自管 webServer；可用 E2E_BASE_URL 覆寫目標。
const baseURL = process.env.E2E_BASE_URL || 'http://localhost:8501';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL,
    // retries=0，用 retain-on-failure 才會在失敗時留下 trace 供除錯。
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
