"""Seam 1: search, called over the network like front's server code does.

Runs on the seed Catalog once the worker has built its vectors. Order and cutoff are
checked with Songs whose vectors are placed at a known Fit from the Description.
"""

import json
import math
import os
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import httpx
import numpy as np
import psycopg
import pytest

from timbre_back import benchmark, main
from timbre_back import model as models
from timbre_back.db import conninfo, vector_literal
from timbre_back.embed import embed_query
from timbre_back.model import BASELINE, Model

API_URL = os.environ.get("API_URL", "http://api:8000")
AUTH = {
    "Authorization": f"Bearer {os.environ['FRONT_TOKEN']}",
    "X-Visitor-IP": "192.0.2.1",  # TEST-NET-1: never a real visitor
}
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


pytestmark = pytest.mark.usefixtures("seed_vectors_built")


@pytest.mark.parametrize("description", SAMPLES)
def test_each_sample_description_has_matches(description: str) -> None:
    response = search(q=description)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert len(body["matches"]) == min(body["count"], 24)
    assert set(body["matches"][0]) == {"id", "title", "artist", "vote"}


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
    """Songs placed at a known Fit from DESCRIPTION, with no or the most listens.
    They have no labels, so their Fit is the cosine with the projected Description."""
    projected, _ = promoted_model().project(np.array([embed_query(DESCRIPTION)]))
    query = projected[0].astype(np.float64)
    with psycopg.connect(conninfo("ml_worker"), autocommit=True) as conn:
        model_row = conn.execute(
            "SELECT cutoff, popularity_weight FROM catalog.model_versions"
            " WHERE promoted"
        ).fetchone()
        assert model_row is not None
        cutoff, weight = float(model_row[0]), float(model_row[1])
        if weight == 0:
            pytest.skip("the evaluate job tuned the Popularity weight to 0")
        if 1 - 2 * weight <= cutoff:
            pytest.skip("far_popular would fall below the promoted cutoff")
        most = 10**12  # above any real listen count, so log1p ratio is exactly 1
        songs = {
            # name: (Fit, listens)
            "exact": (1.0, 0),
            "close_popular": (1 - weight / 2, most),  # + weight beats 1.0
            "far_popular": (1 - 2 * weight, most),  # + weight does not
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


# Search as it was before name matching: Matches by Fit alone, SEARCH_SQL's FIT_SQL.
FIT_RANKING_SQL = """
WITH m AS (
  SELECT cutoff, popularity_weight AS w FROM catalog.model_versions WHERE promoted
), c AS (
  SELECT id, listens, labels, 1 - (vector <=> %(vector)s::vector) AS cosine,
    %(labels)s::vector AS target_labels
  FROM catalog.songs WHERE vector IS NOT NULL
), f AS (
  SELECT id, listens, {fit} AS fit FROM c
)
SELECT coalesce(array_agg(id ORDER BY fit + w * coalesce(
  ln(1 + listens) / nullif(ln(1 + (SELECT max(listens) FROM catalog.songs)), 0), 0
) DESC, id), '{}')
FROM f, m WHERE fit > cutoff
""".replace("{fit}", main.FIT_SQL)


def promoted_model() -> Model:
    with psycopg.connect(conninfo("ml_worker")) as conn:
        (file,) = conn.execute(
            "SELECT file FROM catalog.model_versions WHERE promoted"
        ).fetchone() or (None,)
    return models.load(file)


def fit_ranking(description: str) -> list[UUID]:
    """Every Fit-based Match for the Description, in order, by the promoted model."""
    return ranking(promoted_model().search_params(embed_query(description)))


def ranking(params: dict[str, object]) -> list[UUID]:
    with psycopg.connect(conninfo("ml_worker")) as conn:
        row = conn.execute(FIT_RANKING_SQL, params).fetchone()
    assert row is not None
    return list(row[0])


def benchmark_descriptions() -> list[str]:
    entries = [e for f in benchmark.FILES for e in json.loads(f.read_text())]
    return [e["description"] for e in entries if e["description"]]


@pytest.mark.parametrize("description", SAMPLES + benchmark_descriptions())
def test_feel_descriptions_pick_up_no_name_matches(description: str) -> None:
    body = search(q=description, n=60).json()
    expected = fit_ranking(description)
    assert body["count"] == len(expected)
    assert [UUID(m["id"]) for m in body["matches"]] == expected[:60]


CAP = 60  # related Songs after name matches


def related_vector() -> list[float]:
    """The named Songs sound like a real Song, so its related Songs are their
    Matches. A Song vector, as Song-to-Song Fit runs high across the Catalog."""
    with psycopg.connect(conninfo("ml_worker")) as conn:
        (vector,) = conn.execute(
            "SELECT vector::text FROM catalog.songs WHERE vector IS NOT NULL"
            " ORDER BY id LIMIT 1"
        ).fetchone() or ("[]",)
    return list(json.loads(vector))


def related_ranking() -> list[UUID]:
    """The Songs related to the named Songs, in order: cosine with their vector."""
    return ranking(BASELINE.search_params(related_vector()))


@pytest.fixture
def named_songs() -> Iterator[list[UUID]]:
    """Songs by an accented, made-up artist, most listens first."""
    vector = vector_literal(related_vector())
    songs = [
        ("Pelagic Hum", 500),
        ("Quiet Lantern", 50),
        ("Vellichor Marmalade Harbor", 5),
    ]
    ids = [uuid4() for _ in songs]
    with psycopg.connect(conninfo("ml_worker"), autocommit=True) as conn:
        try:
            for id_, (title, listens) in zip(ids, songs, strict=True):
                conn.execute(
                    "INSERT INTO catalog.songs (id, title, artist, listens, vector)"
                    " VALUES (%s, %s, 'Zórblax Kwintét', %s, %s::vector)",
                    (id_, title, listens, vector),
                )
            yield ids
        finally:
            conn.execute("DELETE FROM catalog.songs WHERE id = ANY(%s)", (ids,))


@pytest.mark.parametrize(
    "q", ["Zórblax Kwintét", "zorblx kwintet"], ids=["exact", "typo-and-no-accents"]
)
def test_artist_songs_come_first_then_songs_like_them(
    named_songs: list[UUID], q: str
) -> None:
    ids = all_ids(q)
    related = [i for i in related_ranking() if i not in named_songs]
    assert related, "the related part should not be empty"
    assert ids == named_songs + related[:CAP]


def test_song_title_comes_first(named_songs: list[UUID]) -> None:
    ids = all_ids("vellichor marmalade harbour")
    related = [i for i in related_ranking() if i != named_songs[2]]
    assert ids == [named_songs[2], *related[:CAP]]


def test_part_of_an_artist_name_with_a_typo_matches() -> None:
    body = search(q="chilli peppers").json()
    assert body["matches"][0]["artist"] == "Red Hot Chili Peppers"  # in the seed


def test_name_matches_without_vectors_get_no_related_songs() -> None:
    """Fit against the typed name would be noise, so there is nothing to relate to."""
    id_ = uuid4()
    with psycopg.connect(conninfo("ml_worker"), autocommit=True) as conn:
        try:
            conn.execute(
                "INSERT INTO catalog.songs (id, title, artist)"
                " VALUES (%s, 'Untold Song', 'Quorvath Ensemble')",
                (id_,),
            )
            body = search(q="Quorvath Ensemble").json()
        finally:
            conn.execute("DELETE FROM catalog.songs WHERE id = %s", (id_,))
    assert body["count"] == 1
    assert [m["id"] for m in body["matches"]] == [str(id_)]


def all_ids(q: str) -> list[UUID]:
    """Every Match, page by page, checking that count and paging agree."""
    pages = [search(q=q, n=60, offset=o).json() for o in (0, 60, 120)]
    count = pages[0]["count"]
    assert {p["count"] for p in pages} == {count}
    ids = [UUID(m["id"]) for p in pages for m in p["matches"]]
    assert len(ids) == len(set(ids)) == count
    return ids


def test_pages_cross_from_name_matches_to_related_songs(
    named_songs: list[UUID],
) -> None:
    everything = search(q="Zórblax Kwintét", n=8).json()
    pages = [search(q="Zórblax Kwintét", n=2, offset=o).json() for o in (0, 2, 4, 6)]
    assert {p["count"] for p in pages} == {everything["count"]}
    assert [m for p in pages for m in p["matches"]] == everything["matches"]
    assert len({m["id"] for m in everything["matches"]}) == 8
    end = search(q="Zórblax Kwintét", n=10, offset=everything["count"]).json()
    assert end == {"count": everything["count"], "matches": []}


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


@pytest.mark.parametrize("ip", [None, "", "not-an-ip", "300.1.2.3"])
def test_search_needs_the_visitor_ip(ip: str | None) -> None:
    headers = {"Authorization": AUTH["Authorization"]}
    if ip is not None:
        headers["X-Visitor-IP"] = ip
    response = httpx.get(f"{API_URL}/search", params={"q": "rock"}, headers=headers)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer wrong"}], ids=["missing", "wrong"]
)
def test_search_needs_the_front_token(headers: dict[str, str]) -> None:
    response = httpx.get(f"{API_URL}/search", params={"q": "rock"}, headers=headers)
    assert response.status_code == 401
