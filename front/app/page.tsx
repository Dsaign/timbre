import { Suspense } from 'react'
import { MatchGrid } from '@/components/match-grid'
import { SearchForm } from '@/components/search-form'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { back } from '@/lib/api/client'
import { GRID } from '@/lib/grid'
import { parseDescription, parsePageSize } from '@/lib/search'

// Cache Components: the shell (panel and an empty form) is prerendered; whatever reads
// searchParams streams in inside a Suspense boundary.
export default function Home({ searchParams }: PageProps<'/'>) {
  return (
    <div className="flex w-full max-w-5xl flex-col items-center gap-8 px-4 py-8">
      <Card
        className="
        w-full lg:max-w-md md:min-w-md rounded-3xl 
        bg-linear-to-br from-indigo-800 to-mauve-500
        p-px text-center text-white
        has-[:hover]:shadow-[-5px_-5px_40px_1px_var(--color-indigo-500)]
        has-[:hover]:shadow-indigo-500/10
        transition-shadow
        duration-500
        "
      >
        <div className="rounded-[calc(1.5rem-2px)] bg-black/60 p-6">
          <h1 className="mb-8 mt-3 text-6xl">timbre.</h1>
          <Suspense fallback={<SearchForm />}>
            <FilledSearchForm searchParams={searchParams} />
          </Suspense>
        </div>
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
  return <SearchForm defaultValue={parseDescription(q) ?? ''} />
}

async function Results({ searchParams }: { searchParams: SearchParams }) {
  const { q, n } = await searchParams
  if (q === undefined) return null
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
    </Suspense>
  )
}

async function Matches({ description, n }: { description: string; n: number }) {
  const { data, response } = await back.GET('/search', {
    params: { query: { q: description, n } },
  })
  // shortcut: any back failure goes to the error page; ticket 09 adds the friendly message
  if (!data) throw new Error(`search failed: HTTP ${response.status}`)

  return (
    <section aria-label="Resultados" className="w-full">
      <p role="status" className="mb-4 text-center text-white">
        {data.count}{' '}
        {data.count === 1 ? 'música encontrada' : 'músicas encontradas'}
      </p>
      <MatchGrid
        description={description}
        n={n}
        count={data.count}
        firstPage={data.matches}
      />
    </section>
  )
}

function MatchesSkeleton({ n }: { n: number }) {
  return (
    <div aria-busy="true" aria-label="Carregando resultados" className="w-full">
      <Skeleton className="mx-auto mb-4 h-5 w-48 rounded-md bg-white/10" />
      <div className={GRID}>
        {Array.from({ length: n }, (_, i) => (
          <Skeleton key={i} className="h-24 rounded-xl bg-white/10" />
        ))}
      </div>
    </div>
  )
}
