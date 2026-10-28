## Conventions

- The Next.js app lives in `front/` with its own `package.json`. Run pnpm commands (`dev`, `lint`, `build`, `exec tsc --noEmit`) from `front/`. The repo root has no JS tooling.
- The FastAPI service lives in `back/` (Python 3.13, `uv`, src layout in `src/timbre_back/`). Run `uv run ruff check .`, `uv run mypy src tests` and `docker compose` from `back/`. pytest runs inside Compose (`docker compose run --rm tests`) because the database port is not published.
- Database changes are plain SQL dbmate migrations in `back/migrations/` (`YYYYMMDDHHMMSS_name.sql`, with `-- migrate:up` / `-- migrate:down`). No ORM, bound parameters only.
- After changing API models, regenerate `back/openapi.json` and `front/lib/api/schema.d.ts` (see README). `scripts/check-openapi-drift.sh` fails if either is stale.
- UI primitives: Radix UI (through shadcn components). Icons: Lucide (`lucide-react`). Brand logos use the official SVGs. See `docs/adr/0003-radix-ui-and-lucide-icons.md`.

## Agent skills

### Issue tracker

Issues and specs are local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
