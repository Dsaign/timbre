# Build the Catalog through the open APIs, not the full dumps

The first Catalog is about 10k well-known Songs: MusicBrainz recordings that have an ISRC and AcousticBrainz data, ranked by ListenBrainz popularity. It is imported through the MusicBrainz, AcousticBrainz and ListenBrainz APIs, which takes a few hours at their 1 request/second limits. The full dumps (AcousticBrainz alone is roughly 40 GB) would give 100k+ Songs but cost far more setup time while the pipeline is still changing. Switching to the dumps happens only when the project owner explicitly asks for it. Until then, agents must not propose or start a dump-based import. See `docs/research/open-music-data.md`.

## Consequences

- The import must be resumable and must respect each API's rate limit and User-Agent rules.
- MusicBrainz tags and genres are CC BY-NC-SA 3.0: credit MusicBrainz in the site footer, and never commit the imported data to git.
