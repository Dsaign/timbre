import { expect, test, type Page } from '@playwright/test'
import { gridColumns, pageSizeFor } from '../lib/grid'

// Needs the back stack with the seed Catalog and its vectors built (see playwright.config.ts).
const DESCRIPTION = 'músicas alegres e dançantes para uma festa'

const textbox = (page: Page) =>
  page.getByRole('textbox', { name: 'Descreva sua música favorita' })

async function search(page: Page, description = DESCRIPTION) {
  // networkidle: wait for hydration, or the form submits natively without n
  await page.goto('/', { waitUntil: 'networkidle' })
  await textbox(page).fill(description)
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
      const n = pageSizeFor(viewport)
      await search(page)

      await expect(page).toHaveURL(
        new RegExp(`\\?q=m%C3%BAsicas\\+[^&]*&n=${n}$`)
      )
      const status = page.getByRole('status')
      await expect(status).toHaveText(/^\d+ músicas? encontradas?$/)
      const count = parseInt((await status.textContent()) ?? '')
      const cards = cardsOf(page)
      await expect(cards).toHaveCount(Math.min(n, count))
      expect(await renderedColumns(page)).toBe(gridColumns(viewport))
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

      // Resizing only reflows: the column count follows and no request is made. Covers are
      // left out: a lazy cover that a wider grid brings into view loads then (Firefox).
      const requests: string[] = []
      page.on('request', (request) => {
        if (request.resourceType() !== 'image') requests.push(request.url())
      })
      const other = viewport.width === 1440 ? 375 : 1440
      await page.setViewportSize({ width: other, height: viewport.height })
      await expect
        .poll(() => renderedColumns(page))
        .toBe(gridColumns({ width: other, height: viewport.height }))
      expect(requests).toEqual([])
    })
  })
}

test('no Matches offers sample Descriptions; a sample searches in one click', async ({
  page,
}) => {
  await search(page, 'qzxjvkwpfhgtbnmlrd')
  await expect(page.getByRole('status')).toHaveText('Nenhuma música encontrada')

  await page
    .getByRole('link', { name: 'violão calmo para estudar', exact: true })
    .click()
  await expect(textbox(page)).toHaveValue('violão calmo para estudar')
  await expect(page.getByRole('status')).toHaveText(
    /^\d+ músicas? encontradas?$/
  )
  await expect(cardsOf(page).first()).toBeVisible()
})

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
