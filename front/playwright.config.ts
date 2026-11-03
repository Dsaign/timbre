import { defineConfig, devices } from '@playwright/test'

// `pnpm test:e2e` builds first and never reuses a running server, so tests always hit the latest code. The back test stack must be up (`docker compose -f compose.yaml -f compose.test.yaml up -d --wait` in back/), or the rate limits answer 429.
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
