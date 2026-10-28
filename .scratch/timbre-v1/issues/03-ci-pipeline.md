# 03: CI pipeline

**What to build:** every push and pull request on GitHub is checked automatically, so problems are caught before anything is deployed. Later tickets only add their tests to this pipeline.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] A GitHub Actions workflow runs on pushes and pull requests:
  - front: lint, type check, Vitest;
  - back: ruff (including S608), mypy, and pytest against the Compose stack;
  - Playwright against the Compose stack;
  - the OpenAPI drift check;
  - gitleaks, `pnpm audit`, `pip-audit`, and Trivy on the built images.
- [ ] Dependabot opens weekly updates for npm, Python (uv/pip), Docker images and GitHub Actions.
- [ ] The workflow is green on the main branch.
- [ ] Spotify credentials are NOT needed yet. Ticket 07 adds them as Actions secrets.
