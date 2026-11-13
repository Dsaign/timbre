"""Seam 2: the Catalog import job on the real database and worker, with the
MetaBrainz APIs replaced by recorded responses.

tests/catalog_import/*.json are real ListenBrainz and AcousticBrainz response bodies,
recorded on 2026-11-12 for the sitewide top 3 artists (Radiohead, Linkin Park, Daft
Punk), trimmed to a few recordings and to the fields the import reads. Their artist and
recording IDs are replaced with 00000000-0000-0000-0012-…, so the tests never touch
real Catalog rows. Of Radiohead's four recordings, "Reckoner (live)" has no ISRC and
"Lucky" has no AcousticBrainz data. tests/catalog_import/seed.json is hand-written: it
stands in for the seed Catalog, with those two and one Song MusicBrainz doesn't know.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, LiteralString

import httpx
import psycopg
import pytest

from timbre_back import catalog_import, metabrainz, worker
from timbre_back.catalog import upsert_songs
from timbre_back.db import conninfo

RECORDED = Path(__file__).with_name("catalog_import")
TEST_IDS = "00000000-0000-0000-0012-%"
KEPT = {
    "Karma Police",
    "Paranoid Android",
    "In the End",
    "Numb",
    "Harder, Better, Faster, Stronger",
    "Digital Love",
}
RADIOHEAD = {"Karma Police", "Paranoid Android"}
LINKIN_PARK_FIRST_RECORDING = "00000000-0000-0000-0012-000000000005"
SEED = RECORDED / "seed.json"
LUCKY = "00000000-0000-0000-0012-000000000004"

pytestmark = pytest.mark.usefixtures("seed_vectors_built")


def recorded(name: str) -> Any:
    return json.loads((RECORDED / f"{name}.json").read_text())


@dataclass
class FakeMetaBrainz:
    """Replays recorded responses; can answer 503 or 404, die, or list no artists."""

    unavailable_once: bool = False
    no_artists: bool = False
    down: bool = False  # every request answers 503
    not_found: str | None = None  # a request whose URL contains this answers 404
    die_on: str | None = None  # a request whose URL contains this raises
    requests: list[httpx.Request] = field(default_factory=list)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.die_on and self.die_on in str(request.url):
            raise RuntimeError("worker killed")
        if self.not_found and self.not_found in str(request.url):
            return httpx.Response(404)
        if self.down:
            return httpx.Response(503)
        if self.unavailable_once:
            self.unavailable_once = False
            return httpx.Response(503)
        path, params = request.url.path, request.url.params
        if path == "/1/stats/sitewide/artists":
            # The stats stop at 1,000 artists; the next page is empty.
            first = params["offset"] == "0" and not self.no_artists
            body = recorded("sitewide_artists" if first else "sitewide_artists_end")
        elif path.startswith("/1/popularity/top-recordings-for-artist/"):
            assert request.headers["Authorization"] == "Token test-token"
            body = recorded(f"top_recordings_{path[-2:]}")
        elif path == "/api/v1/high-level":
            ids = params["recording_ids"].split(";")
            body = {k: v for k, v in recorded("high_level").items() if k in ids}
        elif path == "/1/metadata/recording/":
            ids = params["recording_mbids"].split(",")
            body = {k: v for k, v in recorded("metadata").items() if k in ids}
        else:
            raise AssertionError(f"unexpected request {request.url}")
        return httpx.Response(200, json=body)

    def artists_asked(self) -> list[str]:
        """The test artists (a1, a2, a3) whose top recordings were requested."""
        return [r.url.path[-2:] for r in self.requests if "/popularity/" in r.url.path]


async def delete_test_songs(conn: psycopg.AsyncConnection) -> None:
    await conn.execute("DELETE FROM catalog.songs WHERE id::text LIKE %s", (TEST_IDS,))


async def one(conn: psycopg.AsyncConnection, query: LiteralString, *params: Any) -> Any:
    """The single row the query returns."""
    cur = await conn.execute(query, params)
    row = await cur.fetchone()
    assert row is not None
    return row


async def set_target(
    conn: psycopg.AsyncConnection, monkeypatch: pytest.MonkeyPatch, new_songs: int
) -> None:
    (size,) = await one(conn, "SELECT count(*) FROM catalog.songs")
    monkeypatch.setattr(catalog_import, "TARGET", size + new_songs)


@pytest.fixture
async def committed(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[psycopg.AsyncConnection]:
    """Commits like the job does; may write Songs but not catalog.import_artists."""
    monkeypatch.setenv("METABRAINZ_CONTACT", "tests@example.org")
    monkeypatch.setenv("LISTENBRAINZ_TOKEN", "test-token")
    # The test seed, so tagging never touches the real seed Songs.
    monkeypatch.setattr(catalog_import, "SEED", SEED)
    monkeypatch.setattr(metabrainz, "PAUSE", 0)
    async with await psycopg.AsyncConnection.connect(
        conninfo("ml_worker"), autocommit=True
    ) as conn:
        await delete_test_songs(conn)
        await set_target(conn, monkeypatch, 100)
        try:
            yield conn
        finally:
            await delete_test_songs(conn)


@pytest.fixture
async def conn(
    committed: psycopg.AsyncConnection,
) -> AsyncIterator[psycopg.AsyncConnection]:
    """Every write rolled back: ml_worker may not delete from catalog.import_artists."""
    async with committed.transaction(force_rollback=True):
        yield committed


async def run_import(conn: psycopg.AsyncConnection, fake: FakeMetaBrainz) -> None:
    async with metabrainz.client(httpx.MockTransport(fake)) as http:
        await catalog_import.import_catalog(conn, http)


async def imported_titles(conn: psycopg.AsyncConnection) -> list[str]:
    cur = await conn.execute(
        "SELECT title FROM catalog.songs WHERE id::text LIKE %s ORDER BY title",
        (TEST_IDS,),
    )
    return [title for (title,) in await cur.fetchall()]


async def load_test_seed(conn: psycopg.AsyncConnection) -> None:
    """Like the seed loader: Songs without tags (NULL)."""
    await upsert_songs(conn, recorded("seed"))


async def tags_of(conn: psycopg.AsyncConnection, mbid: str) -> list[str] | None:
    (tags,) = await one(conn, "SELECT tags FROM catalog.songs WHERE id = %s", mbid)
    return tags  # type: ignore[no-any-return]


async def finished_artists(conn: psycopg.AsyncConnection) -> int:
    (finished,) = await one(
        conn,
        "SELECT count(*) FROM catalog.import_artists WHERE artist_mbid::text LIKE %s",
        TEST_IDS,
    )
    return int(finished)


@pytest.mark.anyio
async def test_keeps_only_songs_with_an_isrc_and_acousticbrainz_data(
    conn: psycopg.AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(metabrainz, "ACOUSTICBRAINZ_BATCH", 3)
    fake = FakeMetaBrainz(unavailable_once=True)
    await run_import(conn, fake)

    assert await imported_titles(conn) == sorted(KEPT)
    artist, isrc, listens, tags, instruments, mood_sad = await one(
        conn,
        "SELECT artist, isrc, listens, tags, instruments, acousticbrainz -> 'mood_sad'"
        " FROM catalog.songs WHERE title = 'Karma Police' AND id::text LIKE %s",
        TEST_IDS,
    )
    assert (artist, isrc, listens) == ("Radiohead", "GBAYE9701368", 3890683)
    assert tags == ["alternative rock", "rock", "alternative and punk"]
    assert "glockenspiel" in instruments
    assert mood_sad == {"sad": 0.539, "not_sad": 0.461}
    # AcousticBrainz is asked in batches: Radiohead's 4 recordings take 3 + 1.
    acousticbrainz_batch_sizes = [
        len(r.url.params["recording_ids"].split(";"))
        for r in fake.requests
        if r.url.path == "/api/v1/high-level"
    ]
    assert acousticbrainz_batch_sizes == [3, 1, 2, 2]
    # The 503 was retried, and every call names the contact.
    assert fake.requests[0].url == fake.requests[1].url
    assert {r.headers["User-Agent"] for r in fake.requests} == {
        "timbre/0.1 ( tests@example.org )"
    }


@pytest.mark.anyio
async def test_build_vectors_runs_after_the_import(
    committed: psycopg.AsyncConnection,
) -> None:
    conn = committed  # the real worker must see the Songs
    await load_test_seed(conn)
    await run_import(conn, FakeMetaBrainz(no_artists=True))

    expected = len(recorded("seed"))  # the re-tagged seed Songs
    profiles: dict[str, str] = {}
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        cur = await conn.execute(
            "SELECT id::text, profile FROM catalog.songs"
            " WHERE id::text LIKE %s AND vector IS NOT NULL",
            (TEST_IDS,),
        )
        profiles = dict(await cur.fetchall())
        if len(profiles) == expected:
            break
        await asyncio.sleep(0.5)
    assert len(profiles) == expected, "the worker did not vectorize the import"
    assert profiles[LUCKY] == "Tags: alternative rock, rock, art rock"


@pytest.mark.anyio
async def test_an_interrupted_import_resumes_without_duplicates(
    conn: psycopg.AsyncConnection,
) -> None:
    killed = FakeMetaBrainz(die_on=LINKIN_PARK_FIRST_RECORDING)
    with pytest.raises(RuntimeError, match="worker killed"):
        await run_import(conn, killed)
    assert killed.artists_asked() == ["a1", "a2"]
    assert await imported_titles(conn) == ["Karma Police", "Paranoid Android"]
    assert await finished_artists(conn) == 1

    resumed = FakeMetaBrainz()
    await run_import(conn, resumed)
    assert resumed.artists_asked() == ["a2", "a3"]  # Radiohead is not fetched again
    assert await imported_titles(conn) == sorted(KEPT)  # each Song once
    assert await finished_artists(conn) == 3


@pytest.mark.anyio
async def test_stops_once_the_catalog_reaches_the_target(
    conn: psycopg.AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    await set_target(conn, monkeypatch, 3)
    fake = FakeMetaBrainz()
    await run_import(conn, fake)
    assert fake.artists_asked() == ["a1", "a2"]  # 2 Songs, then 1 of the next 2
    assert len(await imported_titles(conn)) == 3


@pytest.mark.anyio
async def test_seed_songs_get_tags_and_an_interrupted_tagging_resumes(
    conn: psycopg.AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    await load_test_seed(conn)
    monkeypatch.setattr(catalog_import, "METADATA_BATCH", 1)
    # Dies on the second seed Song's batch, after the first one is committed.
    killed = FakeMetaBrainz(die_on=f"recording_mbids={LUCKY}")
    with pytest.raises(RuntimeError, match="worker killed"):
        await run_import(conn, killed)
    assert await tags_of(conn, "00000000-0000-0000-0012-000000000003") == ["rock"]
    assert await tags_of(conn, LUCKY) is None

    resumed = FakeMetaBrainz()
    await run_import(conn, resumed)
    asked = [
        r.url.params["recording_mbids"]
        for r in resumed.requests
        if r.url.path == "/1/metadata/recording/"
    ]
    assert asked == [LUCKY, "00000000-0000-0000-0012-000000000009"]
    assert await tags_of(conn, LUCKY) == ["alternative rock", "rock", "art rock"]
    # Not on MusicBrainz: an empty list, so it is not asked again.
    assert await tags_of(conn, "00000000-0000-0000-0012-000000000009") == []


@pytest.mark.anyio
async def test_an_artist_listenbrainz_does_not_know_is_skipped(
    conn: psycopg.AsyncConnection,
) -> None:
    await run_import(conn, FakeMetaBrainz(not_found="0000000000a1"))
    assert await imported_titles(conn) == sorted(KEPT - RADIOHEAD)
    assert await finished_artists(conn) == 3  # a resume does not ask for it again

    resumed = FakeMetaBrainz()
    await run_import(conn, resumed)
    assert resumed.artists_asked() == []


@pytest.mark.anyio
async def test_an_import_that_finds_the_apis_down_is_deferred_without_blocking(
    conn: psycopg.AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    replayed_client = metabrainz.client
    monkeypatch.setattr(
        catalog_import,
        "client",
        lambda: replayed_client(httpx.MockTransport(FakeMetaBrainz(down=True))),
    )
    later_runs: list[int] = []

    async def later_job(_: psycopg.AsyncConnection) -> None:
        later_runs.append(1)

    monkeypatch.setitem(worker.JOBS, "build-vectors", later_job)
    (import_job,) = await one(
        conn, "INSERT INTO jobs.queue (kind) VALUES ('import-catalog') RETURNING id"
    )
    (later,) = await one(
        conn, "INSERT INTO jobs.queue (kind) VALUES ('build-vectors') RETURNING id"
    )
    # Until the rollback, every other job is not due, so the claims can take only ours.
    await conn.execute(
        "UPDATE jobs.queue SET run_after = 'infinity' WHERE id IN (SELECT id"
        "   FROM jobs.queue WHERE status = 'queued' AND id <> ALL(%s)"
        "   FOR UPDATE SKIP LOCKED)",
        ([import_job, later],),
    )

    assert await worker.run_next_job(conn)  # the real catalog_import.run
    assert await worker.run_next_job(conn)
    status, error, finished_at, deferred = await one(
        conn,
        "SELECT status, error, finished_at, run_after > clock_timestamp()"
        " FROM jobs.queue WHERE id = %s",
        import_job,
    )
    assert (status, finished_at, deferred) == ("queued", None, True)
    assert "answered 503" in error
    assert later_runs == [1]  # the deferred import did not block it
    assert await one(conn, "SELECT status FROM jobs.queue WHERE id = %s", later) == (
        "done",
    )
