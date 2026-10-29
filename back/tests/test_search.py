"""Seam 1: search, called over the network like front's server code does.

Runs on the seed Catalog once the worker has built its vectors. Order and cutoff are
checked with Songs whose vectors are placed at a known Fit from the Description.
"""

import math
import os
import time
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import httpx
import numpy as np
import psycopg
import pytest

from timbre_back.db import conninfo, vector_literal
from timbre_back.embed import embed_query

API_URL = os.environ.get("API_URL", "http://api:8000")
AUTH = {"Authorization": f"Bearer {os.environ['FRONT_TOKEN']}"}
SEED_SIZE = 200
NONSENSE = "xkqzv wplmr tjhgf"
SAMPLES = [
    "violão calmo para estudar",
    "guitarra suja e voz rouca, clima de estrada à noite",
    "something dark and electronic to focus",
    "músicas alegres e dançantes para uma festa",
    "sad piano ballad, slow and quiet",
    "rock pesado e agressivo com bateria forte",
]


def search(**params: Any) -> httpx.Response:
    return httpx.get(f"{API_URL}/search", params=params, headers=AUTH, timeout=30)


@pytest.fixture(scope="module", autouse=True)
def seed_vectors_built() -> None:
    """The worker builds the seed vectors after start; wait for it."""
    deadline = time.monotonic() + 300
    with psycopg.connect(conninfo("ml_worker")) as conn:
        while time.monotonic() < deadline:
            row = conn.execute(
                "SELECT count(*) FILTER (WHERE vector IS NOT NULL),"
                " (SELECT count(*) FROM jobs.queue WHERE status = 'queued')"
                " FROM catalog.songs"
            ).fetchone()
            conn.rollback()
            if row is not None and row[0] >= SEED_SIZE and row[1] == 0:
                return
            time.sleep(1)
    raise TimeoutError("seed Catalog vectors were not built in time")


@pytest.mark.parametrize("description", SAMPLES)
def test_each_sample_description_has_matches(description: str) -> None:
    response = search(q=description)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert len(body["matches"]) == min(body["count"], 24)
    assert set(body["matches"][0]) == {"id", "title", "artist"}


def test_nonsense_has_no_matches() -> None:
    response = search(q=NONSENSE)
    assert response.status_code == 200
    assert response.json() == {"count": 0, "matches": []}


def test_pages_follow_one_order() -> None:
    everything = search(q=SAMPLES[2], n=20).json()
    assert everything["count"] >= 20
    first = search(q=SAMPLES[2], n=10, offset=0).json()
    second = search(q=SAMPLES[2], n=10, offset=10).json()
    assert first["count"] == second["count"] == everything["count"]
    assert first["matches"] + second["matches"] == everything["matches"]
    beyond = search(q=SAMPLES[2], n=10, offset=everything["count"]).json()
    assert beyond == {"count": everything["count"], "matches": []}


DESCRIPTION = "ordem de teste com popularidade"


def at_fit(query: np.ndarray, fit: float, seed: int) -> list[float]:
    """A unit vector whose cosine similarity with `query` is exactly `fit`."""
    other = np.random.default_rng(seed).standard_normal(query.shape)
    other -= other.dot(query) * query
    other /= np.linalg.norm(other)
    return list(fit * query + math.sqrt(1 - fit**2) * other)


@pytest.fixture
def placed_songs() -> Iterator[dict[str, UUID]]:
    """Songs placed at a known Fit from DESCRIPTION, with no or the most listens."""
    query = np.array(embed_query(DESCRIPTION))
    with psycopg.connect(conninfo("ml_worker"), autocommit=True) as conn:
        cutoff_row = conn.execute(
            "SELECT cutoff FROM catalog.model_versions WHERE promoted"
        ).fetchone()
        assert cutoff_row is not None
        cutoff = float(cutoff_row[0])
        most = 10**12  # above any real listen count, so log1p ratio is exactly 1
        songs = {
            # name: (Fit, listens)
            "exact": (1.0, 0),
            "close_popular": (0.995, most),  # 0.995 + 0.02 beats 1.0
            "far_popular": (0.95, most),  # 0.95 + 0.02 does not
            "below_cutoff_popular": (cutoff - 0.01, most),  # never a Match
        }
        ids = {name: uuid4() for name in songs}
        try:
            for i, (name, (fit, listens)) in enumerate(songs.items()):
                conn.execute(
                    "INSERT INTO catalog.songs (id, title, artist, listens, vector)"
                    " VALUES (%s, %s, 'test', %s, %s::vector)",
                    (ids[name], name, listens, vector_literal(at_fit(query, fit, i))),
                )
            yield ids
        finally:
            conn.execute(
                "DELETE FROM catalog.songs WHERE id = ANY(%s)", (list(ids.values()),)
            )


def test_order_is_fit_plus_a_small_popularity_weight(
    placed_songs: dict[str, UUID],
) -> None:
    body = search(q=DESCRIPTION, n=60).json()
    ids = [UUID(m["id"]) for m in body["matches"]]
    assert ids[:3] == [
        placed_songs["close_popular"],
        placed_songs["exact"],
        placed_songs["far_popular"],
    ]
    assert body["count"] == len(ids)  # every Match is on this page, so absence counts
    assert placed_songs["below_cutoff_popular"] not in ids


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"q": ""},
        {"q": "   "},
        {"q": "a" * 301},
        {"q": "rock", "n": 0},
        {"q": "rock", "n": 61},
        {"q": "rock", "n": "many"},
        {"q": "rock", "offset": -1},
        {"q": "rock", "offset": 10_001},
        {"q": "rock", "page": 2},
    ],
    ids=[
        "missing",
        "empty",
        "blank",
        "too-long",
        "n-zero",
        "n-over-60",
        "n-not-int",
        "negative-offset",
        "huge-offset",
        "unknown-param",
    ],
)
def test_invalid_input_is_rejected(params: dict[str, Any]) -> None:
    response = search(**params)
    assert response.status_code == 422
    assert "Traceback" not in response.text


def test_description_is_trimmed_before_its_length_is_checked() -> None:
    response = search(q="  " + "a" * 300 + "  ", n=60)
    assert response.status_code == 200


def test_n_defaults_to_24_and_is_capped_at_60() -> None:
    assert len(search(q=SAMPLES[2]).json()["matches"]) == 24
    assert len(search(q=SAMPLES[2], n=60).json()["matches"]) == 60


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer wrong"}], ids=["missing", "wrong"]
)
def test_search_needs_the_front_token(headers: dict[str, str]) -> None:
    response = httpx.get(f"{API_URL}/search", params={"q": "rock"}, headers=headers)
    assert response.status_code == 401
