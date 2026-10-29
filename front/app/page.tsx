import { Suspense } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { back } from '@/lib/api/client'
import { PAGE_SIZE, parseDescription } from '@/lib/search'

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

function SearchForm({ defaultValue }: { defaultValue?: string }) {
  return (
    <form>
      <Field>
        <Input
          name="q"
          type="text"
          aria-label="Descreva sua música favorita"
          placeholder="Descreva sua música favorita..."
          defaultValue={defaultValue}
          required
          maxLength={300}
          className="
                border-0 text-white
                bg-linear-to-br from-indigo-950 to-mauve-700
                focus:border placeholder:text-zinc-400"
        />

        <Button
          type="submit"
          variant="secondary"
          className="w-full cursor-pointer bg-linear-to-br from-indigo-200 to-mauve-200 hover:from-indigo-300 transition-colors"
        >
          Pesquisar
        </Button>
      </Field>
    </form>
  )
}

async function Results({ searchParams }: { searchParams: SearchParams }) {
  const { q } = await searchParams
  if (q === undefined) return null
  const description = parseDescription(q)
  if (!description)
    return <p role="alert">Descreva a música com 1 a 300 caracteres.</p>
  return (
    <Suspense key={description} fallback={<MatchesSkeleton />}>
      <Matches description={description} />
    </Suspense>
  )
}

async function Matches({ description }: { description: string }) {
  const { data, response } = await back.GET('/search', {
    params: { query: { q: description, n: PAGE_SIZE } },
  })
  // shortcut: any back failure goes to the error page; ticket 09 adds the friendly message
  if (!data) throw new Error(`search failed: HTTP ${response.status}`)

  return (
    <section aria-label="Resultados" className="w-full">
      <p role="status" className="mb-4 text-center text-white">
        {data.count}{' '}
        {data.count === 1 ? 'música encontrada' : 'músicas encontradas'}
      </p>
      <ul aria-label="Músicas" className={GRID}>
        {data.matches.map((match) => (
          <li key={match.id}>
            <Card className="h-full rounded-xl bg-black/40 p-4 text-white">
              <p className="text-sm font-medium">{match.title}</p>
              <p className="text-zinc-300">{match.artist}</p>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  )
}

const GRID = 'grid grid-cols-[repeat(auto-fill,minmax(12rem,1fr))] gap-3'

function MatchesSkeleton() {
  return (
    <div aria-busy="true" aria-label="Carregando resultados" className="w-full">
      <Skeleton className="mx-auto mb-4 h-5 w-48 rounded-md bg-white/10" />
      <div className={GRID}>
        {Array.from({ length: PAGE_SIZE }, (_, i) => (
          <Skeleton key={i} className="h-20 rounded-xl bg-white/10" />
        ))}
      </div>
    </div>
  )
}
