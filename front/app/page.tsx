import { Suspense } from 'react'
import { MatchGrid } from '@/components/match-grid'
import { SampleDescriptions } from '@/components/sample-descriptions'
import { SearchForm } from '@/components/search-form'
import { Card } from '@/components/ui/card'
import { WaveformState } from '@/components/waveform-background'
import { Skeleton } from '@/components/ui/skeleton'
import { GRID } from '@/lib/grid'
import { lookupPreviews } from '@/lib/preview'
import { parseDescription, parsePageSize, searchMatches } from '@/lib/search'

// The one blurred panel behind the grid, shared by the results and their skeleton.
const RESULTS_PANEL = 'bg-glass frosted w-full rounded-3xl p-4'

// Cache Components: the shell (panel and an empty form) is prerendered; whatever reads
// searchParams streams in inside a Suspense boundary.
export default function Home({ searchParams }: PageProps<'/'>) {
  return (
    <div className="flex w-full max-w-5xl flex-col items-center gap-8 px-4 py-8">
      <Card
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
        <h1 className="mb-8 mt-3 text-6xl" data-contrast-skip>
          timbre.
        </h1>
        <Suspense fallback={<SearchForm />}>
          <FilledSearchForm searchParams={searchParams} />
        </Suspense>
        {/* Owner decision: like the title, moving particles can pass under this note on the see-through panel; both skip the contrast check. */}
        <p className="mt-4 text-xs text-foreground" data-contrast-skip>
          Descrições e votos são armazenados para melhorar o modelo.
        </p>
      </Card>
      <Suspense>
        <Results searchParams={searchParams} />
      </Suspense>
    </div>
  )
}

type SearchParams = PageProps<'/'>['searchParams']

async function FilledSearchForm({
  searchParams,
}: {
  searchParams: SearchParams
}) {
  const { q } = await searchParams
  const description = parseDescription(q) ?? ''
  // key: remount so a sample chip replaces text the visitor already typed
  return <SearchForm key={description} defaultValue={description} />
}

async function Results({ searchParams }: { searchParams: SearchParams }) {
  const { q, n } = await searchParams
  if (q === undefined) return <SampleDescriptions />
  const description = parseDescription(q)
  if (!description)
    return <p role="alert">Descreva a música com 1 a 300 caracteres.</p>
  const pageSize = parsePageSize(n)
  return (
    <Suspense
      key={`${pageSize}:${description}`}
      fallback={<MatchesSkeleton n={pageSize} />}
    >
      <Matches description={description} n={pageSize} />
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
      <p role="status" className="mb-4 text-center">
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
      <Skeleton className="mx-auto mb-4 h-5 w-48 rounded-md bg-foreground/10" />
      <div className={GRID}>
        {Array.from({ length: n }, (_, i) => (
          <Skeleton key={i} className="bg-tint h-32 rounded-xl" />
        ))}
      </div>
    </div>
  )
}
