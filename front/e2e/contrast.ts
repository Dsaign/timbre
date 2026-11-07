import type { Page } from '@playwright/test'

type Run = {
  text: string
  color: string
  x: number
  y: number
  w: number
  h: number
  large: boolean
}

/**
 * Text below WCAG AA (4.5:1, or 3:1 for large text) against the pixels actually rendered behind it.
 * axe only reports "incomplete" over translucent, blurred or gradient backgrounds, so this measures
 * instead: it records every visible text run, hides all text, screenshots the page and compares each
 * text colour with the worst background pixel inside that run's box.
 * Fixed elements (the docked player) are left out of the screenshot: a full-page capture pins them
 * over whatever is below the first screen, which the visitor never sees covered (body padding).
 */
export async function lowContrastText(page: Page) {
  const runs: Run[] = await page.evaluate(() => {
    for (const el of document.body.querySelectorAll('*'))
      if (getComputedStyle(el).position === 'fixed')
        el.setAttribute('data-contrast-fixed', '')
    const found: Run[] = []
    const add = (text: string, el: Element, color: string, r: DOMRect) => {
      if (r.width < 2 || r.height < 2) return // visually hidden (sr-only)
      const cs = getComputedStyle(el)
      const size = parseFloat(cs.fontSize)
      found.push({
        text: text.trim().slice(0, 40),
        color,
        x: r.left + scrollX,
        y: r.top + scrollY,
        w: r.width,
        h: r.height,
        large: size >= 24 || (size >= 18.66 && Number(cs.fontWeight) >= 700),
      })
    }
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT
    )
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const el = node.parentElement
      if (!node.textContent?.trim() || !el) continue
      if (
        el.closest(
          '[aria-hidden="true"], [aria-disabled="true"], [data-contrast-fixed], script, style, noscript'
        )
      )
        continue
      if (getComputedStyle(el).visibility !== 'visible') continue
      const range = document.createRange()
      range.selectNodeContents(node)
      for (const r of range.getClientRects())
        add(node.textContent, el, getComputedStyle(el).color, r)
    }
    // An input's value and placeholder are not text nodes.
    for (const input of document.querySelectorAll('input'))
      if ((input.value || input.placeholder) && input.checkVisibility())
        add(
          input.value || input.placeholder,
          input,
          getComputedStyle(input, input.value ? null : '::placeholder').color,
          input.getBoundingClientRect()
        )
    return found
  })

  const shot = await page.screenshot({
    fullPage: true,
    scale: 'css',
    animations: 'disabled',
    style:
      '*, *::placeholder { color: transparent !important; -webkit-text-fill-color: transparent !important; text-shadow: none !important; caret-color: transparent !important } [data-contrast-fixed] { visibility: hidden !important }',
  })
  return page.evaluate(
    async ({ png, runs }) => {
      const img = new Image()
      img.src = `data:image/png;base64,${png}`
      await img.decode()
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d', { willReadFrequently: true })!
      // Any CSS colour (lab, oklch, ...) to sRGB, through the canvas.
      const rgba = (color: string) => {
        ctx.clearRect(0, 0, 1, 1)
        ctx.fillStyle = color
        ctx.fillRect(0, 0, 1, 1)
        return ctx.getImageData(0, 0, 1, 1).data
      }
      const lum = (r: number, g: number, b: number) => {
        const f = (c: number) =>
          (c /= 255) <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
      }
      const colors = runs.map((run) => rgba(run.color))
      ctx.drawImage(img, 0, 0)
      const failures: { text: string; ratio: number; required: number }[] = []
      runs.forEach((run, i) => {
        const [tr, tg, tb, ta] = colors[i]
        const x = Math.max(0, Math.floor(run.x))
        const y = Math.max(0, Math.floor(run.y))
        const w = Math.min(canvas.width - x, Math.ceil(run.w))
        const h = Math.min(canvas.height - y, Math.ceil(run.h))
        if (w <= 0 || h <= 0) return
        const px = ctx.getImageData(x, y, w, h).data
        let worst = Infinity
        for (let p = 0; p < px.length; p += 4) {
          const a = ta / 255 // a translucent text colour blends over this pixel
          const t = lum(
            tr * a + px[p] * (1 - a),
            tg * a + px[p + 1] * (1 - a),
            tb * a + px[p + 2] * (1 - a)
          )
          const b = lum(px[p], px[p + 1], px[p + 2])
          worst = Math.min(
            worst,
            (Math.max(t, b) + 0.05) / (Math.min(t, b) + 0.05)
          )
        }
        const required = run.large ? 3 : 4.5
        if (worst < required)
          failures.push({
            text: run.text,
            ratio: Math.round(worst * 100) / 100,
            required,
          })
      })
      return failures
    },
    { png: shot.toString('base64'), runs }
  )
}
