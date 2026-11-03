'use client'

import { LoaderCircle } from 'lucide-react'
import { Suspense, useEffect, useRef, useState, useTransition } from 'react'
import { loadMore, previewsFor } from '@/app/actions'
import { FeedbackButtons } from '@/components/feedback-buttons'
import { PreviewControls } from '@/components/preview-player'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { components } from '@/lib/api/schema'
import { GRID } from '@/lib/grid'
import type { Previews } from '@/lib/preview'

type Match = components['schemas']['Match']
const MAX_OFFSET = 10_000 // the API's limit

/** The grid of Matches plus "carregar mais", which appends pages without touching the URL. */
export function MatchGrid({
  description,
  n,
  count,
  firstPage,
  firstPreviews,
}: {
  description: string
  n: number
  count: number
  firstPage: Match[]
  firstPreviews: Promise<Previews>
}) {
  // Each Match carries its page's Preview lookup, which its card waits for alone.
  const [matches, setMatches] = useState(() =>
    firstPage.map((match) => ({ ...match, previews: firstPreviews }))
  )
  const [done, setDone] = useState(firstPage.length < n)
  const [focusFrom, setFocusFrom] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()
  const list = useRef<HTMLUListElement>(null)

  // Move focus to the first new card, so keyboard and screen-reader users land on it.
  useEffect(() => {
    if (focusFrom !== null)
      (list.current?.children[focusFrom] as HTMLElement | undefined)?.focus()
  }, [focusFrom])

  const offset = matches.length
  const hasMore = !done && offset < count && offset <= MAX_OFFSET

  return (
    <>
      <ul ref={list} aria-label="Músicas" className={GRID}>
        {matches.map((match, i) => (
          <li
            key={match.id}
            tabIndex={i >= firstPage.length ? -1 : undefined}
            className="rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-white"
          >
            <Card className="h-32 gap-0 rounded-xl bg-black/40 p-4 text-white">
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{match.title}</p>
                  <p className="truncate text-zinc-300">{match.artist}</p>
                </div>
                <FeedbackButtons
                  description={description}
                  songId={match.id}
                  title={match.title}
                  initial={match.vote}
                />
              </div>
              <div className="mt-auto">
                <Suspense
                  fallback={
                    <Skeleton className="h-11 rounded-md bg-white/10" />
                  }
                >
                  <PreviewControls
                    previews={match.previews}
                    songId={match.id}
                    title={match.title}
                  />
                </Suspense>
              </div>
            </Card>
          </li>
        ))}
      </ul>
      {hasMore && (
        <Button
          type="button"
          variant="secondary"
          aria-busy={pending}
          onClick={() => {
            if (pending) return
            startTransition(async () => {
              const result = await loadMore(description, n, offset)
              if ('error' in result) return setError(result.error)
              setError(null)
              const next = result.data.matches
              const previews = previewsFor(next.map((m) => m.id)).catch(
                () => ({})
              )
              setMatches((current) => [
                ...current,
                ...next.map((match) => ({ ...match, previews })),
              ])
              setDone(next.length < n)
              setFocusFrom(offset)
            })
          }}
          className="mx-auto mt-6 flex cursor-pointer"
        >
          {pending && <LoaderCircle aria-hidden className="animate-spin" />}
          Carregar mais
        </Button>
      )}
      {error && (
        <p role="alert" className="mt-2 text-center text-white">
          {error}
        </p>
      )}
    </>
  )
}
