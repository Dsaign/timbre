import type { CSSProperties } from 'react'

// The one source for the results layout: app/layout.tsx sets these as CSS variables on <body>,
// and app/page.tsx, globals.css, GRID, the cards and the dock size themselves from those
// variables, so N below always matches what CSS draws.
// After a search the page is a fixed 100dvh shell, top to bottom: the search bar (barHeight),
// the scrolling cards area, the open Preview dock (dock), the footer (footer). Inside the cards
// area: main's padding (mainPadY), the panel's padding (panel), the "N músicas encontradas" line
// (statusHeight), then rows of cards. Across: the gutter, the cards area's scrollbar, the panel's
// padding, and the grid repeat(auto-fill, minmax(cardMinWidth, 1fr)).
export const LAYOUT = {
  // Narrow: below Tailwind's sm breakpoint (--breakpoint-sm, 40rem), which globals.css uses
  // (max-sm, inside the `tight` variant). Short: height up to `short` (the `tight` variant).
  narrow: 640,
  short: 640,
  gutter: 12,
  barHeight: 60,
  // The shell footer's least height: one line of credits; two when narrow. It grows if the
  // credits need more room, and currentScreen() then measures it.
  footer: { regular: 48, narrow: 56 },
  dock: { height: 80, gap: 8 }, // Spotify's smallest embed, and the space above it
  statusHeight: 24,
  cardMinWidth: 288, // cover, title + thumbs, Preview + Spotify icon side by side
  cardHeight: 128,
  regular: { mainPadY: 16, panel: 24, gap: 16 },
  tight: { mainPadY: 8, panel: 12, gap: 12 }, // narrow or short screens
}
export const MAX_PAGE_SIZE = 60

const isNarrow = (width: number) => width < LAYOUT.narrow
const isTight = (width: number, height: number) =>
  isNarrow(width) || height <= LAYOUT.short
const spacing = (width: number, height: number) =>
  isTight(width, height) ? LAYOUT.tight : LAYOUT.regular

/** The layout as CSS variables, for <body>. */
export const LAYOUT_VARS = {
  '--gutter': `${LAYOUT.gutter}px`,
  '--bar-height': `${LAYOUT.barHeight}px`,
  '--footer-height': `${LAYOUT.footer.regular}px`,
  '--footer-height-narrow': `${LAYOUT.footer.narrow}px`,
  '--dock-height': `${LAYOUT.dock.height}px`,
  '--dock-gap': `${LAYOUT.dock.gap}px`,
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

/** The screen the cards area gets: viewport size, the scrollbar's width, the footer, the dock. */
export type Screen = {
  width: number
  height: number
  scrollbar?: number // the cards area keeps room for it (scrollbar-gutter: stable)
  footer?: number // the shell footer's rendered height, when known; else LAYOUT.footer
  dockOpen?: boolean
}

/** How many grid columns CSS auto-fill makes on this screen. */
export function gridColumns({ width, height, scrollbar = 0 }: Screen) {
  const { panel, gap } = spacing(width, height)
  const inner = width - scrollbar - 2 * LAYOUT.gutter - 2 * panel
  return Math.max(1, Math.floor((inner + gap) / (LAYOUT.cardMinWidth + gap)))
}

/** How many rows of cards fit in the cards area: between the bar and the footer (and the open dock). */
export function gridRows({
  width,
  height,
  footer = isNarrow(width) ? LAYOUT.footer.narrow : LAYOUT.footer.regular,
  dockOpen = false,
}: Screen) {
  const { mainPadY, panel, gap } = spacing(width, height)
  const dock = dockOpen ? LAYOUT.dock.height + LAYOUT.dock.gap : 0
  const area = height - LAYOUT.barHeight - footer - dock
  const forCards = area - 2 * mainPadY - 2 * panel - LAYOUT.statusHeight
  return Math.max(1, Math.floor((forCards + gap) / (LAYOUT.cardHeight + gap)))
}

/** The page size N: the cards that fill the cards area, 1 to 60. */
export function pageSizeFor(screen: Screen) {
  return Math.min(MAX_PAGE_SIZE, gridColumns(screen) * gridRows(screen))
}

/**
 * "Carregar mais": first the cards that complete the last row, then full rows for the screen
 * as it is now, at most 60 and always ending on a full row (so no row is left incomplete).
 */
export function nextPageSize(offset: number, columns: number, rows: number) {
  const fill = (columns - (offset % columns)) % columns
  const fullRows = Math.min(rows, Math.floor((MAX_PAGE_SIZE - fill) / columns))
  return Math.max(1, fill + columns * fullRows)
}

/** The screen right now (browser only). The dock's state comes from PreviewPlayer. */
export function currentScreen(dockOpen: boolean): Screen {
  // Classic scrollbars take width; overlay ones (phones, macOS) measure 0.
  const probe = document.createElement('div')
  probe.style.cssText =
    'position:absolute;visibility:hidden;overflow:scroll;width:100px'
  document.body.append(probe)
  const scrollbar = probe.offsetWidth - probe.clientWidth
  probe.remove()
  // On the results the shell footer is on screen: use its real height (it may have grown).
  const footer = document.querySelector('[data-shell]')
    ? document.querySelector<HTMLElement>('[data-site-footer]')?.offsetHeight
    : undefined
  return {
    width: document.documentElement.clientWidth,
    height: window.innerHeight,
    scrollbar,
    footer,
    dockOpen,
  }
}

export const GRID =
  'grid grid-cols-[repeat(auto-fill,minmax(min(var(--card-min-width),100%),1fr))] gap-(--grid-gap) tight:gap-(--grid-gap-tight)'
