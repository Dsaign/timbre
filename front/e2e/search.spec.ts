import { expect, test, type Page } from '@playwright/test'
import { gridColumns, pageSizeFor } from '../lib/grid'

// Needs the back stack with the seed Catalog and its vectors built (see playwright.config.ts).
const DESCRIPTION = 'músicas alegres e dançantes para uma festa'

async function search(page: Page) {
  // networkidle: wait for hydration, or the form submits natively without n
  await page.goto('/', { waitUntil: 'networkidle' })
  await page
    .getByRole('textbox', { name: 'Descreva sua música favorita' })
    .fill(DESCRIPTION)
  await page.getByRole('button', { name: 'Pesquisar' }).click()
}

const cardsOf = (page: Page) =>
  page.getByRole('list', { name: 'Músicas' }).getByRole('listitem')

/** Cards on the first grid row, i.e. the rendered column count. */
const renderedColumns = (page: Page) =>
  cardsOf(page).evaluateAll((items) => {
    const top = items[0].getBoundingClientRect().top
    return items.filter((li) => li.getBoundingClientRect().top === top).length
  })

for (const viewport of [
  { width: 375, height: 667 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
]) {
  test.describe(`at ${viewport.width}px`, () => {
    test.use({ viewport })

    test('the grid fills the screen and "carregar mais" appends the next page', async ({
      page,
    }) => {
      const n = pageSizeFor(viewport.width, viewport.height)
      await search(page)

      await expect(page).toHaveURL(
        new RegExp(`\\?q=m%C3%BAsicas\\+[^&]*&n=${n}$`)
      )
      const status = page.getByRole('status')
      await expect(status).toHaveText(/^\d+ músicas? encontradas?$/)
      const count = parseInt((await status.textContent()) ?? '')
      const cards = cardsOf(page)
      await expect(cards).toHaveCount(Math.min(n, count))
      expect(await renderedColumns(page)).toBe(gridColumns(viewport.width))
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollWidth <=
            document.documentElement.clientWidth
        )
      ).toBe(true)

      const url = page.url()
      await page.getByRole('button', { name: 'Carregar mais' }).click()
      await expect(cards).toHaveCount(Math.min(2 * n, count))
      await expect(cards.nth(n)).toBeFocused()
      expect(page.url()).toBe(url)

      // Resizing only reflows: the column count follows and no request is made.
      const requests: string[] = []
      page.on('request', (request) => requests.push(request.url()))
      const other = viewport.width === 1440 ? 375 : 1440
      await page.setViewportSize({ width: other, height: viewport.height })
      await expect.poll(() => renderedColumns(page)).toBe(gridColumns(other))
      expect(requests).toEqual([])
    })
  })
}

test.describe('without JavaScript', () => {
  test.use({ javaScriptEnabled: false })

  // Streamed results need JavaScript to be revealed, so count the skeleton's cards.
  test('the form submits only q and the page uses N = 24', async ({ page }) => {
    await search(page)
    await expect(page).toHaveURL(/\?q=m%C3%BAsicas\+[^&]*$/)
    await expect(
      page.getByLabel('Carregando resultados').locator('.grid > *')
    ).toHaveCount(24)
  })
})
