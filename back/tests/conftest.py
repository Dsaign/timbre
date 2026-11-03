import time

import psycopg
import pytest

from timbre_back.db import conninfo

SEED_SIZE = 200


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def seed_vectors_built() -> None:
    """The worker builds the seed vectors after start; wait for it."""
    deadline = time.monotonic() + 300
    with psycopg.connect(conninfo("ml_worker")) as conn:
        while time.monotonic() < deadline:
            row = conn.execute(
                "SELECT count(*) FILTER (WHERE vector IS NOT NULL),"
                " (SELECT count(*) FROM jobs.queue WHERE status = 'queued')"
                " FROM catalog.songs"
            ).fetchone()
            conn.rollback()
            if row is not None and row[0] >= SEED_SIZE and row[1] == 0:
                return
            time.sleep(1)
    raise TimeoutError("seed Catalog vectors were not built in time")
