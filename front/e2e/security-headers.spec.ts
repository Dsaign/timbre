import { expect, test, type Page } from '@playwright/test'

const SEARCH = `/?q=${encodeURIComponent('músicas alegres e dançantes para uma festa')}&n=4`
const POLICY =
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://open.spotify.com https://embed-cdn.spotifycdn.com; frame-src https://open.spotify.com; frame-ancestors 'none'"

test('every page sends the security headers', async ({ request }) => {
  for (const path of ['/', SEARCH]) {
    const headers = (await request.get(path)).headers()
    expect(headers['content-security-policy-report-only']).toBe(POLICY)
    expect(headers['strict-transport-security']).toMatch(/^max-age=\d+/)
    expect(headers['x-content-type-options']).toBe('nosniff')
    expect(headers['referrer-policy']).toBe('strict-origin-when-cross-origin')
    expect(headers['permissions-policy']).toBe(
      'camera=(), microphone=(), geolocation=()'
    )
  }
})

/** Opens the search with timbre's Report-Only policy served as enforced; returns its violations. */
async function searchUnderEnforcedPolicy(page: Page, baseURL: string) {
  // WebKit ignores Report-Only without report-to, so enforcing is the only way every browser reports.
  await page.route(
    (url) => url.origin === new URL(baseURL).origin,
    async (route) => {
      if (route.request().resourceType() !== 'document') return route.fallback()
      const response = await route.fetch()
      const headers = response.headers()
      const policy = headers['content-security-policy-report-only']
      if (!policy) return route.fulfill({ response }) // fails on the exact-policy check below
      delete headers['content-security-policy-report-only']
      await route.fulfill({
        response,
        headers: { ...headers, 'content-security-policy': policy },
      })
    }
  )
  const consoleMessages: string[] = []
  page.on('console', (message) => {
    if (/Content.Security.Policy/i.test(message.text()))
      consoleMessages.push(message.text())
  })
  await page.addInitScript(() => {
    const seen: string[] = ((
      window as unknown as { cspViolations: string[] }
    ).cspViolations = [])
    document.addEventListener('securitypolicyviolation', (e) =>
      seen.push(
        `${e.violatedDirective} ${e.blockedURI} ${e.sourceFile}:${e.lineNumber}`
      )
    )
  })

  const response = await page.goto(SEARCH)
  // The server sent the policy as Report-Only and this page enforces exactly that value.
  expect(response?.headers()['content-security-policy']).toBe(POLICY)
  await expect(
    page.getByRole('list', { name: 'Músicas' }).getByRole('listitem').first()
  ).toBeVisible()
  await page.waitForLoadState('networkidle') // late chunks and hydration have run; no embed yet

  // Read in the page, so violations fired just before this call are included.
  return async () => [
    ...(await page.evaluate(
      () => (window as unknown as { cspViolations: string[] }).cspViolations
    )),
    ...consoleMessages,
  ]
}

const FIREFOX_SKIP =
  "Playwright's route interception of the next-themes chunk keeps Firefox from reaching networkidle"

test('searching breaks no CSP rule, enforced', async ({
  page,
  baseURL,
  browserName,
}) => {
  test.skip(browserName === 'firefox', FIREFOX_SKIP)
  const violations = await searchUnderEnforcedPolicy(page, baseURL!)
  expect(await violations()).toEqual([])
})

test('Preview breaks no CSP rule, enforced', async ({
  page,
  baseURL,
  browserName,
}) => {
  test.skip(browserName === 'firefox', FIREFOX_SKIP)
  test.skip(
    !process.env.SPOTIFY_CLIENT_ID,
    'Preview needs SPOTIFY_CLIENT_ID (and the back started with the Spotify secrets)'
  )
  test.slow() // Spotify's embed loads slower outside Chromium, as in preview.spec.ts
  const violations = await searchUnderEnforcedPolicy(page, baseURL!)
  await page
    .getByRole('list', { name: 'Músicas' })
    .getByRole('listitem')
    .first()
    .getByRole('button', { name: /^Prévia de/ })
    .click()
  // Settled once the embed exists: the API creates it after its scripts ran. Playback: ticket 17.
  await page
    .frameLocator('iframe[src^="https://open.spotify.com/embed/"]')
    .locator('body')
    .waitFor({ timeout: 20_000 })
  expect(await violations()).toEqual([])
})
