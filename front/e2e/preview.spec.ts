import { expect, test } from '@playwright/test'

// Real Spotify: the back looks Songs up with its Client Credentials and the page loads
// Spotify's iFrame API. CI has the secret except on Dependabot and fork PRs.
test.skip(
  !process.env.SPOTIFY_CLIENT_ID,
  'needs SPOTIFY_CLIENT_ID (and the back started with the Spotify secrets)'
)
// Spotify's embed loads slower outside Chromium (Firefox, WebKit); two cards can exceed 30s.
test.slow()
test.fixme(
  ({ browserName }) => browserName !== 'chromium',
  'Firefox and WebKit block the embed play(): .scratch/timbre-v1/issues/17-preview-autoplay-firefox-safari.md'
)

const SEARCH = `/?q=${encodeURIComponent('músicas alegres e dançantes para uma festa')}&n=4`

for (const viewport of [
  { width: 375, height: 667 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
]) {
  test(`at ${viewport.width}px Preview plays the card's track in the one docked player`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport)
    await page.goto(SEARCH)
    const cards = page
      .getByRole('list', { name: 'Músicas' })
      .getByRole('listitem')
    const dock = page.getByRole('region', { name: 'Prévia no Spotify' })

    // A second card switches the same player to its own track.
    for (const i of [0, 1]) {
      const card = cards.nth(i)
      const href = await card
        .getByRole('link', { name: /^Listen on Spotify: / })
        .getAttribute('href')
      const trackId = href?.match(
        /^https:\/\/open\.spotify\.com\/track\/([0-9A-Za-z]{22})$/
      )?.[1]
      expect(trackId).toBeTruthy()

      const preview = card.getByRole('button', { name: /^Prévia de/ })
      await preview.click()
      await expect(dock).toHaveAttribute(
        'data-playing-uri',
        `spotify:track:${trackId}`,
        { timeout: 20_000 }
      )
      await expect(dock).toHaveAttribute('data-paused', 'false', {
        timeout: 20_000,
      })
      // The card shows that its track is the one playing; its name follows the visible text.
      await expect(card.getByRole('button', { name: /^Tocando / })).toHaveText(
        'Tocando'
      )
    }
    await expect(page.locator('iframe')).toHaveCount(1)
  })
}
