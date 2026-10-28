# 12: Catalog import from open data

**What to build:** the real Catalog of about 10k well-known Songs, imported from MusicBrainz, AcousticBrainz and ListenBrainz through their public APIs (ADR 0002). Once it's imported and vectorized, Descriptions search the full Catalog.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] Candidates come from ListenBrainz's sitewide all-time top artists, then each artist's top recordings. There is no language or country quota.
- [ ] Only Songs with at least one ISRC and AcousticBrainz high-level data are kept, until the Catalog reaches about 10k Songs.
- [ ] Each Song's profile also includes MusicBrainz tags and genres (CC BY-NC-SA, credited in the footer). The imported data is never committed to git.
- [ ] Each API is called at no more than 1 request per second, with a proper User-Agent. The import is a worker job that resumes where it stopped after an interruption.
- [ ] The build-vectors job runs after the import for new or changed Songs.
- [ ] Job tests (seam 2) replay recorded API responses. They check that only Songs with an ISRC and AcousticBrainz data are kept, and that an interrupted import resumes without duplicates.
- [ ] Full data dumps are not used (ADR 0002).
