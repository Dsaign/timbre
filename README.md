# timbre

Describe the music you want and get Matches. Early stage: search runs on a 200-Song seed Catalog with the baseline model (multilingual-e5-small).

- `front/`: the Next.js 16 app (pnpm).
- `back/`: the FastAPI service, SQL migrations (dbmate) and the Docker Compose stack (Postgres with pgvector).

## Setup (once per clone)

Secrets live only in `back/.env` and `front/.env.local`, both git-ignored. Copy the names from each `.env.example` and fill in values (`openssl rand -hex 32` for passwords, the salt and the token; `FRONT_TOKEN` must be the same in both files). `SEARCH_LIMIT_PER_MIN` and `VOTE_LIMIT_PER_HOUR` default to 30 and 60 per visitor. The tests need the test stack, which adds `-f compose.yaml -f compose.test.yaml` to raise both (every browser test is the same visitor).

The pre-commit hooks block commits that contain secrets (gitleaks) or fail the fast checks CI runs (ruff on `back/`, ESLint and Prettier on `front/`). Install pre-commit and gitleaks user-locally:

```bash
uv tool install pre-commit
# gitleaks: download the linux_x64 tarball and checksums.txt from
# https://github.com/gitleaks/gitleaks/releases, then:
sha256sum --check --ignore-missing gitleaks_*_checksums.txt
tar -xzf gitleaks_*_linux_x64.tar.gz gitleaks && install -m 755 gitleaks ~/.local/bin/
pre-commit install            # from the repo root
pre-commit run --all-files    # optional: run it now
```

## Run

```bash
cd back
docker compose up -d --wait   # db, migrations, role passwords, seed Catalog, worker, API on 127.0.0.1:8000
cd ../front
pnpm install
pnpm dev                      # logs "[timbre] back /health → 200 ok" when back answers
```

Open http://localhost:3000. With `APP_ENV=development` in `back/.env`, the API docs are at http://localhost:8000/docs. Stop with `docker compose down` (add `-v` to wipe the database).

## Check

```bash
cd back
uv run ruff check . && uv run ruff format --check .
uv run mypy src tests
uv run pyright
# The test stack (raised rate limits). Use it for pytest and for `pnpm test:e2e`.
docker compose -f compose.yaml -f compose.test.yaml up -d --wait --build
docker compose -f compose.yaml -f compose.test.yaml run --rm --build tests   # pytest inside the Compose network (the db port is not published)

cd ../front
pnpm lint
pnpm exec tsc --noEmit   # needs the route types: run `pnpm build` or `pnpm dev` once first
pnpm exec prettier --check .
pnpm build
pnpm test                # Vitest
pnpm test:e2e            # builds, then Playwright against `pnpm start`; needs the back test stack up (above)
pnpm format   # Prettier, rewrites files in place

cd ..
scripts/check-openapi-drift.sh   # fails if back/openapi.json or the TS types are stale
```

Playwright runs in Chromium, Firefox, WebKit and an iPhone 15 viewport (`--project=<name>` picks one). Install the browsers once with `pnpm exec playwright install chromium firefox webkit`; WebKit also needs `sudo pnpm exec playwright install-deps webkit`.

## Workflow

- Every change reaches `main` through a pull request. The `main` ruleset requires a PR (no approval, since the repo has one maintainer) and green `front`, `back`, `stack` and `secrets` checks, and blocks force-pushes and deletion.
- Agents: Bob (`docs/agents/bob.md`) builds a ticket, and Carl (`docs/agents/carl.md`) reviews it before it's committed. The PR template asks for the ticket, the tests and Carl's review.

The first build downloads the e5 model (about 470 MB) into the image. After start, the worker needs a few seconds to build the Song vectors; until then searches find nothing.

## Seed Catalog

`back/src/timbre_back/seed.json` holds about 200 well-known Songs with CC0 fields only (MusicBrainz ID, title, artist, ISRC, AcousticBrainz high-level probabilities, instrument credits, ListenBrainz listen counts). It is loaded on every `compose up` until the Catalog import has started. To fetch it again from the APIs (a few minutes, 1 request per second):

```bash
cd back && METABRAINZ_CONTACT=<your email or URL> uv run python scripts/fetch_seed.py
```

## Catalog import

The full Catalog (ADR 0002) is imported by the worker's `import-catalog` job: ListenBrainz's top artists, each artist's 50 most-listened recordings, kept with an ISRC and AcousticBrainz data, plus MusicBrainz tags (CC BY-NC-SA, so the data stays in the database and never in git). It stops once the Catalog (seed Songs included) has 10k Songs, or earlier when ListenBrainz's sitewide stats run out of artists (they list only the top 1,000), so expect up to about 10k; the worker log states the final count and why it stopped. Afterwards the seed Songs get their MusicBrainz tags too. It takes one to two hours at 1 request per second. Set `METABRAINZ_CONTACT` (your email or URL) and `LISTENBRAINZ_TOKEN` in `back/.env`, then:

```bash
cd back && docker compose up -d --wait
docker compose exec worker python -m timbre_back.catalog_import   # queues the job
docker compose logs -f worker                                     # progress, one line per artist
```

An interrupted import resumes after the last finished artist (or seed tag batch): a restarted worker picks the job up again, and when an API stays down (429, 5xx or no connection after four tries) the job stays queued and runs again a minute later, while other jobs run meanwhile. It retries without limit; to cancel it, set its `status` to `'failed'`. An artist ListenBrainz answers 404 for is logged and skipped. Any other error (for example a 401 from an expired `LISTENBRAINZ_TOKEN`) marks it failed (`jobs.queue.status = 'failed'`, the reason in `error`); fix the cause and queue it again with the same command. build-vectors runs when the import ends, for every new or changed Song.

### Re-check the cutoff

A Song is a Match when its Fit is above the promoted model's cutoff: 0.835, in `catalog.model_versions` (row 1, set in `back/migrations/20261029160000_vectors_jobs_model_versions.sql`). It was picked on the seed, so check it again on the full Catalog. Wait until the import and build-vectors are done (`SELECT kind, status FROM jobs.queue WHERE status = 'queued'` returns nothing), then from `back/`:

```bash
docker compose -f compose.yaml -f compose.test.yaml run --rm tests \
  pytest -p no:cacheprovider tests/test_search.py -k "sample_description or nonsense"
```

The test stack uses the same database volume as `docker compose up`, so these 7 tests search the full Catalog. They pass when the fixed nonsense string `xkqzv wplmr tjhgf` gets 0 Matches and each of the six sample Descriptions (`SAMPLES` in `back/tests/test_search.py`) gets at least 1. If no single cutoff gives both, stop and ask the project owner: don't add a gibberish filter.

## Change the API

After changing request or response models, regenerate and commit both files:

```bash
(cd back && uv run python -m timbre_back.openapi > openapi.json)
(cd front && pnpm api:types)
```

New migrations go in `back/migrations/` as `YYYYMMDDHHMMSS_description.sql` with `-- migrate:up` and `-- migrate:down` sections.
