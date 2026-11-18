-- migrate:up
-- Search quality before launch (ticket 20). The generated Benchmark file, the tag keys that
-- make a Match relevant to a Description (precision@16), each model version's recall@24 and
-- precision@16 per Benchmark file, and the retag job.
ALTER TABLE catalog.benchmark_descriptions
  DROP CONSTRAINT benchmark_descriptions_source_check,
  ADD CONSTRAINT benchmark_descriptions_source_check
    CHECK (source IN ('hand-written', 'drafted', 'generated')),
  ADD COLUMN accept_tags text[] NOT NULL DEFAULT '{}';

-- {"<source>": score}, one key per Benchmark file; benchmark_score stays the promotion score.
ALTER TABLE catalog.model_versions
  ADD COLUMN recall_at_24 jsonb,
  ADD COLUMN precision_at_16 jsonb;

ALTER TABLE jobs.queue
  DROP CONSTRAINT queue_kind_check,
  ADD CONSTRAINT queue_kind_check
    CHECK (kind IN ('build-vectors', 'import-catalog', 'evaluate', 'train', 'retag'));

-- migrate:down
DELETE FROM jobs.queue WHERE kind = 'retag';
ALTER TABLE jobs.queue
  DROP CONSTRAINT queue_kind_check,
  ADD CONSTRAINT queue_kind_check CHECK (kind IN ('build-vectors', 'import-catalog', 'evaluate', 'train'));
ALTER TABLE catalog.model_versions DROP COLUMN recall_at_24, DROP COLUMN precision_at_16;
DELETE FROM catalog.benchmark_descriptions WHERE source = 'generated';
ALTER TABLE catalog.benchmark_descriptions
  DROP COLUMN accept_tags,
  DROP CONSTRAINT benchmark_descriptions_source_check,
  ADD CONSTRAINT benchmark_descriptions_source_check
    CHECK (source IN ('hand-written', 'drafted'));
