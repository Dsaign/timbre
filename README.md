<p align="center">
  <img src="docs/images/timbre-logo.svg" width="96" height="96" alt="timbre logo">
</p>

<h1 align="center">timbre.</h1>

<p align="center">
  Describe the music you want in your own words and get songs that fit.
  <br>
  <a href="https://timbreapp.vercel.app"><strong>timbreapp.vercel.app</strong></a>
</p>

<p align="center">
  <a href="https://github.com/Dsaign/timbre/actions/workflows/ci.yml"><img src="https://github.com/Dsaign/timbre/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <img src="https://img.shields.io/badge/Next.js-16.4-000000?logo=nextdotjs" alt="Next.js 16.4">
  <img src="https://img.shields.io/badge/FastAPI-0.162-009688?logo=fastapi&logoColor=white" alt="FastAPI 0.162">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white" alt="Python 3.13">
  <img src="https://img.shields.io/badge/PostgreSQL-18%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL 18 with pgvector">
</p>

<img width="2880" height="1800" alt="timbre home page, dark theme" src="https://github.com/user-attachments/assets/6524552a-40bb-4057-b0e2-03c69cc6a29a" />
<img width="2880" height="1800" alt="timbre search results, dark theme" src="https://github.com/user-attachments/assets/0c7ba03c-1a51-4ca4-918b-ec647ca669f2" />

## About

timbre is a music search engine for descriptions. You type what you feel like hearing, in Portuguese or English ("emo para chorar e cantar gritando", "sad indie with female vocals"), and it returns matching songs from a catalog of about 38,000 tracks. Each match can be previewed through Spotify and rated with 👍 or 👎, and those votes feed the next training run.

How a search works:

1. **Catalog.** Songs come from open music data: MusicBrainz for titles, artists and tags, AcousticBrainz for mood, genre and voice labels computed from the audio, and ListenBrainz for popularity. Each song gets a short text profile built from its labels and tags.
2. **Vectors.** Profiles and descriptions are embedded with [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) (384 dimensions, ONNX on CPU) and stored in Postgres with pgvector.
3. **Ranking.** Artist and title matches come first. The rest is a fusion of two rankings: vector similarity, optionally through a trained projection, and a direct match between the words of the description and each song's tags.
4. **Evaluation.** A benchmark of about 1,270 descriptions scores every model version, and a new version is promoted only if it doesn't score lower than the current one.

## Stack

| Layer | Technology |
|---|---|
| Front | Next.js 16.4, React 19.3, TypeScript 5.9, Tailwind CSS 4.3, Radix UI 1.8 (through shadcn), Lucide 1.62 |
| Back | Python 3.13, FastAPI 0.162, Uvicorn 0.54, psycopg 3.3, NumPy 2.5 |
| Search | multilingual-e5-small on ONNX Runtime 1.31 and tokenizers 0.23, PostgreSQL 18 with pgvector 0.8.7 |
| Database | plain SQL migrations with dbmate 2.37, row-level security per role |
| Tests | pytest, Vitest 5.0, Playwright 1.64 (Chromium, Firefox, WebKit and an iPhone 15 viewport) |
| Infra | Docker Compose, Caddy 2.11 for TLS, Vercel for the front, a Hetzner VPS for the back, GitHub Actions |

Package managers: pnpm 12 for `front/`, uv for `back/`.

```
front/     Next.js app
back/      FastAPI service, SQL migrations, worker jobs and the Compose stack
docs/      architecture decisions (adr/), agent roles (agents/), research notes, operations
scripts/   OpenAPI drift check and the first-deploy wizard
```

## Getting started

You need Docker with Compose, Node 26 with pnpm 12, and [uv](https://docs.astral.sh/uv/).

### Configure

Secrets live only in `back/.env` and `front/.env.local`, both git-ignored. Copy the names from each `.env.example` and fill in values (`openssl rand -hex 32` for passwords, the salt and the token; `FRONT_TOKEN` must be the same in both files). `SEARCH_LIMIT_PER_MIN` and `VOTE_LIMIT_PER_HOUR` default to 30 and 60 per visitor.

### Run

```bash
cd back
docker compose up -d --wait   # db, migrations, role passwords, seed Catalog, worker, API on 127.0.0.1:8000
cd ../front
pnpm install
pnpm dev                      # logs "[timbre] back /health → 200 ok" when back answers
```

Open http://localhost:3000. With `APP_ENV=development` in `back/.env`, the API docs are at http://localhost:8000/docs. Stop with `docker compose down` (add `-v` to wipe the database).

The first build downloads the e5 model (about 470 MB) into the image. After start, the worker needs a few seconds to build the Song vectors, and searches find nothing until it's done. A fresh stack starts with a seed Catalog of about 200 well-known Songs; [docs/operations.md](docs/operations.md#catalog-import) explains how to import the full one.

### Pre-commit hooks

The hooks block commits that contain secrets (gitleaks) or fail the fast checks CI runs (ruff on `back/`, ESLint and Prettier on `front/`). Install pre-commit and gitleaks user-locally:

```bash
uv tool install pre-commit
# gitleaks: download the linux_x64 tarball and checksums.txt from
# https://github.com/gitleaks/gitleaks/releases, then:
sha256sum --check --ignore-missing gitleaks_*_checksums.txt
tar -xzf gitleaks_*_linux_x64.tar.gz gitleaks && install -m 755 gitleaks ~/.local/bin/
pre-commit install            # from the repo root
pre-commit run --all-files    # optional: run it now
```

## Checks

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
pnpm format              # Prettier, rewrites files in place

cd ..
scripts/check-openapi-drift.sh   # fails if back/openapi.json or the TS types are stale
```

Playwright runs in Chromium, Firefox, WebKit and an iPhone 15 viewport (`--project=<name>` picks one). Install the browsers once with `pnpm exec playwright install chromium firefox webkit`; WebKit also needs `sudo pnpm exec playwright install-deps webkit`.

## Operations

[docs/operations.md](docs/operations.md) covers the jobs that build and maintain search, all run by the worker from `back/`:

- [Seed Catalog](docs/operations.md#seed-catalog) and the [Catalog import](docs/operations.md#catalog-import) from the MetaBrainz APIs
- [Retag](docs/operations.md#retag), which fills in missing MusicBrainz tags
- [Benchmark](docs/operations.md#benchmark): the evaluate job, its files and metrics
- [Own model](docs/operations.md#own-model): training, promotion and rollback

After an import, run them in this order, each once the previous job is done: `retag` → `build-vectors` → `evaluate` → `train`.

## Deploy

The front runs on Vercel (root directory `front`) and the back on one VPS. `back/compose.prod.yaml` puts Caddy in front of the API (TLS for `API_DOMAIN`, HTTP→HTTPS, HSTS), publishes only ports 80 and 443, and forces `APP_ENV=production`, which turns off the API docs. `scripts/deploy-wizard.sh` walks through the first setup: VPS, DNS, `back/.env`, Vercel, GitHub secrets and header checks.

To update the back, on the VPS (its `back/.env` sets `COMPOSE_FILE`):

```bash
cd /root/timbre && git pull && cd back && docker compose up -d --wait --build
```

## Change the API

After changing request or response models, regenerate and commit both files:

```bash
(cd back && uv run python -m timbre_back.openapi > openapi.json)
(cd front && pnpm api:types)
```

New migrations go in `back/migrations/` as `YYYYMMDDHHMMSS_description.sql` with `-- migrate:up` and `-- migrate:down` sections.

## How the project is run

- Every change reaches `main` through a pull request. The `main` ruleset requires green `front`, `back`, `stack` and `secrets` checks and blocks force-pushes and deletion. No approval is required, since the repo has one maintainer.
- Work is planned as tickets in `.scratch/` and decisions are recorded as ADRs in [docs/adr/](docs/adr/). Domain terms (Song, Match, Fit, Benchmark) are defined in [CONTEXT.md](CONTEXT.md).
- Coding agents do the implementation: Bob ([docs/agents/bob.md](docs/agents/bob.md)) builds each ticket, and Carl ([docs/agents/carl.md](docs/agents/carl.md)) reviews it against the repo standards and the ticket before the maintainer commits. The PR template asks for the ticket, the tests and Carl's review.

## Data and credits

- Song metadata, audio labels and listen counts come from [MusicBrainz](https://musicbrainz.org), [AcousticBrainz](https://acousticbrainz.org) and [ListenBrainz](https://listenbrainz.org), all run by the MetaBrainz Foundation. The seed Catalog in git uses only their CC0 fields.
- MusicBrainz tags are CC BY-NC-SA 3.0. They stay in the database and are never committed ([ADR 0002](docs/adr/0002-catalog-via-apis-not-dumps.md)).
- Spotify is used only to preview songs. It never decides which songs match ([ADR 0001](docs/adr/0001-spotify-only-for-preview.md)).
- Fonts: Bricolage Grotesque and Inter, both under the SIL Open Font License.
