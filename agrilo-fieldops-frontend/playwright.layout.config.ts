import { defineConfig } from '@playwright/test'
import base from './playwright.home.config'

// Visual/layout tests use bounded HTTP fixtures, never a real office account.
export default defineConfig({
  ...base,
  testMatch: ['workspace-layout.spec.ts', 'territory.spec.ts'],
  outputDir: 'test-results-layout',
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report-layout' }]],
  use: { ...base.use, baseURL: 'http://127.0.0.1:5177' },
  webServer: {
    command: 'npm run dev -- --port 5177 --strictPort',
    url: 'http://127.0.0.1:5177', reuseExistingServer: false, timeout: 40000,
    env: { VITE_API_MODE: 'http', VITE_API_BASE_URL: '/backend' },
  },
})
