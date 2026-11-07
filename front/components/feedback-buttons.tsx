'use client'

import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { sendVote } from '@/app/actions'
import { Button } from '@/components/ui/button'
import { VOTE_FAILED } from '@/lib/feedback'

type Vote = 'up' | 'down' | null

/** 👍/👎 Feedback on one Match. The other thumb switches; the same thumb withdraws. */
export function FeedbackButtons({
  description,
  songId,
  title,
  initial,
}: {
  description: string
  songId: string
  title: string
  initial: Vote
}) {
  const [vote, setVote] = useState<Vote>(initial)
  // One request at a time, so a revert never restores a stale vote and votes stay in order.
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const hideError = useRef<ReturnType<typeof setTimeout>>(undefined)
  useEffect(() => () => clearTimeout(hideError.current), [])

  function press(thumb: 'up' | 'down') {
    if (pending) return
    const previous = vote
    const next = vote === thumb ? null : thumb
    setVote(next) // optimistic; reverted if back refuses
    setPending(true)
    setError(null)
    sendVote(description, songId, next ?? 'none')
      .then((result) => result.error)
      .catch(() => VOTE_FAILED)
      .then((failed) => {
        if (!failed) return
        setVote(previous)
        setError(failed)
        clearTimeout(hideError.current) // each message stays its full 5 s
        hideError.current = setTimeout(() => setError(null), 5000)
      })
      .finally(() => setPending(false))
  }

  return (
    <div className="relative flex shrink-0 gap-1">
      {(
        [
          ['up', ThumbsUp, `Combina: ${title}`],
          ['down', ThumbsDown, `Não combina: ${title}`],
        ] as const
      ).map(([thumb, Icon, label]) => (
        <Button
          key={thumb}
          type="button"
          variant="ghost"
          size="icon-lg"
          aria-label={label}
          aria-pressed={vote === thumb}
          // aria-disabled, not disabled: the focused thumb keeps keyboard focus meanwhile
          aria-disabled={pending}
          onClick={() => press(thumb)}
          className="cursor-pointer rounded-md text-muted-foreground hover:bg-foreground/10 hover:text-foreground aria-pressed:bg-foreground/15 aria-pressed:text-foreground aria-disabled:cursor-wait aria-disabled:opacity-50"
        >
          <Icon aria-hidden className={vote === thumb ? 'fill-current' : ''} />
        </Button>
      ))}
      {/* Always rendered, so screen readers announce the message when it appears. */}
      <p
        role="status"
        className="absolute top-full right-0 z-10 mt-1 w-48 rounded-md bg-black/90 p-2 text-xs text-white empty:hidden"
      >
        {error}
      </p>
    </div>
  )
}
