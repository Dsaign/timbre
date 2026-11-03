import { expect, test } from '@playwright/test'

// Labels are pt-BR by spec (UI is pt-BR only); these assertions must change if a UI language switch is ever added.
test('home page shows the search form', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'timbre.' })).toBeVisible()
  await expect(
    page.getByRole('textbox', { name: 'Descreva sua música favorita' })
  ).toBeVisible()
  await expect(page.getByRole('button', { name: 'Pesquisar' })).toBeVisible()
})

test('home page offers six keyboard-reachable sample Descriptions', async ({
  page,
}) => {
  await page.goto('/', { waitUntil: 'networkidle' })
  const samples = page
    .getByRole('list', { name: 'Exemplos de descrição' })
    .getByRole('link')
  await expect(samples).toHaveCount(6)
  await page.getByRole('button', { name: 'Pesquisar' }).focus()
  await page.keyboard.press('Tab')
  await expect(samples.first()).toBeFocused()
})
