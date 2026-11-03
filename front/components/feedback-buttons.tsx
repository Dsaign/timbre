'use client'

import { ThumbsDown, ThumbsUp } from 'lucide-react'
import { useState } from 'react'
import { sendVote } from '@/app/actions'
import { Button } from '@/components/ui/button'

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

  function press(thumb: 'up' | 'down') {
    if (pending) return
    const previous = vote
    const next = vote === thumb ? null : thumb
    setVote(next) // optimistic; reverted if back refuses
    setPending(true)
    sendVote(description, songId, next ?? 'none')
      .catch(() => setVote(previous))
      .finally(() => setPending(false))
  }

  return (
    <div className="flex shrink-0 gap-1">
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
          className="cursor-pointer rounded-md text-zinc-300 hover:bg-white/10 hover:text-white aria-pressed:bg-white/20 aria-pressed:text-white aria-disabled:cursor-wait aria-disabled:opacity-50"
        >
          <Icon aria-hidden className={vote === thumb ? 'fill-current' : ''} />
        </Button>
      ))}
    </div>
  )
}
