-- migrate:up
-- Schemas and login roles. Passwords are secrets, so they are set outside migrations.

-- pgvector lives in its own schema; only its owner can create objects there.
CREATE SCHEMA extensions;
CREATE EXTENSION vector SCHEMA extensions;

CREATE SCHEMA catalog;
CREATE SCHEMA feedback;
CREATE SCHEMA preview;
CREATE SCHEMA jobs;

CREATE ROLE ml_worker LOGIN;
CREATE ROLE api_search LOGIN;
CREATE ROLE api_preview LOGIN;

-- Nobody gets anything by default: not the public schema, not the database.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
DO $$ BEGIN
  EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO ml_worker, api_search, api_preview', current_database());
END $$;

-- ml_worker: catalog read/write, feedback read. api_search: catalog read, feedback own votes.
-- api_preview: preview only. jobs has no grants yet (the worker ticket adds them).
GRANT USAGE ON SCHEMA catalog TO ml_worker, api_search;
GRANT USAGE ON SCHEMA feedback TO ml_worker, api_search;
GRANT USAGE ON SCHEMA preview TO api_preview;

-- The vector type and operators (<=>) resolve through search_path, the usual practice per the
-- Postgres docs (5.10.3); qualified operators need OPERATOR(extensions.<=>).
-- Safe because no role but the owner can create objects in "extensions".
GRANT USAGE ON SCHEMA extensions TO ml_worker, api_search;
ALTER ROLE ml_worker SET search_path = extensions;
ALTER ROLE api_search SET search_path = extensions;

-- migrate:down
DROP SCHEMA catalog, feedback, preview, jobs CASCADE;
DROP OWNED BY ml_worker, api_search, api_preview; -- removes the database CONNECT grants
DROP ROLE ml_worker, api_search, api_preview;
GRANT USAGE ON SCHEMA public TO PUBLIC; -- Postgres 15+ default
DO $$ BEGIN
  EXECUTE format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO PUBLIC', current_database());
END $$;
DROP EXTENSION vector;
DROP SCHEMA extensions;
