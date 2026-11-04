"""Seam 1: rate limits, the body cap and production errors.

The running stack has raised limits, so the 429 tests run the API in-process.
"""

import os
from collections.abc import AsyncGenerator
from ipaddress import IPv6Address
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from timbre_back import main
from timbre_back.db import conninfo

API_URL = os.environ.get("API_URL", "http://api:8000")
TOKEN = {"Authorization": f"Bearer {os.environ['FRONT_TOKEN']}"}


def new_visitor() -> dict[str, str]:
    """A fresh visitor (IPv6 documentation range), so no earlier run's hits count."""
    return {
        **TOKEN,
        "X-Visitor-IP": str(IPv6Address((0x20010DB8 << 96) | uuid4().int >> 64)),
    }


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[httpx.AsyncClient]:
    monkeypatch.setattr(main, "SEARCH_LIMIT_PER_MIN", 2)
    monkeypatch.setattr(main, "VOTE_LIMIT_PER_HOUR", 2)
    app: FastAPI = main.create_app(None)
    async with AsyncConnectionPool(
        conninfo("api_search"), min_size=1, connection_class=AsyncConnection
    ) as pool:
        app.state.search_pool = pool  # the lifespan isn't run in-process
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", timeout=30
        ) as client:
            yield client


@pytest.mark.anyio
async def test_searches_over_the_limit_get_429(client: httpx.AsyncClient) -> None:
    visitor = new_visitor()
    statuses = [
        (
            await client.get("/search", params={"q": "piano"}, headers=visitor)
        ).status_code
        for _ in range(3)
    ]
    assert statuses == [200, 200, 429]
    # Another visitor still searches.
    other = await client.get("/search", params={"q": "piano"}, headers=new_visitor())
    assert other.status_code == 200


@pytest.mark.anyio
async def test_votes_over_the_limit_get_429(client: httpx.AsyncClient) -> None:
    visitor = new_visitor()
    body = {"description": "piano", "song_id": str(uuid4()), "vote": "up"}
    statuses = [
        (await client.post("/feedback", json=body, headers=visitor)).status_code
        for _ in range(3)
    ]
    assert statuses == [404, 404, 429]  # an unknown Song, but each vote counts


@pytest.mark.parametrize("chunked", [False, True], ids=["content-length", "chunked"])
def test_bodies_over_16_kb_are_refused(chunked: bool) -> None:
    body = b'{"song_ids": ["' + b"x" * 17_000 + b'"]}'
    content = iter([body]) if chunked else body
    response = httpx.post(
        f"{API_URL}/preview",
        content=content,
        headers={**TOKEN, "Content-Type": "application/json"},
    )
    assert response.status_code == 413


@pytest.mark.anyio
async def test_production_errors_hide_stack_traces_and_sql() -> None:
    app = main.create_app("production")

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError('relation "catalog.secret" does not exist: SELECT * FROM x')

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom", headers=TOKEN)
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
