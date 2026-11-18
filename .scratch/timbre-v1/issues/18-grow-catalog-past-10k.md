# 18: Grow the Catalog past 10k Songs

**What to build:** the Catalog grows from 10,000 Songs to as many as the API import can reach, capped at 50,000. It still imports through the MusicBrainz, AcousticBrainz and ListenBrainz APIs ([ADR 0002](../../../docs/adr/0002-catalog-via-apis-not-dumps.md), no dumps). Search stays fast at the new size, and the model is re-evaluated and retrained on the larger Catalog.

**Blocked by:** 12, 15

**Status:** ready-for-agent

- [ ] `TARGET` in `back/src/timbre_back/catalog_import.py` becomes 50,000, and an existing 10k Catalog resumes past the artists in `catalog.import_artists` without re-fetching them. The import still stops early when ListenBrainz's top artists run out (it lists 1,000); the worker log states the final count and why it stopped.
- [ ] Search stays within today's latency at the new size. Replace the per-search unnest of `tag_keys` (the `shortcut:` comment in `back/src/timbre_back/search.py`) with a GIN index or a precomputed tag table, as a dbmate migration. Check whether the Fit step needs a pgvector index (HNSW) at this size, and add one only if measurements show it is needed. Record the before/after timings in this ticket.
- [ ] Every Benchmark expected Song is still in the Catalog, and the cutoff check still holds: the nonsense string `xkqzv wplmr tjhgf` gets 0 Matches, and each sample Description gets at least 1.
- [ ] The README sections "Catalog import", "Benchmark" and "Own model" describe the new size and give the order to run after an import: `build-vectors` → `evaluate` → `train`.
- [ ] Tests cover the resume past an existing Catalog and the new index or tag table.

Not in scope: the data dumps (only when the owner asks, per ADR 0002), a larger embedding model, and fine-tuning e5.

## Comments

- Owner (2026-11-18): the 10k size was a first target (`docs/research/open-music-data.md`), not a limit of the model. The last import used 236 artists for 10k Songs, so the API route may reach about 30–40k (an estimate). AcousticBrainz stopped collecting data in 2022, so the import drops recent releases. The live import (1 req/s, several hours) and the production rollout are run by the owner, not by Bob.
- Bob (2026-11-18): search timings, in the database (the search query alone, no embedding or HTTP), median and p95 over 109 Descriptions (the 100 Benchmark ones, the nonsense string, "rock", "jazz", ...), promoted model 17, 3 runs each. Measured on copies of the dev database: the real 10k Catalog, and 50k / 30k made by adding synthetic copies of each Song (same vectors and tags, new titles and artists). Default Postgres settings (shared_buffers 128MB, work_mem 4MB).

  | Catalog | before | after |
  |---|---|---|
  | 10k (real) | 220 ms, p95 270 ms | 58 ms, p95 73 ms |
  | 30k | — | 200 ms, p95 330 ms |
  | 50k | 1,350 ms, p95 1,650 ms | 325 ms, p95 450 ms |

  What took the time at 50k (EXPLAIN ANALYZE, one Description): the artist name step scanned every Song (about 580 ms: its trigram index was on the full artist, but search matches the main artist, so the index was never used), the tag step unnested every Song's tags (about 185 ms), and the ranking sorted rows that carried the Description vector (a 90 MB sort on disk). Changes: a trigram index on the main-artist expression, a `catalog.song_tags` table kept by a trigger (tags 185 ms → about 25 ms), and narrower ranking rows. A GIN index on `tag_keys` instead of the table measured 339 ms against 312 ms at 50k, so the table it is. Old and new search return identical Matches, in the same order, for 112 Descriptions at 10k and 50k.

  HNSW: not added. The exact cosine over 50k vectors costs about 50 ms, and search ranks every Song (the Fit rank feeds the tag fusion and the Match count), so a top-k index could not replace that scan without changing the ranking. Storing vectors inline (`SET STORAGE MAIN` plus a table rewrite) measured 325 → 285 ms at 50k; not done.

- Owner (2026-11-18): accepts 325 ms median / 450 ms p95 at the full 50k; no inline vectors or shared_buffers tuning for now.
- Review (Carl, 2026-11-18): Standards 0 hard, 3 judgement calls (worst: "under" log assertion is brittle). Spec: all items done except the Benchmark/cutoff re-check, which waits on the owner's 50k import; worst: the 93 search tests are unverified on a fresh untagged database.
- Review (Carl, round 2, 2026-11-18): Standards 0 hard, round-1 fixes all resolved; optional: stale "raised rate limits" comments in compose.yaml/ci.yml and the tmpfs restart caveat. Spec: test_search.py not weakened, nothing wrong found; only open item is the Benchmark/cutoff re-check after the owner's 50k import.
- Review (Carl, round 3, 2026-11-18): the two optional comment fixes are in (compose.yaml, ci.yml, compose.test.yaml); comments only, nothing left open besides the post-import Benchmark/cutoff re-check.
