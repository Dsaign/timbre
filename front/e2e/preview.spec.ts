import { expect, test, type Locator, type Page } from '@playwright/test'

// Real Spotify: the back looks Songs up with its Client Credentials (a card's Prévia button needs
// that track id) and the page loads Spotify's iFrame API. CI has the secret except on Dependabot and fork PRs.
test.skip(
  !process.env.SPOTIFY_CLIENT_ID,
  'needs SPOTIFY_CLIENT_ID (and the back started with the Spotify secrets)'
)

const SEARCH = `/?q=${encodeURIComponent('músicas alegres e dançantes para uma festa')}&n=4`
// includeHidden: once home the dock is display:none, and its pause must still be checked.
const dockOf = (page: Page) =>
  page.getByRole('region', { name: 'Prévia no Spotify', includeHidden: true })
const cardsOf = (page: Page) =>
  page.getByRole('list', { name: 'Músicas' }).getByRole('listitem')

// One click on Prévia plays in Chromium. Firefox and WebKit block the embed's play(), so the dock asks
// for the embed's own play button (ticket 17, docs/research/spotify-embed-autoplay.md).
const PROMPT = 'Toque em ▶ no player do Spotify para ouvir'
async function expectPlaying(page: Page, browserName: string) {
  const dock = dockOf(page)
  if (browserName !== 'chromium') {
    // Firefox may allow play() after all (see the research), so either outcome is fine.
    const prompt = dock.getByText(PROMPT)
    const playing = dock.and(page.locator('[data-paused="false"]'))
    await expect(prompt.or(playing).first()).toBeVisible({ timeout: 20_000 })
    if (
      (await prompt.isVisible()) &&
      (await dock.getAttribute('data-paused')) === 'true'
    ) {
      // Spotify's test id: the button's accessible name is localized ("Play" / "Pause").
      await page
        .frameLocator('iframe[src^="https://open.spotify.com/embed/"]')
        .getByTestId('play-pause-button')
        .click()
    }
  }
  await expect(dock).toHaveAttribute('data-paused', 'false', {
    timeout: 20_000,
  })
  // Once playing, the prompt is gone (in Chromium it never shows).
  await expect(dock.getByText(PROMPT)).toBeHidden()
}

test.describe('playback', () => {
  // Spotify's embed loads slower outside Chromium (Firefox, WebKit); two cards can exceed 30s.
  test.slow()

  for (const viewport of [
    { width: 375, height: 667 },
    { width: 768, height: 1024 },
    { width: 1440, height: 900 },
  ]) {
    test(`at ${viewport.width}px Preview plays the card's track in the one docked player`, async ({
      page,
      browserName,
    }) => {
      await page.setViewportSize(viewport)
      await page.goto(SEARCH)
      const cards = cardsOf(page)
      const dock = dockOf(page)

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
        await expectPlaying(page, browserName)
        await expect(dock).toHaveAttribute(
          'data-playing-uri',
          `spotify:track:${trackId}`
        )
        // The card shows that its track is the one playing; its name follows the visible text.
        await expect(
          card.getByRole('button', { name: /^Tocando / })
        ).toHaveText('Tocando')
      }
      await expect(page.locator('iframe')).toHaveCount(1)
    })
  }

  test('going home with the logo hides the player and pauses it', async ({
    page,
    browserName,
  }) => {
    await page.goto(SEARCH)
    const dock = dockOf(page)
    await cardsOf(page)
      .first()
      .getByRole('button', { name: /^Prévia de/ })
      .click()
    await expectPlaying(page, browserName)

    await page
      .getByRole('banner')
      .getByRole('link', { name: /página inicial/ })
      .click()
    await expect(page).toHaveURL(/\/$/)
    await expect(dock).toBeHidden()
    await expect(dock).toHaveAttribute('data-paused', 'true', {
      timeout: 20_000,
    })
  })

  test("going back to home with the browser's Back hides the player and pauses it", async ({
    page,
    browserName,
  }) => {
    await page.goto('/', { waitUntil: 'networkidle' })
    await page
      .getByRole('link', {
        name: 'músicas alegres e dançantes para uma festa',
        exact: true,
      })
      .click()
    const dock = dockOf(page)
    await cardsOf(page)
      .first()
      .getByRole('button', { name: /^Prévia de/ })
      .click()
    await expectPlaying(page, browserName)

    await page.goBack()
    await expect(page).toHaveURL(/\/$/)
    await expect(dock).toBeHidden()
    await expect(dock).toHaveAttribute('data-paused', 'true', {
      timeout: 20_000,
    })
  })
})

test('the open dock takes its own space between the cards area and the footer', async ({
  page,
}) => {
  // A phone: four cards overflow once the dock takes its room, so the last one has to scroll into view.
  await page.setViewportSize({ width: 375, height: 667 })
  await page.goto(SEARCH)
  const cards = cardsOf(page)
  await cards
    .first()
    .getByRole('button', { name: /^Prévia de/ })
    .click()
  const dock = dockOf(page)
  await expect(dock).toBeVisible()

  const cardsArea = page.getByRole('main')
  expect(
    await cardsArea.evaluate((main) => main.scrollHeight > main.clientHeight)
  ).toBe(true)
  await cardsArea.evaluate((main) => main.scrollTo(0, main.scrollHeight))
  const box = async (locator: Locator) => (await locator.boundingBox())!
  const area = await box(cardsArea)
  const dockBox = await box(dock)
  const footer = await box(page.getByRole('contentinfo'))
  const lastCard = await box(cards.last())
  expect(area.y + area.height).toBeLessThanOrEqual(dockBox.y)
  expect(dockBox.y + dockBox.height).toBeLessThanOrEqual(footer.y)
  expect(footer.y + footer.height).toBeLessThanOrEqual(
    page.viewportSize()!.height
  )
  expect(lastCard.y).toBeGreaterThanOrEqual(area.y)
  expect(lastCard.y + lastCard.height).toBeLessThanOrEqual(area.y + area.height)
})
