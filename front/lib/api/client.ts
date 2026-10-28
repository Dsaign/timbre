import 'server-only'
import createClient from 'openapi-fetch'
import type { paths } from './schema'

const { BACK_URL, FRONT_TOKEN } = process.env
if (!BACK_URL?.trim() || !FRONT_TOKEN?.trim()) {
  throw new Error(
    'BACK_URL and FRONT_TOKEN must be set for the back API client (see front/.env.example).'
  )
}

// Server-only: the front→back token must never reach the browser.
export const back = createClient<paths>({
  baseUrl: BACK_URL,
  headers: { Authorization: `Bearer ${FRONT_TOKEN}` },
})
