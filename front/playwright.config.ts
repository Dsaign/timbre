import { defineConfig, devices } from '@playwright/test'

// `pnpm test:e2e` builds first and never reuses a running server, so tests always hit the latest code. The back must be up (`docker compose up -d --wait` in back/).
export default defineConfig({
  testDir: 'e2e',
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? 'github' : 'list',
  use: { baseURL: 'http://localhost:3000' },
  projects: [
    { name: 'chromium', use: devices['Desktop Chrome'] },
    { name: 'firefox', use: devices['Desktop Firefox'] },
    { name: 'webkit', use: devices['Desktop Safari'] },
    { name: 'mobile-safari', use: devices['iPhone 15'] },
  ],
  webServer: {
    command: 'pnpm start',
    url: 'http://localhost:3000',
    reuseExistingServer: false,
  },
})
