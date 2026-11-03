'use server'

import { back } from '@/lib/api/client'
import { MAX_PAGE_SIZE } from '@/lib/grid'
import { lookupPreviews } from '@/lib/preview'
import { parseDescription, parsePageSize } from '@/lib/search'
import { visitorHeaders } from '@/lib/visitor'

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

/** "Carregar mais": the next page of Matches. Runs on the server so the token stays there. */
export async function loadMore(q: string, n: number, offset: number) {
  const description = parseDescription(q)
  if (!description || !Number.isSafeInteger(offset) || offset < 0)
    throw new Error('invalid load-more request')
  const { data, response } = await back.GET('/search', {
    params: {
      query: { q: description, n: parsePageSize(String(n)), offset },
      header: await visitorHeaders(),
    },
  })
  // shortcut: any back failure (including offset past 10,000) throws; ticket 09 adds the friendly message
  if (!data) throw new Error(`search failed: HTTP ${response.status}`)
  return data.matches
}

/** Feedback on one Match: 'none' withdraws the visitor's vote. */
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
  const { response } = await back.POST('/feedback', {
    body: { description, song_id: songId, vote },
    params: { header: await visitorHeaders() },
  })
  if (!response.ok) throw new Error(`vote failed: HTTP ${response.status}`)
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
