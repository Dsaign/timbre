# 19: CI browser install fails fast and is cached

**What to build:** the `stack` job's "Install front and browsers" step in `.github/workflows/ci.yml` can no longer hang a run for half an hour. It normally takes about 1 minute, but it took 24 minutes on deploy_fixes (2026-11-18 01:39) and stalled for 20+ minutes on PR #31, because `playwright install --with-deps` (apt plus three browser downloads) can stall and nothing times it out.

**Blocked by:** none

**Status:** resolved

- [x] The install step has `timeout-minutes: 10`, and the `stack` job has a job-level timeout well above a normal run (normal is about 5 min; for example 30).
- [x] The Playwright browsers (`~/.cache/ms-playwright`) are cached with `actions/cache` (pinned by commit SHA like the other actions), keyed on the runner OS and the installed `@playwright/test` version from `front/pnpm-lock.yaml`. On a cache hit, only `pnpm exec playwright install-deps chromium firefox webkit` runs; on a miss, the current `install --with-deps` runs.
- [x] pnpm's store is cached too, if `actions/setup-node`'s `cache: pnpm` is not already set. (Already set in the `stack` job; no change needed.)
- [x] Nothing else in the workflow changes: the same browsers, the same Playwright projects, and the same order of steps.

## Comments

- Review (Carl): Standards: 0 hard violations, 2 low judgement calls (worst: cache key uses `runner.os` (`Linux`), not the Ubuntu image, so a future runner-image change could reuse browsers built for another Ubuntu). Spec: all 4 criteria met, no scope creep, nothing implemented wrong; `actions/cache` SHA verified as v6.1.0.
