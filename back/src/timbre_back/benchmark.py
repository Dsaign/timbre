"""The Benchmark and the evaluate job: `python -m timbre_back.benchmark`.

Loads the committed Benchmark files into catalog and queues evaluate. The job tunes the
promoted model version's cutoff and Popularity weight on the model's own Fit ranking
(fast, in numpy), scores the result through the real search (search.MATCHES_SQL:
name step, tags and model), and records the three on it, with recall@24 and
precision@16 per Benchmark file. The train job uses it only
to evaluate and to keep Benchmark Descriptions out of training (train.may_train_on).
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import NamedTuple

import numpy as np
import psycopg
from psycopg.types.json import Jsonb

from timbre_back import model as models
from timbre_back.db import conninfo
from timbre_back.embed import embed_query
from timbre_back.feedback import normalize
from timbre_back.model import DIMS, LABELS, Floats, Model
from timbre_back.search import FILLER_WORDS, MATCHES_SQL

log = logging.getLogger("timbre.benchmark")
FILES = [
    Path(__file__).with_name("benchmark_hand_written.json"),  # the owner's (ticket 14)
    Path(__file__).with_name("benchmark_drafted.json"),
    # Generated from the Catalog by scripts/generate_benchmark.py (ticket 20).
    Path(__file__).with_name("benchmark_generated.json"),
]
TOP = 24  # the first screen of Matches (SearchParams.n)
PRECISION_TOP = 16  # the first screen on a phone
MIN_SONGS = 3
CUTOFFS = np.round(np.arange(0.5, 1.0, 0.005), 3)
# Small, so Popularity never overrides Fit: top Matches differ in Fit by hundredths.
WEIGHTS = np.round(np.arange(0.0, 0.055, 0.005), 3)
NONSENSE = "xkqzv wplmr tjhgf"  # must get 0 Matches, as in tests/test_search.py
NONSENSE_MARGIN = 0.005  # the cutoff stays this far above the nonsense best Fit


async def load(conn: psycopg.AsyncConnection) -> None:
    """Replace the stored Benchmark with the files, skipping blank template entries."""
    entries = [e for f in FILES for e in json.loads(f.read_text()) if e["description"]]
    for e in entries:
        if len(e["songs"]) < MIN_SONGS:
            raise ValueError(f"{e['description']!r}: fewer than {MIN_SONGS} Songs")
    await conn.execute("DELETE FROM catalog.benchmark_descriptions")
    async with conn.cursor() as cur:
        await cur.executemany(
            "INSERT INTO catalog.benchmark_descriptions"
            " (description, source, reviewed, accept_tags) VALUES (%s, %s, %s, %s)",
            [
                (e["description"], e["source"], e["reviewed"], e.get("accept_tags", []))
                for e in entries
            ],
        )
        await cur.executemany(
            "INSERT INTO catalog.benchmark_songs (description_id, song_id)"
            " SELECT id, %s FROM catalog.benchmark_descriptions WHERE description = %s",
            [(s["id"], e["description"]) for e in entries for s in e["songs"]],
        )


def score(
    fit: Floats,
    popularity: Floats,
    expected: list[list[int]],
    cutoff: float,
    weight: float,
) -> float:
    """Share of expected Songs among the top Matches by Fit alone, averaged over
    Descriptions: search_score's fast stand-in for tuning.

    Mirrors search.MATCHES_SQL's model ranking: Fit above the cutoff, ranked by Fit
    plus the weighted Popularity. An expected Song without a vector is never found
    (index -1).
    """
    rank = np.where(fit > cutoff, fit + weight * popularity, -np.inf)
    k = min(TOP, rank.shape[1])
    # shortcut: rank ties break arbitrarily, not by id, sort by id if ties ever matter
    top = np.argpartition(-rank, k - 1, axis=1)[:, :k]
    shares = []
    for row, songs in enumerate(expected):
        found = {int(i) for i in top[row] if np.isfinite(rank[row, i])}
        shares.append(sum(i in found for i in songs) / len(songs))
    return float(np.mean(shares))


def tune(
    fit: Floats, popularity: Floats, expected: list[list[int]], nonsense_fit: float
) -> tuple[float, float, float]:
    """(score, cutoff, weight) over the grid, for cutoffs at least NONSENSE_MARGIN
    above the nonsense Description's best Fit. Ties go to the highest cutoff, then
    the lowest weight."""
    cutoffs = [c for c in CUTOFFS.tolist() if c >= nonsense_fit + NONSENSE_MARGIN]
    if not cutoffs:
        raise ValueError(f"no cutoff on the grid is above nonsense Fit {nonsense_fit}")
    best = max(
        (score(fit, popularity, expected, c, w), c, -w)
        for c in cutoffs
        for w in WEIGHTS.tolist()
    )
    return best[0], best[1], -best[2]


class Catalog(NamedTuple):
    """The vectorized Songs: IDs, vectors, labels (NaN without) and Popularity."""

    song_ids: list[str]
    vectors: Floats
    labels: Floats
    popularity: Floats


async def catalog_arrays(conn: psycopg.AsyncConnection) -> Catalog:
    """The vectorized Songs, Popularity as in search.POPULARITY."""
    cur = await conn.execute(
        "SELECT id::text, vector::text, labels::text, listens,"
        " (SELECT max(listens) FROM catalog.songs)"
        " FROM catalog.songs WHERE vector IS NOT NULL"
    )
    songs = await cur.fetchall()
    nan = [float("nan")] * LABELS
    return Catalog(
        [song_id for song_id, *_ in songs],
        np.array([json.loads(v) for _, v, *_ in songs], dtype=np.float32).reshape(
            -1, DIMS
        ),
        np.array(
            [json.loads(labels) if labels else nan for _, _, labels, *_ in songs],
            dtype=np.float32,
        ).reshape(-1, LABELS),
        np.array(
            [
                np.log1p(listens) / np.log1p(max_listens) if max_listens else 0.0
                for *_, listens, max_listens in songs
            ],
            dtype=np.float32,
        ),
    )


class Benchmark(NamedTuple):
    descriptions: list[str]
    vectors: Floats  # e5 vectors of the Descriptions, then of NONSENSE
    expected: list[list[int]]  # per Description, its Songs' Catalog indexes
    catalog: Catalog
    sources: list[str]  # per Description, its file's source ("hand-written", ...)
    accept_tags: list[list[str]]  # per Description, the tag keys of a relevant Match

    @property
    def description_vectors(self) -> Floats:
        """The e5 vectors of the Benchmark Descriptions alone, without NONSENSE."""
        return self.vectors[:-1]


async def read(conn: psycopg.AsyncConnection) -> Benchmark | None:
    """The Benchmark against the Catalog, or None when no Song has a vector yet."""
    cur = await conn.execute(
        "SELECT d.description, array_agg(s.song_id::text), d.source, d.accept_tags"
        " FROM catalog.benchmark_descriptions d"
        " JOIN catalog.benchmark_songs s ON s.description_id = d.id"
        " GROUP BY d.id ORDER BY d.id"
    )
    rows = await cur.fetchall()
    if not rows:
        raise ValueError("the Benchmark is empty: run python -m timbre_back.benchmark")
    catalog = await catalog_arrays(conn)
    if not catalog.song_ids:
        return None
    index = {song_id: i for i, song_id in enumerate(catalog.song_ids)}
    descriptions = [d for d, *_ in rows]
    vectors = await asyncio.to_thread(
        lambda: [embed_query(d) for d in [*descriptions, NONSENSE]]
    )
    return Benchmark(
        descriptions,
        np.array(vectors, dtype=np.float32),
        [[index.get(s, -1) for s in ids] for _, ids, *_ in rows],
        catalog,
        [source for _, _, source, _ in rows],
        [accept for *_, accept in rows],
    )


def fits(model: Model, bench: Benchmark) -> tuple[Floats, float]:
    """Each Description's Fit with each Song, and the nonsense Description's best."""
    c = bench.catalog
    all_fit = model.fit(bench.vectors, c.vectors, c.labels)
    return all_fit[:-1], float(all_fit[-1].max())


TOP_MATCHES_SQL = """{matches}
SELECT m.id::text, s.tag_keys FROM matches m JOIN catalog.songs s USING (id)
ORDER BY m.part, m.rank DESC, m.id LIMIT %(top)s
""".replace("{matches}", MATCHES_SQL)


class Scores(NamedTuple):
    """`recall` is the promotion score: the share of expected Songs among the top
    Matches, averaged over all Descriptions. Per file (source): the same recall, and
    precision@16: how many of the first PRECISION_TOP Matches have one of the
    Description's accept_tags, out of PRECISION_TOP (a shorter list counts its missing
    Matches as misses), averaged over the Descriptions that have accept_tags."""

    recall: float
    recall_by_file: dict[str, float]
    precision_by_file: dict[str, float]


def by_file(values: list[tuple[str, float]]) -> dict[str, float]:
    """The mean value per source."""
    grouped: dict[str, list[float]] = {}
    for source, value in values:
        grouped.setdefault(source, []).append(value)
    return {source: float(np.mean(v)) for source, v in sorted(grouped.items())}


async def search_score(
    conn: psycopg.AsyncConnection,
    model: Model,
    bench: Benchmark,
    cutoff: float,
    weight: float,
) -> Scores:
    """Recall and precision of the real search (the API's ranking)."""
    index = {song_id: i for i, song_id in enumerate(bench.catalog.song_ids)}
    recalls: list[tuple[str, float]] = []
    precisions: list[tuple[str, float]] = []
    for description, vector, songs, source, accept in zip(
        bench.descriptions,
        bench.description_vectors,
        bench.expected,
        bench.sources,
        bench.accept_tags,
        strict=True,
    ):
        cur = await conn.execute(
            TOP_MATCHES_SQL,
            {
                **model.search_params(vector.tolist()),
                "description": normalize(description),
                "fillers": FILLER_WORDS,
                "cutoff": cutoff,
                "weight": weight,
                "top": TOP,
            },
        )
        rows = await cur.fetchall()
        # A name match can be a Song without a vector: never an expected one.
        found = {index[i] for i, _ in rows if i in index}
        recalls.append((source, sum(i in found for i in songs) / len(songs)))
        if accept:
            hits = sum(
                bool(set(keys or []) & set(accept)) for _, keys in rows[:PRECISION_TOP]
            )
            precisions.append((source, hits / PRECISION_TOP))
    return Scores(
        float(np.mean([r for _, r in recalls])), by_file(recalls), by_file(precisions)
    )


async def tuned(
    conn: psycopg.AsyncConnection, model: Model, bench: Benchmark
) -> tuple[Scores, float, float]:
    """The model's (search scores, cutoff, weight), tuned on the Benchmark."""
    fit, nonsense_fit = fits(model, bench)
    _, cutoff, weight = await asyncio.to_thread(
        tune, fit, bench.catalog.popularity, bench.expected, nonsense_fit
    )
    return await search_score(conn, model, bench, cutoff, weight), cutoff, weight


async def evaluate(conn: psycopg.AsyncConnection) -> None:
    bench = await read(conn)
    if bench is None:
        log.warning("evaluate: skipped, no Song has a vector yet (build-vectors)")
        return
    cur = await conn.execute(
        "SELECT cutoff, popularity_weight, file FROM catalog.model_versions"
        " WHERE promoted"
    )
    row = await cur.fetchone()
    if row is None:
        raise ValueError("no promoted model version to evaluate and record on")
    old_cutoff, old_weight, file = row
    model = models.load(file)
    before = await search_score(conn, model, bench, old_cutoff, old_weight)
    best, cutoff, weight = await tuned(conn, model, bench)
    await conn.execute(
        "UPDATE catalog.model_versions SET benchmark_score = %s, cutoff = %s,"
        " popularity_weight = %s, recall_at_24 = %s, precision_at_16 = %s"
        " WHERE promoted",
        (
            best.recall,
            cutoff,
            weight,
            Jsonb(best.recall_by_file),
            Jsonb(best.precision_by_file),
        ),
    )
    log.info(
        "evaluate: %d Benchmark Descriptions, %d Songs. Search score (expected Songs"
        " in the top %d) was %.3f at cutoff %.3f and weight %.3f; tuned %.3f at"
        " cutoff %.3f and weight %.3f, recorded on the promoted model version."
        " %s",
        len(bench.descriptions),
        len(bench.catalog.song_ids),
        TOP,
        before.recall,
        old_cutoff,
        old_weight,
        best.recall,
        cutoff,
        weight,
        report(best),
    )


def report(scores: Scores) -> str:
    """recall@24 and precision@16 per file, for the logs."""
    return "; ".join(
        f"{source}: recall@{TOP} {recall:.3f}, precision@{PRECISION_TOP} "
        + (
            f"{scores.precision_by_file[source]:.3f}"
            if source in scores.precision_by_file
            else "-"
        )
        for source, recall in scores.recall_by_file.items()
    )


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(conninfo("ml_worker")) as conn:
        await load(conn)
        await conn.execute("INSERT INTO jobs.queue (kind) VALUES ('evaluate')")


if __name__ == "__main__":
    asyncio.run(main())
