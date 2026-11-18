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
