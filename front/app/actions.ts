'use server'

import { back } from '@/lib/api/client'
import { parseDescription, parsePageSize } from '@/lib/search'

/** "Carregar mais": the next page of Matches. Runs on the server so the token stays there. */
export async function loadMore(q: string, n: number, offset: number) {
  const description = parseDescription(q)
  if (!description || !Number.isSafeInteger(offset) || offset < 0)
    throw new Error('invalid load-more request')
  const { data, response } = await back.GET('/search', {
    params: {
      query: { q: description, n: parsePageSize(String(n)), offset },
    },
  })
  // shortcut: any back failure (including offset past 10,000) throws; ticket 09 adds the friendly message
  if (!data) throw new Error(`search failed: HTTP ${response.status}`)
  return data.matches
}
