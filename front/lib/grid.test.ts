import { describe, expect, it } from 'vitest'
import { gridColumns, pageSizeFor } from './grid'

describe('pageSizeFor', () => {
  it.each([
    // [width, height, columns, N]
    [320, 568, 1, 3],
    [375, 667, 1, 3],
    [768, 1024, 2, 12],
    [1440, 900, 4, 20],
    [1280, 600, 4, 12], // short: tight padding and gaps
  ])('%i×%i → %i columns, N = %i', (width, height, columns, n) => {
    expect(gridColumns(width, height)).toBe(columns)
    expect(pageSizeFor(width, height)).toBe(n)
  })

  it('keeps adding columns on wide screens (no max width)', () => {
    expect(gridColumns(2560)).toBe(8)
  })

  it('caps N at 60', () => {
    expect(pageSizeFor(3840, 4000)).toBe(60)
  })

  it('is at least one card on tiny screens', () => {
    expect(pageSizeFor(200, 50)).toBe(1)
  })
})
