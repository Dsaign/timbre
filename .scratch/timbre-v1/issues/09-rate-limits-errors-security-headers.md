# 09: Rate limits, error states and security headers

**What to build:** scripts can't abuse searching or voting. Visitors get friendly messages when they hit a limit or when the service is down. Every page ships with strict security headers.

**Blocked by:** 07, 08

**Status:** resolved

- [x] Rate limits per visitor hash, counted in Postgres (no Redis), with env-var defaults `SEARCH_LIMIT_PER_MIN=30` and `VOTE_LIMIT_PER_HOUR=60`.
  - Over the limit, the API returns 429.
  - The test stack raises the limits, and one API test sets them low to assert the 429.
- [x] Front shows "muitas buscas, tente em instantes" on 429, and a friendly message when the API is unreachable.
- [x] Request bodies over about 16 KB are rejected. Production errors never include stack traces or SQL.
- [x] Front sends a static CSP through Next's headers config, in Report-Only mode: `script-src 'self' 'unsafe-inline' https://open.spotify.com`, `frame-src https://open.spotify.com`, `frame-ancestors 'none'`. There is no reporting endpoint; violations show in the browser console. It also sends HSTS, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and a Permissions-Policy turning off camera, microphone and location.
- [x] Preview and the theme script work with no CSP violations in the console.

## Comments

- Review (Carl): Standards 0 hard + 5 judgement (worst: rate-limit cleanup and SQL live in feedback.py/main.py instead of their own module); Spec 3 partial, 2 to confirm (worst: CSP adds `'unsafe-eval'` + spotifycdn beyond the ticket; vote 429 has no friendly message; test stack limits raised only in CI).
- Review (Carl, re-review): previous findings all fixed. Standards 0 hard + 5 judgement (worst: auto-merged compose.override.yaml fails open, limits 100000 if prod forgets `-f compose.yaml`); Spec 0 missing, 2 risks (worst: same override leak; stale 5 s timer hides a newer vote message early).
- Review (Carl, round 3): previous findings all fixed. Standards 0 hard, 1 doc drift + 1 judgement (worst: CLAUDE.md still runs pytest without compose.test.yaml); Spec 0 findings.

## Answer

Built. Rate limits count in `ratelimit.hits` (one fixed-window row per visitor hash and action), touched only through the `ratelimit.hit()` SECURITY DEFINER function (migration `20261103200000_rate_limits.sql`, code in `back/src/timbre_back/ratelimit.py`). `/search` and `/feedback` return 429 over `SEARCH_LIMIT_PER_MIN` (30) / `VOTE_LIMIT_PER_HOUR` (60). A separate daily task drops counters older than a day. `back/compose.test.yaml` raises both limits only when passed explicitly (`-f compose.yaml -f compose.test.yaml`, as in CI and the README); a plain `docker compose up` keeps 30/60. Bodies over 16 KB get 413 (chunked included). Production 500s are plain "Internal Server Error". Front shows "Muitas buscas, tente em instantes." on 429 and "Não foi possível buscar agora. Tente de novo em instantes." when back fails or can't be reached, for the first page and for "carregar mais". A refused vote is undone and shows "Muitos votos, tente mais tarde." (429) or "Não foi possível votar agora. Tente de novo em instantes." in a `role="status"` bubble under the thumbs for 5 seconds. `next.config.ts` sends the Report-Only CSP, HSTS, nosniff, Referrer-Policy and Permissions-Policy.

Approved deviation (user): Spotify's iFrame API loads its code from `https://embed-cdn.spotifycdn.com` and that code runs each module through `eval()`. So with the CSP exactly as written, Preview logs violations. `script-src` also allows `'unsafe-eval'` and `https://embed-cdn.spotifycdn.com`; the user approved keeping both. HSTS has no `preload`; the user decides that in ticket 16. There is no theme script yet (ticket 10).

Tests: `back/tests/test_limits.py` (429 for search and votes with low in-process limits, 413 by length and chunked, no trace in production 500s), ratelimit cases in `back/tests/test_db_roles.py`, and `front/e2e/security-headers.spec.ts` (headers, and no CSP violation during search plus Preview).
