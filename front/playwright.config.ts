import { defineConfig, devices } from '@playwright/test'

// Tests never make sound (the machine is in use while they run): every browser is muted.
const muted = {
  chromium: { launchOptions: { args: ['--mute-audio'] } },
  firefox: {
    launchOptions: { firefoxUserPrefs: { 'media.volume_scale': '0.0' } },
  },
  // WebKit has no mute switch: point it at no sound server, so GStreamer plays into a fake sink (media still advances).
  webkit: {
    launchOptions: {
      env: {
        ...process.env,
        PULSE_SERVER: 'unix:/nonexistent',
        PIPEWIRE_REMOTE: '/nonexistent',
      },
    },
  },
}

// `pnpm test:e2e` builds first and never reuses a running server, so tests always hit the latest code. The back test stack must be up (`docker compose -f compose.yaml -f compose.test.yaml up -d --wait` in back/), or the rate limits answer 429.
export default defineConfig({
  testDir: 'e2e',
  forbidOnly: !!process.env.CI,
  // CI runner: 4 vCPUs (default would be 2); one is left for next-server and the Compose stack.
  workers: process.env.CI ? 3 : undefined,
  reporter: process.env.CI ? 'github' : 'list',
  // Reduced motion: no entrance fades or card stagger, so axe and the contrast check never
  // measure a half-faded element.
  use: { baseURL: 'http://localhost:3000', reducedMotion: 'reduce' },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], ...muted.chromium },
    },
    // Longer timeout: next-themes reads localStorage, which stalls navigations for seconds in fresh Firefox profiles under load.
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'], ...muted.firefox },
      timeout: 60_000,
    },
    { name: 'webkit', use: { ...devices['Desktop Safari'], ...muted.webkit } },
    {
      name: 'mobile-safari',
      use: { ...devices['iPhone 15'], ...muted.webkit },
    },
  ],
  webServer: {
    command: 'pnpm start',
    url: 'http://localhost:3000',
    reuseExistingServer: false,
  },
})
