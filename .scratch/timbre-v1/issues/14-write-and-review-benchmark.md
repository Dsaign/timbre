# 14: Write and review the Benchmark

**What to build:** the owner completes the Benchmark. They write 40 Descriptions by hand and review the 60 drafted ones, so the score reflects how real people describe music.

**Blocked by:** 13

**Status:** resolved

- [x] 40 hand-written Descriptions (pt-BR and English, covering mood, instrument and preference), each with at least 3 expected Songs from the Catalog, added through the template.
- [x] Each of the 60 drafted Descriptions is reviewed: fixed or replaced as needed, then marked reviewed.
- [x] The evaluate job is run on the complete Benchmark of 100, and the baseline's score is recorded.

## Answer

Benchmark: 100 Descriptions (40 hand-written, 60 drafted, all reviewed), 346 expected Songs, every ID checked against the 10,000-Song Catalog and its title and artist.

Baseline (multilingual-e5-small), evaluate run 2026-11-16: score **0.112** (expected Songs in the top 24 Matches, averaged over Descriptions), cutoff 0.830, Popularity weight 0.050, nonsense best Fit 0.825. On the 60 unreviewed drafted Descriptions alone (ticket 13) it was 0.132. Recorded on model version 1 and in the README.

The tuned weight sits at the top of the grid (0.05), so a wider grid might score higher; the ticket 13 cap keeps Popularity from overriding Fit.

The worker image bakes in the Benchmark files, so the first run read the stale copies (60 unreviewed). The README now says to rebuild the worker after editing them.

## Comments

- Review (Carl): Standards 0 hard, 3 judgement calls (worst: benchmark_hand_written.json is expanded one key per line, unlike the drafted file, and lost its trailing newline); Spec 0 missing, 2 partial, 6 wrong labels, 0 creep (worst: hand-written expected Songs that don't fit, e.g. Hurt by Johnny Cash under roots reggae and Lady Gaga under reggaeton; the drafted review changed only the reviewed flags).
- Fixes after review: replaced the mislabelled Songs in 6 hand-written Descriptions (sad female voice, roots reggae, 2000s pop, British classic rock, Latin pop/reggaeton, disco grooves; the reggae and reggaeton sets no longer copy drafted ones), swapped London Calling for American Idiot in "short and loud punk rock", and renamed the 80s-synth drafted Description to "retrô" to fit its post-2008 Songs. Hand-written file reformatted to one Song per line. Re-run score: 0.102 → 0.112.
