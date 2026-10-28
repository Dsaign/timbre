# 04: First Matches end to end (baseline)

**What to build:** a visitor types a Description, submits, and sees how many Matches were found plus a grid of Matches (title and artist). This runs on a small seed Catalog with the baseline model: the first full path through the database, worker, API and front.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] A one-off fetch script produces a committed JSON seed of about 200 well-known Songs. It contains **CC0 fields only**: MusicBrainz recording ID, title, artist, ISRC, AcousticBrainz high-level labels and probabilities, instrument credits, and ListenBrainz listen counts. No MusicBrainz tags or genres (ADR 0002, licence).
- [ ] A Postgres-backed job queue and a worker process exist. The build-vectors job writes each Song's profile text (AcousticBrainz labels above a probability threshold, written as words, plus instruments) and its `multilingual-e5-small` passage vector, for Songs that have none.
- [ ] A model-versions table exists, with row 1 for the baseline: no Benchmark score yet, plus the cutoff and the Popularity weight.
  - Order = Fit + 0.02 × log1p(listens) / log1p(max listens).
  - The cutoff is chosen on the seed so that a fixed nonsense string returns 0 Matches and each of the six approved sample Descriptions (ticket 06) returns at least 1.
  - If no single cutoff achieves both, stop and ask the owner. Don't add a gibberish filter.
- [ ] Search endpoint:
  - takes a Description (1–300 characters after trimming), `n` (1–60, default 24) and an `offset` (≥ 0);
  - returns the total Match count and one ordered page of Matches (Song ID, title, artist);
  - invalid input gets a validation error;
  - the front token is required.
- [ ] Front: the form submits GET `?q=`. The server renders the count and the grid (fixed N = 24) inside a Suspense boundary, with a skeleton loading state. Front server code validates input with the same rules before calling the API.
- [ ] API tests (seam 1) cover count, cutoff (nonsense → 0), order, validation and the token. One Playwright happy path: type, submit, see the count and cards.
