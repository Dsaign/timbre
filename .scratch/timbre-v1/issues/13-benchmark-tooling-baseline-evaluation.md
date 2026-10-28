# 13: Benchmark tooling and baseline evaluation

**What to build:** the project can measure how good its Matches are. A Benchmark of Descriptions with expected Songs is stored. An evaluate job scores the current model and tunes the cutoff and Popularity weight. The baseline gets its first real score as model version 1.

**Blocked by:** 12

**Status:** ready-for-agent

- [ ] The Benchmark is stored in `catalog`: Descriptions, each with its expected Songs (MusicBrainz IDs, CC0), each marked `hand-written` or `drafted`, and `reviewed` or not.
- [ ] Bob drafts 60 Benchmark Descriptions, about half pt-BR and half English, covering mood, instrument and preference, each with at least 3 expected Songs from the Catalog. They go into a committed file marked as drafted and not reviewed, plus a ready template for the owner's 40 hand-written ones.
- [ ] The evaluate job computes the score: the share of expected Songs that appear in the top 24, averaged over Benchmark Descriptions. It also tunes the cutoff and the Popularity weight, prints a short report, and records the score, cutoff and weight on model version 1 (the baseline).
- [ ] The Benchmark is never readable by training code paths (enforced in ticket 15).
- [ ] Job test (seam 2): on a tiny fixture Catalog and Benchmark, evaluate produces the expected score and records it.
