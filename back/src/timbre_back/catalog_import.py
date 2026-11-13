"""The import-catalog job (ADR 0002). Queue it: python -m timbre_back.catalog_import"""

import asyncio
import json
import logging
import os
from itertools import count

import httpx
import psycopg

from timbre_back.catalog import SEED, queue_build_vectors, upsert_songs
from timbre_back.db import conninfo
from timbre_back.metabrainz import (
    LISTENBRAINZ_API,
    METADATA_BATCH,
    STATS_PAGE,
    Song,
    client,
    fetch_high_level,
    fetch_json,
    recordings_metadata,
    to_song,
    top_tags,
)

log = logging.getLogger("timbre.import")
TARGET = 10_000
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
            log.warning(
                "import: stopped at %d Songs, under the %d target: no more"
                " ListenBrainz top artists (the sitewide stats stop at %d)",
                await catalog_size(conn),
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


async def tag_seed_songs(
    conn: psycopg.AsyncConnection, http: httpx.AsyncClient
) -> None:
    """Tag untagged seed Songs ([] when MusicBrainz has none), a batch per commit."""
    seed_ids = [song["id"] for song in json.loads(SEED.read_text())]
    cur = await conn.execute(
        "SELECT id::text FROM catalog.songs"
        " WHERE tags IS NULL AND id = ANY(%s::uuid[]) ORDER BY id",
        (seed_ids,),
    )
    untagged = [mbid for (mbid,) in await cur.fetchall()]
    for i in range(0, len(untagged), METADATA_BATCH):
        batch = untagged[i : i + METADATA_BATCH]
        recordings = await recordings_metadata(http, batch)
        async with conn.transaction(), conn.cursor() as update:
            await update.executemany(
                "UPDATE catalog.songs SET tags = %s, profile = NULL, vector = NULL"
                " WHERE id = %s",
                [
                    (top_tags(recordings.get(mbid, {}).get("tag", {})), mbid)
                    for mbid in batch
                ],
            )
        log.info("import: tagged %d seed Songs", i + len(batch))


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


async def run(job_conn: psycopg.AsyncConnection) -> None:
    """Commits on its own connection, so a failed run keeps every finished step."""
    # The job's transaction only holds the claim, idle for the hours the import takes.
    await job_conn.execute("SET LOCAL idle_in_transaction_session_timeout = 0")
    async with (
        await psycopg.AsyncConnection.connect(
            conninfo("ml_worker"), autocommit=True
        ) as conn,
        client() as http,
    ):
        await import_catalog(conn, http)


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(conninfo("ml_worker")) as conn:
        await conn.execute(
            "INSERT INTO jobs.queue (kind) SELECT 'import-catalog'"
            " WHERE NOT EXISTS (SELECT FROM jobs.queue"
            "   WHERE kind = 'import-catalog' AND status = 'queued')"
        )


if __name__ == "__main__":
    asyncio.run(main())
