"""Load the seed Catalog: `python -m timbre_back.seed`. Safe to run on every start.

Upserts the Songs from seed.json and queues build-vectors if any Song has no
vector. seed.json is written by scripts/fetch_seed.py. Once the Catalog import
(catalog_import.py) has started, the seed is left out: it would undo the import's tags.
"""

import asyncio
import json

import psycopg

from timbre_back.catalog import SEED, queue_build_vectors, upsert_songs
from timbre_back.db import conninfo


async def main() -> None:
    songs = json.loads(SEED.read_text())
    async with await psycopg.AsyncConnection.connect(conninfo("ml_worker")) as conn:
        cur = await conn.execute("SELECT EXISTS (SELECT FROM catalog.import_artists)")
        if await cur.fetchone() == (False,):
            await upsert_songs(conn, songs)
        await queue_build_vectors(conn)


if __name__ == "__main__":
    asyncio.run(main())
