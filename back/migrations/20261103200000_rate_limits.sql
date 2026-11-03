-- migrate:up
-- Rate limits per visitor hash, counted in Postgres (no Redis). One row per (visitor, action):
-- a fixed window that restarts at the first hit after it ends.
-- shortcut: a fixed window lets up to 2x the limit through around a window boundary, use a sliding window if scripts exploit it
CREATE SCHEMA ratelimit;
CREATE TABLE ratelimit.hits (
  visitor_hash text NOT NULL,
  action text NOT NULL CHECK (action IN ('search', 'feedback')),
  window_start timestamptz NOT NULL,
  count integer NOT NULL,
  PRIMARY KEY (visitor_hash, action)
);
-- No grants and no policies: only the functions below (run as the owner) touch the counters.
ALTER TABLE ratelimit.hits ENABLE ROW LEVEL SECURITY;
ALTER TABLE ratelimit.hits FORCE ROW LEVEL SECURITY;

-- Counts one hit and returns the hits in the current window, this one included.
-- Relies on the owner bypassing RLS (today the postgres superuser), like feedback.forget_old_visitor_hashes().
CREATE FUNCTION ratelimit.hit(visitor text, act text, per interval) RETURNS integer
LANGUAGE sql SECURITY DEFINER SET search_path = '' AS $$
  INSERT INTO ratelimit.hits AS h (visitor_hash, action, window_start, count)
  VALUES (visitor, act, now(), 1)
  ON CONFLICT (visitor_hash, action) DO UPDATE SET
    window_start = CASE WHEN h.window_start <= now() - per THEN now() ELSE h.window_start END,
    count = CASE WHEN h.window_start <= now() - per THEN 1 ELSE h.count + 1 END
  RETURNING count
$$;

-- Counters hold visitor hashes, so they expire too (the longest window is an hour).
CREATE FUNCTION ratelimit.forget_old_hits() RETURNS bigint
LANGUAGE sql SECURITY DEFINER SET search_path = '' AS $$
  WITH forgotten AS (
    DELETE FROM ratelimit.hits WHERE window_start < now() - interval '1 day' RETURNING 1
  )
  SELECT count(*) FROM forgotten
$$;

REVOKE ALL ON FUNCTION ratelimit.hit(text, text, interval), ratelimit.forget_old_hits() FROM PUBLIC;
GRANT USAGE ON SCHEMA ratelimit TO api_search;
GRANT EXECUTE ON FUNCTION ratelimit.hit(text, text, interval), ratelimit.forget_old_hits() TO api_search;

-- migrate:down
DROP SCHEMA ratelimit CASCADE;
