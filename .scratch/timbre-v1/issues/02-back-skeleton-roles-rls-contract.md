# 02: back/ skeleton: database roles, RLS and the API contract

**What to build:** a running back end next to the front. One Docker Compose command starts Postgres (with pgvector) and the FastAPI service. The database already has the schemas, roles and row level security the whole project depends on. The front's server code can call the API through a typed client generated from the committed OpenAPI spec, and the API refuses any caller without the front's token.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] One Compose command starts Postgres with pgvector and the API. The database port is not published outside the Compose network.
- [ ] Plain, numbered, descriptive SQL migrations (no ORM) create:
  - the schemas `catalog`, `feedback`, `preview` and `jobs`;
  - the roles `ml_worker`, `api_search` and `api_preview`, each with only the grants the spec lists;
  - minimal placeholder tables where needed.
- [ ] Row level security is enabled and forced on every table, with deny-by-default policies.
- [ ] Database-role tests (seam 3), run by connecting as each real role:
  - `ml_worker` and `api_search` cannot read `preview`;
  - `api_preview` cannot read `catalog` or `feedback`;
  - each role can do its allowed operations.
- [ ] A health endpoint answers only when called with the correct front token. A missing or wrong token gets 401. The front's server code calls it through the generated typed client, and the result is visible in a dev-only way (for example a log line or a small status indicator).
- [ ] The OpenAPI spec is generated from the API models and committed. The typed TypeScript client in `front` is generated from it. One command fails when the committed spec and the code disagree.
- [ ] Interactive API docs are enabled only in the development environment.
- [ ] The root `.env` is split and then removed:
  - `front/.env.local` holds the front→back token and the back URL;
  - `back/.env` holds the Spotify client ID and secret, one password per database role, the IP-hash salt and the front→back token.
  
  Each service has a names-only `.env.example`, and git ignores every real env file.
- [ ] A gitleaks pre-commit hook is configured. Installing gitleaks locally is documented in the README.
- [ ] `back` tooling: Python 3.13 with `uv`, `ruff` (including the SQL-string rule S608), `mypy` and `pytest`. All of it passes.
