# 15: Own model: train, evaluate, promote

**What to build:** timbre trains its own model on top of the frozen baseline, using drafted pairs and visitor Feedback. The new model goes live only if it scores no worse on the Benchmark, and visitors get it with no downtime.

**Blocked by:** 14, 08

**Status:** ready-for-agent

- [ ] Bob drafts the initial training pairs (Description, Song) offline, as a committed file. Training also reads Feedback: 👍 are positives and 👎 are hard negatives.
- [ ] Training excludes every Benchmark Description and Benchmark expected pair, and any Description with e5 cosine ≥ 0.92 to a Benchmark Description.
- [ ] The model keeps e5-small frozen and trains a small layer on CPU: a learned projection of the Description vector, plus a head that predicts AcousticBrainz label probabilities and compares them with the Song's real values. Fit combines the two.
- [ ] The train → evaluate → promote worker job trains, evaluates on the Benchmark (re-tuning the cutoff and Popularity weight) and records a new model version. It promotes the version only if its score is not worse than the current promoted one. Model files live on a Docker volume.
- [ ] The API switches to a newly promoted version without downtime and without a restart.
- [ ] Job tests (seam 2): on fixture data, a clearly better model is promoted and a clearly worse one is refused.
