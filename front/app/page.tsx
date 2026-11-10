import Link from 'next/link'
import { Suspense } from 'react'
import { MatchGrid } from '@/components/match-grid'
import { SampleDescriptions } from '@/components/sample-descriptions'
import { SearchForm } from '@/components/search-form'
import { ThemeToggle } from '@/components/theme-toggle'
import { Card } from '@/components/ui/card'
import { WaveformState } from '@/components/waveform-background'
import { Skeleton } from '@/components/ui/skeleton'
import { GRID } from '@/lib/grid'
import { lookupPreviews } from '@/lib/preview'
import { parseDescription, parsePageSize, searchMatches } from '@/lib/search'

// The one blurred panel behind the grid, shared by the results and their skeleton.
const RESULTS_PANEL =
  'w-full rounded-3xl p-(--panel-pad) tight:p-(--panel-pad-tight)'

// Cache Components: the shell (the home layout with an empty form) is prerendered; whatever
// reads searchParams streams in inside a Suspense boundary.
export default function Home({ searchParams }: PageProps<'/'>) {
  return (
    <Suspense fallback={<HeroLayout />}>
      <LayoutFor searchParams={searchParams} />
    </Suspense>
  )
}

type SearchParams = PageProps<'/'>['searchParams']

/** Home: the hero search panel. After a search (q present): the compact bar and the results. */
async function LayoutFor({ searchParams }: { searchParams: SearchParams }) {
  const { q, n } = await searchParams
  if (q === undefined) return <HeroLayout />
  return (
    <SearchedLayout description={parseDescription(q)} n={parsePageSize(n)} />
  )
}

/** The sticky compact search bar over the full-width results. */
function SearchedLayout({
  description,
  n,
}: {
  description: string | null
  n: number
}) {
  return (
    <>
      <header
        data-enter="1"
        className="sticky top-0 z-20 flex h-(--bar-height) items-center gap-3 bg-glass frosted px-(--gutter) max-sm:gap-2"
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
      {/* The results are the entrance's step 2 on a first load (globals.css). */}
      <main
        data-enter="2"
        className="flex flex-1 flex-col items-center px-(--gutter) py-(--main-pad-y) tight:py-(--main-pad-y-tight)"
      >
        {description ? (
          <Results description={description} n={n} />
        ) : (
          <p role="alert">Descreva a música com 1 a 300 caracteres.</p>
        )}
      </main>
    </>
  )
}

/** "timbre.": large in the hero; in the compact bar a link home, "t." on small screens. */
function Logo({ compact = false }: { compact?: boolean }) {
  // Same view-transition-name in both layouts: the search morphs one into the other.
  const className = 'select-none [view-transition-name:logo]'
  if (!compact)
    return (
      <h1
        className={`${className} mt-3 mb-8 self-center text-6xl`}
        data-contrast-skip
      >
        timbre.
      </h1>
    )
  return (
    <h1 className={`${className} shrink-0 text-2xl`} data-contrast-skip>
      {/* The name starts with the visible text at every width (WCAG 2.5.3):
          "t. (página inicial)" on small screens, "timbre. (página inicial)" otherwise. */}
      <Link
        href="/"
        className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-foreground"
      >
        <span className="sm:hidden">t.</span>
        <span className="max-sm:hidden">timbre.</span>
        <span className="sr-only"> (página inicial)</span>
      </Link>
    </h1>
  )
}

function HeroLayout() {
  return (
    <>
      <header data-enter="1" className="flex justify-end px-3 pt-3">
        <ThemeToggle />
      </header>
      <main className="grid flex-1 place-items-center">
        <div className="flex w-full max-w-5xl flex-col items-center gap-8 px-4 py-8">
          <Card
            data-enter="2"
            className="
            w-full lg:max-w-md md:min-w-md rounded-3xl
            frosted gradient-border ring-0 gap-0
            p-6 text-center text-foreground bg-transparent/30
            [@media(prefers-reduced-transparency:reduce)]:bg-glass
            has-[:hover]:shadow-[-5px_-5px_40px_1px_var(--color-indigo-500)]
            has-[:hover]:shadow-indigo-500/10
            transition-shadow
            duration-500
            "
          >
            <Logo />
            <SearchForm />
            {/* Owner decision: like the title, moving particles can pass under this note on the see-through panel; both skip the contrast check. */}
            <p className="mt-4 text-xs text-foreground" data-contrast-skip>
              Descrições e votos são armazenados para melhorar o modelo.
            </p>
          </Card>
          <div data-enter="3">
            <SampleDescriptions />
          </div>
        </div>
      </main>
    </>
  )
}

function Results({ description, n }: { description: string; n: number }) {
  return (
    <Suspense key={`${n}:${description}`} fallback={<MatchesSkeleton n={n} />}>
      <Matches description={description} n={n} />
      {/* Revealed together with the Matches (or their message): the waveform relaxes. */}
      <WaveformState state="matches" />
    </Suspense>
  )
}

async function Matches({ description, n }: { description: string; n: number }) {
  const result = await searchMatches({ q: description, n })
  if ('error' in result)
    return (
      <p role="alert" className="text-center">
        {result.error}
      </p>
    )
  const { data } = result

  if (data.count === 0)
    return (
      <section
        aria-label="Resultados"
        className="flex flex-col items-center gap-4"
      >
        <p role="status">Nenhuma música encontrada</p>
        <SampleDescriptions />
      </section>
    )

  return (
    <section aria-label="Resultados" className={RESULTS_PANEL}>
      <p role="status" className="h-(--status-height) text-sm text-center">
        {data.count}{' '}
        {data.count === 1 ? 'música encontrada' : 'músicas encontradas'}
      </p>
      <MatchGrid
        description={description}
        n={n}
        count={data.count}
        firstPage={data.matches}
        // Not awaited: the grid shows now, each card's Preview controls stream in.
        firstPreviews={lookupPreviews(data.matches.map((m) => m.id))}
      />
    </section>
  )
}

function MatchesSkeleton({ n }: { n: number }) {
  return (
    <div
      aria-busy="true"
      aria-label="Carregando resultados"
      className={RESULTS_PANEL}
    >
      <div className="h-(--status-height)">
        <Skeleton className="mx-auto h-5 w-48 rounded-md bg-foreground/10" />
      </div>
      <div className={GRID}>
        {Array.from({ length: n }, (_, i) => (
          <Skeleton key={i} className="bg-tint h-(--card-height) rounded-xl" />
        ))}
      </div>
    </div>
  )
}
