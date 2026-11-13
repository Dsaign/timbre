"""Writes shared by the Catalog loaders (seed.py and catalog_import.py)."""

from collections.abc import Iterable
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from timbre_back.metabrainz import Song

SEED = Path(__file__).with_name("seed.json")  # written by scripts/fetch_seed.py


async def upsert_songs(conn: psycopg.AsyncConnection, songs: Iterable[Song]) -> None:
    async with conn.cursor() as cur:
        await cur.executemany(
            "INSERT INTO catalog.songs"
            " (id, title, artist, isrc, listens, acousticbrainz, instruments, tags)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            # A changed Song gets its vector cleared, so build-vectors redoes it.
            " ON CONFLICT (id) DO UPDATE SET title = excluded.title,"
            " artist = excluded.artist, isrc = excluded.isrc,"
            " listens = excluded.listens, acousticbrainz = excluded.acousticbrainz,"
            " instruments = excluded.instruments, tags = excluded.tags,"
            " profile = NULL, vector = NULL"
            " WHERE (songs.title, songs.artist, songs.isrc, songs.listens,"
            "   songs.acousticbrainz, songs.instruments, songs.tags) IS DISTINCT FROM"
            " (excluded.title, excluded.artist, excluded.isrc, excluded.listens,"
            "   excluded.acousticbrainz, excluded.instruments, excluded.tags)",
            [
                (
                    s["id"],
                    s["title"],
                    s["artist"],
                    s["isrc"],
                    s["listens"],
                    Jsonb(s["acousticbrainz"]),
                    s["instruments"],
                    s.get("tags"),  # NULL: not fetched yet (the seed is CC0 only)
                )
                for s in songs
            ],
        )


async def queue_build_vectors(conn: psycopg.AsyncConnection) -> None:
    # SKIP LOCKED leaves out a running job: it may have read the Songs before these.
    await conn.execute(
        "INSERT INTO jobs.queue (kind) SELECT 'build-vectors'"
        " WHERE EXISTS (SELECT FROM catalog.songs WHERE vector IS NULL)"
        " AND NOT EXISTS (SELECT FROM jobs.queue"
        "   WHERE kind = 'build-vectors' AND status = 'queued'"
        "   FOR UPDATE SKIP LOCKED)"
    )
