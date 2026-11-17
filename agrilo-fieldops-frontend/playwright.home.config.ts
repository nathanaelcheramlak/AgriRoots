import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  outputDir: 'test-results-home',
  testDir: './e2e', testMatch: 'home-backend.spec.ts', fullyParallel: false, workers: 1, retries: 0, timeout: 60000,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report-home' }]],
  use: { baseURL: 'http://127.0.0.1:5176', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], channel: 'chromium', ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { launchOptions: { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } } : {}), viewport: { width: 1440, height: 1000 } } }],
  webServer: { command: 'npm run dev -- --port 5176 --strictPort', url: 'http://127.0.0.1:5176', reuseExistingServer: false, timeout: 40000 },
})
