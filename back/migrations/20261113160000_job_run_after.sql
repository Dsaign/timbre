-- migrate:up
-- A job that found an API down waits until run_after, so later jobs run meanwhile.
ALTER TABLE jobs.queue ADD COLUMN run_after timestamptz NOT NULL DEFAULT now();

-- migrate:down
ALTER TABLE jobs.queue DROP COLUMN run_after;
