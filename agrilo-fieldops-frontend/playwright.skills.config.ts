import { defineConfig } from '@playwright/test'
import home from './playwright.home.config'
export default defineConfig({ ...home, testMatch: ['home-backend.spec.ts', 'plugins-backend.spec.ts', 'skills-backend.spec.ts'], outputDir: 'test-results-skills',
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report-skills' }]],
})
