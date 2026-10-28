"""Seam 3: database roles. Each test logs in as a real role and runs real SQL.

Seed rows (one Song, one vote) are committed for the module so that allowed reads
see real data, and removed afterwards. Each case runs in a rolled-back transaction.
"""

import os
from collections.abc import Iterator
from typing import LiteralString

import psycopg
import pytest
from psycopg import errors

DB_HOST = os.environ.get("DB_HOST", "db")
DENIED = "denied"

SEED_SONG: LiteralString = (
    "INSERT INTO catalog.songs"
    " VALUES ('00000000-0000-0000-0000-000000000099', 'seed', 'seed')"
    " ON CONFLICT DO NOTHING"
)
AS_VISITOR_SEED: LiteralString = "SELECT set_config('app.visitor_hash', 'seed', true)"
SEED_VOTE: LiteralString = (
    "INSERT INTO feedback.votes (visitor_hash, description, song_id, vote)"
    " VALUES ('seed', 'seed', '00000000-0000-0000-0000-000000000099', 'up')"
    " ON CONFLICT DO NOTHING"
)
INSERT_SONG: LiteralString = (
    "INSERT INTO catalog.songs"
    " VALUES ('00000000-0000-0000-0000-000000000001', 't', 'a')"
)
AS_VISITOR_H1: LiteralString = "SELECT set_config('app.visitor_hash', 'h1', true)"
INSERT_VOTE_H1: LiteralString = (
    "INSERT INTO feedback.votes (visitor_hash, description, song_id, vote)"
    " VALUES ('h1', 'calm piano', '00000000-0000-0000-0000-000000000001', 'up')"
)
INSERT_CACHE: LiteralString = (
    "INSERT INTO preview.spotify_cache (song_id, expires_at)"
    " VALUES ('00000000-0000-0000-0000-000000000001', now() + interval '24 hours')"
)

# (role, setup statements, statement under test, expected rowcount or DENIED)
CASES: list[tuple[str, tuple[LiteralString, ...], LiteralString, int | str]] = [
    # ml_worker: read and write catalog, read feedback, nothing in preview or jobs.
    ("ml_worker", (), INSERT_SONG, 1),
    ("ml_worker", (INSERT_SONG,), "SELECT * FROM catalog.songs", 2),  # seed + new
    (
        "ml_worker",
        (INSERT_SONG,),
        "UPDATE catalog.songs SET title = 'x'"
        " WHERE id = '00000000-0000-0000-0000-000000000001'",
        1,
    ),
    (
        "ml_worker",
        (INSERT_SONG,),
        "DELETE FROM catalog.songs WHERE id = '00000000-0000-0000-0000-000000000001'",
        1,
    ),
    ("ml_worker", (), "SELECT * FROM feedback.votes", 1),  # the seeded vote
    ("ml_worker", (), INSERT_VOTE_H1, DENIED),
    ("ml_worker", (), "UPDATE feedback.votes SET vote = 'down'", DENIED),
    ("ml_worker", (), "DELETE FROM feedback.votes", DENIED),
    ("ml_worker", (), "SELECT * FROM preview.spotify_cache", DENIED),
    ("ml_worker", (), INSERT_CACHE, DENIED),
    # api_search: read catalog, read and write only its own votes, nothing in preview.
    ("api_search", (), "SELECT * FROM catalog.songs", 1),  # the seeded Song
    ("api_search", (AS_VISITOR_SEED,), "SELECT * FROM feedback.votes", 1),  # own vote
    ("api_search", (), "SELECT * FROM feedback.votes", 0),  # no visitor set: none own
    ("api_search", (), INSERT_SONG, DENIED),
    ("api_search", (), "UPDATE catalog.songs SET title = 'x'", DENIED),
    ("api_search", (), "DELETE FROM catalog.songs", DENIED),
    ("api_search", (AS_VISITOR_H1,), INSERT_VOTE_H1, 1),
    (
        "api_search",
        (AS_VISITOR_H1, INSERT_VOTE_H1),
        INSERT_VOTE_H1 + " ON CONFLICT (visitor_hash, description, song_id)"
        " DO UPDATE SET vote = excluded.vote, updated_at = now()",
        1,
    ),
    (
        "api_search",
        (AS_VISITOR_H1, INSERT_VOTE_H1),
        "UPDATE feedback.votes SET vote = 'down'",
        1,
    ),
    ("api_search", (AS_VISITOR_H1, INSERT_VOTE_H1), "DELETE FROM feedback.votes", 1),
    ("api_search", (), INSERT_VOTE_H1, DENIED),  # no visitor set: not its own vote
    ("api_search", (), "SELECT * FROM preview.spotify_cache", DENIED),
    ("api_search", (), INSERT_CACHE, DENIED),
    # api_preview: the preview cache only.
    ("api_preview", (), INSERT_CACHE, 1),
    ("api_preview", (INSERT_CACHE,), "SELECT * FROM preview.spotify_cache", 1),
    (
        "api_preview",
        (INSERT_CACHE,),
        "UPDATE preview.spotify_cache SET spotify_track_id = 'x'",
        1,
    ),
    ("api_preview", (INSERT_CACHE,), "DELETE FROM preview.spotify_cache", 1),
    ("api_preview", (), "SELECT * FROM catalog.songs", DENIED),
    ("api_preview", (), "SELECT * FROM feedback.votes", DENIED),
    ("api_preview", (), INSERT_SONG, DENIED),
    ("api_preview", (), "SELECT '[1,2,3]'::extensions.vector", DENIED),
    # Nobody can create objects or touch the jobs schema yet.
    ("ml_worker", (), "CREATE TABLE public.x (i int)", DENIED),
    ("api_search", (), "CREATE TABLE jobs.x (i int)", DENIED),
    ("api_preview", (), "CREATE TABLE preview.x (i int)", DENIED),
]


async def connect(role: str, password: str | None = None) -> psycopg.AsyncConnection:
    return await psycopg.AsyncConnection.connect(
        host=DB_HOST,
        dbname="timbre",
        user=role,
        password=password or os.environ[f"{role.upper()}_PASSWORD"],
    )


def connect_sync(role: str) -> psycopg.Connection:
    password = os.environ[f"{role.upper()}_PASSWORD"]
    return psycopg.connect(host=DB_HOST, dbname="timbre", user=role, password=password)


@pytest.fixture(scope="module", autouse=True)
def seed_rows() -> Iterator[None]:
    # Seeded by the roles themselves: the tests have no superuser password.
    with connect_sync("ml_worker") as conn:
        conn.execute(SEED_SONG)
    with connect_sync("api_search") as conn:
        conn.execute(AS_VISITOR_SEED)
        conn.execute(SEED_VOTE)
    yield
    with connect_sync("api_search") as conn:
        conn.execute(AS_VISITOR_SEED)
        conn.execute("DELETE FROM feedback.votes")
    with connect_sync("ml_worker") as conn:
        conn.execute(
            "DELETE FROM catalog.songs"
            " WHERE id = '00000000-0000-0000-0000-000000000099'"
        )


@pytest.mark.anyio
@pytest.mark.parametrize(("role", "setup", "sql", "expected"), CASES)
async def test_role_can_do_exactly_its_operations(
    role: str, setup: tuple[LiteralString, ...], sql: LiteralString, expected: int | str
) -> None:
    async with await connect(role) as conn, conn.transaction(force_rollback=True):
        for statement in setup:
            await conn.execute(statement)
        if expected == DENIED:
            with pytest.raises(errors.InsufficientPrivilege):
                await conn.execute(sql)
        else:
            assert (await conn.execute(sql)).rowcount == expected


@pytest.mark.anyio
async def test_api_search_cannot_see_or_change_another_visitors_votes() -> None:
    async with (
        await connect("api_search") as conn,
        conn.transaction(force_rollback=True),
    ):
        await conn.execute(AS_VISITOR_H1)
        await conn.execute(INSERT_VOTE_H1)
        await conn.execute("SELECT set_config('app.visitor_hash', 'h2', true)")
        assert (await conn.execute("SELECT * FROM feedback.votes")).rowcount == 0
        assert (
            await conn.execute("UPDATE feedback.votes SET vote = 'down'")
        ).rowcount == 0
        assert (await conn.execute("DELETE FROM feedback.votes")).rowcount == 0


@pytest.mark.anyio
@pytest.mark.parametrize("role", ["ml_worker", "api_search"])
async def test_role_can_use_pgvector_type_and_operators(role: str) -> None:
    async with await connect(role) as conn:
        cur = await conn.execute("SELECT '[1,2,3]'::vector <=> '[2,4,6]'::vector")
        assert await cur.fetchone() == (0.0,)  # same direction: cosine distance 0


@pytest.mark.anyio
@pytest.mark.parametrize("role", ["ml_worker", "api_search", "api_preview"])
async def test_role_login_needs_its_password(role: str) -> None:
    with pytest.raises(
        psycopg.OperationalError, match="password authentication failed"
    ):
        await connect(role, password="wrong-password")
