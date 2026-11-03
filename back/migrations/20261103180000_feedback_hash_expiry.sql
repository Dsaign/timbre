-- migrate:up
-- Visitor hashes expire: after 7 days the hash becomes NULL and the vote is kept.
-- One vote per (visitor hash, normalized Description, Song) is now a unique constraint
-- instead of the primary key, since NULLs are distinct: an expired vote belongs to nobody
-- and never blocks the visitor's next vote.
ALTER TABLE feedback.votes DROP CONSTRAINT votes_pkey;
ALTER TABLE feedback.votes ALTER COLUMN visitor_hash DROP NOT NULL;
ALTER TABLE feedback.votes
  ADD CONSTRAINT votes_one_per_visitor UNIQUE (visitor_hash, description, song_id);

-- api_search may touch only its own votes (RLS), so the expiry runs as the owner, through
-- this one fixed statement. Age counts from when the hash was first stored (created_at).
-- Relies on the owner bypassing RLS (today the postgres superuser); a non-superuser owner would update 0 rows with no error.
CREATE FUNCTION feedback.forget_old_visitor_hashes() RETURNS bigint
LANGUAGE sql SECURITY DEFINER SET search_path = '' AS $$
  WITH forgotten AS (
    UPDATE feedback.votes SET visitor_hash = NULL
    WHERE visitor_hash IS NOT NULL AND created_at < now() - interval '7 days'
    RETURNING 1
  )
  SELECT count(*) FROM forgotten
$$;
REVOKE ALL ON FUNCTION feedback.forget_old_visitor_hashes() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION feedback.forget_old_visitor_hashes() TO api_search;

-- migrate:down
DROP FUNCTION feedback.forget_old_visitor_hashes();
-- Keep every vote: expired ones get a unique placeholder hash that matches no visitor's HMAC.
UPDATE feedback.votes SET visitor_hash = 'expired-' || gen_random_uuid() WHERE visitor_hash IS NULL;
ALTER TABLE feedback.votes DROP CONSTRAINT votes_one_per_visitor;
ALTER TABLE feedback.votes ALTER COLUMN visitor_hash SET NOT NULL;
ALTER TABLE feedback.votes ADD PRIMARY KEY (visitor_hash, description, song_id);
