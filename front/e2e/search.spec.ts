import { expect, test } from '@playwright/test'

// Needs the back stack with the seed Catalog and its vectors built (see playwright.config.ts).
test('typing a Description and submitting shows the count and Matches', async ({
  page,
}) => {
  await page.goto('/')
  await page
    .getByRole('textbox', { name: 'Descreva sua música favorita' })
    .fill('músicas alegres e dançantes para uma festa')
  await page.getByRole('button', { name: 'Pesquisar' }).click()

  await expect(page).toHaveURL(/\?q=m%C3%BAsicas\+alegres/)
  await expect(page.getByRole('status')).toHaveText(
    /^\d+ músicas? encontradas?$/
  )
  const cards = page
    .getByRole('list', { name: 'Músicas' })
    .getByRole('listitem')
  await expect(cards).toHaveCount(24)
})
