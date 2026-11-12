'use client'

import { LoaderCircle } from 'lucide-react'
import { Suspense, useEffect, useRef, useState, useTransition } from 'react'
import { loadMore, previewsFor } from '@/app/actions'
import { FeedbackButtons } from '@/components/feedback-buttons'
import {
  COVER_BOX,
  useDockOpen,
  PreviewControls,
  PreviewCover,
} from '@/components/preview-player'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { components } from '@/lib/api/schema'
import { currentScreen, GRID, gridRows, nextPageSize } from '@/lib/grid'
import type { Previews } from '@/lib/preview'

type Match = components['schemas']['Match']
const MAX_OFFSET = 10_000 // the API's limit
const STAGGER_MS = 30
const STAGGER_STEPS = 15 // a page of 60 still enters in under half a second
const CARD_ENTER_MS = 300

/** A card's entrance: its fade's delay and length, and when it is over (--card-entered).
    On a first load both also wait for the results' entrance step (--enter-offset, globals.css). */
const enterTiming = (delay: number) =>
  ({
    animationDelay: `calc(${delay}ms + var(--enter-offset, 0ms))`,
    animationDuration: `${CARD_ENTER_MS}ms`,
    '--card-entered': `calc(${delay + CARD_ENTER_MS}ms + var(--enter-offset, 0ms))`,
  }) as React.CSSProperties

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
  // Each Match carries its page's Preview lookup, which its card waits for alone, and
  // where its page starts, so a page's cards stagger in from its first card.
  const [matches, setMatches] = useState(() =>
    firstPage.map((match) => ({ ...match, previews: firstPreviews, from: 0 }))
  )
  const [done, setDone] = useState(firstPage.length < n)
  const [focusFrom, setFocusFrom] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()
  const list = useRef<HTMLUListElement>(null)
  const dockOpen = useDockOpen()

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
            // Each card fades in on its own; reduced motion shows it at once.
            style={enterTiming(
              Math.min(i - match.from, STAGGER_STEPS) * STAGGER_MS
            )}
            className="rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-foreground motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:fill-mode-both"
          >
            <Card className="bg-glass gradient-border gradient-border-hover h-(--card-height) flex-row gap-3 rounded-xl p-3 tight:gap-2.5 tight:p-2.5">
              {/* Spotify artwork stays as delivered: no crop, overlay or animation. It shows only
                  once its card has finished entering, so it never fades with the card.
                  Wrapped, so Card's own first-image styles (no radius, no top padding) skip it. */}
              <div className="shrink-0 after-card-enter">
                <Suspense
                  fallback={
                    <Skeleton className={`${COVER_BOX} bg-foreground/10`} />
                  }
                >
                  <PreviewCover previews={match.previews} songId={match.id} />
                </Suspense>
              </div>
              <div className="flex min-w-0 flex-1 flex-col">
                <div className="flex items-start gap-1">
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-sm leading-5 font-semibold text-pretty">
                      {match.title}
                    </p>
                    <p className="truncate text-muted-foreground">
                      {match.artist}
                    </p>
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
                      <Skeleton className="h-11 rounded-md bg-foreground/10" />
                    }
                  >
                    <PreviewControls
                      previews={match.previews}
                      songId={match.id}
                      title={match.title}
                    />
                  </Suspense>
                </div>
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
            // Sized for the screen as it is now: complete the last row, then fill the cards area.
            const columns = getComputedStyle(
              list.current!
            ).gridTemplateColumns.split(' ').length
            const size = nextPageSize(
              offset,
              columns,
              gridRows(currentScreen(dockOpen))
            )
            startTransition(async () => {
              const result = await loadMore(description, size, offset)
              if ('error' in result) return setError(result.error)
              setError(null)
              const next = result.data.matches
              const previews = previewsFor(next.map((m) => m.id)).catch(
                () => ({})
              )
              setMatches((current) => [
                ...current,
                ...next.map((match) => ({ ...match, previews, from: offset })),
              ])
              setDone(next.length < size)
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
        <p role="alert" className="mt-2 text-center">
          {error}
        </p>
      )}
    </>
  )
}
