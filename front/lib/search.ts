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
