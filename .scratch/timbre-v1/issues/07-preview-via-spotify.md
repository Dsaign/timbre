# 07: Preview via Spotify

**What to build:** Matches that are available on Spotify get a Preview button and a "LISTEN ON SPOTIFY" link. Clicking Preview plays the Song in one docked Spotify player at the bottom of the page. Matches not on Spotify show neither. Spotify stays behind its wall (ADR 0001).

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] The Spotify cache lives in the `preview` schema and is reached only through the API's `api_preview` connection pool. It stores the Song ID as a plain value with no foreign key.
- [ ] The Preview lookup endpoint takes up to 60 Song IDs and reports, for each one, a Spotify track reference or "not available".
  - It searches by ISRC first, then by title + artist (Client Credentials).
  - At most 4 lookups run at a time.
  - On 429 it honors `Retry-After`, otherwise retries with exponential backoff and jitter (about 0.5 s, 1 s, 2 s), at most 3 retries.
  - Found and not-found results are cached for 24 h. Errors are never cached and are reported as "not available".
- [ ] A daily timer in the API process, on the `api_preview` pool, deletes expired cache rows. The worker never holds preview credentials.
- [ ] Each card's Preview controls are inside their own Suspense boundary, so the grid appears before lookups finish.
- [ ] A Song is either found, with Preview and "LISTEN ON SPOTIFY" linking directly to the track, or not available, with neither.
- [ ] One docked Spotify Embed, through the iFrame API. Starting another card's Preview switches the player. The page listens only for play and pause events.
- [ ] Spotify branding follows `docs/research/spotify-platform-terms.md`: the full logo at 70 px or larger, "LISTEN ON SPOTIFY", and metadata unchanged.
- [ ] Tests:
  - API tests use recorded Spotify HTTP responses for backoff, caching and not-found.
  - Seam 3 tests confirm that the search and worker roles still cannot read `preview`.
- [ ] The Spotify client ID and secret are added as GitHub Actions secrets. Playwright, against real Spotify, checks that clicking Preview loads the right track in the docked player and that the iFrame API reports `isPaused=false`. This test is skipped only when the secret is absent (Dependabot and fork PRs).
