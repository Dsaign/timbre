# 12: Catalog import from open data

**What to build:** the real Catalog of about 10k well-known Songs, imported from MusicBrainz, AcousticBrainz and ListenBrainz through their public APIs (ADR 0002). Once it's imported and vectorized, Descriptions search the full Catalog.

**Blocked by:** 04

**Status:** resolved

- [x] Candidates come from ListenBrainz's sitewide all-time top artists, then each artist's top recordings. There is no language or country quota.
- [x] Only Songs with at least one ISRC and AcousticBrainz high-level data are kept, until the Catalog reaches about 10k Songs.
- [x] Each Song's profile also includes MusicBrainz tags and genres (CC BY-NC-SA, credited in the footer). The imported data is never committed to git.
- [x] Each API is called at no more than 1 request per second, with a proper User-Agent (contact read from `METABRAINZ_CONTACT`, never hardcoded, as in `back/scripts/fetch_seed.py`). The import is a worker job that resumes where it stopped after an interruption.
- [x] The build-vectors job runs after the import for new or changed Songs.
- [x] Job tests (seam 2) replay recorded API responses. They check that only Songs with an ISRC and AcousticBrainz data are kept, and that an interrupted import resumes without duplicates.
- [x] Full data dumps are not used (ADR 0002).
- [x] ListenBrainz `/1/popularity/*` needs an auth token (401 without one, found in ticket 04). Read it from `LISTENBRAINZ_TOKEN` (already in the local `back/.env`); add it as an Actions secret only if CI ever calls the live API (job tests replay recorded responses).
- [x] Re-run ticket 04's cutoff check on the full Catalog: the fixed nonsense string must return 0 Matches and each of the six sample Descriptions at least 1. If no cutoff separates them anymore, stop and ask the owner.

## Comments

- Review (Carl): Standards 0 hard, 2 soft and 7 smells (worst: shared Catalog writers live in seed.py, so catalog_import depends on seed); Spec 1 missing, 2 partial, 1 questionable (worst: no written instructions for the full-Catalog cutoff re-check; also seed Songs stay untagged and count toward 10k).
- Review (Carl, re-review): Standards 0 hard, 3 soft and 7 smells (worst: catalog_import.py mixes HTTP client, parsers, DB steps, job and CLI, and still imports SEED from seed.py); Spec 0 wrong, 1 missing and 2 partial (worst: the full-Catalog cutoff re-check has not been run yet, and a failed job must be re-queued by hand).
- Review (Carl, 2nd re-review): Standards 0 hard, 4 soft (multi-line comments) and 10 smells (worst: Song built twice, in catalog_import and fetch_seed; token still read per artist); Spec 0 missing, 1 wrong, 1 test gap (worst: a re-queued import keeps its low id and blocks every later job, retrying forever with no cap, while an API is down).
- Review (Carl, 3rd re-review): Standards 0 hard and 7 judgement calls (worst: leftover `ab` name in worker.build_vectors; worker.py catches the MetaBrainz-specific ApiUnavailable); Spec 0 missing, 0 wrong (only note: a small flake window in the new deferral test).
- Review (Carl, 4th re-review): Standards 0 hard and 1 judgement call (worker.py imports catalog_import.run as `import_catalog`, which is also the name of a different function in catalog_import); Spec 0 findings (refactor keeps behaviour; the deferral test is deterministic and fully rolled back).
- Review (Carl, final): the `import_catalog` alias is renamed to `run_catalog_import`; nothing open.

## Answer

Built. The worker's `import-catalog` job (`back/src/timbre_back/catalog_import.py`) takes ListenBrainz's sitewide top artists and each artist's top recordings. It keeps the Songs with an ISRC and AcousticBrainz high-level data, adds MusicBrainz tags to every Song's profile, seed Songs included, and stops at exactly 10k Songs, seed Songs counted. Each finished artist is recorded in `catalog.import_artists`, so an interrupted import resumes after it. API access lives in `back/src/timbre_back/metabrainz.py`, shared with `scripts/fetch_seed.py`: 1 request per second, a User-Agent from `METABRAINZ_CONTACT`, and retries with back-off.

Owner decisions:
- An API outage defers the job by 60 s through `jobs.queue.run_after` (migration `20261113160000_job_run_after.sql`), without blocking other jobs, and retries without limit.
- A 401 fails the job. A 404 on one artist is logged and that artist is skipped.
- Naming MusicBrainz in the footer is enough credit for the tags.

Live run (2026-11-13): 236 artists, 10,000 Songs. One AcousticBrainz 500 was deferred and recovered by itself. build-vectors then ran on all 10,000 Songs. The cutoff check passed on the full Catalog, run by the owner: the nonsense string got 0 Matches and each of the six sample Descriptions at least 1.

Tests: `back/tests/test_catalog_import.py` replays recorded responses (`back/tests/catalog_import/`) and covers the ISRC and AcousticBrainz filter, resume without duplicates, the 1 request per second pace, the 404 skip, the exact target, and deferral without blocking.
