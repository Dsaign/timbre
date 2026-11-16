-- migrate:up
-- The Benchmark (ticket 13): Descriptions with the Songs that should be Matches, loaded from
-- the committed benchmark_*.json files. Only the evaluate job reads it: the API roles get no
-- grant, and training must never read it (ticket 15 enforces that).

CREATE TABLE catalog.benchmark_descriptions (
  id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  description text NOT NULL UNIQUE,
  source text NOT NULL CHECK (source IN ('hand-written', 'drafted')),
  reviewed boolean NOT NULL
);
CREATE TABLE catalog.benchmark_songs (
  description_id integer NOT NULL REFERENCES catalog.benchmark_descriptions ON DELETE CASCADE,
  song_id uuid NOT NULL REFERENCES catalog.songs, -- MusicBrainz recording ID (CC0)
  PRIMARY KEY (description_id, song_id)
);
ALTER TABLE catalog.benchmark_descriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.benchmark_descriptions FORCE ROW LEVEL SECURITY;
ALTER TABLE catalog.benchmark_songs ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.benchmark_songs FORCE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, DELETE ON catalog.benchmark_descriptions, catalog.benchmark_songs TO ml_worker;
CREATE POLICY ml_worker_all ON catalog.benchmark_descriptions TO ml_worker USING (true) WITH CHECK (true);
CREATE POLICY ml_worker_all ON catalog.benchmark_songs TO ml_worker USING (true) WITH CHECK (true);

ALTER TABLE jobs.queue
  DROP CONSTRAINT queue_kind_check,
  ADD CONSTRAINT queue_kind_check CHECK (kind IN ('build-vectors', 'import-catalog', 'evaluate'));

-- migrate:down
DELETE FROM jobs.queue WHERE kind = 'evaluate';
ALTER TABLE jobs.queue
  DROP CONSTRAINT queue_kind_check,
  ADD CONSTRAINT queue_kind_check CHECK (kind IN ('build-vectors', 'import-catalog'));
DROP TABLE catalog.benchmark_songs, catalog.benchmark_descriptions;
