import 'server-only'
import { headers } from 'next/headers'

/** The visitor's IP for back, which stores only its salted hash. */
export async function visitorHeaders() {
  // Vercel overwrites X-Forwarded-For with the client IP; `next start` only fills it in when missing.
  // shortcut: on a self-hosted `next start` the client can spoof this header and vote as many visitors, put a proxy in front that overwrites it when self-hosting
  const ip = (await headers()).get('x-forwarded-for')?.split(',')[0].trim()
  if (!ip) throw new Error('no visitor IP in X-Forwarded-For')
  return { 'x-visitor-ip': ip }
}
