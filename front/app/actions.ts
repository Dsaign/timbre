'use server'

import { back } from '@/lib/api/client'
import { TOO_MANY_VOTES, VOTE_FAILED } from '@/lib/feedback'
import { MAX_PAGE_SIZE } from '@/lib/grid'
import { lookupPreviews } from '@/lib/preview'
import { parseDescription, parsePageSize, searchMatches } from '@/lib/search'
import { visitorHeaders } from '@/lib/visitor'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** "Carregar mais": the next page of Matches, or a friendly error message. Runs on the server so the token stays there. */
export async function loadMore(q: string, n: number, offset: number) {
  const description = parseDescription(q)
  if (!description || !Number.isSafeInteger(offset) || offset < 0)
    throw new Error('invalid load-more request')
  return searchMatches({ q: description, n: parsePageSize(String(n)), offset })
}

/** Feedback on one Match: 'none' withdraws the visitor's vote. Returns a friendly message if back refuses or is unreachable. */
export async function sendVote(
  q: string,
  songId: string,
  vote: 'up' | 'down' | 'none'
) {
  const description = parseDescription(q)
  if (
    !description ||
    typeof songId !== 'string' ||
    !UUID.test(songId) ||
    !['up', 'down', 'none'].includes(vote)
  )
    throw new Error('invalid vote')
  const header = await visitorHeaders()
  try {
    const { response } = await back.POST('/feedback', {
      body: { description, song_id: songId, vote },
      params: { header },
    })
    if (response.ok) return {}
    if (response.status === 429) return { error: TOO_MANY_VOTES }
  } catch {} // back unreachable
  return { error: VOTE_FAILED }
}

/** Preview availability for a page of Matches that "carregar mais" appended. */
export async function previewsFor(songIds: string[]) {
  if (
    !Array.isArray(songIds) ||
    songIds.length > MAX_PAGE_SIZE ||
    !songIds.every((id) => typeof id === 'string')
  )
    throw new Error('invalid preview request')
  return lookupPreviews(songIds)
}
