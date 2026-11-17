"""The train job (seam 2, on the real database and worker, rolled back) and the live
model switch (seam 1, over the network).

Fixture: every Benchmark Description is one axis, each Song has a chosen Fit with it and
the rest on an axis of its own. The Benchmark keeps the top 1:
- A: Y (Fit 0.9) beats the expected X (0.8), so the baseline finds nothing for A.
- B: the expected Z (0.9) beats W (0.85), so the baseline finds Z: score (0 + 1/3) / 2.
Training on "a-like" (cosine 0.8 with A) -> X projects A towards X: X comes first, 1/3.
Training on "b-like" -> W projects B towards W: W comes first, and the score drops to 0.
"""

import json
import math
import os
from collections.abc import AsyncIterator, Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, LiteralString
from uuid import uuid4

import httpx
import numpy as np
import psycopg
import pytest

from timbre_back import benchmark, train, worker
from timbre_back import model as models
from timbre_back.db import conninfo
from timbre_back.embed import embed_query
from timbre_back.model import DIMS, LABELS, Model

# Description: its vector, as {axis: value}
DESCRIPTION_VECTORS = {
    "A": {0: 1.0},
    "B": {1: 1.0},
    benchmark.NONSENSE: {3: 1.0},
    "a-like": {0: 0.8, 5: 0.6},
    "b-like": {1: 0.8, 6: 0.6},
    # training only (examples() lowercases Descriptions)
    "calm": {0: 1.0},
    "quiet": {7: 1.0},
    "loud": {1: 1.0},
}
# name: (axis, Fit with it); the rest of each vector is on an axis of its own
SONGS = {
    "X": (0, 0.8),
    "Y": (0, 0.9),
    "A2": (0, 0.5),
    "A3": (0, 0.5),
    "Z": (1, 0.9),
    "W": (1, 0.85),
    "B2": (1, 0.5),
    "B3": (1, 0.5),
    "N": (3, 0.6),
    # For the Feedback job test only: on axis 7, away from every Benchmark Description.
    "QU": (7, 0.7),
    "QD": (7, 0.9),
}
EXPECTED = {"A": ["X", "A2", "A3"], "B": ["Z", "B2", "B3"]}


def song_id(name: str) -> str:
    return f"00000000-0000-0000-0015-{list(SONGS).index(name):012d}"


def vector(axes: dict[int, float]) -> list[float]:
    return [axes.get(i, 0.0) for i in range(DIMS)]


def fixture_vector(name: str) -> list[float]:
    """A fixture Song's vector: its Fit on its axis, the rest on an axis of its own."""
    axis, fit = SONGS[name]
    return vector({axis: fit, 10 + list(SONGS).index(name): math.sqrt(1 - fit**2)})


def fake_embed(description: str) -> list[float]:
    # Real visitor votes in the database get an axis no fixture Song uses.
    return vector(DESCRIPTION_VECTORS.get(description, {300: 1.0}))


def write(path: Path, entries: dict[str, list[str]], **fields: Any) -> None:
    path.write_text(
        json.dumps(
            [
                {"description": d, **fields, "songs": [{"id": song_id(s)} for s in ss]}
                for d, ss in entries.items()
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
    monkeypatch.setattr(benchmark, "embed_query", fake_embed)
    monkeypatch.setattr(train, "embed_query", fake_embed)
    monkeypatch.setattr(benchmark, "FILES", [tmp_path / "benchmark.json"])
    monkeypatch.setattr(train, "FILES", [tmp_path / "training.json"])
    monkeypatch.setattr(models, "MODEL_DIR", tmp_path)
    models.load.cache_clear()
    write(benchmark.FILES[0], EXPECTED, source="drafted", reviewed=False)
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
                    "INSERT INTO catalog.songs (id, title, artist, vector)"
                    " VALUES (%s, %s, 'fixture', %s::vector)",
                    [(song_id(name), name, fixture_vector(name)) for name in SONGS],
                )
            await benchmark.load(conn)
            yield conn
    models.load.cache_clear()


async def run_train(conn: psycopg.AsyncConnection) -> tuple[Any, ...]:
    """Runs a train job through the worker; the new version's row."""
    (job,) = await one(
        conn, "INSERT INTO jobs.queue (kind) VALUES ('train') RETURNING id"
    )
    # Until the rollback, every other job is not due, so the claim can take only ours.
    await conn.execute(
        "UPDATE jobs.queue SET run_after = 'infinity' WHERE id IN (SELECT id"
        "   FROM jobs.queue WHERE status = 'queued' AND id <> %s"
        "   FOR UPDATE SKIP LOCKED)",
        (job,),
    )
    assert await worker.run_next_job(conn)
    status = await one(conn, "SELECT status, error FROM jobs.queue WHERE id = %s", job)
    assert status == ("done", None)
    return tuple(
        await one(
            conn,
            "SELECT id, benchmark_score, promoted, file FROM catalog.model_versions"
            " ORDER BY id DESC LIMIT 1",
        )
    )


@pytest.mark.anyio
async def test_a_clearly_better_model_is_promoted(
    conn: psycopg.AsyncConnection, tmp_path: Path
) -> None:
    write(train.FILES[0], {"a-like": ["X"]})
    (before,) = await one(conn, "SELECT id FROM catalog.model_versions WHERE promoted")

    version, score, promoted, file = await run_train(conn)

    assert version > before
    assert score == pytest.approx(1 / 3, abs=1e-6)  # the baseline's is 1/6
    assert promoted
    assert (tmp_path / file).is_file()
    assert await one(
        conn, "SELECT count(*) FROM catalog.model_versions WHERE promoted"
    ) == (1,)


@pytest.mark.anyio
async def test_a_clearly_worse_model_is_refused(
    conn: psycopg.AsyncConnection, tmp_path: Path
) -> None:
    write(train.FILES[0], {"b-like": ["W"]})
    (before,) = await one(conn, "SELECT id FROM catalog.model_versions WHERE promoted")

    version, score, promoted, file = await run_train(conn)

    assert score == pytest.approx(0.0, abs=1e-6)
    assert not promoted
    assert (tmp_path / file).is_file()  # recorded, just not live
    assert await one(conn, "SELECT id FROM catalog.model_versions WHERE promoted") == (
        before,
    )
    assert version > before


@pytest.fixture
def votes() -> Iterator[None]:
    """Visitor votes for "quiet" (committed: the job reads them on another
    connection): 👍 QU and 👎 QD. Deleted afterwards."""
    visitor = f"test-{uuid4().hex}"
    with psycopg.connect(conninfo("api_search")) as conn:

        def as_visitor(sql: LiteralString, *params: Any) -> None:
            with conn.transaction():
                conn.execute(
                    "SELECT set_config('app.visitor_hash', %s, true)", (visitor,)
                )
                conn.execute(sql, params)

        as_visitor(
            "INSERT INTO feedback.votes (visitor_hash, description, song_id, vote)"
            " VALUES (%s, 'quiet', %s, 'up'), (%s, 'quiet', %s, 'down')",
            visitor,
            song_id("QU"),
            visitor,
            song_id("QD"),
        )
        try:
            yield
        finally:
            as_visitor("DELETE FROM feedback.votes WHERE visitor_hash = %s", visitor)


@pytest.mark.anyio
@pytest.mark.usefixtures("votes")
async def test_feedback_votes_change_the_trained_model(
    conn: psycopg.AsyncConnection,
) -> None:
    """Plain e5 ranks the 👎 Song QD (Fit 0.9) above the 👍 Song QU (0.7) for
    "quiet"; the trained version ranks QD at least MARGIN below QU."""
    write(train.FILES[0], {})  # no drafted pairs: only Feedback to learn from
    quiet = np.array([fake_embed("quiet")], dtype=np.float32)
    songs = np.array([fixture_vector("QU"), fixture_vector("QD")], dtype=np.float32)
    no_labels = np.full((2, LABELS), np.nan, dtype=np.float32)
    up, down = models.BASELINE.fit(quiet, songs, no_labels)[0]
    assert down > up

    *_, file = await run_train(conn)

    up, down = models.load(file).fit(quiet, songs, no_labels)[0]
    assert up - down >= train.MARGIN - 1e-6


def test_votes_are_grouped_by_normalized_description() -> None:
    grouped = train.examples(
        [("Calm  Piano", "s1", "up"), ("calm piano", "s2", "down"), ("x", "s3", "up")]
    )
    assert grouped == {"calm piano": (["s1"], ["s2"]), "x": (["s3"], [])}


def test_training_leaves_out_benchmark_descriptions_and_near_copies() -> None:
    def at(cosine: float) -> list[float]:  # this e5 cosine with the Benchmark's
        return vector({0: cosine, 1: math.sqrt(1 - cosine**2)})

    usable = train.may_train_on(
        ["fast punk", "punk, fast", "punk-ish"],
        # The first is the Benchmark Description itself (normalized), on any vector.
        np.array([vector({2: 1.0}), at(0.93), at(0.91)], dtype=np.float32),
        ["Fast  Punk"],
        np.array([vector({0: 1.0})], dtype=np.float32),
    )
    assert usable == [False, False, True]


def song(axis: int, fit: float, own: int) -> list[float]:
    """A Song vector with this Fit on the axis, the rest on an axis of its own."""
    return vector({axis: fit, own: math.sqrt(1 - fit**2)})


def labels(*high: int) -> list[float]:
    return [0.9 if i in high else 0.1 for i in range(LABELS)]


def learn(
    votes: list[tuple[str, str, str]], songs: dict[str, tuple[list[float], list[float]]]
) -> Model:
    """Trains on the votes over a Catalog of `songs` (name: (vector, labels)), with
    Description vectors from DESCRIPTION_VECTORS."""
    catalog = benchmark.Catalog(
        list(songs),
        np.array([v for v, _ in songs.values()], dtype=np.float32),
        np.array([lb for _, lb in songs.values()], dtype=np.float32),
        np.zeros(len(songs), dtype=np.float32),
    )
    grouped = train.examples(votes)
    vectors = np.array([fake_embed(d) for d in grouped], dtype=np.float32)
    model, _, _ = train.learn(grouped, vectors, [True] * len(grouped), catalog)
    return model


def test_the_head_learns_the_labels_of_a_descriptions_songs() -> None:
    songs = {"U": (song(0, 0.8, 10), labels(0, 1)), "V": (song(1, 0.8, 11), labels(5))}
    model = learn([("calm", "U", "up"), ("loud", "V", "up")], songs)
    assert model.head_weight == train.HEAD_WEIGHT
    _, predicted = model.project(np.array([fake_embed("calm")], dtype=np.float32))
    u, v = (np.array(lb, dtype=np.float32) for _, lb in songs.values())
    assert np.abs(predicted[0] - u).mean() < np.abs(predicted[0] - v).mean()


def test_feedback_pulls_up_votes_up_and_pushes_down_votes_below_them() -> None:
    """Before training, the 👎 Song D fits "calm" best and the 👍 Song U worst. After, U
    fits better than before, and D ends at least MARGIN below U."""
    songs = {
        "U": (song(0, 0.7, 10), labels(0)),
        "D": (song(0, 0.9, 11), labels(1)),
        "O": (song(0, 0.8, 12), labels(2)),
        "V": (song(1, 0.8, 13), labels(3)),  # gives the head a second Description
    }
    calm = np.array([fake_embed("calm")], dtype=np.float32)
    catalog_vectors = np.array([v for v, _ in songs.values()], dtype=np.float32)
    catalog_labels = np.array([lb for _, lb in songs.values()], dtype=np.float32)
    before = models.BASELINE.fit(calm, catalog_vectors, catalog_labels)[0]
    assert before[1] > before[0]

    model = learn(
        [("calm", "U", "up"), ("calm", "D", "down"), ("loud", "V", "up")], songs
    )

    after = model.fit(calm, catalog_vectors, catalog_labels)[0]
    assert model.head_weight > 0  # the hinge also moved the head
    assert after[0] > before[0]
    assert after[0] - after[1] >= train.MARGIN - 1e-6


def test_the_hinge_ranks_a_down_vote_below_the_up_vote() -> None:
    """From a model where the 👎 Song D fits better than the 👍 Song U, projection and
    head both, the hinge alone moves D MARGIN below U."""
    calm = np.array([fake_embed("calm")], dtype=np.float32)
    up, down = song(0, 0.7, 10), song(0, 0.9, 11)
    up_labels, down_labels = labels(0), labels(1)
    start = models.BASELINE._replace(
        bias=np.array(down_labels, dtype=np.float32), head_weight=0.2
    )
    vectors = np.array([up, down], dtype=np.float32)
    song_labels = np.array([up_labels, down_labels], dtype=np.float32)
    assert np.diff(start.fit(calm, vectors, song_labels)[0])[0] > 0

    model = train.push_negatives(
        start,
        train.Triples(
            calm,
            np.array([up], dtype=np.float32),
            np.array([up_labels], dtype=np.float32),
            np.array([down], dtype=np.float32),
            np.array([down_labels], dtype=np.float32),
        ),
    )

    fit = model.fit(calm, vectors, song_labels)[0]
    assert fit[0] - fit[1] >= train.MARGIN - 1e-6
    assert not np.array_equal(model.bias, start.bias)  # the head moved too


API_URL = os.environ.get("API_URL", "http://api:8000")
AUTH = {
    "Authorization": f"Bearer {os.environ['FRONT_TOKEN']}",
    "X-Visitor-IP": "192.0.2.1",
}
SWAP = "something dark and electronic to focus"


def search_swap() -> Any:
    response = httpx.get(
        f"{API_URL}/search", params={"q": SWAP}, headers=AUTH, timeout=30
    )
    assert response.status_code == 200
    return response.json()


def first_match() -> str:
    return str(search_swap()["matches"][0]["id"])


@contextmanager
def promoted_version(
    file: str | None, settings: tuple[float, float] | None = None
) -> Generator[None]:
    """Promotes a new version with `file` (None: the baseline) and `settings`
    (cutoff, weight; default: the promoted version's) on the shared database, then
    puts back exactly what was promoted before."""
    with psycopg.connect(conninfo("ml_worker"), autocommit=True) as conn:
        before = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM catalog.model_versions WHERE promoted"
            ).fetchall()
        ]
        cutoff, weight = (
            settings
            or conn.execute(
                "SELECT cutoff, popularity_weight FROM catalog.model_versions"
                " WHERE promoted"
            ).fetchone()
            or (0.83, 0.05)
        )
        with conn.transaction():
            conn.execute("UPDATE catalog.model_versions SET promoted = false")
            (version,) = conn.execute(
                "INSERT INTO catalog.model_versions"
                " (name, cutoff, popularity_weight, promoted, file)"
                " VALUES ('test version', %s, %s, true, %s) RETURNING id",
                (cutoff, weight, file),
            ).fetchone() or (None,)
        try:
            yield
        finally:
            with conn.transaction():
                conn.execute(
                    "DELETE FROM catalog.model_versions WHERE id = %s", (version,)
                )
                conn.execute(
                    "UPDATE catalog.model_versions SET promoted = true"
                    " WHERE id = ANY(%s)",
                    (before,),
                )


@pytest.mark.usefixtures("seed_vectors_built")
def test_the_api_switches_to_a_newly_promoted_version_without_a_restart() -> None:
    """A version that projects the Description onto one Song puts it first, on the
    running API, as soon as it is promoted; promoting the old one back undoes it."""
    with psycopg.connect(conninfo("ml_worker")) as conn:
        target, target_vector = conn.execute(
            "SELECT id::text, vector::text FROM catalog.songs"
            " WHERE vector IS NOT NULL AND id <> %s ORDER BY id LIMIT 1",
            (first_match(),),
        ).fetchone() or ("", "[]")
    description = np.array(embed_query(SWAP), dtype=np.float32)
    projection = np.outer(description, json.loads(target_vector)).astype(np.float32)
    file = f"test-{uuid4().hex}.npz"  # new each run: the API caches by file name
    models.BASELINE._replace(projection=projection).save(file)
    try:
        with promoted_version(file):
            assert first_match() == target
        assert first_match() != target
    finally:
        (models.MODEL_DIR / file).unlink()


@pytest.mark.usefixtures("seed_vectors_built")
def test_a_missing_model_file_falls_back_to_the_baseline_version() -> None:
    """Plain e5 at the baseline version's cutoff and weight, not the broken one's
    (cutoff 0.999 would leave no Match)."""
    with psycopg.connect(conninfo("ml_worker")) as conn:
        baseline = conn.execute(
            "SELECT cutoff, popularity_weight FROM catalog.model_versions WHERE id = 1"
        ).fetchone()
    assert baseline is not None
    with promoted_version(None, baseline):
        expected = search_swap()
    with promoted_version(f"missing-{uuid4().hex}.npz", (0.999, 0.0)):
        assert search_swap() == expected
    assert expected["count"] > 0
