import { expect, test, type Locator, type Page } from '@playwright/test'

// Needs the back stack with the seed Catalog. Every project votes as the same visitor
// (localhost), so each one uses its own card to run in parallel.
const SEARCH = `/?q=${encodeURIComponent('músicas alegres e dançantes para uma festa')}&n=4`
const PROJECTS = ['chromium', 'firefox', 'webkit', 'mobile-safari']

/** Press a thumb (by keyboard or click), wait for back to store the vote, then reload. */
async function press(page: Page, thumb: Locator, by: 'click' | 'keyboard') {
  const stored = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.ok()
  )
  if (by === 'keyboard') {
    await thumb.focus()
    await page.keyboard.press('Enter')
  } else await thumb.click()
  await stored
  await page.reload()
}

test('a vote is highlighted, withdrawn and switched, and survives a reload', async ({
  page,
}, testInfo) => {
  const card = page
    .getByRole('list', { name: 'Músicas' })
    .getByRole('listitem')
    .nth(Math.max(0, PROJECTS.indexOf(testInfo.project.name)))
  const up = card.getByRole('button', { name: /^Combina: / })
  const down = card.getByRole('button', { name: /^Não combina: / })
  async function expectVote(vote: 'up' | 'down' | null) {
    await expect(up).toHaveAttribute('aria-pressed', String(vote === 'up'))
    await expect(down).toHaveAttribute('aria-pressed', String(vote === 'down'))
  }

  await page.goto(SEARCH)
  await expect(up).toBeVisible()
  // A run that failed midway may have left a vote: withdraw it first.
  for (const thumb of [up, down])
    if ((await thumb.getAttribute('aria-pressed')) === 'true')
      await press(page, thumb, 'click')
  await expectVote(null)

  await press(page, up, 'keyboard')
  await expectVote('up')

  await press(page, up, 'click') // the same thumb again withdraws
  await expectVote(null)

  await press(page, down, 'click')
  await expectVote('down')

  await press(page, up, 'click') // the other thumb switches
  await expectVote('up')

  await press(page, up, 'click') // leave no vote behind
  await expectVote(null)
})
