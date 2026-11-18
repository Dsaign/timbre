"""The import-catalog job (ADR 0002). Queue it: python -m timbre_back.catalog_import

And the retag job, which fills Songs that have fewer than TAGS_PER_SONG tags. Queue it:
python -m timbre_back.catalog_import retag"""

import asyncio
import json
import logging
import os
import sys
from collections.abc import Awaitable, Callable
from itertools import count

import httpx
import psycopg

from timbre_back.catalog import SEED, queue_build_vectors, upsert_songs
from timbre_back.db import conninfo
from timbre_back.metabrainz import (
    LISTENBRAINZ_API,
    METADATA_BATCH,
    STATS_PAGE,
    TAGS_PER_SONG,
    Song,
    client,
    fetch_high_level,
    fetch_json,
    recordings_metadata,
    to_song,
    top_tags,
)

log = logging.getLogger("timbre.import")
TARGET = 50_000
PER_ARTIST = 50  # candidate Songs per artist, most listened first


async def import_artist_songs(
    conn: psycopg.AsyncConnection,
    http: httpx.AsyncClient,
    token: str,
    artist_mbid: str,
    room: int,
) -> int:
    """Fetch and commit at most `room` of one artist's Songs; returns how many."""
    try:
        popular = await fetch_json(
            http,
            f"{LISTENBRAINZ_API}/popularity/top-recordings-for-artist/" + artist_mbid,
            headers={"Authorization": f"Token {token}"},
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 404:
            raise
        log.warning("import: artist %s not found (404), skipped", artist_mbid)
        popular = []
    candidates = popular[:PER_ARTIST]
    acousticbrainz = await fetch_high_level(
        http, [c["recording_mbid"] for c in candidates]
    )
    analysed = [c for c in candidates if c["recording_mbid"] in acousticbrainz]
    recordings = {}
    if analysed:
        recordings = await recordings_metadata(
            http, [c["recording_mbid"] for c in analysed]
        )
    songs: list[Song] = []
    for candidate in analysed:
        mbid = candidate["recording_mbid"]
        metadata = recordings.get(mbid, {})
        recording = metadata.get("recording", {})
        if not recording.get("isrcs"):
            continue
        song = to_song(
            mbid,
            candidate["recording_name"],
            candidate["artist_name"],
            candidate.get("total_listen_count") or 0,
            acousticbrainz[mbid],
            recording,
        )
        song["tags"] = top_tags(metadata.get("tag", {}))
        songs.append(song)
    songs = songs[:room]
    async with conn.transaction():
        await upsert_songs(conn, songs)
        await conn.execute(
            "INSERT INTO catalog.import_artists (artist_mbid) VALUES (%s)",
            (artist_mbid,),
        )
    return len(songs)


async def catalog_size(conn: psycopg.AsyncConnection) -> int:
    cur = await conn.execute("SELECT count(*) FROM catalog.songs")
    ((size,),) = await cur.fetchall()
    return int(size)


async def import_top_artists(
    conn: psycopg.AsyncConnection, http: httpx.AsyncClient, token: str
) -> None:
    cur = await conn.execute("SELECT artist_mbid::text FROM catalog.import_artists")
    imported_artists = {mbid for (mbid,) in await cur.fetchall()}
    # shortcut: only ListenBrainz's top 1,000 artists; add a source if the log is short
    for offset in count(0, STATS_PAGE):
        page = await fetch_json(
            http,
            f"{LISTENBRAINZ_API}/stats/sitewide/artists",
            params={
                "range": "all_time",
                "count": STATS_PAGE,
                "offset": offset,
            },
        )
        if not page["payload"]["artists"]:
            size = await catalog_size(conn)
            if size >= TARGET:  # a resume whose artists were all imported already
                log.info("import: stopped at %d Songs, the target is %d", size, TARGET)
                return
            log.warning(
                "import: stopped at %d Songs, under the %d target: no more"
                " ListenBrainz top artists (the sitewide stats stop at %d)",
                size,
                TARGET,
                offset,
            )
            return
        for artist in page["payload"]["artists"]:
            mbid = artist.get("artist_mbid")
            if not mbid or mbid in imported_artists:
                continue
            size = await catalog_size(conn)
            if size >= TARGET:
                log.info("import: stopped at %d Songs, the target is %d", size, TARGET)
                return
            kept = await import_artist_songs(conn, http, token, mbid, TARGET - size)
            imported_artists.add(mbid)
            log.info("import: %s, %d Songs kept", artist["artist_name"], kept)


async def tag_songs(
    conn: psycopg.AsyncConnection, http: httpx.AsyncClient, song_ids: list[str]
) -> None:
    """(Re-)fetch the Songs' tags ([] when MusicBrainz has none), a batch per commit.
    A Song whose tags change keeps its vector, so it stays searchable, and loses its
    profile, so build-vectors redoes it."""
    for i in range(0, len(song_ids), METADATA_BATCH):
        batch = song_ids[i : i + METADATA_BATCH]
        recordings = await recordings_metadata(http, batch)
        async with conn.transaction(), conn.cursor() as update:
            await update.executemany(
                "UPDATE catalog.songs SET tags = %(tags)s, profile = NULL"
                " WHERE id = %(id)s AND tags IS DISTINCT FROM %(tags)s",
                [
                    {
                        "tags": top_tags(recordings.get(mbid, {}).get("tag", {})),
                        "id": mbid,
                    }
                    for mbid in batch
                ],
            )
        log.info("tags: fetched for %d of %d Songs", i + len(batch), len(song_ids))


async def tag_seed_songs(
    conn: psycopg.AsyncConnection, http: httpx.AsyncClient
) -> None:
    """Tag the untagged seed Songs; an interrupted run resumes where it stopped."""
    seed_ids = [song["id"] for song in json.loads(SEED.read_text())]
    cur = await conn.execute(
        "SELECT id::text FROM catalog.songs"
        " WHERE tags IS NULL AND id = ANY(%s::uuid[]) ORDER BY id",
        (seed_ids,),
    )
    await tag_songs(conn, http, [mbid for (mbid,) in await cur.fetchall()])


async def retag(conn: psycopg.AsyncConnection, http: httpx.AsyncClient) -> None:
    """Re-fetch the tags of every Song with fewer than TAGS_PER_SONG, then queue
    build-vectors. `conn` must be autocommit."""
    # shortcut: a rerun asks again for every short Song, done or not; record progress
    # if the run (minutes at 50 Songs per call) ever gets long.
    cur = await conn.execute(
        "SELECT id::text FROM catalog.songs"
        " WHERE coalesce(cardinality(tags), 0) < %s ORDER BY id",
        (TAGS_PER_SONG,),
    )
    await tag_songs(conn, http, [mbid for (mbid,) in await cur.fetchall()])
    await queue_build_vectors(conn)


async def import_catalog(
    conn: psycopg.AsyncConnection, http: httpx.AsyncClient
) -> None:
    """Import, tag the seed, queue build-vectors. `conn` must be autocommit."""
    token = os.environ.get("LISTENBRAINZ_TOKEN")
    if not token:
        raise RuntimeError("set LISTENBRAINZ_TOKEN in back/.env")
    await import_top_artists(conn, http, token)
    await tag_seed_songs(conn, http)
    await queue_build_vectors(conn)


async def run_on_own_connection(
    job_conn: psycopg.AsyncConnection,
    job: Callable[[psycopg.AsyncConnection, httpx.AsyncClient], Awaitable[None]],
) -> None:
    """Commits on its own connection, so a failed run keeps every finished step."""
    # The job's transaction only holds the claim, idle for the hours the job takes.
    await job_conn.execute("SET LOCAL idle_in_transaction_session_timeout = 0")
    async with (
        await psycopg.AsyncConnection.connect(
            conninfo("ml_worker"), autocommit=True
        ) as conn,
        client() as http,
    ):
        await job(conn, http)


async def run(job_conn: psycopg.AsyncConnection) -> None:
    await run_on_own_connection(job_conn, import_catalog)


async def run_retag(job_conn: psycopg.AsyncConnection) -> None:
    await run_on_own_connection(job_conn, retag)


async def main(kind: str) -> None:
    async with await psycopg.AsyncConnection.connect(conninfo("ml_worker")) as conn:
        await conn.execute(
            "INSERT INTO jobs.queue (kind) SELECT %(kind)s"
            " WHERE NOT EXISTS (SELECT FROM jobs.queue"
            "   WHERE kind = %(kind)s AND status = 'queued')",
            {"kind": kind},
        )


if __name__ == "__main__":
    # `python -m timbre_back.catalog_import retag` queues the retag job instead.
    asyncio.run(main("retag" if sys.argv[1:] == ["retag"] else "import-catalog"))
