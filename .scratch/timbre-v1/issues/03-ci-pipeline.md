# 03: CI pipeline

**What to build:** every push and pull request on GitHub is checked automatically, so problems are caught before anything is deployed. Later tickets only add their tests to this pipeline.

**Blocked by:** 02

**Status:** ready-for-human

- [x] A GitHub Actions workflow runs on pushes and pull requests:
  - front: lint, type check, Vitest;
  - back: ruff (including S608), mypy, and pytest against the Compose stack;
  - Playwright against the Compose stack;
  - the OpenAPI drift check;
  - gitleaks, `pnpm audit`, `pip-audit`, and Trivy on the built images.
- [x] Dependabot opens weekly updates for npm, Python (uv/pip), Docker images and GitHub Actions.
- [ ] The workflow is green on the main branch.
- [x] Spotify credentials are NOT needed yet. Ticket 07 adds them as Actions secrets.

## Comments

- 2026-10-29, implemented by Bob; waiting on the owner's review and commit. `.github/workflows/ci.yml` has four jobs: `front` (lint, Prettier, `next typegen` + tsc, Vitest, `pnpm audit --audit-level moderate`, the drift check), `back` (ruff check and format, mypy strict, pip-audit on the uv lock export), `stack` (a throwaway `back/.env` from `openssl rand`, pytest through Compose, Playwright on Chromium against `pnpm start` with the stack up, then Trivy HIGH/CRITICAL with ignore-unfixed on the `back-api` image) and `secrets` (gitleaks v8.30.1 over the full history). Actions are pinned to commit SHAs, the token has `contents: read` only, and checkout doesn't persist credentials. `.github/dependabot.yml` covers npm, uv, docker, docker-compose and github-actions weekly. Vitest and Playwright weren't installed yet, so this adds them as front dev deps, plus `pnpm test` (Vitest, passes with no tests, excludes `e2e/`), `pnpm test:e2e` and a one-test Playwright smoke check (the home page shows the search form). Fixes found by running the CI steps locally: the system pip is removed from the back image (only its vendored urllib3/msgpack/setuptools had HIGH CVEs), and the db healthcheck gets `start_period: 60s` (initdb on a fresh volume ran out of retries). Unchecked until the first push: green on main.
