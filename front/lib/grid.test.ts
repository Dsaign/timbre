import { describe, expect, it } from 'vitest'
import { gridColumns, gridRows, nextPageSize, pageSizeFor } from './grid'

describe('pageSizeFor', () => {
  it.each([
    // [width, height, columns, N]
    [320, 568, 1, 2],
    [375, 667, 1, 3],
    [390, 844, 1, 4],
    [768, 1024, 2, 10],
    [1440, 900, 4, 16],
    [1280, 600, 4, 12], // short: tight padding and gaps
  ])('%i×%i → %i columns, N = %i', (width, height, columns, n) => {
    expect(gridColumns({ width, height })).toBe(columns)
    expect(pageSizeFor({ width, height })).toBe(n)
  })

  it('gives the open dock its room: fewer rows', () => {
    expect(gridRows({ width: 1440, height: 1000 })).toBe(5)
    expect(gridRows({ width: 1440, height: 1000, dockOpen: true })).toBe(4)
  })

  it('uses the rendered footer height when it has grown', () => {
    expect(gridRows({ width: 1440, height: 1000 })).toBe(5)
    expect(gridRows({ width: 1440, height: 1000, footer: 150 })).toBe(4)
  })

  it("leaves room for the cards area's scrollbar", () => {
    expect(gridColumns({ width: 1576, height: 900 })).toBe(5)
    expect(gridColumns({ width: 1576, height: 900, scrollbar: 15 })).toBe(4)
  })

  it('keeps adding columns on wide screens (no max width)', () => {
    expect(gridColumns({ width: 2560, height: 1440 })).toBe(8)
  })

  it('caps N at 60', () => {
    expect(pageSizeFor({ width: 3840, height: 4000 })).toBe(60)
  })

  it('is at least one card on tiny screens', () => {
    expect(pageSizeFor({ width: 200, height: 50 })).toBe(1)
  })
})

describe('nextPageSize', () => {
  it.each([
    // [offset, columns, rows, next page]
    [16, 4, 4, 16], // last row full: only full rows
    [16, 3, 4, 14], // 2 complete the last row, then 4 rows of 3
    [10, 7, 9, 60], // 4 complete the row, then as many full rows as fit under 60
    [5, 1, 2, 2],
  ])('offset %i, %i columns, %i rows → %i', (offset, columns, rows, next) => {
    expect(nextPageSize(offset, columns, rows)).toBe(next)
    expect((offset + next) % columns).toBe(0)
  })
})
