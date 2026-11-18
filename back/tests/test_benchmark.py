"""Seam 2: the evaluate job on the real database and worker, with a tiny fixture Catalog
and Benchmark in place of the real ones (inside a transaction that is rolled back).

Every Description's query vector is one axis; each fixture Song has a chosen Fit on one
axis and the rest on its own axis, so the Fits are known exactly. With the top cut to 1:
- A: X (popular, Fit 0.90) is the top Match only once the weight beats Y's 0.917 lead:
  0.02, the lowest weight on the grid that does.
- B: Z (Fit 0.802) stays a Match up to cutoff 0.800, the highest cutoff keeping it.
- C: V (Fit 0.60) is below the nonsense Song's 0.62, and the guard keeps the cutoff at
  0.630 or more (0.625 would sit exactly on the margin, but the float32 Fit is a hair
  above 0.62, so 0.625 fails the check), so V never matches.
Score: (1/3 + 1/3 + 0) / 3. Without the guard, cutoff 0.595 would score 3/9.
"""

import json
import math
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import numpy as np
import psycopg
import pytest
from psycopg.types.json import Jsonb

from timbre_back import benchmark, main, worker
from timbre_back.db import conninfo, vector_literal
from timbre_back.model import BASELINE, DIMS, LABELS, Model
from timbre_back.profile import WORDS
from timbre_back.search import FILLER_WORDS

AXES = {"A": 0, "B": 1, "C": 2, benchmark.NONSENSE: 3}
# name: (axes, Fit with their sum, listens)
SONGS = {
    "X": ((0,), 0.90, 1000),
    "Y": ((0,), 0.917, 0),
    "A2": ((0,), 0.5, 0),
    "A3": ((0,), 0.5, 0),
    "Z": ((1,), 0.802, 0),
    "B2": ((1,), 0.5, 0),
    "B3": ((1,), 0.5, 0),
    "V": ((2,), 0.60, 0),
    "C2": ((2,), 0.5, 0),
    "C3": ((2,), 0.5, 0),
    "N": ((3,), 0.62, 0),
    # For the SEARCH_SQL parity test only: on A or B alone their Fit stays below 0.63,
    # the lowest cutoff the evaluate test allows, so they never change its result.
    "M": ((0, 1), 0.63, 30),  # mid Popularity: log1p(30) / log1p(1000) = 0.497
    "E": ((0, 1), 0.402, 0),  # just above the parity cutoff 0.4
    "F": ((0, 1), 0.398, 0),  # just below it
}
EXPECTED = {"A": ["X", "A2", "A3"], "B": ["Z", "B2", "B3"], "C": ["V", "C2", "C3"]}


def song_id(name: str) -> str:
    return f"00000000-0000-0000-0013-{list(SONGS).index(name):012d}"


def unit(axis: int) -> list[float]:
    return [1.0 if i == axis else 0.0 for i in range(DIMS)]


def song_vector(n: int, axes: tuple[int, ...], fit: float) -> list[float]:
    vector = [0.0] * DIMS
    for axis in axes:
        vector[axis] = fit / math.sqrt(len(axes))
    vector[10 + n] = math.sqrt(1 - fit**2)  # an axis of its own
    return vector


def write_benchmark(
    path: Path,
    expected: dict[str, list[str]],
    accept_tags: dict[str, list[str]] | None = None,
) -> None:
    path.write_text(
        json.dumps(
            [
                {
                    "description": description,
                    "source": "drafted",
                    "reviewed": False,
                    "accept_tags": (accept_tags or {}).get(description, []),
                    "songs": [{"id": song_id(s)} for s in songs],
                }
                for description, songs in expected.items()
            ]
        )
    )


async def one(conn: psycopg.AsyncConnection, query: Any, *params: Any) -> Any:
    cur = await conn.execute(query, params)
    row = await cur.fetchone()
    assert row is not None
    return row


@pytest.fixture
async def conn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[psycopg.AsyncConnection]:
    """Only the fixture Catalog and Benchmark, every write rolled back."""
    monkeypatch.setattr(benchmark, "TOP", 1)
    monkeypatch.setattr(benchmark, "embed_query", lambda d: unit(AXES[d]))
    monkeypatch.setattr(benchmark, "FILES", [tmp_path / "benchmark.json"])
    async with await psycopg.AsyncConnection.connect(
        conninfo("ml_worker"), autocommit=True
    ) as conn:
        async with conn.transaction(force_rollback=True):
            await conn.execute("DELETE FROM catalog.benchmark_descriptions")
            await conn.execute("DELETE FROM catalog.songs")
            # The fixture's Fits are the baseline's (plain e5 cosine).
            await conn.execute("UPDATE catalog.model_versions SET promoted = false")
            await conn.execute(
                "UPDATE catalog.model_versions SET promoted = true WHERE id = 1"
            )
            async with conn.cursor() as cur:
                await cur.executemany(
                    "INSERT INTO catalog.songs (id, title, artist, listens, vector)"
                    " VALUES (%s, %s, 'fixture', %s, %s::vector)",
                    [
                        (
                            song_id(name),
                            name,
                            listens,
                            vector_literal(song_vector(n, a, f)),
                        )
                        for n, (name, (a, f, listens)) in enumerate(SONGS.items())
                    ],
                )
            yield conn


@pytest.mark.anyio
async def test_evaluate_scores_tunes_and_records_on_the_baseline(
    conn: psycopg.AsyncConnection,
) -> None:
    write_benchmark(benchmark.FILES[0], EXPECTED)
    await benchmark.load(conn)
    (job,) = await one(
        conn, "INSERT INTO jobs.queue (kind) VALUES ('evaluate') RETURNING id"
    )
    # Until the rollback, every other job is not due, so the claim can take only ours.
    await conn.execute(
        "UPDATE jobs.queue SET run_after = 'infinity' WHERE id IN (SELECT id"
        "   FROM jobs.queue WHERE status = 'queued' AND id <> %s"
        "   FOR UPDATE SKIP LOCKED)",
        (job,),
    )

    assert await worker.run_next_job(conn)
    assert await one(
        conn, "SELECT status, error FROM jobs.queue WHERE id = %s", job
    ) == (
        "done",
        None,
    )
    score, cutoff, weight = await one(
        conn,
        "SELECT benchmark_score, cutoff, popularity_weight"
        " FROM catalog.model_versions WHERE promoted",
    )
    assert score == pytest.approx(2 / 9, abs=1e-6)
    assert cutoff == pytest.approx(0.800, abs=1e-6)
    assert weight == pytest.approx(0.020, abs=1e-6)
    recall, precision = await one(
        conn,
        "SELECT recall_at_24, precision_at_16 FROM catalog.model_versions"
        " WHERE promoted",
    )
    assert recall == {"drafted": pytest.approx(2 / 9, abs=1e-6)}
    assert precision == {}  # no Description has accept_tags


@pytest.mark.anyio
async def test_precision_counts_the_first_16_matches_with_an_accept_tag(
    conn: psycopg.AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """At cutoff 0, A has 7 Matches and B 6, fewer than the 16 of the first screen.
    Only Y (a Match of A) has an accept tag of its Description, so A scores 1/16, not
    1/7: missing Matches count as misses. C has no accept_tags, so it is left out."""
    monkeypatch.setattr(benchmark, "TOP", benchmark.PRECISION_TOP)
    write_benchmark(
        benchmark.FILES[0], EXPECTED, {"A": ["zylo fonk"], "B": ["zylo fonk"]}
    )
    await conn.execute(
        "UPDATE catalog.songs SET tags = %s WHERE id = %s",
        (["Zylo-Fonk"], song_id("Y")),
    )
    await benchmark.load(conn)
    bench = await benchmark.read(conn)
    assert bench is not None
    scores = await benchmark.search_score(conn, BASELINE, bench, 0.0, 0.0)
    assert scores.precision_by_file == {"drafted": (1 / 16 + 0) / 2}
    assert scores.recall_by_file == {"drafted": scores.recall}


@pytest.mark.anyio
async def test_a_name_match_without_a_vector_scores_as_not_found(
    conn: psycopg.AsyncConnection,
) -> None:
    """The real search can name a Song that has no vector (so no Catalog index)."""
    write_benchmark(benchmark.FILES[0], EXPECTED)
    await benchmark.load(conn)
    bench = await benchmark.read(conn)
    assert bench is not None
    await conn.execute(
        "INSERT INTO catalog.songs (id, title, artist)"
        " VALUES (%s, 'Untold', 'Quorvath Ensemble')",
        ("00000000-0000-0000-0013-999999999998",),
    )
    named = benchmark.Benchmark(
        ["Quorvath Ensemble"],
        np.array([unit(0), unit(3)], dtype=np.float32),
        [[bench.catalog.song_ids.index(song_id("X"))]],
        bench.catalog,
        ["drafted"],
        [[]],
    )
    # TOP is 1: the named Song fills it, so X is not found.
    scores = await benchmark.search_score(conn, BASELINE, named, 0.0, 0.0)
    assert scores.recall == 0.0


@pytest.mark.anyio
async def test_load_refuses_a_description_with_fewer_than_3_songs(
    conn: psycopg.AsyncConnection,
) -> None:
    write_benchmark(benchmark.FILES[0], {"A": ["X", "A2"]})
    with pytest.raises(ValueError, match="fewer than 3 Songs"):
        await benchmark.load(conn)


@pytest.mark.anyio
async def test_load_refuses_a_song_missing_from_the_catalog(
    conn: psycopg.AsyncConnection,
) -> None:
    missing = "00000000-0000-0000-0013-999999999999"
    songs = [{"id": song_id("X")}, {"id": song_id("A2")}, {"id": missing}]
    benchmark.FILES[0].write_text(
        json.dumps(
            [
                {
                    "description": "A",
                    "source": "drafted",
                    "reviewed": False,
                    "songs": songs,
                }
            ]
        )
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        async with conn.transaction():
            await benchmark.load(conn)


@pytest.mark.anyio
async def test_evaluate_skips_a_catalog_without_vectors(
    conn: psycopg.AsyncConnection,
) -> None:
    write_benchmark(benchmark.FILES[0], EXPECTED)
    await benchmark.load(conn)
    await conn.execute("UPDATE catalog.songs SET vector = NULL")
    query = (
        "SELECT benchmark_score, cutoff, popularity_weight FROM catalog.model_versions"
    )
    before = await one(conn, query + " WHERE promoted")
    await benchmark.evaluate(conn)
    assert await one(conn, query + " WHERE promoted") == before


@pytest.mark.anyio
@pytest.mark.parametrize(("weight", "n"), [(0.0, 1), (0.05, 1), (0.05, 2), (0.05, 10)])
async def test_ranking_matches_search_sql(
    conn: psycopg.AsyncConnection,
    monkeypatch: pytest.MonkeyPatch,
    weight: float,
    n: int,
) -> None:
    """Between A and B: Fits Y 0.648, X 0.636, M 0.63, Z 0.567, E 0.402, F 0.398,
    the rest 0.354 or less. At weight 0.05 popular X leads, and M's mid Popularity
    lifts it to 0.655, past Y, only if normalised by log as SEARCH_SQL does. With
    room for all, the Matches are exactly X, M, Y, Z and E: F is just below the cutoff.
    """
    cutoff = 0.4
    await conn.execute(
        "UPDATE catalog.model_versions SET cutoff = %s, popularity_weight = %s"
        " WHERE promoted",
        (cutoff, weight),
    )
    query = [(a + b) / math.sqrt(2) for a, b in zip(unit(0), unit(1), strict=True)]
    sql_top = await search_sql(conn, BASELINE, query, n)

    song_ids, vectors, _, popularity = await benchmark.catalog_arrays(conn)
    fit = (vectors @ query)[None, :].astype("float32")
    monkeypatch.setattr(benchmark, "TOP", n)
    in_sql = [song_ids.index(i) for i in sql_top]
    others = [[i] for i in range(len(song_ids)) if i not in in_sql]
    # Python's top n holds every Song SQL returned, and no other.
    assert benchmark.score(fit, popularity, [in_sql], cutoff, weight) == 1.0
    rows = fit.repeat(len(others), axis=0)  # one row per expected list
    assert benchmark.score(rows, popularity, others, cutoff, weight) == 0.0
    assert len(sql_top) == min(n, 5)


async def search_sql(
    conn: psycopg.AsyncConnection, model: Model, query: list[float], n: int
) -> list[str]:
    """The IDs of SEARCH_SQL's first n Matches, with the promoted cutoff and weight."""
    cutoff, weight = await one(
        conn,
        "SELECT cutoff, popularity_weight FROM catalog.model_versions WHERE promoted",
    )
    cur = await conn.execute(
        main.SEARCH_SQL,
        {
            **model.search_params(query),
            "cutoff": cutoff,
            "weight": weight,
            "n": n,
            "offset": 0,
            "description": "parity",
            "fillers": FILLER_WORDS,
            "visitor": "parity",
        },
    )
    _, matches = await cur.fetchone() or (0, [])
    return [m["id"] for m in matches]


@pytest.mark.anyio
async def test_trained_model_fit_matches_search_sql(
    conn: psycopg.AsyncConnection,
) -> None:
    """A model with a projection and a head ranks the same in Python and SEARCH_SQL,
    a Song without labels (Z) included."""
    rng = np.random.default_rng(15)
    projection = np.eye(DIMS) + rng.normal(0, 0.05, (DIMS, DIMS))
    head = rng.normal(0, 0.5, (DIMS, LABELS))
    model = Model(
        projection.astype(np.float32),
        head.astype(np.float32),
        np.full(LABELS, 0.5, dtype=np.float32),
        0.3,
    )
    await conn.execute(
        "UPDATE catalog.model_versions SET cutoff = 0, popularity_weight = 0.02"
        " WHERE promoted"
    )
    for name in SONGS:
        if name != "Z":
            values = rng.uniform(0, 1, LABELS).round(3).tolist()
            acousticbrainz: dict[str, dict[str, float]] = {}
            for (classifier, label), value in zip(WORDS, values, strict=True):
                acousticbrainz.setdefault(classifier, {})[label] = value
            await conn.execute(
                "UPDATE catalog.songs SET acousticbrainz = %s WHERE id = %s",
                (Jsonb(acousticbrainz), song_id(name)),
            )
    query = [(a + b) / math.sqrt(2) for a, b in zip(unit(0), unit(1), strict=True)]
    sql_top = await search_sql(conn, model, query, len(SONGS))

    song_ids, vectors, labels, popularity = await benchmark.catalog_arrays(conn)
    fit = model.fit(np.array([query], dtype=np.float32), vectors, labels)[0]
    rank = fit + 0.02 * popularity
    assert [song_ids[i] for i in np.argsort(-rank)] == sql_top
    assert np.isnan(labels[song_ids.index(song_id("Z"))]).all()


@pytest.mark.anyio
async def test_evaluate_refuses_without_a_promoted_model_version(
    conn: psycopg.AsyncConnection,
) -> None:
    write_benchmark(benchmark.FILES[0], EXPECTED)
    await benchmark.load(conn)
    await conn.execute("UPDATE catalog.model_versions SET promoted = false")
    with pytest.raises(ValueError, match="no promoted model version"):
        await benchmark.evaluate(conn)
