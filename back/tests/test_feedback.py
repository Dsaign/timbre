"""Seam 1: Feedback, called over the network like front's server code does.

Each test votes as its own visitor IP (TEST-NET), and its votes are removed afterwards.
"""

import hashlib
import hmac
import os
import unicodedata
from collections.abc import Iterator
from ipaddress import ip_address
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from timbre_back.db import conninfo
from timbre_back.feedback import forget_old_hashes, normalize

API_URL = os.environ.get("API_URL", "http://api:8000")
TOKEN = {"Authorization": f"Bearer {os.environ['FRONT_TOKEN']}"}
SALT = os.environ["IP_HASH_SALT"].encode()
DESCRIPTION = "músicas alegres e dançantes para uma festa"

pytestmark = pytest.mark.usefixtures("seed_vectors_built")


def hash_of(ip: str) -> str:
    return hmac.new(SALT, ip_address(ip).packed, hashlib.sha256).hexdigest()


def votes_of(visitor_hash: str) -> list[tuple[str, UUID, str]]:
    with psycopg.connect(conninfo("api_search")) as conn:
        conn.execute("SELECT set_config('app.visitor_hash', %s, true)", (visitor_hash,))
        return conn.execute(
            "SELECT description, song_id, vote FROM feedback.votes"
        ).fetchall()


@pytest.fixture
def ip() -> Iterator[str]:
    """A fresh visitor; its votes are deleted afterwards."""
    ip = f"198.51.100.{uuid4().int % 254 + 1}"
    yield ip
    with psycopg.connect(conninfo("api_search")) as conn:
        conn.execute("SELECT set_config('app.visitor_hash', %s, true)", (hash_of(ip),))
        conn.execute("DELETE FROM feedback.votes")


def search(ip: str, q: str = DESCRIPTION) -> list[dict[str, Any]]:
    response = httpx.get(
        f"{API_URL}/search",
        params={"q": q},
        headers={**TOKEN, "X-Visitor-IP": ip},
        timeout=30,
    )
    assert response.status_code == 200
    matches: list[dict[str, Any]] = response.json()["matches"]
    return matches


def vote(
    ip: str, song_id: UUID | str, vote: str, description: str = DESCRIPTION
) -> httpx.Response:
    return httpx.post(
        f"{API_URL}/feedback",
        json={"description": description, "song_id": str(song_id), "vote": vote},
        headers={**TOKEN, "X-Visitor-IP": ip},
        timeout=30,
    )


def vote_on(ip: str, song_id: str, q: str = DESCRIPTION) -> str | None:
    """The visitor's vote on that Match, as the search returns it."""
    current: str | None = next(m["vote"] for m in search(ip, q) if m["id"] == song_id)
    return current


def test_vote_is_stored_switched_and_withdrawn(ip: str) -> None:
    song = search(ip)[0]["id"]
    assert vote_on(ip, song) is None

    assert vote(ip, song, "up").status_code == 204
    assert vote_on(ip, song) == "up"
    assert vote(ip, song, "up").status_code == 204  # the same vote again is one vote
    assert votes_of(hash_of(ip)) == [(DESCRIPTION, UUID(song), "up")]

    assert vote(ip, song, "down").status_code == 204
    assert vote_on(ip, song) == "down"
    assert votes_of(hash_of(ip)) == [(DESCRIPTION, UUID(song), "down")]

    assert vote(ip, song, "none").status_code == 204
    assert vote_on(ip, song) is None
    assert votes_of(hash_of(ip)) == []
    assert vote(ip, song, "none").status_code == 204  # withdrawing nothing is fine


def test_votes_belong_to_one_visitor(ip: str) -> None:
    song = search(ip)[0]["id"]
    assert vote(ip, song, "up").status_code == 204
    other = "203.0.113.7"
    assert vote_on(other, song) is None
    assert vote(other, song, "none").status_code == 204  # can't withdraw ip's vote
    assert vote_on(ip, song) == "up"


def test_description_is_normalized(ip: str) -> None:
    song = search(ip)[0]["id"]
    # NFD, extra whitespace and capitals: the same Description once normalized.
    messy = unicodedata.normalize("NFD", f" {DESCRIPTION.upper()}\t").replace(" ", "  ")
    assert vote(ip, song, "up", description=messy).status_code == 204
    assert votes_of(hash_of(ip)) == [(DESCRIPTION, UUID(song), "up")]
    # The search normalizes too (whitespace only here, so the Matches stay the same).
    assert vote_on(ip, song, q=DESCRIPTION.replace(" ", "  ")) == "up"


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("Rock  Pesado", "rock pesado"),
        ("\n\tviolão calmo  ", "violão calmo"),
        ("Café", "café"),  # e + combining acute → precomposed é
    ],
)
def test_normalize(raw: str, normalized: str) -> None:
    assert normalize(raw) == normalized


def test_the_stored_hash_is_salted_not_the_ip(ip: str) -> None:
    song = search(ip)[0]["id"]
    assert vote(ip, song, "up").status_code == 204
    assert len(votes_of(hash_of(ip))) == 1
    unsalted = hashlib.sha256(ip_address(ip).packed).hexdigest()
    assert votes_of(unsalted) == votes_of(ip) == []
    # The IPv4-mapped IPv6 form is the same visitor.
    assert vote_on(f"::ffff:{ip}", song) == "up"


def test_a_song_outside_the_catalog_is_not_found(ip: str) -> None:
    assert vote(ip, uuid4(), "up").status_code == 404
    assert votes_of(hash_of(ip)) == []


@pytest.mark.parametrize(
    "body",
    [
        {"description": "", "song_id": str(uuid4()), "vote": "up"},
        {"description": "   ", "song_id": str(uuid4()), "vote": "up"},
        {"description": "a" * 301, "song_id": str(uuid4()), "vote": "up"},
        {"description": "rock", "song_id": "not-a-uuid", "vote": "up"},
        {"description": "rock", "song_id": str(uuid4()), "vote": "meh"},
        {"description": "rock", "song_id": str(uuid4())},
        {"description": "rock", "song_id": str(uuid4()), "vote": "up", "x": 1},
    ],
    ids=["empty", "blank", "too-long", "not-uuid", "bad-vote", "no-vote", "extra"],
)
def test_invalid_feedback_is_rejected(body: dict[str, Any]) -> None:
    response = httpx.post(
        f"{API_URL}/feedback", json=body, headers={**TOKEN, "X-Visitor-IP": "192.0.2.1"}
    )
    assert response.status_code == 422
    assert "Traceback" not in response.text


@pytest.mark.parametrize(
    "headers",
    [TOKEN, {**TOKEN, "X-Visitor-IP": "not-an-ip"}, {"X-Visitor-IP": "192.0.2.1"}],
    ids=["no-ip", "bad-ip", "no-token"],
)
def test_feedback_needs_the_token_and_a_visitor_ip(headers: dict[str, str]) -> None:
    body = {"description": "rock", "song_id": str(uuid4()), "vote": "up"}
    response = httpx.post(f"{API_URL}/feedback", json=body, headers=headers)
    assert response.status_code == (401 if "Authorization" not in headers else 422)


@pytest.mark.anyio
async def test_hashes_older_than_7_days_are_cleared_and_the_vote_kept() -> None:
    # shortcut: the anonymized row can't be deleted by any test role, so each run leaves
    # one vote for a Song that is not in the Catalog; CI starts from an empty database.
    old, fresh, song = f"test-old-{uuid4()}", f"test-fresh-{uuid4()}", uuid4()
    description = f"test hash expiry {song}"
    with psycopg.connect(conninfo("api_search"), autocommit=True) as conn:
        for visitor_hash, age in [(old, "8 days"), (fresh, "6 days")]:
            with conn.transaction():
                conn.execute(
                    "SELECT set_config('app.visitor_hash', %s, true)", (visitor_hash,)
                )
                conn.execute(
                    "INSERT INTO feedback.votes"
                    " (visitor_hash, description, song_id, vote, created_at)"
                    " VALUES (%s, %s, %s, 'up', now() - %s::interval)",
                    (visitor_hash, description, song, age),
                )
    try:
        async with AsyncConnectionPool(
            conninfo("api_search"), open=False, connection_class=psycopg.AsyncConnection
        ) as pool:
            assert await forget_old_hashes(pool) >= 1
        with psycopg.connect(conninfo("ml_worker")) as conn:
            rows = conn.execute(
                "SELECT visitor_hash, vote FROM feedback.votes WHERE description = %s"
                " ORDER BY visitor_hash",
                (description,),
            ).fetchall()
        assert rows == [(fresh, "up"), (None, "up")]
        assert votes_of(old) == []  # the old visitor no longer owns it
    finally:
        with psycopg.connect(conninfo("api_search")) as conn:
            conn.execute("SELECT set_config('app.visitor_hash', %s, true)", (fresh,))
            conn.execute("DELETE FROM feedback.votes")
