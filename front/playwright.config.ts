import { defineConfig } from '@playwright/test'

// Runs against `pnpm start`, so run `pnpm build` first. The back must be up (`docker compose up -d --wait` in back/).
export default defineConfig({
  testDir: 'e2e',
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? 'github' : 'list',
  use: { baseURL: 'http://localhost:3000' },
  webServer: {
    command: 'pnpm start',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
})
