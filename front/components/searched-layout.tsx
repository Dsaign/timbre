import { HomeLink } from '@/components/preview-player'
import { SearchForm } from '@/components/search-form'
import { ThemeToggle } from '@/components/theme-toggle'
import { Skeleton } from '@/components/ui/skeleton'
import { GRID } from '@/lib/grid'

// Shared by the server page (app/page.tsx) and the hero's pending search (pending-search.tsx),
// so it imports nothing server-only.

// The one blurred panel behind the grid, shared by the results and their skeleton.
export const RESULTS_PANEL =
  'w-full rounded-3xl p-(--panel-pad) tight:p-(--panel-pad-tight)'

/** The sticky compact search bar over the full-width results (children). */
export function SearchedLayout({
  description,
  children,
}: {
  description: string | null
  children: React.ReactNode
}) {
  return (
    <>
      <header
        data-enter="1"
        className="z-20 flex h-(--bar-height) shrink-0 items-center gap-3 bg-glass frosted px-(--gutter) max-sm:gap-2"
      >
        <Logo compact />
        {/* key: remount so a sample chip replaces text the visitor already typed */}
        <SearchForm
          key={description}
          defaultValue={description ?? ''}
          compact
        />
        <ThemeToggle />
      </header>
      {/* The results are the entrance's step 2 on a first load (globals.css). data-shell: the
          page becomes a fixed 100dvh shell and only this cards area scrolls (globals.css). Its
          scrollbar keeps its room even when nothing overflows, as lib/grid.ts counts it. */}
      <main
        data-enter="2"
        data-shell
        className="flex min-h-0 flex-1 flex-col items-center overflow-y-auto [scrollbar-gutter:stable] px-(--gutter) py-(--main-pad-y) tight:py-(--main-pad-y-tight)"
      >
        {children}
      </main>
    </>
  )
}

/** "timbre.": large in the hero; in the compact bar a link home, "t." on small screens. */
export function Logo({ compact = false }: { compact?: boolean }) {
  // Same view-transition-name in both layouts: the search morphs one into the other.
  const className =
    'select-none font-display font-extrabold tracking-tight [view-transition-name:logo]'
  if (!compact)
    return (
      <h1
        className={`${className} mt-3 mb-3 self-center text-6xl`}
        data-contrast-skip
      >
        timbre.
      </h1>
    )
  return (
    <h1 className={`${className} shrink-0 text-2xl`} data-contrast-skip>
      {/* The name starts with the visible text at every width (WCAG 2.5.3):
          "t. (página inicial)" on small screens, "timbre. (página inicial)" otherwise. */}
      {/* Going home also closes the Preview dock and pauses it. */}
      <HomeLink
        href="/"
        className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-foreground"
      >
        <span className="sm:hidden">t.</span>
        <span className="max-sm:hidden">timbre.</span>
        <span className="sr-only"> (página inicial)</span>
      </HomeLink>
    </h1>
  )
}

export function MatchesSkeleton({ n }: { n: number }) {
  return (
    <div
      aria-busy="true"
      aria-label="Carregando resultados"
      className={RESULTS_PANEL}
    >
      <div className="h-(--status-height)">
        <Skeleton className="mx-auto h-4 w-40 rounded-md bg-foreground/10" />
      </div>
      <div className={GRID}>
        {Array.from({ length: n }, (_, i) => (
          <Skeleton key={i} className="bg-tint h-(--card-height) rounded-xl" />
        ))}
      </div>
    </div>
  )
}
