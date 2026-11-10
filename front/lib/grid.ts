import type { CSSProperties } from 'react'

// The one source for the results layout: app/layout.tsx sets these as CSS variables on <body>,
// and app/page.tsx, GRID and the cards size themselves from those variables, so N below always
// matches what CSS draws. Top to bottom: the sticky search bar (barHeight), main's padding
// (mainPadY), the panel's padding (panel), the "N músicas encontradas" line with its space
// below (statusHeight), then rows of cards. Across: the gutter, the panel's padding, and the
// grid repeat(auto-fill, minmax(cardMinWidth, 1fr)).
export const LAYOUT = {
  gutter: 12,
  barHeight: 60,
  statusHeight: 30,
  cardMinWidth: 288, // cover, title + thumbs, Preview + Spotify icon side by side
  cardHeight: 128,
  regular: { mainPadY: 12, panel: 16, gap: 10 },
  tight: { mainPadY: 8, panel: 8, gap: 8 }, // narrow or short screens
}
export const MAX_PAGE_SIZE = 60

// The `tight` variant in app/globals.css uses the same two limits; keep them in sync.
const isTight = (width: number, height: number) => width < 640 || height <= 640

/** The layout as CSS variables, for <body>. */
export const LAYOUT_VARS = {
  '--gutter': `${LAYOUT.gutter}px`,
  '--bar-height': `${LAYOUT.barHeight}px`,
  '--status-height': `${LAYOUT.statusHeight}px`,
  '--main-pad-y': `${LAYOUT.regular.mainPadY}px`,
  '--main-pad-y-tight': `${LAYOUT.tight.mainPadY}px`,
  '--card-min-width': `${LAYOUT.cardMinWidth}px`,
  '--card-height': `${LAYOUT.cardHeight}px`,
  '--panel-pad': `${LAYOUT.regular.panel}px`,
  '--panel-pad-tight': `${LAYOUT.tight.panel}px`,
  '--grid-gap': `${LAYOUT.regular.gap}px`,
  '--grid-gap-tight': `${LAYOUT.tight.gap}px`,
} as CSSProperties

/** How many grid columns CSS auto-fill makes at this viewport size. */
export function gridColumns(viewportWidth: number, viewportHeight = Infinity) {
  const { panel, gap } = isTight(viewportWidth, viewportHeight)
    ? LAYOUT.tight
    : LAYOUT.regular
  const width = viewportWidth - 2 * LAYOUT.gutter - 2 * panel
  return Math.max(1, Math.floor((width + gap) / (LAYOUT.cardMinWidth + gap)))
}

/** The page size N: columns × the rows that fit in one screen, 1 to 60. */
export function pageSizeFor(viewportWidth: number, viewportHeight: number) {
  const { mainPadY, panel, gap } = isTight(viewportWidth, viewportHeight)
    ? LAYOUT.tight
    : LAYOUT.regular
  const above =
    LAYOUT.barHeight + mainPadY + panel + LAYOUT.statusHeight + panel + mainPadY
  const rows = Math.max(
    1,
    Math.floor((viewportHeight - above + gap) / (LAYOUT.cardHeight + gap))
  )
  return Math.min(
    MAX_PAGE_SIZE,
    gridColumns(viewportWidth, viewportHeight) * rows
  )
}

export const GRID =
  'grid grid-cols-[repeat(auto-fill,minmax(min(var(--card-min-width),100%),1fr))] gap-(--grid-gap) tight:gap-(--grid-gap-tight)'
