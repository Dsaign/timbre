-- migrate:up
-- The Catalog import job (ticket 12): MusicBrainz tags on each Song, and the import's progress.

-- MusicBrainz tags, CC BY-NC-SA 3.0 (ADR 0002): never in git. NULL until fetched.
ALTER TABLE catalog.songs ADD COLUMN tags text[];

-- One row per artist whose Songs the import has committed; a resumed import skips them.
CREATE TABLE catalog.import_artists (
  artist_mbid uuid PRIMARY KEY -- MusicBrainz artist ID
);
ALTER TABLE catalog.import_artists ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.import_artists FORCE ROW LEVEL SECURITY;
GRANT SELECT, INSERT ON catalog.import_artists TO ml_worker;
CREATE POLICY ml_worker_all ON catalog.import_artists TO ml_worker USING (true) WITH CHECK (true);

ALTER TABLE jobs.queue
  DROP CONSTRAINT queue_kind_check,
  ADD CONSTRAINT queue_kind_check CHECK (kind IN ('build-vectors', 'import-catalog'));

-- migrate:down
DELETE FROM jobs.queue WHERE kind = 'import-catalog';
ALTER TABLE jobs.queue
  DROP CONSTRAINT queue_kind_check,
  ADD CONSTRAINT queue_kind_check CHECK (kind IN ('build-vectors'));
DROP TABLE catalog.import_artists;
ALTER TABLE catalog.songs DROP COLUMN tags;
