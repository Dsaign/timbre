// Mirrors the layout in app/page.tsx: content is max-w-5xl with px-4, the grid is
// repeat(auto-fill, minmax(12rem, 1fr)) with gap-3, and each card is h-24.
const MAX_CONTENT_WIDTH = 1024
const SIDE_PADDING = 16
const CARD_MIN_WIDTH = 192
const CARD_HEIGHT = 96
const GAP = 12
export const MAX_PAGE_SIZE = 60

/** How many grid columns CSS auto-fill makes at this viewport width. */
export function gridColumns(viewportWidth: number) {
  const width = Math.min(viewportWidth, MAX_CONTENT_WIDTH) - 2 * SIDE_PADDING
  return Math.max(1, Math.floor((width + GAP) / (CARD_MIN_WIDTH + GAP)))
}

/** The page size N: columns × the rows that fit in one screen height, 1 to 60. */
export function pageSizeFor(viewportWidth: number, viewportHeight: number) {
  const rows = Math.max(
    1,
    Math.floor((viewportHeight + GAP) / (CARD_HEIGHT + GAP))
  )
  return Math.min(MAX_PAGE_SIZE, gridColumns(viewportWidth) * rows)
}

export const GRID = 'grid grid-cols-[repeat(auto-fill,minmax(12rem,1fr))] gap-3'
