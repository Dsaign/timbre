# 13: Benchmark tooling and baseline evaluation

**What to build:** the project can measure how good its Matches are. A Benchmark of Descriptions with expected Songs is stored. An evaluate job scores the current model and tunes the cutoff and Popularity weight. The baseline gets its first real score as model version 1.

**Blocked by:** 12

**Status:** resolved

- [x] The Benchmark is stored in `catalog`: Descriptions, each with its expected Songs (MusicBrainz IDs, CC0), each marked `hand-written` or `drafted`, and `reviewed` or not.
- [x] Bob drafts 60 Benchmark Descriptions, about half pt-BR and half English, covering mood, instrument and preference, each with at least 3 expected Songs from the Catalog. They go into a committed file marked as drafted and not reviewed, plus a ready template for the owner's 40 hand-written ones.
- [x] The evaluate job computes the score: the share of expected Songs that appear in the top 24, averaged over Benchmark Descriptions. It also tunes the cutoff and the Popularity weight, prints a short report, and records the score, cutoff and weight on model version 1 (the baseline).
- [x] The Benchmark is never readable by training code paths (enforced in ticket 15).
- [x] Job test (seam 2): on a tiny fixture Catalog and Benchmark, evaluate produces the expected score and records it.

## Answer

Built. The Benchmark lives in `catalog.benchmark_descriptions` (source `hand-written`/`drafted`, `reviewed`) and `catalog.benchmark_songs` (foreign key to `catalog.songs`), migration `20261113200000_benchmark.sql`. Only `ml_worker` may read it; the API roles get no grant (role tests). Training code does not exist yet; ticket 15 enforces that it never reads these tables.

The 60 drafted Descriptions (30 English, 30 pt-BR; mood, instrument and preference; 3 to 5 Songs each, 226 in total) are in `back/src/timbre_back/benchmark_drafted.json`, all `drafted` and not reviewed. Every Song ID was looked up in the real Catalog by title and artist. `benchmark_hand_written.json` is the template for the owner's 40 (blank entries are skipped). The drafts lean towards well-known Songs, which favours a higher Popularity weight; worth keeping in mind in ticket 14's review.

`python -m timbre_back.benchmark` (`back/src/timbre_back/benchmark.py`) loads the files and queues the worker's `evaluate` job. The job scores the promoted model version, today version 1 (share of expected Songs in the top 24 Matches, averaged over Descriptions), tunes the cutoff and the Popularity weight, logs a one-line report and records score, cutoff and weight on the promoted version. With no vectorized Song it logs a skip and changes nothing. With no promoted model version it fails with an error instead of recording nothing.

Owner decisions:
- Cutoff: the best score among cutoffs on a 0.005 grid that keep the fixed nonsense string `xkqzv wplmr tjhgf` at 0 Matches, with a safety gap: cutoff at least its best Fit + 0.005 (after Carl's review); ties go to the highest cutoff.
- Popularity weight: 0 to 0.05 in 0.005 steps; ties go to the lowest weight.

Dev run (2026-11-16, after the review fixes; 60 drafted Descriptions, 10,000 Songs): score 0.132 at cutoff 0.830 and weight 0.05, recorded on the promoted version 1 (before tuning: 0.107 at 0.835 and 0.02). The nonsense string's best Fit is 0.8248. The README cutoff re-check (nonsense 0 Matches, each sample at least 1) passes at the new cutoff.

Tests: `back/tests/test_benchmark.py` runs the job through the real worker on a tiny fixture Catalog and Benchmark (rolled back) and checks the recorded score, cutoff and weight, including the nonsense guard and both tie rules. It also checks that the Python ranking gives the same top Matches as `SEARCH_SQL`, that the loader refuses a Description with fewer than 3 Songs or a Song missing from the Catalog, and that evaluate skips a Catalog without vectors. A test checks that evaluate refuses to run without a promoted version. `tests/test_search.py`'s order test now reads the promoted cutoff and weight instead of assuming 0.02, and skips (with a reason) when the weight is 0 or its popular Song would fall below the cutoff, so a re-tune can skip it.

## Comments

- Review (Carl): Standards 1 hard, 5 bug/drift risks and 3 smells (worst: evaluate hand-copies the SEARCH_SQL ranking with no parity test, and targets id = 1 while search reads the promoted row); Spec 0 missing, 1 partial, 0 creep (worst: tuned cutoff sits 0.0002 above the nonsense Fit in a float32 column; the baseline score lives only in the dev DB, not in a fresh one).
- Review (Carl, re-review): Standards 0 hard, 3 soft and 1 smell (worst: the parity test leaves the Popularity normalisation and the cutoff boundary unexercised; with no promoted version, evaluate logs success after writing nothing); Spec 0 wrong, 2 partial, 0 creep (worst: the job test still never exercises the top-24 cut; the baseline result lives only in the dev DB).
- Review (Carl, re-review 2): Standards 0 hard, 1 judgement call (test_benchmark.py docstring blames grid rounding for the 0.630 floor; it is float32 noise); Spec 0 wrong, 2 docs-only partial, 0 creep (worst: the Answer section omits the no-promoted-version error and the new test_search.py skip guard).
