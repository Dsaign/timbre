'use client'

import { LoaderCircle } from 'lucide-react'
import { useEffect, useRef, useState, useTransition } from 'react'
import { loadMore } from '@/app/actions'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import type { components } from '@/lib/api/schema'
import { GRID } from '@/lib/grid'

type Match = components['schemas']['Match']
const MAX_OFFSET = 10_000 // the API's limit

/** The grid of Matches plus "carregar mais", which appends pages without touching the URL. */
export function MatchGrid({
  description,
  n,
  count,
  firstPage,
}: {
  description: string
  n: number
  count: number
  firstPage: Match[]
}) {
  const [matches, setMatches] = useState(firstPage)
  const [done, setDone] = useState(firstPage.length < n)
  const [focusFrom, setFocusFrom] = useState<number | null>(null)
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
            <Card className="h-24 rounded-xl bg-black/40 p-4 text-white">
              <p className="truncate text-sm font-medium">{match.title}</p>
              <p className="truncate text-zinc-300">{match.artist}</p>
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
              const next = await loadMore(description, n, offset)
              setMatches((current) => [...current, ...next])
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
    </>
  )
}
