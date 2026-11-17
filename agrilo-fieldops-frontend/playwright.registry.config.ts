import { defineConfig } from '@playwright/test'
import base from './playwright.home.config'
export default defineConfig({ ...base, testMatch: 'registry-backend.spec.ts', timeout: 180000, expect: { timeout: 15000 },
  outputDir: 'test-results-registry', reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report-registry' }]],
  use: { ...base.use, baseURL: 'http://127.0.0.1:5180', actionTimeout: 15000, navigationTimeout: 30000 },
  webServer: { command: 'npm run dev -- --port 5180 --strictPort', url: 'http://127.0.0.1:5180', reuseExistingServer: false, timeout: 40000 },
})
