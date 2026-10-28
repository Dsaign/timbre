# 09: Rate limits, error states and security headers

**What to build:** scripts can't abuse searching or voting. Visitors get friendly messages when they hit a limit or when the service is down. Every page ships with strict security headers.

**Blocked by:** 07, 08

**Status:** ready-for-agent

- [ ] Rate limits per visitor hash, counted in Postgres (no Redis), with env-var defaults `SEARCH_LIMIT_PER_MIN=30` and `VOTE_LIMIT_PER_HOUR=60`.
  - Over the limit, the API returns 429.
  - The test stack raises the limits, and one API test sets them low to assert the 429.
- [ ] Front shows "muitas buscas, tente em instantes" on 429, and a friendly message when the API is unreachable.
- [ ] Request bodies over about 16 KB are rejected. Production errors never include stack traces or SQL.
- [ ] Front sends a static CSP through Next's headers config, in Report-Only mode: `script-src 'self' 'unsafe-inline' https://open.spotify.com`, `frame-src https://open.spotify.com`, `frame-ancestors 'none'`. There is no reporting endpoint; violations show in the browser console. It also sends HSTS, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and a Permissions-Policy turning off camera, microphone and location.
- [ ] Preview and the theme script work with no CSP violations in the console.
