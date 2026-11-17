"""The one search ranking, shared by the API (main.SEARCH_SQL) and the Benchmark.

Matches, in order: the Songs the Description names (by artist or title), then the rest,
ranked by Reciprocal Rank Fusion (the usual k = 60) of two rankings: the model's (Fit
plus a small Popularity weight) and a direct match of the Description's phrases with
each Song's tags. The tag ranking is weighted by the share of the Description its tag
covers, so "rock" goes by tags while a long Description keeps to its meaning. After a
name match, Fit is measured against the Description averaged with the named Songs, so
the Description's own meaning always counts. A Match has Fit above the cutoff, or a
matching tag among its Song's 3 most-voted.

Parameters: description (normalized), vector and labels (model.search_params),
head_weight, cutoff and weight (the model version's).
"""

# Fit from a row's cosine, labels and target_labels, as model.Model.fit: the head
# counts only when both label vectors exist.
FIT_SQL = """coalesce(
    (1 - %(head_weight)s) * cosine
      + %(head_weight)s * (1 - (labels <+> target_labels) / vector_dims(labels)),
    cosine
  )"""

# The main artist, accent-free: guests after feat./ft./featuring don't count.
MAIN_ARTIST = (
    r"catalog.unaccented("
    r"regexp_replace(artist, '\s+(feat\.?|ft\.?|featuring)\s.*$', '', 'i'))"
)
POPULARITY = (
    "coalesce(ln(1 + listens)"
    " / nullif(ln(1 + (SELECT max(listens) FROM catalog.songs)), 0), 0)"
)
RRF_K = "60"  # the usual Reciprocal Rank Fusion constant
# Song-to-Song Fit passes the cutoff for almost the whole Catalog, so after a name match
# the related Songs are capped.
RELATED_CAP = "60"
STRONG_TAGS = "3"  # a tag-only Match needs the tag among its Song's 3 most-voted

# The CTEs up to `matches` (id, title, artist, part, rank); order: part, rank DESC, id.
# Names match whole: the main artist (guests after feat./ft. don't count) or a title of
# two words or more, so one everyday word ("rock", "love") never takes over a search.
# A tag matches when it is a phrase of the Description (both normalized by
# catalog.tag_keys); the most-voted tags count most.
# shortcut: the tag step unnests every Song's tag_keys per search (search took about
# 50-110 ms in the database before it, 200-350 ms with it, at 10k Songs); once the
# Catalog grows, use a GIN index on tag_keys or a precomputed tag table.
MATCHES_SQL = (
    r"""
WITH description_words AS (
  SELECT string_to_array((catalog.tag_keys(ARRAY[%(description)s]))[1], ' ') AS words
), description AS (
  SELECT catalog.unaccented(%(description)s) AS unaccented,
    -- Every phrase of 1 to 4 words: the longest tags have 4 ("east coast hip hop").
    ARRAY(
      SELECT array_to_string(words[i:i + n - 1], ' ')
      FROM description_words, generate_subscripts(words, 1) i, generate_series(1, 4) n
      WHERE i + n - 1 <= cardinality(words)
    ) AS phrases,
    cardinality(words) AS word_count
  FROM description_words
), named AS (
  SELECT id, title, artist, listens, vector, labels
  FROM catalog.songs, description
  -- 0.6: typos and a missing "The" still match ("linkn park" 0.64, "beatles" 0.67),
  -- "rock" against "A$AP Rocky" (0.36) and every genre word tried stay far below.
  WHERE {artist} %% unaccented AND similarity({artist}, unaccented) >= 0.6
    OR catalog.unaccented(title) %% unaccented
      -- 0.7: titles are everyday words, so a title needs a closer match than a name.
      AND similarity(catalog.unaccented(title), unaccented) >= 0.7
      AND title ~ '\S\s+\S'
), target AS (
  -- The Description, averaged with the named Songs when they have vectors.
  SELECT avg(vector) AS vector, avg(labels) AS labels FROM (
    SELECT %(vector)s::vector, %(labels)s::vector
    UNION ALL
    SELECT avg(vector), avg(labels) FROM named HAVING count(vector) > 0
  ) t (vector, labels)
), cosine AS (
  SELECT s.id, s.title, s.artist, s.listens, s.labels,
    1 - (s.vector <=> target.vector) AS cosine, target.labels AS target_labels
  FROM catalog.songs s, target
  WHERE s.vector IS NOT NULL AND s.id NOT IN (SELECT id FROM named)
), tagged AS (
  -- Matching tags, in one pass over the Songs that have any: each weighs 1 / its vote
  -- rank, and the longest gives the share of the Description they cover.
  SELECT s.id, sum(1.0 / i) AS tag_score, min(i) AS best_vote_rank,
    max(cardinality(string_to_array(k, ' ')))::float8 / word_count AS coverage
  FROM catalog.songs s, description, unnest(s.tag_keys) WITH ORDINALITY t (k, i)
  WHERE s.tag_keys && phrases AND k = ANY (phrases)
  GROUP BY s.id, word_count
), scored AS (
  SELECT id, title, artist, {fit} AS fit, {popularity} AS popularity,
    tag_score, best_vote_rank, coverage
  FROM cosine LEFT JOIN tagged USING (id)
), ranked AS (
  SELECT *, rank() OVER (ORDER BY fit + %(weight)s * popularity DESC) AS by_fit
  FROM scored
), fused AS (
  -- Tag ties (often hundreds of Songs) break by Fit, so no tie outranks the model.
  SELECT *,
    row_number() OVER (ORDER BY tag_score DESC NULLS LAST, by_fit, id) AS by_tags
  FROM ranked
), matches AS (
  SELECT id, title, artist, 0 AS part, listens::float8 AS rank FROM named
  UNION ALL
  (SELECT id, title, artist, 1 AS part,
    1.0 / ({k} + by_fit) + coalesce(coverage / ({k} + by_tags), 0) AS rank
  FROM fused WHERE fit > %(cutoff)s OR best_vote_rank <= {strong}
  ORDER BY rank DESC, id
  LIMIT CASE WHEN EXISTS (SELECT FROM named) THEN {cap} END) -- NULL: no limit
)""".replace("{fit}", FIT_SQL)
    .replace("{artist}", MAIN_ARTIST)
    .replace("{popularity}", POPULARITY)
    .replace("{k}", RRF_K)
    .replace("{cap}", RELATED_CAP)
    .replace("{strong}", STRONG_TAGS)
)
