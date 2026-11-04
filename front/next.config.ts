import type { NextConfig } from 'next'

// Report-Only first: violations show in the browser console, nothing is blocked or reported.
// 'unsafe-inline': Next's inline bootstrap scripts (no nonces, so pages stay static).
// Spotify's iFrame API (open.spotify.com) loads its code from embed-cdn.spotifycdn.com, and that
// code runs each module through eval(), so Preview needs both the CDN and 'unsafe-eval'.
const csp = [
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://open.spotify.com https://embed-cdn.spotifycdn.com",
  'frame-src https://open.spotify.com',
  "frame-ancestors 'none'",
].join('; ')

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Content-Security-Policy-Report-Only', value: csp },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains',
          },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
        ],
      },
    ]
  },
  experimental: {
    agentFeedback: true,
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      '*.css': {
        loaders: ['@tailwindcss/turbopack'],
        as: '*.css',
      },
    },
  },
}

export default nextConfig
