"""Seam 1: search, called over the network like front's server code does.

Runs on the seed Catalog once the worker has built its vectors. Order and cutoff are
checked with Songs whose vectors are placed at a known Fit from the Description.
"""

import json
import math
import os
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID, uuid4

import httpx
import numpy as np
import psycopg
import pytest

from timbre_back import benchmark
from timbre_back import model as models
from timbre_back.db import conninfo, vector_literal
from timbre_back.embed import embed_query
from timbre_back.feedback import normalize
from timbre_back.model import Model
from timbre_back.search import FIT_SQL, MATCHES_SQL, POPULARITY

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


# Search by Fit alone (the seed Catalog has no tags), with SEARCH_SQL's FIT_SQL.
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
SELECT coalesce(array_agg(id ORDER BY fit + w * {popularity} DESC, id), '{}')
FROM f, m WHERE fit > cutoff
""".replace("{fit}", FIT_SQL).replace("{popularity}", POPULARITY)


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


ARTIST_SEARCHES = {"linkin park"}  # Benchmark Descriptions that name an artist


def benchmark_descriptions() -> list[str]:
    entries = [e for f in benchmark.FILES for e in json.loads(f.read_text())]
    return [
        e["description"]
        for e in entries
        if e["description"] and e["description"] not in ARTIST_SEARCHES
    ]


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


def related_ranking(q: str) -> list[UUID]:
    """The Songs related to the named Songs, in order: Fit with the Description averaged
    with their vector, so the Description's own meaning still counts."""
    params = promoted_model().search_params(embed_query(q))
    description = json.loads(str(params["vector"]))
    params["vector"] = vector_literal(
        ((np.array(description) + np.array(related_vector())) / 2).tolist()
    )
    return ranking(params)


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
    related = [i for i in related_ranking(q) if i not in named_songs]
    assert related, "the related part should not be empty"
    assert ids == named_songs + related[:CAP]


def test_song_title_comes_first(named_songs: list[UUID]) -> None:
    ids = all_ids("vellichor marmalade harbour")
    related = [
        i for i in related_ranking("vellichor marmalade harbour") if i != named_songs[2]
    ]
    assert ids == [named_songs[2], *related[:CAP]]


NAMED_SQL = "{matches} SELECT id FROM matches WHERE part = 0 ORDER BY id".replace(
    "{matches}", MATCHES_SQL
)


def named(q: str) -> list[UUID]:
    """The Songs the Description names (the name step alone), by the real search."""
    params = promoted_model().search_params(embed_query(q))
    with psycopg.connect(conninfo("ml_worker")) as conn:
        rows = conn.execute(
            NAMED_SQL,
            {**params, "description": normalize(q), "cutoff": 1, "weight": 0},
        ).fetchall()
    return [row[0] for row in rows]


@pytest.fixture
def name_clashes() -> Iterator[dict[str, UUID]]:
    """Names one word away from a mood or genre: "rock" in an artist's name, a guest
    called "Love", a one-word title "Love"."""
    songs = {
        "rocky": ("Long Live", "Q$Q Rocky"),
        "guest": ("Somebody Else", "Marlo Vint ft. Drew Love"),
        "title": ("Love", "Quillon Barr"),
    }
    ids = {key: uuid4() for key in songs}
    with psycopg.connect(conninfo("ml_worker"), autocommit=True) as conn:
        try:
            for key, (title, artist) in songs.items():
                conn.execute(
                    "INSERT INTO catalog.songs (id, title, artist) VALUES (%s, %s, %s)",
                    (ids[key], title, artist),
                )
            yield ids
        finally:
            conn.execute(
                "DELETE FROM catalog.songs WHERE id = ANY(%s)", (list(ids.values()),)
            )


@pytest.mark.parametrize("q", ["rock", "love", "drew love"])
def test_one_word_of_a_name_names_nothing(
    name_clashes: dict[str, UUID], q: str
) -> None:
    """Whole names only: "rock" is not "Q$Q Rocky", "love" is not the title "Love" or
    the guest Drew Love, and guests never count."""
    assert not set(named(q)) & set(name_clashes.values())


@pytest.mark.parametrize(
    ("q", "key"), [("q$q rocky", "rocky"), ("marlo vint", "guest")]
)
def test_a_whole_main_artist_name_names_its_songs(
    name_clashes: dict[str, UUID], q: str, key: str
) -> None:
    assert name_clashes[key] in named(q)


@contextmanager
def tagged(q: str, songs: dict[str, list[str]]) -> Generator[dict[str, UUID]]:
    """Songs with the given tags (most-voted first) and Fit 0 with the Description, so
    only their tags can make them Matches. The seed Catalog has no tags."""
    projected, _ = promoted_model().project(np.array([embed_query(q)]))
    query = projected[0].astype(np.float64)
    ids = {name: uuid4() for name in songs}
    with psycopg.connect(conninfo("ml_worker"), autocommit=True) as conn:
        try:
            for n, (name, tags) in enumerate(songs.items()):
                conn.execute(
                    "INSERT INTO catalog.songs (id, title, artist, tags, vector)"
                    " VALUES (%s, %s, 'Tag Test', %s, %s::vector)",
                    (ids[name], name, tags, vector_literal(at_fit(query, 0.0, n))),
                )
            yield ids
        finally:
            conn.execute(
                "DELETE FROM catalog.songs WHERE id = ANY(%s)", (list(ids.values()),)
            )


def test_a_tag_match_ranks_first_even_below_the_cutoff() -> None:
    """A tag counts as a phrase of the Description, whatever its punctuation."""
    with tagged("vorpal wave", {"tagged": ["Vorpal-Wave", "pop"]}) as ids:
        body = search(q="vorpal wave").json()
    assert body["matches"][0]["id"] == str(ids["tagged"])


def test_more_votes_for_the_tag_rank_higher() -> None:
    songs = {"first": ["zylofonk", "pop"], "third": ["pop", "rock", "zylofonk"]}
    with tagged("zylofonk", songs) as ids:
        body = search(q="zylofonk").json()
    assert [m["id"] for m in body["matches"][:2]] == [
        str(ids["first"]),
        str(ids["third"]),
    ]


def test_a_tag_only_match_needs_one_of_the_3_most_voted_tags() -> None:
    songs = {"strong": ["pop", "rock", "zylofonk"], "weak": ["a", "b", "c", "zylofonk"]}
    with tagged("zylofonk", songs) as ids:
        found = {m["id"] for m in search(q="zylofonk", n=60).json()["matches"]}
    assert str(ids["strong"]) in found
    assert str(ids["weak"]) not in found


def test_a_one_word_tag_does_not_take_over_a_longer_description() -> None:
    """The tag ranking weighs by the share of the Description the tag covers (1 of 6
    words here), so the model's best Matches stay first."""
    q = "sad piano ballad, slow and quiet"
    expected = fit_ranking(q)[:5]
    assert expected, "the Description should have Fit Matches"
    with tagged(q, {"piano": ["piano"]}) as ids:
        body = search(q=q, n=60).json()
    found = [UUID(m["id"]) for m in body["matches"]]
    assert found[: len(expected)] == expected
    assert ids["piano"] in found  # still a Match, by its tag


def song_tags(conn: psycopg.Connection, song: UUID) -> list[tuple[int, str]]:
    return conn.execute(
        "SELECT vote_rank, key FROM catalog.song_tags WHERE song_id = %s"
        " ORDER BY vote_rank",
        (song,),
    ).fetchall()


def test_the_tag_table_follows_each_songs_tags() -> None:
    """Search looks tags up in catalog.song_tags; a trigger keeps it from songs.tags."""
    with tagged("zylofonk", {"song": ["Zylo-Fonk", "pop"]}) as ids:
        song = ids["song"]
        with psycopg.connect(conninfo("ml_worker"), autocommit=True) as conn:
            assert song_tags(conn, song) == [(1, "zylo fonk"), (2, "pop")]
            assert search(q="zylo fonk").json()["matches"][0]["id"] == str(song)

            conn.execute(
                "UPDATE catalog.songs SET tags = %s WHERE id = %s", (["vorpal"], song)
            )
            assert song_tags(conn, song) == [(1, "vorpal")]
            found = {m["id"] for m in search(q="zylo fonk", n=60).json()["matches"]}
            assert str(song) not in found

            conn.execute("UPDATE catalog.songs SET tags = NULL WHERE id = %s", (song,))
            assert song_tags(conn, song) == []
            conn.execute(
                "UPDATE catalog.songs SET tags = %s WHERE id = %s", (["pop"], song)
            )
    with psycopg.connect(conninfo("ml_worker")) as conn:
        assert song_tags(conn, song) == []  # deleted with its Song


PLAN_SQL = "EXPLAIN {matches} SELECT * FROM matches".replace("{matches}", MATCHES_SQL)


def test_search_reads_tags_and_main_artists_through_indexes() -> None:
    """At 50k Songs a scan per search is too slow (ticket 18): the plan uses both."""
    with psycopg.connect(conninfo("api_search")) as conn:
        conn.execute("SET enable_seqscan = off")  # the seed Catalog is small
        params = {
            **promoted_model().search_params(embed_query("q$q rocky")),
            "description": normalize("q$q rocky"),
            "cutoff": 0.9,
            "weight": 0.05,
        }
        plan = "\n".join(line for (line,) in conn.execute(PLAN_SQL, params).fetchall())
    assert "song_tags_key" in plan
    assert "songs_main_artist_trgm" in plan


def test_love_returns_its_tagged_songs() -> None:
    songs = {"love": ["love", "pop"], "romantic love": ["pop", "romantic", "love"]}
    with tagged("love", songs) as ids:
        body = search(q="love").json()
    assert {m["id"] for m in body["matches"][:2]} == {str(i) for i in ids.values()}


def test_name_matches_without_vectors_get_no_related_songs() -> None:
    """With nothing to average the name with, related Songs follow the Description
    alone, and a made-up name means nothing."""
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
