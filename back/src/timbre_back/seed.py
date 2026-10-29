"""Load the seed Catalog: `python -m timbre_back.seed`. Safe to run on every start.

Upserts the Songs from seed.json and queues build-vectors if any Song has no
vector. seed.json is written by scripts/fetch_seed.py.
"""

import asyncio
import json
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from timbre_back.db import conninfo

SEED = Path(__file__).with_name("seed.json")


async def main() -> None:
    songs = json.loads(SEED.read_text())
    async with await psycopg.AsyncConnection.connect(conninfo("ml_worker")) as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO catalog.songs"
                " (id, title, artist, isrc, listens, acousticbrainz, instruments)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)"
                # A changed Song gets its vector cleared, so build-vectors redoes it.
                " ON CONFLICT (id) DO UPDATE SET title = excluded.title,"
                " artist = excluded.artist, isrc = excluded.isrc,"
                " listens = excluded.listens, acousticbrainz = excluded.acousticbrainz,"
                " instruments = excluded.instruments, profile = NULL, vector = NULL"
                " WHERE (songs.title, songs.artist, songs.isrc, songs.listens,"
                "   songs.acousticbrainz, songs.instruments) IS DISTINCT FROM"
                " (excluded.title, excluded.artist, excluded.isrc, excluded.listens,"
                "   excluded.acousticbrainz, excluded.instruments)",
                [
                    (
                        s["id"],
                        s["title"],
                        s["artist"],
                        s["isrc"],
                        s["listens"],
                        Jsonb(s["acousticbrainz"]),
                        s["instruments"],
                    )
                    for s in songs
                ],
            )
        await conn.execute(
            "INSERT INTO jobs.queue (kind) SELECT 'build-vectors'"
            " WHERE EXISTS (SELECT FROM catalog.songs WHERE vector IS NULL)"
            " AND NOT EXISTS (SELECT FROM jobs.queue"
            "   WHERE kind = 'build-vectors' AND status = 'queued')"
        )


if __name__ == "__main__":
    asyncio.run(main())
