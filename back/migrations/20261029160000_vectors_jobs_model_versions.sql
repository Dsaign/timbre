-- migrate:up
-- Song data for matching, the job queue, and the model versions table with the baseline.

ALTER TABLE catalog.songs
  ADD COLUMN isrc text,
  ADD COLUMN listens bigint NOT NULL DEFAULT 0, -- Popularity: ListenBrainz listen count
  ADD COLUMN acousticbrainz jsonb, -- high-level class probabilities, {classifier: {class: p}}
  ADD COLUMN instruments text[] NOT NULL DEFAULT '{}',
  ADD COLUMN profile text, -- written by the build-vectors job
  ADD COLUMN vector extensions.vector(384); -- multilingual-e5-small passage vector of profile

CREATE TABLE catalog.model_versions (
  id integer PRIMARY KEY,
  name text NOT NULL,
  benchmark_score real, -- NULL until the Benchmark exists
  cutoff real NOT NULL, -- a Song is a Match when its Fit is above this
  popularity_weight real NOT NULL,
  promoted boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- At most one promoted version.
CREATE UNIQUE INDEX model_versions_one_promoted ON catalog.model_versions (promoted) WHERE promoted;
ALTER TABLE catalog.model_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.model_versions FORCE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON catalog.model_versions TO ml_worker;
GRANT SELECT ON catalog.model_versions TO api_search;
CREATE POLICY ml_worker_all ON catalog.model_versions TO ml_worker USING (true) WITH CHECK (true);
CREATE POLICY api_search_read ON catalog.model_versions FOR SELECT TO api_search USING (true);

-- Baseline: e5 cosine Fit. The cutoff is picked on the seed Catalog (ticket 04): the fixed
-- nonsense Description "xkqzv wplmr tjhgf" has a best Fit of 0.806 (0 Matches), and the
-- weakest of the six sample Descriptions ("sad piano ballad, slow and quiet") 0.842.
-- 0.835 sits between them and keeps every sample at 3+ Matches.
INSERT INTO catalog.model_versions (id, name, cutoff, popularity_weight, promoted)
VALUES (1, 'baseline multilingual-e5-small', 0.835, 0.02, true);

-- A job row is locked by the worker for the whole run (FOR UPDATE SKIP LOCKED), so a crashed
-- run rolls back and the job stays queued.
CREATE TABLE jobs.queue (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  kind text NOT NULL CHECK (kind IN ('build-vectors')),
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'done', 'failed')),
  error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
ALTER TABLE jobs.queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs.queue FORCE ROW LEVEL SECURITY;
GRANT USAGE ON SCHEMA jobs TO ml_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON jobs.queue TO ml_worker;
CREATE POLICY ml_worker_all ON jobs.queue TO ml_worker USING (true) WITH CHECK (true);

-- migrate:down
DROP TABLE jobs.queue;
REVOKE USAGE ON SCHEMA jobs FROM ml_worker;
DROP TABLE catalog.model_versions;
ALTER TABLE catalog.songs
  DROP COLUMN isrc,
  DROP COLUMN listens,
  DROP COLUMN acousticbrainz,
  DROP COLUMN instruments,
  DROP COLUMN profile,
  DROP COLUMN vector;
