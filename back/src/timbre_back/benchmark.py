"""The Benchmark and the evaluate job: `python -m timbre_back.benchmark`.

Loads the committed Benchmark files into catalog and queues evaluate. The job scores the
promoted model version on the Benchmark, tunes its cutoff and Popularity weight, and
records the three on it. The train job uses it only to evaluate and to keep Benchmark
Descriptions out of training (train.may_train_on).
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import NamedTuple

import numpy as np
import psycopg

from timbre_back import model as models
from timbre_back.db import conninfo
from timbre_back.embed import embed_query
from timbre_back.model import DIMS, LABELS, Floats, Model

log = logging.getLogger("timbre.benchmark")
FILES = [
    Path(__file__).with_name("benchmark_hand_written.json"),  # the owner's (ticket 14)
    Path(__file__).with_name("benchmark_drafted.json"),
]
TOP = 24  # the first screen of Matches (SearchParams.n)
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
            "INSERT INTO catalog.benchmark_descriptions (description, source, reviewed)"
            " VALUES (%s, %s, %s)",
            [(e["description"], e["source"], e["reviewed"]) for e in entries],
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
    """Share of expected Songs among the top Matches, averaged over Descriptions.

    Mirrors main.SEARCH_SQL: Matches have Fit above the cutoff, ranked by Fit plus the
    weighted Popularity. An expected Song without a vector is never found (index -1).
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
    """The vectorized Songs, Popularity as in SEARCH_SQL."""
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

    @property
    def description_vectors(self) -> Floats:
        """The e5 vectors of the Benchmark Descriptions alone, without NONSENSE."""
        return self.vectors[:-1]


async def read(conn: psycopg.AsyncConnection) -> Benchmark | None:
    """The Benchmark against the Catalog, or None when no Song has a vector yet."""
    cur = await conn.execute(
        "SELECT d.description, array_agg(s.song_id::text)"
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
    descriptions = [d for d, _ in rows]
    vectors = await asyncio.to_thread(
        lambda: [embed_query(d) for d in [*descriptions, NONSENSE]]
    )
    return Benchmark(
        descriptions,
        np.array(vectors, dtype=np.float32),
        [[index.get(s, -1) for s in ids] for _, ids in rows],
        catalog,
    )


def fits(model: Model, bench: Benchmark) -> tuple[Floats, float]:
    """Each Description's Fit with each Song, and the nonsense Description's best."""
    c = bench.catalog
    all_fit = model.fit(bench.vectors, c.vectors, c.labels)
    return all_fit[:-1], float(all_fit[-1].max())


async def tuned(model: Model, bench: Benchmark) -> tuple[float, float, float]:
    """The model's (score, cutoff, weight), tuned on the Benchmark."""
    fit, nonsense_fit = fits(model, bench)
    return await asyncio.to_thread(
        tune, fit, bench.catalog.popularity, bench.expected, nonsense_fit
    )


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
    fit, nonsense_fit = fits(models.load(file), bench)
    popularity = bench.catalog.popularity
    before = score(fit, popularity, bench.expected, old_cutoff, old_weight)
    best, cutoff, weight = await asyncio.to_thread(
        tune, fit, popularity, bench.expected, nonsense_fit
    )
    await conn.execute(
        "UPDATE catalog.model_versions"
        " SET benchmark_score = %s, cutoff = %s, popularity_weight = %s WHERE promoted",
        (best, cutoff, weight),
    )
    log.info(
        "evaluate: %d Benchmark Descriptions, %d Songs. Score (expected Songs in"
        " the top %d) was %.3f at cutoff %.3f and weight %.3f; tuned %.3f at"
        " cutoff %.3f and weight %.3f (nonsense best Fit %.3f), recorded on the"
        " promoted model version",
        len(bench.descriptions),
        len(bench.catalog.song_ids),
        TOP,
        before,
        old_cutoff,
        old_weight,
        best,
        cutoff,
        weight,
        nonsense_fit,
    )


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(conninfo("ml_worker")) as conn:
        await load(conn)
        await conn.execute("INSERT INTO jobs.queue (kind) VALUES ('evaluate')")


if __name__ == "__main__":
    asyncio.run(main())
