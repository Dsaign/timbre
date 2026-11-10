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

test('after a search the form sits in the sticky compact bar, without the info note', async ({
  page,
}) => {
  await page.goto('/', { waitUntil: 'networkidle' })
  await expect(page.getByText(/^Descrições e votos/)).toBeVisible()
  await page
    .getByRole('textbox', { name: 'Descreva sua música favorita' })
    .fill('violão calmo para estudar')
  await page.getByRole('button', { name: 'Pesquisar' }).click()

  const bar = page.getByRole('banner')
  await expect(
    // "t." on small screens (mobile-safari), "timbre." otherwise.
    bar.getByRole('link', { name: /^(timbre|t)\. \(página inicial\)$/ })
  ).toHaveAttribute('href', '/')
  await expect(
    bar.getByRole('textbox', { name: 'Descreva sua música favorita' })
  ).toHaveValue('violão calmo para estudar')
  await expect(bar.getByRole('button', { name: 'Pesquisar' })).toBeVisible()
  await expect(
    bar.getByRole('button', { name: 'Alternar tema claro/escuro' })
  ).toBeVisible()
  await expect(bar).toHaveCSS('position', 'sticky')
  await expect(page.getByText(/^Descrições e votos/)).toHaveCount(0)
})
