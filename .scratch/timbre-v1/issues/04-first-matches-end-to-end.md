# 04: First Matches end to end (baseline)

**What to build:** a visitor types a Description, submits, and sees how many Matches were found plus a grid of Matches (title and artist). This runs on a small seed Catalog with the baseline model: the first full path through the database, worker, API and front.

**Blocked by:** 02

**Status:** ready-for-human

- [x] A one-off fetch script produces a committed JSON seed of about 200 well-known Songs. It contains **CC0 fields only**: MusicBrainz recording ID, title, artist, ISRC, AcousticBrainz high-level labels and probabilities, instrument credits, and ListenBrainz listen counts. No MusicBrainz tags or genres (ADR 0002, licence).
- [x] A Postgres-backed job queue and a worker process exist. The build-vectors job writes each Song's profile text (AcousticBrainz labels above a probability threshold, written as words, plus instruments) and its `multilingual-e5-small` passage vector, for Songs that have none.
- [x] A model-versions table exists, with row 1 for the baseline: no Benchmark score yet, plus the cutoff and the Popularity weight.
  - Order = Fit + 0.02 × log1p(listens) / log1p(max listens).
  - The cutoff is chosen on the seed so that a fixed nonsense string returns 0 Matches and each of the six approved sample Descriptions (ticket 06) returns at least 1.
  - If no single cutoff achieves both, stop and ask the owner. Don't add a gibberish filter.
- [x] Search endpoint:
  - takes a Description (1–300 characters after trimming), `n` (1–60, default 24) and an `offset` (≥ 0);
  - returns the total Match count and one ordered page of Matches (Song ID, title, artist);
  - invalid input gets a validation error;
  - the front token is required.
- [x] Front: the form submits GET `?q=`. The server renders the count and the grid (fixed N = 24) inside a Suspense boundary, with a skeleton loading state. Front server code validates input with the same rules before calling the API.
- [x] API tests (seam 1) cover count, cutoff (nonsense → 0), order, validation and the token. One Playwright happy path: type, submit, see the count and cards.

## Comments

- 2026-10-29, implemented by Bob; waiting on the owner's review and commit. The seed comes from `back/scripts/fetch_seed.py` → `back/src/timbre_back/seed.json` (200 Songs, 138 artists, CC0 fields only). Candidates are ListenBrainz's sitewide all-time top recordings (at most 3 per artist), kept only with an ISRC (LB metadata API) and AcousticBrainz high-level data (AB bulk API, still live). ListenBrainz now answers 401 without an auth token on `/1/popularity/*`, so the per-artist route in ticket 12 needs a ListenBrainz token. e5 runs as the ONNX export from the model's own Hugging Face repo with `onnxruntime` + `tokenizers` (no torch), and is baked into the image by `ADD --checksum` at a pinned revision (+470 MB). The queue is `jobs.queue`: the worker holds the row lock for the whole run, so a crash leaves the job queued. A `seed` Compose service upserts the seed and queues build-vectors, and a `worker` service runs the queue. `catalog.model_versions` row 1 is the baseline: cutoff 0.835, Popularity weight 0.02, promoted. Cutoff on the seed (best Fit): nonsense `xkqzv wplmr tjhgf` 0.806; samples 0.846 / 0.852 / 0.873 / 0.878 / 0.842 / 0.859. At 0.835, Matches are 18 / 24 / 102 / 74 / 3 / 26 and the nonsense string gets 0. The margin is thin: about 26% of 300 random letter strings still get ≥1 Match at 0.835 (15% at 0.84, where "sad piano ballad" keeps only 1). The API caps `offset` at 10,000 (not in the spec) so huge values give 422, not 500. Verified: ruff, ruff format, mypy strict, pytest 83 passed on a fresh volume, front lint/Prettier/tsc/build, Vitest, Playwright (2 passed), the drift check, pip-audit and Trivy (0 HIGH/CRITICAL), and dbmate rollback/up.
