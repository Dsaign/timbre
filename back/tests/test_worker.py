"""Seam 2: worker jobs, run by the real worker through the real queue."""

import time
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

from timbre_back.db import conninfo


def wait_for_job(conn: psycopg.Connection, job_id: int, timeout: float = 60) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = conn.execute(
            "SELECT status FROM jobs.queue WHERE id = %s", (job_id,)
        ).fetchone()
        assert row is not None
        if row[0] != "queued":
            return str(row[0])
        time.sleep(0.5)
    raise TimeoutError(f"job {job_id} still queued after {timeout}s")


def test_build_vectors_fills_profile_and_vector_for_new_songs() -> None:
    song_id = uuid4()
    with psycopg.connect(conninfo("ml_worker"), autocommit=True) as conn:
        try:
            conn.execute(
                "INSERT INTO catalog.songs"
                " (id, title, artist, acousticbrainz, instruments)"
                " VALUES (%s, 'new', 'new', %s, %s)",
                (
                    song_id,
                    Jsonb({"mood_relaxed": {"relaxed": 0.9, "not_relaxed": 0.1}}),
                    ["piano"],
                ),
            )
            job = conn.execute(
                "INSERT INTO jobs.queue (kind) VALUES ('build-vectors') RETURNING id"
            ).fetchone()
            assert job is not None

            assert wait_for_job(conn, job[0]) == "done"
            song = conn.execute(
                "SELECT profile, vector_dims(vector) FROM catalog.songs WHERE id = %s",
                (song_id,),
            ).fetchone()
            assert song == ("relaxed, calm. Instruments: piano", 384)
        finally:
            conn.execute("DELETE FROM catalog.songs WHERE id = %s", (song_id,))
