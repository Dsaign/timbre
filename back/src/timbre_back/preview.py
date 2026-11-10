"""Preview: find Songs on Spotify (ADR 0001).

Only this module calls Spotify or touches the preview schema, and only through the
api_preview pool. Song details for the search come from the catalog (api_search pool);
nothing Spotify-derived ever flows back into the catalog.
"""

import asyncio
import logging
import random
import re
import time
from typing import Any, NamedTuple
from uuid import UUID

import httpx
from psycopg_pool import AsyncConnectionPool

log = logging.getLogger("timbre.preview")

TOKEN_URL = "https://accounts.spotify.com/api/token"  # noqa: S105 (a URL)
SEARCH_URL = "https://api.spotify.com/v1/search"
PARALLEL = 4  # Spotify lookups at a time, across all requests
RETRIES = 3
BACKOFF = 0.5  # seconds before the first retry; doubles each time
MAX_RETRY_AFTER = 10.0  # a longer Retry-After gives up instead of holding the grid
TRACK_ID = re.compile(r"[0-9A-Za-z]{22}")  # Spotify base-62 ID
IMAGE_URL = re.compile(r"https://i\.scdn\.co/image/[0-9a-f]+")  # Spotify's image CDN
MIN_COVER = 64  # px: the card shows the cover at 64 px
sleep = asyncio.sleep  # tests swap this to skip and record the waits


class SpotifyError(Exception):
    pass


class Track(NamedTuple):
    id: str
    album_image_url: str | None


def album_image(album: dict[str, Any]) -> str | None:
    """The smallest album image of at least MIN_COVER px, from a trusted host."""
    images = [
        image
        for image in album.get("images") or []
        if min(image.get("width") or 0, image.get("height") or 0) >= MIN_COVER
    ]
    if not images:
        return None
    url = min(images, key=lambda image: image["width"] * image["height"])["url"]
    return url if isinstance(url, str) and IMAGE_URL.fullmatch(url) else None


class Spotify:
    """Spotify Web API search with Client Credentials, retries and a concurrency cap."""

    def __init__(self, http: httpx.AsyncClient, client_id: str, secret: str) -> None:
        self.http = http
        self.auth = (client_id, secret)
        self.token = ""
        self.token_expires = 0.0
        self.token_lock = asyncio.Lock()
        self.limit = asyncio.Semaphore(PARALLEL)

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Retry 429 (after Retry-After), 5xx and network errors up to RETRIES times."""
        problem = ""  # always set below; pyright can't see the loop runs at least once
        for attempt in range(RETRIES + 1):
            try:
                response = await self.http.request(method, url, **kwargs)
                if response.status_code != 429 and response.status_code < 500:
                    if response.status_code == 401:
                        self.token = ""  # expired or revoked: fetch a new one next time
                    return response.raise_for_status()
                problem = f"HTTP {response.status_code}"
                retry_after = response.headers.get("Retry-After")
            except httpx.TransportError as e:
                problem, retry_after = repr(e), None
            if attempt == RETRIES:
                break
            if retry_after is not None and retry_after.isdigit():
                delay = float(retry_after)
                if delay > MAX_RETRY_AFTER:
                    raise SpotifyError(f"{problem}, Retry-After {delay:.0f}s")
            else:
                delay = BACKOFF * 2**attempt * random.uniform(0.8, 1.2)  # noqa: S311
            await sleep(delay)
        raise SpotifyError(f"{problem} after {RETRIES} retries")

    async def bearer(self) -> str:
        async with self.token_lock:
            if not self.token or time.monotonic() >= self.token_expires:
                if not all(self.auth):
                    raise SpotifyError("Spotify credentials are not set")
                body = (
                    await self.request(
                        "POST",
                        TOKEN_URL,
                        data={"grant_type": "client_credentials"},
                        auth=self.auth,
                    )
                ).json()
                self.token = body["access_token"]
                self.token_expires = time.monotonic() + body["expires_in"] - 60
            return self.token

    async def find_track(
        self, isrc: str | None, title: str, artist: str
    ) -> Track | None:
        """The Spotify track, by ISRC first, then title + artist. None: not found."""
        queries = [f"isrc:{isrc}"] if isrc else []
        # Quotes would end the field filter early.
        queries.append(
            f'track:"{title.replace('"', " ")}" artist:"{artist.replace('"', " ")}"'
        )
        async with self.limit:
            for q in queries:
                response = await self.request(
                    "GET",
                    SEARCH_URL,
                    params={"q": q, "type": "track", "limit": 1},
                    headers={"Authorization": f"Bearer {await self.bearer()}"},
                )
                items = response.json()["tracks"]["items"]
                if items:
                    track_id = items[0]["id"]
                    if not TRACK_ID.fullmatch(track_id):
                        raise SpotifyError("unexpected track ID format")
                    return Track(
                        str(track_id), album_image(items[0].get("album") or {})
                    )
        return None


async def lookup(
    song_ids: list[UUID],
    search_pool: AsyncConnectionPool,
    preview_pool: AsyncConnectionPool,
    spotify: Spotify,
) -> dict[UUID, Track | None]:
    """Each Song's Spotify track and album cover, or None for "not available".

    Found and not-found answers are cached for 24 h; errors are not cached.
    """
    async with preview_pool.connection() as conn:
        cur = await conn.execute(
            "SELECT song_id, spotify_track_id, album_image_url"
            " FROM preview.spotify_cache"
            " WHERE song_id = ANY(%s) AND expires_at > now()",
            (song_ids,),
        )
        known: dict[UUID, Track | None] = {
            song_id: Track(track_id, image) if track_id else None
            for song_id, track_id, image in await cur.fetchall()
        }
    missing = [song_id for song_id in song_ids if song_id not in known]
    if missing:
        async with search_pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id, isrc, title, artist FROM catalog.songs WHERE id = ANY(%s)",
                (missing,),
            )
            songs = await cur.fetchall()
        answers = await asyncio.gather(
            *(
                spotify.find_track(isrc, title, artist)
                for _, isrc, title, artist in songs
            ),
            return_exceptions=True,
        )
        fresh: list[tuple[UUID, Track | None]] = []
        for (song_id, *_), answer in zip(songs, answers, strict=True):
            if isinstance(answer, BaseException):
                log.warning("Spotify lookup failed: %r", answer)
            else:
                fresh.append((song_id, answer))
        if fresh:
            async with preview_pool.connection() as conn, conn.cursor() as cur:
                await cur.executemany(
                    "INSERT INTO preview.spotify_cache"
                    " (song_id, spotify_track_id, album_image_url, expires_at)"
                    " VALUES (%s, %s, %s, now() + interval '24 hours')"
                    " ON CONFLICT (song_id) DO UPDATE SET"
                    " spotify_track_id = excluded.spotify_track_id,"
                    " album_image_url = excluded.album_image_url,"
                    " fetched_at = now(), expires_at = excluded.expires_at",
                    [(song_id, *(track or (None, None))) for song_id, track in fresh],
                )
            known.update(fresh)
    return {song_id: known.get(song_id) for song_id in song_ids}


async def delete_expired(preview_pool: AsyncConnectionPool) -> int:
    async with preview_pool.connection() as conn:
        cur = await conn.execute(
            "DELETE FROM preview.spotify_cache WHERE expires_at <= now()"
        )
        return cur.rowcount


async def delete_expired_daily(preview_pool: AsyncConnectionPool) -> None:
    """Spotify data is never kept past its 24 h TTL (Policy: "not indefinitely")."""
    while True:
        try:
            log.info(
                "preview cache cleanup: %d expired rows",
                await delete_expired(preview_pool),
            )
        except Exception:
            log.exception("preview cache cleanup failed")
        await asyncio.sleep(24 * 60 * 60)
