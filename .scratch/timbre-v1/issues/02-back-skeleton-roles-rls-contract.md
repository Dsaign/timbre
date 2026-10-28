# 02: back/ skeleton: database roles, RLS and the API contract

**What to build:** a running back end next to the front. One Docker Compose command starts Postgres (with pgvector) and the FastAPI service. The database already has the schemas, roles and row level security the whole project depends on. The front's server code can call the API through a typed client generated from the committed OpenAPI spec, and the API refuses any caller without the front's token.

**Blocked by:** 01

**Status:** resolved

- [x] One Compose command starts Postgres with pgvector and the API. The database port is not published outside the Compose network.
- [x] Plain, numbered, descriptive SQL migrations (no ORM) create:
  - the schemas `catalog`, `feedback`, `preview` and `jobs`;
  - the roles `ml_worker`, `api_search` and `api_preview`, each with only the grants the spec lists;
  - minimal placeholder tables where needed.
- [x] Row level security is enabled and forced on every table, with deny-by-default policies.
- [x] Database-role tests (seam 3), run by connecting as each real role:
  - `ml_worker` and `api_search` cannot read `preview`;
  - `api_preview` cannot read `catalog` or `feedback`;
  - each role can do its allowed operations.
- [x] A health endpoint answers only when called with the correct front token. A missing or wrong token gets 401. The front's server code calls it through the generated typed client, and the result is visible in a dev-only way (for example a log line or a small status indicator).
- [x] The OpenAPI spec is generated from the API models and committed. The typed TypeScript client in `front` is generated from it. One command fails when the committed spec and the code disagree.
- [x] Interactive API docs are enabled only in the development environment.
- [x] The root `.env` is split and then removed:
  - `front/.env.local` holds the front→back token and the back URL;
  - `back/.env` holds the Spotify client ID and secret, one password per database role, the IP-hash salt and the front→back token.
  
  Each service has a names-only `.env.example`, and git ignores every real env file.
- [x] A gitleaks pre-commit hook is configured. Installing gitleaks locally is documented in the README.
- [x] `back` tooling: Python 3.13 with `uv`, `ruff` (including the SQL-string rule S608), `mypy` and `pytest`. All of it passes.

## Comments

- 2026-10-28, implemented by Bob and reviewed against standards and spec; waiting on the owner's commit. Owner decisions: dbmate migrations plus a psql step for role passwords, async psycopg 3, a Bearer token (401 + `WWW-Authenticate`), the uv src layout (`back/src/timbre_back/`), openapi-typescript + openapi-fetch, and gitleaks through the pre-commit framework (`gitleaks-system`). Review fixes applied: pgvector lives in its own `extensions` schema, reached through a per-role `search_path` for ml_worker and api_search; allowed-read tests use seeded rows (shown red with the policy dropped); the front client is `server-only` and fails fast without env vars; handlers are async, and both branches of the dev-only docs are tested; the api, migrate, role-passwords and tests containers run with `cap_drop: ALL`, `no-new-privileges` and `read_only`. The final fresh-volume run passed 49 tests, along with ruff (S608), mypy strict, the drift check (red when stale), the front checks and pre-commit. Notes for later: `db` isn't hardened (the postgres entrypoint needs root caps); `jobs` has no grants yet (worker ticket); IP_HASH_SALT and the Spotify creds aren't wired into the API yet (tickets 04 and 07); psycopg_pool comes with the first DB query (ticket 04); every `compose up` resets role passwords from `back/.env`.
