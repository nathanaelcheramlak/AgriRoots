import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', testIgnore: ['**/workspace-layout.spec.ts', '**/territory.spec.ts'], fullyParallel: false, workers: 1, retries: 0, timeout: 40000,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:5175', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], channel: 'chromium', ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { launchOptions: { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } } : {}), viewport: { width: 1440, height: 1000 } } }],
  webServer: { command: 'npm run dev', url: 'http://127.0.0.1:5175', reuseExistingServer: !process.env.CI, timeout: 30000 },
})
