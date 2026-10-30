import { describe, expect, it } from 'vitest'
import { gridColumns, pageSizeFor } from './grid'

describe('pageSizeFor', () => {
  it.each([
    // [width, height, columns, N]
    [375, 667, 1, 6],
    [768, 1024, 3, 27],
    [1440, 900, 4, 32],
  ])('%i×%i → %i columns, N = %i', (width, height, columns, n) => {
    expect(gridColumns(width)).toBe(columns)
    expect(pageSizeFor(width, height)).toBe(n)
  })

  it('stops growing columns at the max content width', () => {
    expect(gridColumns(3840)).toBe(gridColumns(1440))
  })

  it('caps N at 60', () => {
    expect(pageSizeFor(3840, 2160)).toBe(60)
  })

  it('is at least one card on tiny screens', () => {
    expect(pageSizeFor(200, 50)).toBe(1)
  })
})
