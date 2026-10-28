"""Seam 1: the HTTP API, called over the network like front's server code does."""

import os

import httpx
import pytest

from timbre_back.main import create_app

API_URL = os.environ.get("API_URL", "http://api:8000")
TOKEN = os.environ["FRONT_TOKEN"]


def get(
    path: str, headers: dict[str, str] | dict[bytes, bytes] | None = None
) -> httpx.Response:
    return httpx.get(f"{API_URL}{path}", headers=headers)


def test_health_answers_with_the_front_token() -> None:
    response = get("/health", {"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "headers",
    [
        None,
        {"Authorization": "Bearer wrong-token"},
        {"Authorization": f"Bearer {TOKEN}x"},
        {"Authorization": f"Basic {TOKEN}"},
        {b"Authorization": "Bearer ünïcode".encode("latin-1")},
    ],
    ids=["missing", "wrong", "longer", "other-scheme", "non-ascii"],
)
def test_health_refuses_a_missing_or_wrong_token(
    headers: dict[str, str] | dict[bytes, bytes] | None,
) -> None:
    response = get("/health", headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("app_env", "expected"),
    [("development", 200), ("production", 404), (None, 404)],
)
async def test_interactive_docs_only_in_development(
    app_env: str | None, expected: int
) -> None:
    # In-process, so both branches run whatever APP_ENV the running stack uses.
    transport = httpx.ASGITransport(app=create_app(app_env))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/docs")).status_code == expected
        assert (await client.get("/openapi.json")).status_code == expected
