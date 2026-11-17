-- migrate:up
-- Own model (ticket 15). Song labels: the AcousticBrainz class probabilities the model's head
-- predicts, in profile.WORDS order. Generated, so they always follow acousticbrainz.
ALTER TABLE catalog.songs ADD COLUMN labels extensions.vector(30) GENERATED ALWAYS AS (
  CASE WHEN acousticbrainz IS NOT NULL THEN ARRAY[
      coalesce((acousticbrainz #>> '{mood_relaxed,relaxed}')::real, 0),
      coalesce((acousticbrainz #>> '{mood_happy,happy}')::real, 0),
      coalesce((acousticbrainz #>> '{mood_sad,sad}')::real, 0),
      coalesce((acousticbrainz #>> '{mood_aggressive,aggressive}')::real, 0),
      coalesce((acousticbrainz #>> '{mood_party,party}')::real, 0),
      coalesce((acousticbrainz #>> '{mood_acoustic,acoustic}')::real, 0),
      coalesce((acousticbrainz #>> '{mood_electronic,electronic}')::real, 0),
      coalesce((acousticbrainz #>> '{danceability,danceable}')::real, 0),
      coalesce((acousticbrainz #>> '{voice_instrumental,instrumental}')::real, 0),
      coalesce((acousticbrainz #>> '{voice_instrumental,voice}')::real, 0),
      coalesce((acousticbrainz #>> '{gender,female}')::real, 0),
      coalesce((acousticbrainz #>> '{gender,male}')::real, 0),
      coalesce((acousticbrainz #>> '{timbre,dark}')::real, 0),
      coalesce((acousticbrainz #>> '{timbre,bright}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_dortmund,alternative}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_dortmund,blues}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_dortmund,electronic}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_dortmund,folkcountry}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_dortmund,funksoulrnb}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_dortmund,jazz}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_dortmund,pop}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_dortmund,raphiphop}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_dortmund,rock}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_rosamerica,cla}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_rosamerica,dan}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_rosamerica,hip}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_rosamerica,jaz}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_rosamerica,pop}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_rosamerica,rhy}')::real, 0),
      coalesce((acousticbrainz #>> '{genre_rosamerica,roc}')::real, 0)
  ]::extensions.vector(30) END
) STORED;

-- A trained version's weights, a file on the models volume. NULL: the baseline, plain e5.
ALTER TABLE catalog.model_versions ADD COLUMN file text;

ALTER TABLE jobs.queue
  DROP CONSTRAINT queue_kind_check,
  ADD CONSTRAINT queue_kind_check CHECK (kind IN ('build-vectors', 'import-catalog', 'evaluate', 'train'));

-- migrate:down
DELETE FROM jobs.queue WHERE kind = 'train';
ALTER TABLE jobs.queue
  DROP CONSTRAINT queue_kind_check,
  ADD CONSTRAINT queue_kind_check CHECK (kind IN ('build-vectors', 'import-catalog', 'evaluate'));
-- Trained versions cannot run without their files' model: back to the baseline.
DELETE FROM catalog.model_versions WHERE file IS NOT NULL;
UPDATE catalog.model_versions SET promoted = true
WHERE id = 1 AND NOT EXISTS (SELECT FROM catalog.model_versions WHERE promoted);
ALTER TABLE catalog.model_versions DROP COLUMN file;
ALTER TABLE catalog.songs DROP COLUMN labels;
