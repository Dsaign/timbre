"""The job worker: `python -m timbre_back.worker`. Runs queued jobs one at a time."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

import psycopg

from timbre_back.catalog_import import run as run_catalog_import
from timbre_back.db import conninfo, vector_literal
from timbre_back.embed import embed_passages
from timbre_back.jobs import JobDeferred
from timbre_back.profile import profile_text

log = logging.getLogger("timbre.worker")
BATCH = 32
RETRY_AFTER = 60  # seconds before a job that found an API down is due again


async def build_vectors(conn: psycopg.AsyncConnection) -> None:
    """Write the profile text and passage vector of every Song that has no vector."""
    cur = await conn.execute(
        "SELECT id, acousticbrainz, instruments, tags FROM catalog.songs"
        " WHERE vector IS NULL"
    )
    rows = await cur.fetchall()
    for i in range(0, len(rows), BATCH):
        batch = rows[i : i + BATCH]
        profiles = [
            profile_text(acousticbrainz or {}, instruments, tags or [])
            for _, acousticbrainz, instruments, tags in batch
        ]
        vectors = await asyncio.to_thread(embed_passages, profiles)
        async with conn.cursor() as update:
            await update.executemany(
                "UPDATE catalog.songs SET profile = %s, vector = %s::vector"
                " WHERE id = %s",
                [
                    (profile, vector_literal(vector), song_id)
                    for (song_id, *_), profile, vector in zip(
                        batch, profiles, vectors, strict=True
                    )
                ],
            )
    log.info("build-vectors: %d Songs", len(rows))


JOBS: dict[str, Callable[[psycopg.AsyncConnection], Awaitable[None]]] = {
    "build-vectors": build_vectors,
    "import-catalog": run_catalog_import,
}


async def run_next_job(conn: psycopg.AsyncConnection) -> bool:
    """Run the oldest due job. The row stays locked until the run commits."""
    async with conn.transaction():
        cur = await conn.execute(
            "SELECT id, kind FROM jobs.queue"
            " WHERE status = 'queued' AND run_after <= now()"
            " ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED"
        )
        job = await cur.fetchone()
        if job is None:
            return False
        job_id, kind = job
        error: str | None
        try:
            async with conn.transaction():  # savepoint: a failed run leaves no writes
                await JOBS[kind](conn)
        except JobDeferred as e:
            log.warning("job %s (%s) deferred: %s", job_id, kind, e)
            await conn.execute(
                # clock_timestamp(): now() is the claim's start, before the run.
                "UPDATE jobs.queue SET error = %s,"
                " run_after = clock_timestamp() + make_interval(secs => %s)"
                " WHERE id = %s",
                (repr(e), RETRY_AFTER, job_id),
            )
            return True
        except Exception as e:
            log.exception("job %s (%s) failed", job_id, kind)
            status, error = "failed", repr(e)
        else:
            status, error = "done", None
        await conn.execute(
            "UPDATE jobs.queue SET status = %s, error = %s, finished_at = now()"
            " WHERE id = %s",
            (status, error, job_id),
        )
    return True


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    async with await psycopg.AsyncConnection.connect(conninfo("ml_worker")) as conn:
        while True:
            # shortcut: polls once a second; switch to LISTEN/NOTIFY if latency matters
            if not await run_next_job(conn):
                await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
