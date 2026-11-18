-- migrate:up
-- Search at 50k Songs (ticket 18). Two steps scanned every Song per search: the artist
-- match (its index was on the full artist, but search matches the main artist) and the tag
-- match (it unnested every Song's tag_keys).

-- The main artist, as search.MAIN_ARTIST has it, so the trigram index serves it.
CREATE INDEX songs_main_artist_trgm ON catalog.songs USING gin (
  catalog.unaccented(regexp_replace(artist, '\s+(feat\.?|ft\.?|featuring)\s.*$', '', 'i'))
  extensions.gin_trgm_ops
);
DROP INDEX catalog.songs_artist_trgm;

-- Each Song's tag keys, one row each, kept by a trigger from songs.tag_keys: search looks up
-- a Description's phrases by key.
CREATE TABLE catalog.song_tags (
  song_id uuid NOT NULL REFERENCES catalog.songs ON DELETE CASCADE,
  vote_rank integer NOT NULL, -- 1 = the most-voted tag
  key text NOT NULL,
  PRIMARY KEY (song_id, vote_rank)
);
CREATE INDEX song_tags_key ON catalog.song_tags (key);
ALTER TABLE catalog.song_tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.song_tags FORCE ROW LEVEL SECURITY;
-- ml_worker writes Songs, so the trigger writes their tags as ml_worker.
GRANT SELECT, INSERT, DELETE ON catalog.song_tags TO ml_worker;
GRANT SELECT ON catalog.song_tags TO api_search;
CREATE POLICY ml_worker_all ON catalog.song_tags TO ml_worker USING (true) WITH CHECK (true);
CREATE POLICY api_search_read ON catalog.song_tags FOR SELECT TO api_search USING (true);

-- If catalog.tag_keys() is ever redefined, rebuild songs.tag_keys and then song_tags with it.
CREATE FUNCTION catalog.sync_song_tags() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  DELETE FROM catalog.song_tags WHERE song_id = NEW.id;
  INSERT INTO catalog.song_tags (song_id, vote_rank, key)
    SELECT NEW.id, i, k FROM unnest(NEW.tag_keys) WITH ORDINALITY t (k, i);
  RETURN NULL;
END
$$;
REVOKE ALL ON FUNCTION catalog.sync_song_tags() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION catalog.sync_song_tags() TO ml_worker;
-- AFTER: the generated tag_keys is computed by then.
CREATE TRIGGER songs_sync_tags AFTER INSERT OR UPDATE OF tags ON catalog.songs
  FOR EACH ROW EXECUTE FUNCTION catalog.sync_song_tags();

INSERT INTO catalog.song_tags (song_id, vote_rank, key)
  SELECT s.id, i, k FROM catalog.songs s, unnest(s.tag_keys) WITH ORDINALITY t (k, i);

-- migrate:down
DROP TRIGGER songs_sync_tags ON catalog.songs;
DROP FUNCTION catalog.sync_song_tags();
DROP TABLE catalog.song_tags;
CREATE INDEX songs_artist_trgm ON catalog.songs
  USING gin (catalog.unaccented(artist) extensions.gin_trgm_ops);
DROP INDEX catalog.songs_main_artist_trgm;
