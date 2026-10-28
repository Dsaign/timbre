# timbre

Describe a song you like and get music recommendations. Early stage: the search form exists, the recommendation logic does not yet.

- `front/`: the Next.js 16 app (pnpm).
- `back/`: the FastAPI service, SQL migrations (dbmate) and the Docker Compose stack (Postgres with pgvector).

## Setup (once per clone)

Secrets live only in `back/.env` and `front/.env.local`, both git-ignored. Copy the names from each `.env.example` and fill in values (`openssl rand -hex 32` for passwords, the salt and the token; `FRONT_TOKEN` must be the same in both files).

A gitleaks pre-commit hook blocks commits that contain secrets. Install both tools user-locally:

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
docker compose up -d --wait   # db, migrations, role passwords, API on 127.0.0.1:8000
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
docker compose run --rm --build tests   # pytest inside the Compose network (the db port is not published)

cd ../front
pnpm lint
pnpm exec tsc --noEmit   # needs the route types: run `pnpm build` or `pnpm dev` once first
pnpm exec prettier --check .
pnpm build
pnpm format   # Prettier, rewrites files in place

cd ..
scripts/check-openapi-drift.sh   # fails if back/openapi.json or the TS types are stale
```

## Change the API

After changing request or response models, regenerate and commit both files:

```bash
(cd back && uv run python -m timbre_back.openapi > openapi.json)
(cd front && pnpm api:types)
```

New migrations go in `back/migrations/` as `YYYYMMDDHHMMSS_description.sql` with `-- migrate:up` and `-- migrate:down` sections.
