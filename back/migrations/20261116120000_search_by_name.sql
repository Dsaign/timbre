-- migrate:up
-- Search by artist or song title (ticket 14.5): trigram similarity, ignoring case (pg_trgm)
-- and accents (unaccent). Both ship with Postgres.
CREATE EXTENSION pg_trgm SCHEMA extensions;
CREATE EXTENSION unaccent SCHEMA extensions;

-- unaccent() is only STABLE (its dictionary could change), so indexes need this IMMUTABLE
-- wrapper with the dictionary named explicitly, the usual practice.
CREATE FUNCTION catalog.unaccented(text) RETURNS text
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
  RETURN extensions.unaccent('extensions.unaccent'::regdictionary, $1);
-- api_search runs Search; ml_worker writes Songs, which evaluates the index expressions.
REVOKE ALL ON FUNCTION catalog.unaccented(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION catalog.unaccented(text) TO api_search, ml_worker;

CREATE INDEX songs_title_trgm ON catalog.songs
  USING gin (catalog.unaccented(title) extensions.gin_trgm_ops);
CREATE INDEX songs_artist_trgm ON catalog.songs
  USING gin (catalog.unaccented(artist) extensions.gin_trgm_ops);

-- migrate:down
DROP INDEX catalog.songs_artist_trgm, catalog.songs_title_trgm;
REVOKE EXECUTE ON FUNCTION catalog.unaccented(text) FROM api_search, ml_worker;
DROP FUNCTION catalog.unaccented(text);
DROP EXTENSION unaccent;
DROP EXTENSION pg_trgm;
