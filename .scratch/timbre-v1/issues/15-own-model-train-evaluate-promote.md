# 15: Own model: train, evaluate, promote

**What to build:** timbre trains its own model on top of the frozen baseline, using drafted pairs and visitor Feedback. The new model goes live only if it scores no worse on the Benchmark, and visitors get it with no downtime.

**Blocked by:** 14, 08

**Status:** ready-for-agent

- [x] Bob drafts the initial training pairs (Description, Song) offline, as a committed file. Training also reads Feedback: 👍 are positives and 👎 are hard negatives.
- [x] Training excludes every Benchmark Description and Benchmark expected pair, and any Description with e5 cosine ≥ 0.92 to a Benchmark Description.
- [x] The model keeps e5-small frozen and trains a small layer on CPU: a learned projection of the Description vector, plus a head that predicts AcousticBrainz label probabilities and compares them with the Song's real values. Fit combines the two.
- [x] The train → evaluate → promote worker job trains, evaluates on the Benchmark (re-tuning the cutoff and Popularity weight) and records a new model version. It promotes the version only if its score is not worse than the current promoted one. Model files live on a Docker volume.
- [x] The API switches to a newly promoted version without downtime and without a restart.
- [x] Job tests (seam 2): on fixture data, a clearly better model is promoted and a clearly worse one is refused.

## Answer

Built. `python -m timbre_back.train` queues the `train` job (`back/src/timbre_back/train.py`). It reads the drafted pairs (`training_drafted.json`: 130 Descriptions, 80 English and 50 pt-BR, 650 Songs picked from Catalog tags, instruments and AcousticBrainz labels) and every Feedback vote (👍 positive, 👎 hard negative), drops any Description that is a Benchmark Description or within e5 cosine 0.92 of one, and fits the model (`model.py`) on CPU: e5 stays frozen, a projection of the Description vector (ridge regression pulled towards the identity) and a head predicting the 30 AcousticBrainz label probabilities of `profile.WORDS` (ridge). Fit = 0.8 × cosine(projected Description, Song vector) + 0.2 × (1 − mean |predicted − Song labels|), the cosine alone for a Song without labels. The job then tunes cutoff and Popularity weight on the Benchmark for the new version and for the promoted one, records the new version (score, cutoff, weight, file) and promotes it if its score is not lower. Files are `<id>.npz` on the `models` volume (worker read-write, API read-only).

The API reads the promoted version (id, file) on every search, loads its file once (cached) and passes the projected vector, predicted labels and head weight to `SEARCH_SQL`, which reads the cutoff and weight of that same version. Migration `20261116180000_own_model.sql`: `catalog.songs.labels` (generated from `acousticbrainz`), `catalog.model_versions.file`, job kind `train`. The evaluate job now scores the promoted version's own model.

Dev run (2026-11-16, 10,000 Songs, 100 Benchmark Descriptions): 96 Descriptions trained (34 excluded as Benchmark or near it), version 2 scores 0.125 at cutoff 0.905 and weight 0.050 against the baseline's 0.112: promoted.

Tests: `back/tests/test_train.py` runs the job through the worker on a fixture Catalog and Benchmark (rolled back): a clearly better model is promoted, a clearly worse one is recorded but refused; unit tests for vote grouping, Benchmark exclusion (same Description normalized, cosine 0.93 out, 0.91 in) and the projection; and a network test that promotes a version on the running API and sees its first Match change, then switches back. `test_benchmark.py` adds a Python vs SQL ranking parity test for a model with projection and head. `test_search.py` now ranks with the promoted model, so it passes with the baseline or a trained version promoted.

## Comments

Review (Carl): Standards 2 bob.md breaches (head-training path untested; no `shortcut:` notes for fixed hyperparameters and single-worker max(id)+1 versioning) + 5 smells; Spec 2 partial (👎 only soft-shifts the target, not a hard negative; no test that Feedback affects the model) + 2 risks (concurrent train jobs reuse a version id and overwrite its file; missing promoted file makes every search 500).

Decision (user): keep version 2 live; fixed settings (head 0.2, ridge 1.0, 👎 0.5) and the 0.92 exclusion threshold approved. All Carl findings sent back to Bob.

Fixes after Carl's review: 👎 are now real hard negatives (`train.push_negatives`: after the ridge fit, gradient steps on a hinge loss over (Description, 👍 Song, 👎 Song) triples move projection and head until the 👎 Song's Fit is 0.05 below the 👍 Song's; a 👎 with no 👍 on its Description still only moves the ridge target, marked `shortcut:`). Version ids come from a sequence (migration `20261116190000_model_version_ids.sql`), so concurrent runs never share an id or a file. A missing promoted model file makes the API log an error and search with plain e5 instead of failing. `SEARCH_SQL` and the test ranking share one Fit expression (`main.FIT_SQL`). Renames: `may_train_on` (was `exclude`), `Model.project` (was `queries`), `Benchmark.description_vectors`. New tests: the head learns labels, Feedback pulls a 👍 Song up and ranks the 👎 Song below it, the hinge alone fixes a wrong order, a missing file falls back; the live-switch test restores exactly what was promoted and uses a fresh file name. Re-run on dev: version 17 scores 0.125 (same as version 2), promoted as not worse.

Review (Carl, round 2): all round-1 findings fixed (one partly: Feedback effect tested at unit level, not through the job reading feedback.votes); 0 hard Standards breaches, 3 mild smells; risks: missing-file fallback reuses the trained version's cutoff/weight and logs a traceback every search; 20261116180000 down can hit the one-promoted index if another version is promoted.

Fixes after Carl's second review: a missing promoted model file now falls back to the whole baseline version (plain e5 with version 1's cutoff and weight) and is logged once per file; its test gives the broken version a cutoff of 0.999 and checks the baseline's Matches come back. New seam-2 job test: a 👍 and a 👎 vote in `feedback.votes` make the trained version rank the 👎 Song at least the margin below the 👍 Song, where plain e5 ranked it above. The `own_model` migration's down path re-promotes version 1 only when nothing else is promoted; up, down and up again checked on a throwaway database.

Review (Carl, round 3): all round-2 findings fixed; 0 Standards breaches, 2 mild smells (baseline id 1 hard-coded in 3 places; lru_cache as log-once); Spec: nothing missing or wrong, minor: job-level Feedback test would still pass if 👎 were dropped (hard negatives covered by unit tests).
