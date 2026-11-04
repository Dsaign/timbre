import 'server-only'
import { back } from '@/lib/api/client'
import type { components, paths } from '@/lib/api/schema'
import { visitorHeaders } from '@/lib/visitor'
import { MAX_PAGE_SIZE } from './grid'

export const PAGE_SIZE = 24
const DESCRIPTION_MAX = 300

/** The API's rule: a Description is 1–300 characters (code points) after trimming. */
export function parseDescription(q: string | string[] | undefined) {
  if (typeof q !== 'string') return null
  const description = q.trim()
  const length = [...description].length
  return length >= 1 && length <= DESCRIPTION_MAX ? description : null
}

/** N from the URL: a positive integer, capped at 60 (the API rejects more); else 24. */
export function parsePageSize(n: string | string[] | undefined) {
  const size = typeof n === 'string' && /^\d+$/.test(n) ? Number(n) : 0
  return size >= 1 ? Math.min(size, MAX_PAGE_SIZE) : PAGE_SIZE
}

const TOO_MANY_SEARCHES = 'Muitas buscas, tente em instantes.'
const SEARCH_FAILED =
  'Não foi possível buscar agora. Tente de novo em instantes.'

/** A page of Matches, or the friendly message to show when back refuses or is unreachable. */
export async function searchMatches(
  query: paths['/search']['get']['parameters']['query']
): Promise<
  { data: components['schemas']['SearchResult'] } | { error: string }
> {
  const header = await visitorHeaders()
  try {
    const { data, response } = await back.GET('/search', {
      params: { query, header },
    })
    if (data) return { data }
    return {
      error: response.status === 429 ? TOO_MANY_SEARCHES : SEARCH_FAILED,
    }
  } catch {
    return { error: SEARCH_FAILED } // back unreachable
  }
}
