import { expect, test } from '@playwright/test'

const SEARCH = `/?q=${encodeURIComponent('músicas alegres e dançantes para uma festa')}&n=4`

test('every page sends the security headers', async ({ request }) => {
  for (const path of ['/', SEARCH]) {
    const headers = (await request.get(path)).headers()
    expect(headers['content-security-policy-report-only']).toBe(
      "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://open.spotify.com https://embed-cdn.spotifycdn.com; frame-src https://open.spotify.com; frame-ancestors 'none'"
    )
    expect(headers['strict-transport-security']).toMatch(/^max-age=\d+/)
    expect(headers['x-content-type-options']).toBe('nosniff')
    expect(headers['referrer-policy']).toBe('strict-origin-when-cross-origin')
    expect(headers['permissions-policy']).toBe(
      'camera=(), microphone=(), geolocation=()'
    )
  }
})

test('searching and Preview break no CSP rule', async ({ page }) => {
  const violations: string[] = []
  page.on('console', (message) => {
    if (/Content.Security.Policy|Report Only/i.test(message.text()))
      violations.push(message.text())
  })
  await page.exposeFunction('reportViolation', (v: string) =>
    violations.push(v)
  )
  await page.addInitScript(() =>
    document.addEventListener('securitypolicyviolation', (e) =>
      (
        window as unknown as { reportViolation(v: string): void }
      ).reportViolation(
        `${e.violatedDirective} ${e.blockedURI} ${e.sourceFile}:${e.lineNumber}`
      )
    )
  )

  await page.goto(SEARCH)
  const card = page
    .getByRole('list', { name: 'Músicas' })
    .getByRole('listitem')
    .first()
  await expect(card).toBeVisible()
  // Preview loads Spotify's iFrame API script and its embed frame.
  if (process.env.SPOTIFY_CLIENT_ID) {
    await card.getByRole('button', { name: /^Prévia de/ }).click()
    await expect(
      page.locator('iframe[src^="https://open.spotify.com/"]')
    ).toBeAttached({
      timeout: 20_000,
    })
  }
  await page.waitForLoadState('networkidle')
  expect(violations).toEqual([])
})
