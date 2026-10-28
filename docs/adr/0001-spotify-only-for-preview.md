# Spotify is used only for Preview

The Spotify Developer Policy (v10, May 2025) forbids analysing Spotify Content or ingesting it into any ML model (III.13, III.14), and allows storing it only "as strictly necessary" and "not indefinitely". So the Catalog and every feature used to rank Matches come only from open data (MusicBrainz, AcousticBrainz, ListenBrainz), and Spotify is called only to find a Song for Preview. Each time a grid of Matches is shown, the server looks the Songs up on Spotify (by ISRC, then title + artist) and keeps the Spotify track IDs in a short-lived cache, in its own table. No model, training job, metric or evaluation ever reads that table. Matches not found on Spotify show no Preview button. See `docs/research/spotify-platform-terms.md`.

## Consequences

- Spotify data must never be joined into training or evaluation queries, not even "just the ID". This is enforced by the database, not by convention: the cache lives in its own `preview` schema, and the database roles used by the ML worker and the search code have no grant on it.
- Preview clicks are timbre's own events, but they are only available for Songs that are on Spotify, so they are biased. They are not used as a training signal unless a later ADR decides otherwise.
- The Spotify app stays in development mode (extended quota needs 250k+ monthly active users), so lookups must handle rate limits (HTTP 429) without breaking the grid.
