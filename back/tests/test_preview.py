"""Preview lookups: the real database and pools, Spotify replaced by recorded responses.

tests/spotify/*.json are real Spotify search response bodies (no tokens or credentials),
recorded with Client Credentials for BTS "Dynamite" (ISRC QM7282022872).
"""

import asyncio
import json
import os
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from psycopg_pool import AsyncConnectionPool

from timbre_back import preview
from timbre_back.db import conninfo

API_URL = os.environ.get("API_URL", "http://api:8000")
AUTH = {"Authorization": f"Bearer {os.environ['FRONT_TOKEN']}"}
RECORDED = Path(__file__).with_name("spotify")
# The smallest image of at least 64 px in the recorded album.images (640, 300, 64).
COVER = "https://i.scdn.co/image/ab67616d00004851c07d5d2fdc02ae252fcd07e5"
DYNAMITE = preview.Track("5QDLhrAOJJdNAmCTJ8xMyW", COVER)


def recorded(name: str) -> httpx.Response:
    return httpx.Response(200, json=json.loads((RECORDED / f"{name}.json").read_text()))


def rate_limited(retry_after: str) -> httpx.Response:
    # Spotify's documented 429 shape.
    return httpx.Response(
        429,
        headers={"Retry-After": retry_after},
        json={"error": {"status": 429, "message": "API rate limit exceeded"}},
    )


@dataclass
class FakeSpotify:
    """Answers the token request, then serves search responses in order."""

    responses: list[httpx.Response]
    searches: list[str] = field(default_factory=list)
    in_flight: int = 0
    most_in_flight: int = 0

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "accounts.spotify.com":
            return httpx.Response(
                200,
                json={"access_token": "t", "token_type": "Bearer", "expires_in": 3600},
            )
        self.searches.append(request.url.params["q"])
        self.in_flight += 1
        self.most_in_flight = max(self.most_in_flight, self.in_flight)
        await asyncio.sleep(0.02)  # let concurrent lookups overlap
        self.in_flight -= 1
        return self.responses.pop(0)


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Retry waits, recorded instead of slept."""
    waits: list[float] = []

    async def fake_sleep(delay: float) -> None:
        waits.append(delay)

    monkeypatch.setattr(preview, "sleep", fake_sleep)
    return waits


@pytest.fixture
def songs() -> Iterator[list[UUID]]:
    """Ten fresh "Dynamite" Songs (new IDs, so nothing is cached yet)."""
    ids = [uuid4() for _ in range(10)]
    with psycopg.connect(conninfo("ml_worker"), autocommit=True) as conn:
        for song_id in ids:
            conn.execute(
                "INSERT INTO catalog.songs (id, title, artist, isrc)"
                " VALUES (%s, 'Dynamite', 'BTS', 'QM7282022872')",
                (song_id,),
            )
    yield ids
    with psycopg.connect(conninfo("ml_worker"), autocommit=True) as conn:
        conn.execute("DELETE FROM catalog.songs WHERE id = ANY(%s)", (ids,))
    with psycopg.connect(conninfo("api_preview"), autocommit=True) as conn:
        conn.execute(
            "DELETE FROM preview.spotify_cache WHERE song_id = ANY(%s)", (ids,)
        )


Lookup = Callable[[list[UUID]], Awaitable[dict[UUID, preview.Track | None]]]


@asynccontextmanager
async def lookups(fake: FakeSpotify) -> AsyncGenerator[Lookup]:
    """preview.lookup on the real pools, with Spotify answered by `fake`."""
    async with (
        AsyncConnectionPool(
            conninfo("api_search"), open=False, connection_class=psycopg.AsyncConnection
        ) as search_pool,
        AsyncConnectionPool(
            conninfo("api_preview"),
            open=False,
            connection_class=psycopg.AsyncConnection,
        ) as preview_pool,
        httpx.AsyncClient(transport=httpx.MockTransport(fake)) as http,
    ):
        spotify = preview.Spotify(http, "id", "secret")
        yield lambda ids: preview.lookup(ids, search_pool, preview_pool, spotify)


def cached(song_id: UUID) -> tuple[str | None, str | None, float] | None:
    """The cache row's track ID, cover and TTL in hours, or None when not cached."""
    with psycopg.connect(conninfo("api_preview")) as conn:
        row = conn.execute(
            "SELECT spotify_track_id, album_image_url,"
            " extract(epoch FROM expires_at - fetched_at) / 3600"
            " FROM preview.spotify_cache WHERE song_id = %s",
            (song_id,),
        ).fetchone()
    return None if row is None else (row[0], row[1], float(row[2]))


@pytest.mark.anyio
async def test_found_by_isrc_is_cached_for_24_hours(songs: list[UUID]) -> None:
    fake = FakeSpotify([recorded("isrc_found")])
    async with lookups(fake) as lookup:
        assert await lookup(songs[:1]) == {songs[0]: DYNAMITE}
        assert await lookup(songs[:1]) == {songs[0]: DYNAMITE}
    assert fake.searches == [
        "isrc:QM7282022872"
    ]  # the second answer came from the cache
    assert cached(songs[0]) == (*DYNAMITE, 24.0)


@pytest.mark.anyio
async def test_falls_back_to_title_and_artist(songs: list[UUID]) -> None:
    fake = FakeSpotify([recorded("isrc_empty"), recorded("title_artist_found")])
    async with lookups(fake) as lookup:
        assert await lookup(songs[:1]) == {songs[0]: DYNAMITE}
    assert fake.searches == ["isrc:QM7282022872", 'track:"Dynamite" artist:"BTS"']


@pytest.mark.anyio
async def test_not_found_is_cached_as_not_available(songs: list[UUID]) -> None:
    fake = FakeSpotify([recorded("isrc_empty"), recorded("isrc_empty")])
    async with lookups(fake) as lookup:
        assert await lookup(songs[:1]) == {songs[0]: None}
        assert await lookup(songs[:1]) == {songs[0]: None}
    assert len(fake.searches) == 2  # ISRC + title/artist once, then the cache
    assert cached(songs[0]) == (None, None, 24.0)


@pytest.mark.anyio
async def test_429_honors_retry_after(songs: list[UUID], sleeps: list[float]) -> None:
    fake = FakeSpotify([rate_limited("3"), recorded("isrc_found")])
    async with lookups(fake) as lookup:
        assert await lookup(songs[:1]) == {songs[0]: DYNAMITE}
    assert sleeps == [3.0]


@pytest.mark.anyio
async def test_a_very_long_retry_after_gives_up(
    songs: list[UUID], sleeps: list[float]
) -> None:
    fake = FakeSpotify([rate_limited("3600")])
    async with lookups(fake) as lookup:
        assert await lookup(songs[:1]) == {songs[0]: None}
    assert sleeps == []
    assert cached(songs[0]) is None


@pytest.mark.anyio
async def test_errors_back_off_and_are_never_cached(
    songs: list[UUID], sleeps: list[float]
) -> None:
    fake = FakeSpotify([httpx.Response(503)] * 4 + [recorded("isrc_found")])
    async with lookups(fake) as lookup:
        assert await lookup(songs[:1]) == {songs[0]: None}
        assert cached(songs[0]) is None
        # Exponential backoff with jitter: about 0.5 s, 1 s, 2 s, then give up.
        assert len(sleeps) == 3
        for wait, base in zip(sleeps, [0.5, 1, 2], strict=True):
            assert 0.8 * base <= wait <= 1.2 * base
        # Not cached, so the next search asks Spotify again.
        assert await lookup(songs[:1]) == {songs[0]: DYNAMITE}
    assert len(fake.searches) == 5


@pytest.mark.anyio
async def test_at_most_4_lookups_at_a_time(songs: list[UUID]) -> None:
    fake = FakeSpotify([recorded("isrc_found") for _ in songs])
    async with lookups(fake) as lookup:
        assert await lookup(songs) == dict.fromkeys(songs, DYNAMITE)
    assert fake.most_in_flight == 4


@pytest.mark.anyio
async def test_a_song_outside_the_catalog_is_not_available() -> None:
    fake = FakeSpotify([])
    unknown = uuid4()
    async with lookups(fake) as lookup:
        assert await lookup([unknown]) == {unknown: None}
    assert fake.searches == []
    assert cached(unknown) is None


@pytest.mark.anyio
async def test_cleanup_deletes_only_expired_rows() -> None:
    expired, fresh = uuid4(), uuid4()
    with psycopg.connect(conninfo("api_preview"), autocommit=True) as conn:
        conn.execute(
            "INSERT INTO preview.spotify_cache (song_id, expires_at)"
            " VALUES (%s, now() - interval '1 second'),"
            " (%s, now() + interval '24 hours')",
            (expired, fresh),
        )
    try:
        async with AsyncConnectionPool(
            conninfo("api_preview"),
            open=False,
            connection_class=psycopg.AsyncConnection,
        ) as pool:
            assert await preview.delete_expired(pool) >= 1
        assert cached(expired) is None
        assert cached(fresh) is not None
    finally:
        with psycopg.connect(conninfo("api_preview"), autocommit=True) as conn:
            conn.execute(
                "DELETE FROM preview.spotify_cache WHERE song_id = %s", (fresh,)
            )


@pytest.mark.parametrize(
    ("images", "expected"),
    [
        ([], None),
        ([{"width": 32, "height": 32, "url": COVER}], None),  # too small
        ([{"width": None, "height": None, "url": COVER}], None),  # unknown size
        (
            [
                {"width": 640, "height": 640, "url": COVER + "0"},
                {"width": 64, "height": 64, "url": COVER},
                {"width": 300, "height": 300, "url": COVER + "1"},
            ],
            COVER,
        ),
        ([{"width": 64, "height": 64, "url": "https://evil.example/x.jpg"}], None),
    ],
    ids=["none", "too-small", "no-size", "smallest-64", "other-host"],
)
def test_album_image_is_the_smallest_trusted_cover_of_64_px(
    images: list[dict[str, object]], expected: str | None
) -> None:
    assert preview.album_image({"images": images}) == expected


def post_preview(song_ids: list[str], headers: dict[str, str] = AUTH) -> httpx.Response:
    return httpx.post(
        f"{API_URL}/preview", json={"song_ids": song_ids}, headers=headers, timeout=30
    )


def test_endpoint_reports_each_song() -> None:
    unknown = str(uuid4())  # not in the Catalog, so Spotify is never called
    response = post_preview([unknown, unknown])
    assert response.status_code == 200
    assert response.json() == [
        {"song_id": unknown, "spotify_track_id": None, "album_image_url": None}
    ]


@pytest.mark.parametrize(
    "song_ids",
    [[], [str(uuid4()) for _ in range(61)], ["not-a-uuid"]],
    ids=["empty", "over-60", "not-uuid"],
)
def test_endpoint_rejects_invalid_input(song_ids: list[str]) -> None:
    response = post_preview(song_ids)
    assert response.status_code == 422
    assert "Traceback" not in response.text


def test_endpoint_needs_the_front_token() -> None:
    assert post_preview([str(uuid4())], headers={}).status_code == 401
