-- migrate:up
-- Minimal placeholder tables so every role has something to be granted and tested against.
-- Later tickets add columns. RLS is enabled and forced on every table: no policy, no rows.

CREATE TABLE catalog.songs (
  id uuid PRIMARY KEY, -- MusicBrainz recording ID
  title text NOT NULL,
  artist text NOT NULL
);
ALTER TABLE catalog.songs ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.songs FORCE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON catalog.songs TO ml_worker;
GRANT SELECT ON catalog.songs TO api_search;
CREATE POLICY ml_worker_all ON catalog.songs TO ml_worker USING (true) WITH CHECK (true);
CREATE POLICY api_search_read ON catalog.songs FOR SELECT TO api_search USING (true);

CREATE TABLE feedback.votes (
  visitor_hash text NOT NULL,
  description text NOT NULL,
  song_id uuid NOT NULL,
  vote text NOT NULL CHECK (vote IN ('up', 'down')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (visitor_hash, description, song_id)
);
ALTER TABLE feedback.votes ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback.votes FORCE ROW LEVEL SECURITY;
GRANT SELECT ON feedback.votes TO ml_worker;
-- SELECT is needed for INSERT ... ON CONFLICT DO UPDATE and for DELETE ... WHERE; the policy limits it to own rows.
GRANT SELECT, INSERT, UPDATE, DELETE ON feedback.votes TO api_search;
CREATE POLICY ml_worker_read ON feedback.votes FOR SELECT TO ml_worker USING (true);
-- "Own" = the visitor hash the API sets per transaction with set_config('app.visitor_hash', ..., true).
CREATE POLICY api_search_own ON feedback.votes TO api_search
  USING (visitor_hash = current_setting('app.visitor_hash', true))
  WITH CHECK (visitor_hash = current_setting('app.visitor_hash', true));

CREATE TABLE preview.spotify_cache (
  song_id uuid PRIMARY KEY, -- plain value, deliberately no foreign key to catalog (ADR 0001)
  spotify_track_id text, -- NULL means "not found on Spotify"
  fetched_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL
);
ALTER TABLE preview.spotify_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE preview.spotify_cache FORCE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON preview.spotify_cache TO api_preview;
CREATE POLICY api_preview_all ON preview.spotify_cache TO api_preview USING (true) WITH CHECK (true);

-- migrate:down
DROP TABLE catalog.songs, feedback.votes, preview.spotify_cache;
