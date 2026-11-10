import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { lowContrastText } from './contrast'

const SEARCH = `/?q=${encodeURIComponent('músicas alegres e dançantes para uma festa')}&n=4`
const SCHEMES = ['light', 'dark'] as const
type Scheme = (typeof SCHEMES)[number]

const html = (page: Page) => page.locator('html')
const themeClass = (scheme: Scheme) => new RegExp(`\\b${scheme}\\b`)
const toggle = (page: Page) =>
  page.getByRole('button', { name: 'Alternar tema claro/escuro' })
const cards = (page: Page) =>
  page.getByRole('list', { name: 'Músicas' }).getByRole('listitem')

/** Opens a path in a theme and waits until the grid (if any) is there. */
async function open(page: Page, path: string, scheme: Scheme) {
  await page.goto(path, { waitUntil: 'networkidle' })
  if (path !== '/') await expect(cards(page).first()).toBeVisible()
  await expect(html(page)).toHaveClass(themeClass(scheme))
}

/** axe finds nothing, and every text run reaches AA against what is really rendered behind it. */
async function expectAccessible(page: Page, label: string) {
  // Spotify's embed is a third-party document timbre cannot change.
  const { violations } = await new AxeBuilder({ page })
    .exclude('iframe')
    .analyze()
  expect(violations, label).toEqual([])
  expect(await lowContrastText(page), label).toEqual([])
}

test('follows the system theme by default', async ({ page }) => {
  for (const scheme of SCHEMES) {
    await page.emulateMedia({ colorScheme: scheme })
    await page.goto('/')
    await expect(html(page)).toHaveClass(themeClass(scheme))
  }
})

test('the toggle switches the theme and the choice survives a reload', async ({
  page,
  context,
}) => {
  await page.emulateMedia({ colorScheme: 'light' })
  await open(page, '/', 'light')
  await toggle(page).click()
  await expect(html(page)).toHaveClass(themeClass('dark'))

  await page.reload()
  await expect(html(page)).toHaveClass(themeClass('dark'))
  expect(await page.evaluate(() => localStorage.getItem('theme'))).toBe('dark')
  expect(await context.cookies()).toEqual([]) // local storage only

  await toggle(page).click()
  await expect(html(page)).toHaveClass(themeClass('light'))
})

test('the stored theme applies before any app JavaScript runs (no flash)', async ({
  page,
}) => {
  await page.emulateMedia({ colorScheme: 'light' })
  await page.addInitScript(() => localStorage.setItem('theme', 'dark'))
  // Without the app's bundles React never hydrates: only next-themes' inline script can set the class.
  await page.route('**/_next/static/**/*.js', (route) => route.abort())
  await page.goto('/')
  await expect(html(page)).toHaveClass(themeClass('dark'))
  await expect(html(page)).toHaveCSS('color-scheme', 'dark')
})

for (const scheme of SCHEMES) {
  test(`the ${scheme} theme is accessible, contrast included`, async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: scheme })
    for (const path of ['/', SEARCH]) {
      await open(page, path, scheme)
      await expectAccessible(page, path)
    }
  })

  test(`the ${scheme} theme is accessible with the docked player open`, async ({
    page,
  }) => {
    test.skip(
      !process.env.SPOTIFY_CLIENT_ID,
      'Preview needs SPOTIFY_CLIENT_ID (and the back started with the Spotify secrets)'
    )
    test.slow() // Spotify's embed loads slower outside Chromium, as in preview.spec.ts
    await page.emulateMedia({ colorScheme: scheme })
    await open(page, SEARCH, scheme)
    await cards(page)
      .first()
      .getByRole('button', { name: /^Prévia de/ })
      .click()
    await expect(
      page.getByRole('region', { name: 'Prévia no Spotify' })
    ).toBeVisible()
    await page
      .frameLocator('iframe[src^="https://open.spotify.com/embed/"]')
      .locator('body')
      .waitFor({ timeout: 20_000 })
    await expectAccessible(page, 'docked player')
  })

  test(`prefers-reduced-transparency turns the ${scheme} surfaces solid`, async ({
    page,
    browserName,
  }) => {
    test.skip(
      browserName !== 'chromium',
      'only Chromium can emulate prefers-reduced-transparency (through CDP)'
    )
    const cdp = await page.context().newCDPSession(page)
    // This call replaces every emulated media feature, so it sets the colour scheme too.
    await cdp.send('Emulation.setEmulatedMedia', {
      features: [
        { name: 'prefers-color-scheme', value: scheme },
        { name: 'prefers-reduced-transparency', value: 'reduce' },
      ],
    })
    await open(page, SEARCH, scheme)
    // The floating player has no surface of its own: it is only Spotify's embed.
    for (const surface of [
      page.getByRole('banner'), // compact search bar
      page.getByRole('region', { name: 'Resultados' }),
      cards(page).first().locator('[data-slot=card]'),
    ]) {
      await expect(surface).toHaveCSS('backdrop-filter', 'none')
      // Opaque: no "/ alpha" in the computed colour.
      expect(
        await surface.evaluate((el) => getComputedStyle(el).backgroundColor)
      ).not.toMatch(/\/\s*[\d.]+\)|transparent|rgba/)
    }
    await expectAccessible(page, 'reduced transparency')
  })
}
