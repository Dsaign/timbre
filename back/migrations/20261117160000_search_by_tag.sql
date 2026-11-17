-- migrate:up
-- Search by tag (ticket 15.5): each Song's tags as keys (lowercase, no accents, words joined by
-- one space), most-voted first, so search can find a Description's phrases among them. The
-- same function normalizes the Description.
CREATE FUNCTION catalog.tag_keys(text[]) RETURNS text[]
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
  RETURN ARRAY(
    SELECT trim(regexp_replace(lower(catalog.unaccented(tag)), '[^[:alnum:]&]+', ' ', 'g'))
    FROM unnest($1) WITH ORDINALITY AS t (tag, i) ORDER BY i
  );
-- api_search normalizes the Description; ml_worker writes Songs, which computes the column.
REVOKE ALL ON FUNCTION catalog.tag_keys(text[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION catalog.tag_keys(text[]) TO api_search, ml_worker;

ALTER TABLE catalog.songs
  ADD COLUMN tag_keys text[] GENERATED ALWAYS AS (catalog.tag_keys(tags)) STORED;

-- migrate:down
ALTER TABLE catalog.songs DROP COLUMN tag_keys;
REVOKE EXECUTE ON FUNCTION catalog.tag_keys(text[]) FROM api_search, ml_worker;
DROP FUNCTION catalog.tag_keys(text[]);
