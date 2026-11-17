import { Suspense } from 'react'
import { MatchGrid } from '@/components/match-grid'
import { PendingSearch } from '@/components/pending-search'
import { ClosePreview } from '@/components/preview-player'
import { SampleDescriptions } from '@/components/sample-descriptions'
import { SearchForm } from '@/components/search-form'
import {
  Logo,
  MatchesSkeleton,
  RESULTS_PANEL,
  SearchedLayout,
} from '@/components/searched-layout'
import { ThemeToggle } from '@/components/theme-toggle'
import { Card } from '@/components/ui/card'
import { WaveformState } from '@/components/waveform-background'
import { lookupPreviews } from '@/lib/preview'
import { parseDescription, parsePageSize, searchMatches } from '@/lib/search'

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
  const description = parseDescription(q)
  return (
    <SearchedLayout description={description}>
      {description ? (
        <Results description={description} n={parsePageSize(n)} />
      ) : (
        <p role="alert">Descreva a música com 1 a 300 caracteres.</p>
      )}
    </SearchedLayout>
  )
}

function HeroLayout() {
  return (
    <PendingSearch>
      <ClosePreview />
      <header data-enter="1" className="flex justify-end px-3 pt-3">
        <ThemeToggle />
      </header>
      <main className="grid flex-1 place-items-center">
        <div className="flex w-full max-w-5xl flex-col items-center gap-8 px-4 py-8">
          <Card
            data-enter="2"
            className="
            w-full max-w-md rounded-3xl
            frosted gradient-border gap-0
            p-6 text-center text-foreground bg-transparent/30
            [@media(prefers-reduced-transparency:reduce)]:bg-glass
            has-[:hover]:shadow-[-5px_-5px_40px_1px_var(--color-indigo-500)]
            has-[:hover]:shadow-indigo-500/10
            transition-shadow
            duration-500
            "
          >
            <Logo />
            {/* Like the note below: particles can pass under it on the see-through panel. */}
            <p
              className="mb-8 text-sm text-foreground text-balance"
              data-contrast-skip
            >
              Descreva o clima de uma música e encontre outras com a mesma
              sensação.
            </p>
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
    </PendingSearch>
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
        <p role="status" className="text-center text-balance">
          Nenhuma música encontrada. Tente descrever o clima ou os instrumentos,
          ou use um exemplo:
        </p>
        <SampleDescriptions />
      </section>
    )

  return (
    <section aria-label="Resultados" className={RESULTS_PANEL}>
      <p
        role="status"
        className="h-(--status-height) text-center text-xs text-foreground"
      >
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
