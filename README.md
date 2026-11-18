# timbre

<img width="2880" height="1800" alt="timbre-home-dark" src="https://github.com/user-attachments/assets/6524552a-40bb-4057-b0e2-03c69cc6a29a" />
<img width="2880" height="1800" alt="timbre-dark" src="https://github.com/user-attachments/assets/0c7ba03c-1a51-4ca4-918b-ec647ca669f2" />

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
# The test stack (raised rate limits, its own fresh seed database and models volume; the dev
# Catalog stays untouched). Use it for pytest and for `pnpm test:e2e`. `docker compose up -d`
# switches back to the dev database.
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

The full Catalog (ADR 0002) is imported by the worker's `import-catalog` job: ListenBrainz's top artists, each artist's 50 most-listened recordings, kept with an ISRC and AcousticBrainz data, plus MusicBrainz tags (CC BY-NC-SA, so the data stays in the database and never in git). It stops once the Catalog (seed Songs included) has 50k Songs, or earlier when ListenBrainz's sitewide stats run out of artists (they list only the top 1,000); the first import reached 10k Songs with 236 artists, so expect roughly 30–40k (an estimate: AcousticBrainz stopped in 2022, so recent releases drop out). The worker log states the final count and why it stopped. Afterwards the seed Songs get their MusicBrainz tags too. It takes several hours at 1 request per second. Set `METABRAINZ_CONTACT` (your email or URL) and `LISTENBRAINZ_TOKEN` in `back/.env`, then:

```bash
cd back && docker compose up -d --wait
docker compose exec worker python -m timbre_back.catalog_import   # queues the job
docker compose logs -f worker                                     # progress, one line per artist
```

An interrupted import resumes after the last finished artist (or seed tag batch): a restarted worker picks the job up again, and when an API stays down (429, 5xx or no connection after four tries) the job stays queued and runs again a minute later, while other jobs run meanwhile. It retries without limit; to cancel it, set its `status` to `'failed'`. An artist ListenBrainz answers 404 for is logged and skipped. Any other error (for example a 401 from an expired `LISTENBRAINZ_TOKEN`) marks it failed (`jobs.queue.status = 'failed'`, the reason in `error`); fix the cause and queue it again with the same command. build-vectors runs when the import ends, for every new or changed Song. A Catalog imported under a lower target grows the same way: queue the job again and it skips every artist in `catalog.import_artists` and goes on with the next ones.

### Retag

A Song keeps up to 5 MusicBrainz tags: its recording's own first, then its release group's, then its artist's, most-voted first within each. Songs imported before ticket 20 kept only the most specific level that had any tag (Slayer's "Bloodline" had only `00s`). The `retag` job fetches the tags again for every Song with fewer than 5, 50 Songs per ListenBrainz call (about 4 minutes for 11k Songs). Each Song changes in place: it keeps its vector, so it stays searchable, and build-vectors (queued at the end) redoes the ones whose tags changed. Then, each once the previous job is done: `retag` → `build-vectors` → `evaluate` → `train`.

```bash
docker compose exec worker python -m timbre_back.catalog_import retag   # queues the job
docker compose logs -f worker | grep tags:                              # progress
```

An API that stays down defers it like the import. A rerun asks again for every Song that still has fewer than 5 tags.

After an import, in this order, each once the previous job is done (`SELECT kind, status FROM jobs.queue WHERE status = 'queued'` returns nothing): build-vectors (queued by the import itself), then evaluate (see Benchmark) so the cutoff and Popularity weight fit the new Catalog, then train (see Own model). Then re-check the cutoff (below).

### Re-check the cutoff

A Song is a Match when its Fit is above the promoted model's cutoff, in `catalog.model_versions` (the row with `promoted`). It started at 0.835, picked on the seed in `back/migrations/20261029160000_vectors_jobs_model_versions.sql`; the evaluate job (see Benchmark) now tunes it. Check it again on the full Catalog. Wait until the import and build-vectors are done (`SELECT kind, status FROM jobs.queue WHERE status = 'queued'` returns nothing), then from `back/`:

```bash
docker compose up -d --wait
docker compose --profile test run --rm tests \
  pytest -p no:cacheprovider tests/test_search.py -k "sample_description or nonsense"
```

Without `compose.test.yaml` the tests service runs on the dev stack, so these 7 tests search the full Catalog (the test stack has its own fresh seed database). They pass when the fixed nonsense string `xkqzv wplmr tjhgf` gets 0 Matches and each of the six sample Descriptions (`SAMPLES` in `back/tests/test_search.py`) gets at least 1. If no single cutoff gives both, stop and ask the project owner: don't add a gibberish filter.

## Benchmark

The Benchmark scores the model: Descriptions, each with at least 3 Songs that should be Matches. It lives in three committed files in `back/src/timbre_back/`, each a JSON list of `{"description", "source", "reviewed", "accept_tags", "songs": [{"id", "title", "artist"}]}` where `id` is the Song's MusicBrainz recording ID in the Catalog (`title` and `artist` are only for reading) and the optional `accept_tags` are the tag keys (lowercase, no accents, words joined by one space) that make a Match relevant to the Description:

- `benchmark_drafted.json`: 60 Descriptions drafted by Bob (`"source": "drafted"`), reviewed by the owner.
- `benchmark_hand_written.json`: the owner's 41 (`"source": "hand-written"`), in pt-BR and English.
- `benchmark_generated.json`: 1,173 Descriptions generated from the Catalog by `back/scripts/generate_benchmark.py` (`"source": "generated"`, not reviewed), half pt-BR, half English: a frequent genre tag crossed with an AcousticBrainz mood or voice label ("rock pra treinar", "sad mechanical noisy beats"). Over half name no accept tag word for word (paraphrases and Portuguese names). Its expected Songs carry the genre among their 3 most-voted tags and the label, most listened first. A candidate within e5 cosine 0.92 of a `training_drafted.json` Description is dropped, so the file keeps no drafted training Description out of training. Regenerate it with the command in the script's docstring (deterministic for a given Catalog).

Load the files into `catalog` and score the model, from `back/` with the stack up. The worker image holds a copy of the files, so rebuild it after editing them:

```bash
docker compose up -d --build worker                          # picks up edited Benchmark files
docker compose exec worker python -m timbre_back.benchmark   # loads the files, queues the evaluate job
docker compose logs worker | grep evaluate                   # the report
```

The score is the share of expected Songs in the top 24 Matches (recall@24), averaged over Descriptions; promotion uses it. The log also gives, per file, recall@24 and precision@16: how many of the first 16 Matches carry one of the Description's `accept_tags`, out of 16 (a shorter list counts its missing Matches as misses), averaged over the Descriptions that have them. Both are recorded per file on the model version (`recall_at_24`, `precision_at_16`, JSON by `source`). The job also tunes the cutoff (0.005 grid, only cutoffs at least 0.005 above the best Fit of the nonsense string `xkqzv wplmr tjhgf`, so it keeps 0 Matches; ties to the highest) and the Popularity weight (0 to 0.05 in 0.005 steps, ties to the lowest), and records the score, cutoff and weight on the promoted model version. With no Song vectorized yet it logs that it skipped and changes nothing. The new cutoff and weight are live at once. A Song ID missing from the Catalog, or a Description with fewer than 3 Songs, stops the load with an error. Training never learns from it (see Own model).

Baseline (multilingual-e5-small) on the full Benchmark of 100, on the 10,000-Song Catalog (2026-11-16): score 0.112, cutoff 0.830, Popularity weight 0.050. A grown Catalog (up to 50k Songs, see Catalog import) keeps every Benchmark Song, since an import never deletes Songs; run evaluate after its build-vectors, before train.

## Own model

The train job trains a model version on top of the frozen multilingual-e5-small, on CPU: a projection of the Description vector, and a head that predicts the Song's AcousticBrainz labels (`catalog.songs.labels`). Fit is 0.8 × the cosine of the projected Description with the Song vector + 0.2 × (1 − mean label difference); see `back/src/timbre_back/model.py`. Both layers are ridge regressions, then a hinge loss on CPU moves each 👎 Song's Fit at least 0.05 below the 👍 Songs of the same Description; a run takes seconds.

It learns from `back/src/timbre_back/training_drafted.json` (Descriptions with Songs drafted by Bob from Catalog tags and labels, same format as the Benchmark files without `source`/`reviewed`) and from Feedback: 👍 Songs are positives, 👎 Songs are hard negatives. Any Description that is a Benchmark Description, or within e5 cosine 0.92 of one, is left out. Then it scores the new version on the Benchmark (tuning cutoff and weight as evaluate does), scores the promoted version the same way, records the new version with its file on the `models` volume, and promotes it if its score is not lower. Version ids come from a sequence, so two runs never share a file. The API reads the promoted version on every search, so a promotion is live at once, without a restart; if its file is missing, the API logs it once and searches with the baseline (version 1: plain e5, its cutoff and weight).

```bash
docker compose up -d --build worker                       # picks up an edited training file
docker compose exec worker python -m timbre_back.train    # queues the train job
docker compose logs worker | grep train:                  # the report
```

To go back to an earlier version, move `promoted` in one transaction (`UPDATE catalog.model_versions SET promoted = false; UPDATE catalog.model_versions SET promoted = true WHERE id = <id>;`).

Retrain after a Catalog import, once build-vectors and evaluate are done (see Catalog import), so the new version is trained and scored on the grown Catalog.

First run (2026-11-16, 96 Descriptions after excluding 34 near the Benchmark, 10,000-Song Catalog): version 2 scores 0.125 at cutoff 0.905 and weight 0.050, against the baseline's 0.112. Promoted. A re-run with the hinge (version 17; ids skipped by tests) scores the same 0.125 and, not being worse, is promoted.

## Deploy

Front on Vercel (root directory `front`), back on one VPS: `back/compose.prod.yaml` adds Caddy (TLS for `API_DOMAIN`, HTTP→HTTPS, HSTS) in front of the API, publishes only ports 80 and 443, and forces `APP_ENV=production` (no API docs). `scripts/deploy-wizard.sh` walks through the first setup (VPS, DNS, `back/.env`, Vercel, GitHub secrets, header checks). Update the back with `cd /root/timbre && git pull && cd back && docker compose up -d --wait --build` on the VPS (its `back/.env` sets `COMPOSE_FILE`).

## Change the API

After changing request or response models, regenerate and commit both files:

```bash
(cd back && uv run python -m timbre_back.openapi > openapi.json)
(cd front && pnpm api:types)
```

New migrations go in `back/migrations/` as `YYYYMMDDHHMMSS_description.sql` with `-- migrate:up` and `-- migrate:down` sections.
