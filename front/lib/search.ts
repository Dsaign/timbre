export const PAGE_SIZE = 24
const DESCRIPTION_MAX = 300

/** The API's rule: a Description is 1–300 characters (code points) after trimming. */
export function parseDescription(q: string | string[] | undefined) {
  if (typeof q !== 'string') return null
  const description = q.trim()
  const length = [...description].length
  return length >= 1 && length <= DESCRIPTION_MAX ? description : null
}
