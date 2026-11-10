-- migrate:up
-- The album cover shown on a card (ticket 11.5): the smallest image of at least 64 px from the
-- same Search response, so no extra Spotify call. Same row, so the same 24 h TTL (ADR 0001).
ALTER TABLE preview.spotify_cache ADD COLUMN album_image_url text;

-- migrate:down
ALTER TABLE preview.spotify_cache DROP COLUMN album_image_url;
